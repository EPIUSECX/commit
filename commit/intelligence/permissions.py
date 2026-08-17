import frappe

ROLE_LEVEL = {"Viewer": 1, "Editor": 2, "Maintainer": 3, "Owner": 4}


def _user(user=None):
    return user or frappe.session.user


def _is_system_manager(user=None):
    return "System Manager" in frappe.get_roles(_user(user))


def _project_condition(user=None):
    user = frappe.db.escape(_user(user))
    return (
        f"(`tabCommit Project`.owner = {user} OR EXISTS ("
        "SELECT 1 FROM `tabCommit Organization Member` member "
        f"WHERE member.parent = `tabCommit Project`.org AND member.user = {user}))"
    )


def membership_for_project(project: str, user: str | None = None):
    user = user or frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return "Owner"
    values = frappe.db.get_value("Commit Project", project, ["org", "owner"], as_dict=True)
    if not values:
        return None
    if values.owner == user:
        return "Owner"
    return frappe.db.get_value("Commit Organization Member", {"parent": values.org, "user": user}, "access_level")


def project_query(user=None):
    return "" if _is_system_manager(user) else _project_condition(user)


def branch_query(user=None):
    if _is_system_manager(user):
        return ""
    condition = _project_condition(user).replace("`tabCommit Project`", "project")
    return f"EXISTS (SELECT 1 FROM `tabCommit Project` project WHERE project.name = `tabCommit Project Branch`.project AND {condition})"


def snapshot_query(user=None):
    if _is_system_manager(user):
        return ""
    branch_condition = branch_query(user).replace("`tabCommit Project Branch`", "branch")
    return f"EXISTS (SELECT 1 FROM `tabCommit Project Branch` branch WHERE branch.name = `tabCommit Scan Snapshot`.project_branch AND {branch_condition})"


def snapshot_child_query(doctype, user=None):
    if _is_system_manager(user):
        return ""
    snapshot_condition = snapshot_query(user).replace("`tabCommit Scan Snapshot`", "snapshot")
    return f"EXISTS (SELECT 1 FROM `tabCommit Scan Snapshot` snapshot WHERE snapshot.name = `tab{doctype}`.snapshot AND {snapshot_condition})"


def component_query(user=None):
    return snapshot_child_query("Commit Discovered Component", user)


def discovered_api_query(user=None):
    return snapshot_child_query("Commit Discovered API", user)


def change_query(user=None):
    return snapshot_child_query("Commit Snapshot Change", user)


def finding_query(user=None):
    if _is_system_manager(user):
        return ""
    branch_condition = branch_query(user).replace("`tabCommit Project Branch`", "branch")
    return f"EXISTS (SELECT 1 FROM `tabCommit Project Branch` branch WHERE branch.name = `tabCommit Finding`.project_branch AND {branch_condition})"


def project_link_query(doctype, user=None):
    if _is_system_manager(user):
        return ""
    condition = _project_condition(user).replace("`tabCommit Project`", "project")
    return f"EXISTS (SELECT 1 FROM `tabCommit Project` project WHERE project.name = `tab{doctype}`.project AND {condition})"


def api_collection_query(user=None):
    return project_link_query("Commit API Collection", user)


def api_environment_query(user=None):
    return project_link_query("Commit API Environment", user)


def notification_query(user=None):
    return project_link_query("Commit Notification Endpoint", user)


def policy_query(user=None):
    return project_link_query("Commit Policy", user)


def audit_query(user=None):
    return project_link_query("Commit Audit Event", user)


def search_entry_query(user=None):
    if _is_system_manager(user):
        return ""
    condition = _project_condition(user).replace("`tabCommit Project`", "project")
    return f"(`tabCommit Search Entry`.is_public = 1 OR EXISTS (SELECT 1 FROM `tabCommit Project` project WHERE project.name = `tabCommit Search Entry`.project AND {condition}))"


def test_run_query(user=None):
    if _is_system_manager(user):
        return ""
    collection_condition = api_collection_query(user).replace("`tabCommit API Collection`", "collection")
    return f"EXISTS (SELECT 1 FROM `tabCommit API Collection` collection WHERE collection.name = `tabCommit API Test Run`.collection AND {collection_condition})"


def has_project_permission(doc, user=None, permission_type="read"):
    if _is_system_manager(user):
        return True
    if doc.is_new() and doc.org:
        level = frappe.db.get_value("Commit Organization Member", {"parent": doc.org, "user": _user(user)}, "access_level")
    else:
        level = membership_for_project(doc.name, _user(user))
    required = "Viewer" if permission_type in {"read", "select", "print", "email", "report"} else "Editor" if permission_type in {"create", "write"} else "Maintainer"
    return bool(level and ROLE_LEVEL.get(level, 0) >= ROLE_LEVEL[required])


def has_branch_permission(doc, user=None, permission_type="read"):
    level = membership_for_project(doc.project, _user(user))
    required = "Viewer" if permission_type in {"read", "select", "print", "email", "report"} else "Editor" if permission_type in {"create", "write"} else "Maintainer"
    return bool(level and ROLE_LEVEL.get(level, 0) >= ROLE_LEVEL[required])


def has_finding_permission(doc, user=None, permission_type="read"):
    branch = frappe.get_doc("Commit Project Branch", doc.project_branch)
    return has_branch_permission(branch, user, permission_type)


def has_snapshot_permission(doc, user=None, permission_type="read"):
    branch = frappe.get_doc("Commit Project Branch", doc.project_branch)
    return has_branch_permission(branch, user, permission_type)


def has_snapshot_child_permission(doc, user=None, permission_type="read"):
    snapshot = frappe.get_doc("Commit Scan Snapshot", doc.snapshot)
    return has_snapshot_permission(snapshot, user, permission_type)


def has_project_link_permission(doc, user=None, permission_type="read"):
    level = membership_for_project(doc.project, _user(user))
    required = "Viewer" if permission_type in {"read", "select", "print", "email", "report"} else "Editor"
    return bool(level and ROLE_LEVEL.get(level, 0) >= ROLE_LEVEL[required])


def has_search_entry_permission(doc, user=None, permission_type="read"):
    if doc.is_public and permission_type == "read":
        return True
    return bool(doc.project and membership_for_project(doc.project, _user(user)))


def require_project_access(project: str, level="Viewer"):
    actual = membership_for_project(project)
    if not actual or ROLE_LEVEL.get(actual, 0) < ROLE_LEVEL[level]:
        frappe.throw("You do not have access to this project", frappe.PermissionError)
    return actual


def require_branch_access(branch: str, level="Viewer"):
    project = frappe.db.get_value("Commit Project Branch", branch, "project")
    if not project:
        frappe.throw("Project branch not found")
    require_project_access(project, level)
    return project
