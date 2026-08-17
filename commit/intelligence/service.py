from __future__ import annotations

import json

import frappe

from commit.intelligence.diff import compare_components, risk_score
from commit.intelligence.policy import evaluate_components, evaluate_custom_policies
from commit.intelligence.scanner import scan_repository


def _json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def _json_string(value):
    """Return JSON field values in the scalar form expected by Frappe documents."""
    return json.dumps(value, separators=(",", ":"), default=str)


def _previous_components(snapshot):
    if not snapshot:
        return []
    rows = frappe.get_all(
        "Commit Discovered Component",
        filters={"snapshot": snapshot},
        fields=["component_type", "identity", "display_name", "file_path", "line_number", "fingerprint", "definition"],
        limit_page_length=0,
    )
    for row in rows:
        row["definition"] = _json(row.definition)
    return rows


def _create_search_entries(branch, project, components):
    frappe.db.delete("Commit Search Entry", {"project_branch": branch})
    for item in components:
        definition = item.get("definition") or {}
        frappe.get_doc({
            "doctype": "Commit Search Entry",
            "entry_type": item["component_type"] if item["component_type"] in {"API", "DocType", "Hook", "Dependency"} else "API",
            "source_doctype": "Commit Discovered Component",
            "source_name": item["identity"],
            "title": item.get("display_name") or item["identity"],
            "content": " ".join((item["identity"], item.get("file_path") or "", json.dumps(definition, default=str)))[:10000],
            "route": f"/intelligence/{branch}?component={item['identity']}",
            "project": project,
            "project_branch": branch,
        }).insert(ignore_permissions=True)


def _mark_stale_docs(changes):
    for change in changes:
        if change["change_type"] == "Added":
            continue
        pages = frappe.get_all("Commit Docs Page", filters={"source_identity": change["identity"]}, pluck="name")
        for page in pages:
            frappe.db.set_value("Commit Docs Page", page, {"stale": 1, "review_status": "Needs Review"}, update_modified=False)


def persist_repository_scan(branch_doc, initiated_by=None):
    result = scan_repository(branch_doc.path_to_folder, branch_doc.app_name)
    documentation = _json(branch_doc.documentation).get("apis", []) if branch_doc.documentation else []
    docs_by_path = {item.get("path"): item for item in documentation if isinstance(item, dict) and item.get("path")}
    for component in result["components"]:
        if component["component_type"] == "API" and component["identity"] in docs_by_path:
            component["definition"]["documentation"] = docs_by_path[component["identity"]].get("documentation")
    previous = frappe.get_all(
        "Commit Scan Snapshot",
        filters={"project_branch": branch_doc.name, "status": "Completed"},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )
    previous_snapshot = previous[0] if previous else None
    snapshot = frappe.get_doc({
        "doctype": "Commit Scan Snapshot", "project_branch": branch_doc.name,
        "commit_hash": branch_doc.commit_hash, "previous_snapshot": previous_snapshot,
        "status": "Running", "initiated_by": initiated_by or frappe.session.user,
        "started_on": frappe.utils.now_datetime(),
    }).insert(ignore_permissions=True)

    for api in result["apis"]:
        definition = next(
            (
                item["definition"]
                for item in result["components"]
                if item["component_type"] == "API"
                and item["definition"].get("api_path") == api.get("api_path")
                and item["definition"].get("block_start") == api.get("block_start")
            ),
            dict(api),
        )
        frappe.get_doc({
            "doctype": "Commit Discovered API", "snapshot": snapshot.name,
            "api_path": api.get("api_path"), "function_name": api.get("name"),
            "file_path": definition.get("file", ""), "request_methods": _json_string(api.get("request_types") or []),
            "allow_guest": api.get("allow_guest", 0), "xss_safe": api.get("xss_safe", 0),
            "block_start": api.get("block_start"), "block_end": api.get("block_end"), "definition": _json_string(definition),
        }).insert(ignore_permissions=True)
    for component in result["components"]:
        component_values = {**component, "definition": _json_string(component.get("definition") or {})}
        frappe.get_doc({"doctype": "Commit Discovered Component", "snapshot": snapshot.name, **component_values}).insert(ignore_permissions=True)

    changes = compare_components(_previous_components(previous_snapshot), result["components"])
    for change in changes:
        frappe.get_doc({
            "doctype": "Commit Snapshot Change", "snapshot": snapshot.name,
            "component_type": change["component_type"], "identity": change["identity"],
            "change_type": change["change_type"], "severity": change["severity"],
            "breaking": change["breaking"], "summary": change["summary"],
            "before_definition": _json_string(change["before"]), "after_definition": _json_string(change["after"]),
        }).insert(ignore_permissions=True)

    findings = evaluate_components(result["components"]) + evaluate_custom_policies(branch_doc.project, result["components"])
    component_by_identity = {item["identity"]: item for item in result["components"]}
    for finding in findings:
        component = component_by_identity.get(finding["identity"], {})
        frappe.get_doc({
            "doctype": "Commit Finding", "snapshot": snapshot.name, "project_branch": branch_doc.name,
            "rule": finding["rule"], "title": finding["title"], "severity": finding["severity"],
            "blocking": finding.get("blocking", 0), "status": "Open", "component_identity": finding["identity"],
            "file_path": component.get("file_path"), "line_number": component.get("line_number"),
            "evidence": _json_string(finding.get("evidence")) if isinstance(finding.get("evidence"), (dict, list)) else finding.get("evidence"),
            "remediation": finding.get("remediation") or remediation_for(finding["rule"]),
        }).insert(ignore_permissions=True)

    _create_search_entries(branch_doc.name, branch_doc.project, result["components"])
    _mark_stale_docs(changes)
    branch_doc.whitelisted_apis = _json_string({"apis": result["apis"]})
    branch_doc.latest_scan_snapshot = snapshot.name
    branch_doc.scan_status = "Completed"
    snapshot.status = "Completed"
    snapshot.completed_on = frappe.utils.now_datetime()
    snapshot.api_count = len(result["apis"])
    snapshot.component_count = len(result["components"])
    snapshot.change_count = len(changes)
    snapshot.breaking_change_count = sum(bool(item["breaking"]) for item in changes)
    snapshot.finding_count = len(findings)
    snapshot.risk_score = risk_score(changes, findings)
    snapshot.save(ignore_permissions=True)
    return snapshot, changes, findings


def remediation_for(rule):
    return {
        "guest-mutation": "Require authentication and a document-level permission check for mutations.",
        "guest-no-rate-limit": "Add a rate limit or remove guest access.",
        "unsafe-get-mutation": "Restrict mutating methods to POST, PUT, PATCH, or DELETE.",
        "ignore-permissions": "Apply explicit document permissions instead of bypassing them.",
        "manual-commit": "Let Frappe commit successful POST requests automatically.",
        "filesystem-network": "Validate paths and outbound destinations; add timeouts and allowlists.",
        "undocumented-api": "Generate or curate API documentation and link it to the component.",
        "guest-doctype-mutation": "Remove Guest mutation permissions and expose a narrowly scoped permission-checked method if required.",
        "guest-doctype-read": "Confirm the DocType is safe for public disclosure or remove the Guest role permission.",
        "unpinned-dependency": "Set an explicit compatible version range and update it through reviewed dependency changes.",
    }.get(rule, "Review the component and apply the project security policy.")
