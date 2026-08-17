from __future__ import annotations

import frappe

from commit.intelligence.audit import record_event
from commit.intelligence.permissions import require_branch_access


def _latest_snapshot(branch):
    return frappe.db.get_value("Commit Project Branch", branch, "latest_scan_snapshot")


@frappe.whitelist()
def get_overview(project_branch: str):
    project = require_branch_access(project_branch)
    branch_details = frappe.db.get_value(
        "Commit Project Branch",
        project_branch,
        ["branch_name", "commit_hash", "last_fetched", "scan_status", "frequency"],
        as_dict=True,
    )
    project_details = frappe.db.get_value(
        "Commit Project",
        project,
        ["name", "display_name", "repo_name", "org", "description"],
        as_dict=True,
    )
    snapshot_name = _latest_snapshot(project_branch)
    snapshot = frappe.get_doc("Commit Scan Snapshot", snapshot_name).as_dict() if snapshot_name else None
    snapshots = frappe.get_all(
        "Commit Scan Snapshot", filters={"project_branch": project_branch},
        fields=["name", "commit_hash", "status", "creation", "risk_score", "change_count", "breaking_change_count", "finding_count", "component_count"],
        order_by="creation desc", limit=25,
    )
    component_counts = []
    finding_counts = []
    if snapshot_name:
        component_counts = frappe.get_all(
            "Commit Discovered Component",
            filters={"snapshot": snapshot_name},
            fields=["component_type", {"COUNT": "name", "as": "count"}],
            group_by="component_type",
            order_by="count desc",
        )
        finding_counts = frappe.get_all(
            "Commit Finding",
            filters={"snapshot": snapshot_name, "status": ["!=", "Resolved"]},
            fields=["severity", {"COUNT": "name", "as": "count"}],
            group_by="severity",
        )
    return {
        "project": project,
        "project_details": project_details,
        "branch": project_branch,
        "branch_details": branch_details,
        "snapshot": snapshot,
        "snapshots": snapshots,
        "component_counts": component_counts,
        "finding_counts": finding_counts,
    }


@frappe.whitelist()
def get_changes(project_branch: str, snapshot: str | None = None):
    require_branch_access(project_branch)
    snapshot = snapshot or _latest_snapshot(project_branch)
    if not snapshot or frappe.db.get_value("Commit Scan Snapshot", snapshot, "project_branch") != project_branch:
        return []
    return frappe.get_all("Commit Snapshot Change", filters={"snapshot": snapshot}, fields=["name", "component_type", "identity", "change_type", "severity", "breaking", "summary", "before_definition", "after_definition"], order_by="breaking desc, creation asc", limit_page_length=0)


@frappe.whitelist()
def get_findings(project_branch: str, snapshot: str | None = None, status: str | None = None):
    require_branch_access(project_branch)
    filters = {"project_branch": project_branch}
    if snapshot:
        filters["snapshot"] = snapshot
    if status:
        filters["status"] = status
    return frappe.get_all("Commit Finding", filters=filters, fields=["name", "snapshot", "rule", "title", "severity", "blocking", "status", "component_identity", "file_path", "line_number", "evidence", "remediation", "assignee", "suppression_reason", "suppression_expires_on"], order_by="creation desc", limit_page_length=0)


@frappe.whitelist(methods=["POST"])
def update_finding(name: str, status: str, assignee: str | None = None, suppression_reason: str | None = None, suppression_expires_on: str | None = None):
    finding = frappe.get_doc("Commit Finding", name)
    project = require_branch_access(finding.project_branch, "Maintainer")
    finding.status = status
    finding.assignee = assignee
    finding.suppression_reason = suppression_reason
    finding.suppression_expires_on = suppression_expires_on
    finding.save(ignore_permissions=True)
    record_event("finding.updated", project=project, project_branch=finding.project_branch, details={"finding": name, "status": status})
    return finding.as_dict()


@frappe.whitelist()
def get_architecture(project_branch: str, snapshot: str | None = None):
    require_branch_access(project_branch)
    snapshot = snapshot or _latest_snapshot(project_branch)
    rows = frappe.get_all("Commit Discovered Component", filters={"snapshot": snapshot}, fields=["component_type", "identity", "display_name", "file_path", "definition"], limit_page_length=0)
    nodes, edges = [], []
    api_ids = set()
    for row in rows:
        definition = frappe.parse_json(row.definition) if isinstance(row.definition, str) else row.definition
        nodes.append({"id": f"{row.component_type}:{row.identity}", "type": row.component_type, "label": row.display_name or row.identity, "file": row.file_path})
        if row.component_type == "API":
            api_ids.add(row.identity)
        if row.component_type == "DocType":
            for field in (definition or {}).get("fields", []):
                if field.get("fieldtype") in {"Link", "Table", "Table MultiSelect"} and field.get("options"):
                    edges.append({"source": f"DocType:{row.identity}", "target": f"DocType:{field['options']}", "type": field.get("fieldtype"), "label": field.get("fieldname")})
        if row.component_type == "Consumer" and (definition or {}).get("endpoint") in api_ids:
            edges.append({"source": f"Consumer:{row.identity}", "target": f"API:{definition['endpoint']}", "type": "calls"})
    return {"nodes": nodes, "edges": edges}


@frappe.whitelist(allow_guest=True)
def search(query: str, project_branch: str | None = None, entry_type: str | None = None, limit: int = 30):
    query = (query or "").strip()[:200]
    if not query:
        return []
    filters = []
    if frappe.session.user == "Guest":
        filters.append(["is_public", "=", 1])
    elif project_branch:
        require_branch_access(project_branch)
    if entry_type:
        filters.append(["entry_type", "=", entry_type])
    words = [word for word in query.split() if word]
    or_filters = [["title", "like", f"%{word}%"] for word in words] + [["content", "like", f"%{word}%"] for word in words]
    candidates = frappe.get_all("Commit Search Entry", filters=filters, or_filters=or_filters, fields=["entry_type", "title", "route", "project", "project_branch", "source_name", "is_public"], limit=min(int(limit) * 4, 400), order_by="modified desc")
    results = [item for item in candidates if not project_branch or item.project_branch == project_branch or item.is_public][: min(int(limit), 100)]
    project = frappe.db.get_value("Commit Project Branch", project_branch, "project") if project_branch else None
    frappe.get_doc({"doctype": "Commit Analytics Event", "event_type": "Search" if results else "Search Miss", "project": project, "project_branch": project_branch, "query": query, "user": None if frappe.session.user == "Guest" else frappe.session.user, "details": {"result_count": len(results)}}).insert(ignore_permissions=True)
    return results


@frappe.whitelist()
def get_component(project_branch: str, identity: str, snapshot: str | None = None):
    require_branch_access(project_branch)
    snapshot = snapshot or _latest_snapshot(project_branch)
    return frappe.get_all("Commit Discovered Component", filters={"snapshot": snapshot, "identity": identity}, fields=["component_type", "identity", "display_name", "file_path", "line_number", "definition"], limit=1)


@frappe.whitelist()
def get_analytics(project_branch: str):
    project = require_branch_access(project_branch)
    searches = frappe.get_all("Commit Analytics Event", filters={"project": project, "event_type": ["in", ["Search", "Search Miss"]]}, fields=["event_type", "query", "creation"], order_by="creation desc", limit=100)
    audits = frappe.get_all("Commit Audit Event", filters={"project": project}, fields=["action", "user", "project_branch", "details", "creation"], order_by="creation desc", limit=100)
    return {"searches": searches, "audit_events": audits}
