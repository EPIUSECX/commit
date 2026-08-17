import frappe

from commit.intelligence.docs import export_markdown
from commit.intelligence.github import (
    create_docs_pull_request,
    verify_webhook,
)
from commit.intelligence.permissions import require_branch_access


@frappe.whitelist(allow_guest=True, methods=["POST"])
def github_webhook():
    body = frappe.request.get_data()
    verify_webhook(body, frappe.get_request_header("X-Hub-Signature-256"))
    event = frappe.get_request_header("X-GitHub-Event")
    delivery = frappe.get_request_header("X-GitHub-Delivery")
    payload = frappe.parse_json(body)
    if event == "ping":
        return {"ok": True}
    repository = payload.get("repository") or {}
    org = (repository.get("owner") or {}).get("login")
    repo = repository.get("name")
    branch_name = None
    head_sha = None
    if event == "push":
        branch_name = (payload.get("ref") or "").removeprefix("refs/heads/")
        head_sha = payload.get("after")
    elif event == "pull_request" and payload.get("action") in {"opened", "reopened", "synchronize", "ready_for_review"}:
        branch_name = payload["pull_request"]["head"]["ref"]
        head_sha = payload["pull_request"]["head"]["sha"]
    if not branch_name or not head_sha:
        return {"accepted": False, "reason": "Event does not require a scan"}
    projects = frappe.get_all("Commit Project", filters={"repo_name": repo}, pluck="name")
    project = next((name for name in projects if frappe.db.get_value("Commit Organization", frappe.db.get_value("Commit Project", name, "org"), "github_org") == org), None)
    branch = frappe.db.get_value("Commit Project Branch", {"project": project, "branch_name": branch_name}) if project else None
    if not branch:
        return {"accepted": False, "reason": "No tracked Commit branch matches this event"}
    frappe.enqueue(
        "commit.intelligence.github.process_event",
        queue="long",
        project_branch=branch,
        head_sha=head_sha,
        delivery=delivery,
        deduplicate=True,
        job_id=f"commit-github-scan-{delivery}",
    )
    return {"accepted": True, "project_branch": branch}


@frappe.whitelist(methods=["POST"])
def publish_docs_pr(project_branch: str, commit_docs: str):
    require_branch_access(project_branch, "Maintainer")
    exported = export_markdown(project_branch, commit_docs)
    return create_docs_pull_request(project_branch, exported)
