import frappe


def record_event(action: str, *, project=None, project_branch=None, details=None, user=None):
    return frappe.get_doc({
        "doctype": "Commit Audit Event",
        "action": action,
        "user": user or frappe.session.user,
        "project": project,
        "project_branch": project_branch,
        "details": details or {},
    }).insert(ignore_permissions=True)
