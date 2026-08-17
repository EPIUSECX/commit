import frappe

from commit.intelligence.api_testing import execute_collection
from commit.intelligence.permissions import require_project_access


@frappe.whitelist(methods=["POST"])
def run_collection(collection: str):
    document = frappe.get_doc("Commit API Collection", collection)
    require_project_access(document.project, "Editor")
    return execute_collection(collection).as_dict()


@frappe.whitelist()
def get_collections(project: str):
    require_project_access(project)
    collections = frappe.get_all("Commit API Collection", filters={"project": project}, fields=["name", "collection_name", "description", "environment", "schedule", "modified"], order_by="modified desc")
    for collection in collections:
        collection["last_run"] = frappe.get_all("Commit API Test Run", filters={"collection": collection.name}, fields=["name", "status", "duration_ms", "passed", "failed", "creation"], order_by="creation desc", limit=1)
    return collections


@frappe.whitelist()
def get_branch_collections(project_branch: str):
    project = frappe.db.get_value("Commit Project Branch", project_branch, "project")
    require_project_access(project)
    return get_collections(project)


@frappe.whitelist()
def get_run(run: str):
    document = frappe.get_doc("Commit API Test Run", run)
    collection = frappe.get_doc("Commit API Collection", document.collection)
    require_project_access(collection.project)
    return document.as_dict()
