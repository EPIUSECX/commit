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
                    "modules",
                    "whitelisted_apis",
                    "name",
                    "frequency",
                ],
            )
            project["branches"] = branches
        organization["projects"] = projects

    return organizations
