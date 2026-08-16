import json
from pathlib import Path

import frappe

from commit.commit.code_analysis.apis import find_all_occurrences_of_whitelist
from commit.security import get_permitted_doc, resolve_path_within


@frappe.whitelist()
def get_apis_for_project(project_branch: str):
    """
    Gets the Project Branch document with the organization and app name
    """
    branch_doc = get_permitted_doc("Commit Project Branch", project_branch)

    apis = (
        json.loads(branch_doc.whitelisted_apis).get("apis", [])
        if branch_doc.whitelisted_apis
        else []
    )
    documentation = (
        json.loads(branch_doc.documentation).get("apis", [])
        if branch_doc.documentation
        else []
    )
    for api in apis:
        # find the documentation for the api whose function_name equals to name and path same as path
        for doc in documentation:
            if isinstance(doc, str):
                try:
                    doc = json.loads(doc)
                except json.JSONDecodeError:
                    frappe.log_error(
                        f"Invalid JSON format in documentation entry: {doc}",
                        "Commit Docs Error",
                    )
                    continue

            if doc.get("function_name") == api.get("name") and doc.get(
                "path"
            ) == api.get("api_path"):
                api["documentation"] = doc.get("documentation")
                api["last_updated"] = doc.get("last_updated")
                api["is_published"] = doc.get("is_published", 0)
                api["published_on"] = doc.get("published_on", None)
                api["published_by"] = doc.get("published_by", None)
                api["publish_id"] = doc.get("publish_id", None)
                api["published_route"] = doc.get("published_route", None)
                break

        try:
            api["file"] = str(
                Path(api["file"]).resolve().relative_to(
                    Path(branch_doc.path_to_folder).resolve()
                )
            )
        except (KeyError, ValueError):
            api.pop("file", None)

    app_name, organization, app_logo = frappe.db.get_value(
        "Commit Project", branch_doc.project, ["app_name", "org", "image"]
    )
    organization_name, org_logo, organization_id = frappe.db.get_value(
        "Commit Organization", organization, ["organization_name", "image", "name"]
    )

    return {
        "apis": apis,
        "app_name": app_name,
        "organization_name": organization_name,
        "organization_id": organization_id,
        "app_logo": app_logo,
        "org_logo": org_logo,
        "branch_name": branch_doc.branch_name,
        "project_branch": branch_doc.name,
        "last_updated": branch_doc.last_fetched,
    }


@frappe.whitelist()
def get_file_content_from_path(
    project_branch: str,
    file_path: str,
    block_start: int,
    block_end: int,
    viewer_type: str,
):
    """
    Gets the Project Branch document with the organization and app name
    """
    if viewer_type == "project":
        branch_doc = get_permitted_doc("Commit Project Branch", project_branch)

        api_data = json.loads(branch_doc.whitelisted_apis)["apis"]
    else:
        if "System Manager" not in frappe.get_roles():
            frappe.throw("System Manager role required", frappe.PermissionError)
        app_path = frappe.get_app_path(project_branch)

        # remove last part of the path which is the app name
        app_path = app_path.rsplit("/", 1)[0]
        api_data = find_all_occurrences_of_whitelist(app_path, project_branch)

    found = False

    root = branch_doc.path_to_folder if viewer_type == "project" else app_path
    requested_path = resolve_path_within(root, file_path)
    for api in api_data:
        try:
            api_path = resolve_path_within(root, api["file"])
        except (KeyError, OSError):
            continue
        if api_path == requested_path:
            found = True
            break

    if not found:
        frappe.throw("File not found-")
    else:
        safe_path = requested_path
        if safe_path.is_file():
            with safe_path.open("r", encoding="utf-8") as source_file:
                file_content = source_file.readlines()
            # fetch the block
            file_content = file_content[block_start:block_end]
            return {"file_content": file_content}
        else:
            frappe.throw("File not found")
