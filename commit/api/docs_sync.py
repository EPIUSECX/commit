import frappe

from commit.intelligence.docs import export_markdown, import_markdown, release_notes
from commit.intelligence.permissions import require_branch_access


@frappe.whitelist(methods=["POST"])
def import_docs(project_branch: str, commit_docs: str):
    return import_markdown(project_branch, commit_docs)


@frappe.whitelist(methods=["POST"])
def export_docs(project_branch: str, commit_docs: str):
    return export_markdown(project_branch, commit_docs)


@frappe.whitelist()
def get_release_notes(snapshot: str):
    branch = frappe.db.get_value("Commit Scan Snapshot", snapshot, "project_branch")
    require_branch_access(branch)
    return release_notes(snapshot)


@frappe.whitelist(allow_guest=True)
def resolve_redirect(route: str):
    target = frappe.db.get_value("Commit Docs Redirect", {"old_route": route, "enabled": 1}, "new_route")
    return {"route": target} if target else None
