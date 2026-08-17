from __future__ import annotations

import base64
import hashlib
import hmac
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import frappe
import jwt
import requests

from commit.intelligence.audit import record_event

GITHUB = "https://api.github.com"


@contextmanager
def git_auth_environment():
    """Provide Git with a non-interactive, temporary GitHub App credential."""
    settings = frappe.get_single("Github Settings")
    configured = bool(settings.get_password("installation_token") or (settings.github_app_id and settings.installation_id and settings.get_password("private_key")))
    if not configured:
        yield None
        return
    token = installation_token()
    with tempfile.TemporaryDirectory(prefix="commit-git-auth-") as directory:
        askpass = Path(directory) / "askpass.sh"
        askpass.write_text('#!/bin/sh\ncase "$1" in *Username*) printf x-access-token;; *) printf %s "$COMMIT_GITHUB_TOKEN";; esac\n', encoding="utf-8")
        askpass.chmod(0o700)
        yield {"GIT_ASKPASS": str(askpass), "GIT_TERMINAL_PROMPT": "0", "COMMIT_GITHUB_TOKEN": token, **{key: value for key, value in os.environ.items() if key.startswith("LC_") or key == "PATH"}}


def verify_webhook(body: bytes, signature: str | None):
    settings = frappe.get_single("Github Settings")
    if not settings.webhook_enabled:
        frappe.throw("GitHub webhooks are disabled", frappe.PermissionError)
    secret = settings.get_password("webhook_secret")
    if not secret or not signature:
        frappe.throw("Webhook signature missing", frappe.AuthenticationError)
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        frappe.throw("Invalid webhook signature", frappe.AuthenticationError)


def installation_token():
    settings = frappe.get_single("Github Settings")
    configured = settings.get_password("installation_token")
    if configured:
        return configured
    private_key = settings.get_password("private_key")
    if not private_key or not settings.github_app_id or not settings.installation_id:
        frappe.throw("Configure the GitHub App ID, installation ID, and private key")
    now = int(time.time())
    app_jwt = jwt.encode({"iat": now - 60, "exp": now + 540, "iss": str(settings.github_app_id)}, private_key, algorithm="RS256")
    response = requests.post(
        f"{GITHUB}/app/installations/{settings.installation_id}/access_tokens",
        headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        timeout=(5, 20),
    )
    response.raise_for_status()
    return response.json()["token"]


def github_request(method, path, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.update({"Authorization": f"Bearer {installation_token()}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    response = requests.request(method, f"{GITHUB}{path}", headers=headers, timeout=(5, 30), **kwargs)
    response.raise_for_status()
    return response.json() if response.content else {}


def check_payload(branch, snapshot, head_sha):
    project = frappe.get_doc("Commit Project", branch.project)
    findings = frappe.get_all("Commit Finding", filters={"snapshot": snapshot.name, "severity": ["in", ["Critical", "High"]]}, fields=["title", "severity", "blocking", "file_path", "line_number", "remediation"], limit=50)
    blocked = project.policy_mode == "Blocking" and (snapshot.breaking_change_count or any(item.severity == "Critical" or item.blocking for item in findings))
    annotations = []
    for finding in findings:
        if finding.file_path:
            annotations.append({"path": finding.file_path, "start_line": max(1, finding.line_number or 1), "end_line": max(1, finding.line_number or 1), "annotation_level": "failure" if finding.severity == "Critical" else "warning", "message": finding.title, "title": finding.remediation or "Commit policy finding"})
    summary = f"Risk score: {snapshot.risk_score}/100\n\n{snapshot.breaking_change_count} breaking changes, {snapshot.finding_count} findings, {snapshot.component_count} components."
    return {
        "name": "Commit Intelligence", "head_sha": head_sha, "status": "completed",
        "conclusion": "failure" if blocked else "success",
        "details_url": f"{frappe.utils.get_url()}/commit/intelligence/{branch.name}?snapshot={snapshot.name}",
        "output": {"title": "Commit repository intelligence", "summary": summary, "annotations": annotations[:50]},
    }


def publish_check(project_branch, head_sha):
    branch = frappe.get_doc("Commit Project Branch", project_branch)
    snapshot = frappe.get_doc("Commit Scan Snapshot", branch.latest_scan_snapshot)
    project = frappe.get_doc("Commit Project", branch.project)
    org = frappe.db.get_value("Commit Organization", project.org, "github_org")
    return github_request("POST", f"/repos/{org}/{project.repo_name}/check-runs", json=check_payload(branch, snapshot, head_sha))


def process_event(project_branch, head_sha, delivery=None):
    from commit.commit.doctype.commit_project_branch.commit_project_branch import (
        background_fetch_process,
    )

    background_fetch_process(project_branch, force_fetch=True, initiated_by="Administrator")
    result = publish_check(project_branch, head_sha)
    project = frappe.db.get_value("Commit Project Branch", project_branch, "project")
    record_event("github.check-published", project=project, project_branch=project_branch, details={"delivery": delivery, "check": result.get("id")}, user="Administrator")


def create_docs_pull_request(project_branch, export_result):
    branch = frappe.get_doc("Commit Project Branch", project_branch)
    project = frappe.get_doc("Commit Project", branch.project)
    org = frappe.db.get_value("Commit Organization", project.org, "github_org")
    new_branch = export_result["branch"]
    base_ref = github_request("GET", f"/repos/{org}/{project.repo_name}/git/ref/heads/{project.default_branch or 'main'}")
    github_request("POST", f"/repos/{org}/{project.repo_name}/git/refs", json={"ref": f"refs/heads/{new_branch}", "sha": base_ref["object"]["sha"]})
    for path in export_result["files"]:
        content = base64.b64encode(export_result["contents"][path].encode()).decode()
        github_request("PUT", f"/repos/{org}/{project.repo_name}/contents/{path}", json={"message": f"docs: sync {path} from Commit", "content": content, "branch": new_branch})
    return github_request("POST", f"/repos/{org}/{project.repo_name}/pulls", json={"title": "docs: synchronize documentation from Commit", "head": new_branch, "base": project.default_branch or "main", "body": "Generated by Commit's reviewed docs-as-code workflow."})
