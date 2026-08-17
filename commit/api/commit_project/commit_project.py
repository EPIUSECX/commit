import frappe

from commit.security import require_any_role


@frappe.whitelist()
def get_project_list_with_branches():
    """
    Get list of projects with branches for each organization
    """

    require_any_role("Commit Project Member", "System Manager")
    organizations = frappe.get_list(
        "Commit Organization",
        fields=[
            "name",
            "organization_name",
            "github_org",
            "image",
            "about",
            "creation",
        ],
    )
    for organization in organizations:
        projects = frappe.get_list(
            "Commit Project",
            filters={"org": organization.get("name")},
            fields=[
                "name",
                "display_name",
                "repo_name",
                "app_name",
                "image",
                "banner_image",
                "description",
                "default_branch",
            ],
            order_by="creation desc",
        )
        # organization["projects"] = projects
        for project in projects:
            branches = frappe.get_list(
                "Commit Project Branch",
                filters={"project": project.get("name")},
                fields=[
                    "branch_name",
                    "last_fetched",
                    "commit_hash",
                    "scan_status",
                    "latest_scan_snapshot",
                    "modules",
                    "whitelisted_apis",
                    "name",
                    "frequency",
                ],
            )
            for branch in branches:
                snapshot = branch.get("latest_scan_snapshot")
                branch["intelligence"] = (
                    frappe.db.get_value(
                        "Commit Scan Snapshot",
                        snapshot,
                        [
                            "risk_score",
                            "finding_count",
                            "breaking_change_count",
                            "component_count",
                            "completed_on",
                        ],
                        as_dict=True,
                    )
                    if snapshot
                    else None
                )
            project["branches"] = branches
        organization["projects"] = projects

    return organizations
