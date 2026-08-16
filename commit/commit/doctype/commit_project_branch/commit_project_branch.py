# Copyright (c) 2023, The Commit Company and contributors
# For license information, please see license.txt

import json
import os
import shutil
from pathlib import Path

import frappe
import git
from frappe.model.document import Document
from frappe.utils import now

from commit.api.generate_documentation import generate_docs_for_apis
from commit.commit.code_analysis.apis import find_all_occurrences_of_whitelist
from commit.commit.code_analysis.doctypes import (
    get_doctype_json,
    get_doctypes_in_module,
)
from commit.security import get_permitted_doc


class CommitProjectBranch(Document):

    def before_insert(self):
        self.path_to_folder = self.get_path_to_folder()
        self.create_branch_folder()

    def after_insert(self):
        frappe.enqueue(
            method=background_fetch_process,
            is_async=True,
            job_name="Fetch Project Branch",
            enqueue_after_commit=True,
            at_front=True,
            project_branch=self.name,
            initiated_by=frappe.session.user,
        )

    def on_update(self):
        old_doc = self.get_doc_before_save()
        if type(self.whitelisted_apis) == str:
            apis = json.loads(
                self.whitelisted_apis if self.whitelisted_apis else ""
            ).get("apis", [])
        else:
            apis = (
                self.whitelisted_apis.get("apis", []) if self.whitelisted_apis else []
            )
        if (
            old_doc
            and old_doc.whitelisted_apis != self.whitelisted_apis
            and len(apis) > 0
        ):
            frappe.enqueue(
                method=generate_branch_documentation,
                is_async=True,
                job_name="Generate Branch Documentation",
                enqueue_after_commit=True,
                at_front=True,
                queue="long",
                project_branch=self.name,
            )

    def create_branch_folder(self):
        if not os.path.exists(self.path_to_folder):
            os.mkdir(self.path_to_folder)

    def get_path_to_folder(self):
        project = frappe.get_cached_doc("Commit Project", self.project)
        base = Path(project.path_to_folder).resolve()
        branch_path = (base / self.branch_name).resolve()
        try:
            branch_path.relative_to(base)
        except ValueError:
            frappe.throw("Invalid branch name")
        return str(branch_path)

    def clone_repo(self):
        project = frappe.get_cached_doc("Commit Project", self.project)
        self.app_name = project.app_name
        repo_url = f"https://github.com/{project.org}/{project.repo_name}"

        folder_path = self.path_to_folder

        repo = git.Repo.clone_from(
            repo_url, folder_path, branch=self.branch_name, single_branch=True
        )
        self.last_fetched = frappe.utils.now_datetime()
        self.commit_hash = repo.head.object.hexsha

    def fetch_repo(self):
        previous_hash = self.commit_hash
        repo = git.Repo(self.path_to_folder)
        repo.remotes.origin.fetch()

        # Force fast-forward only to avoid merge commits
        try:
            # Try fast-forward pull
            repo.git.pull("--ff-only")
        except Exception:
            # If fast-forward not possible, reset to remote branch
            repo.git.reset("--hard", "origin/" + self.branch_name)

        self.last_fetched = now()
        self.commit_hash = repo.head.object.hexsha

        return previous_hash != self.commit_hash

    def get_modules(self):
        modules_path = os.path.join(self.path_to_folder, self.app_name, "modules.txt")
        if os.path.isfile(modules_path):
            modules_file = open(modules_path)
            modules = modules_file.read().splitlines()
            self.modules = ",".join(modules)

            module_doctypes_map = {}
            doctype_module_map = {}
            for module in modules:
                module_doctypes_map[module] = get_doctypes_in_module(
                    self.path_to_folder, self.app_name, module
                )
                for doctype in module_doctypes_map[module].get("doctype_names", []):
                    doctype_module_map[doctype] = module

            self.module_doctypes_map = module_doctypes_map
            self.doctype_module_map = doctype_module_map

    def find_all_apis(self):
        apis = find_all_occurrences_of_whitelist(self.path_to_folder, self.app_name)
        # Convert list to string and save to database
        self.whitelisted_apis = {"apis": apis}
        self.persist_scan_snapshot(apis)
        return apis

    def persist_scan_snapshot(self, apis):
        """Persist queryable scan results while retaining the legacy JSON cache."""
        snapshot = frappe.get_doc(
            {
                "doctype": "Commit Scan Snapshot",
                "project_branch": self.name,
                "commit_hash": self.commit_hash,
                "status": "Running",
                "initiated_by": frappe.session.user,
                "started_on": frappe.utils.now_datetime(),
            }
        ).insert(ignore_permissions=True)

        root = Path(self.path_to_folder).resolve()
        for api in apis:
            source_path = Path(api.get("file", "")).resolve()
            try:
                relative_path = str(source_path.relative_to(root))
            except ValueError:
                continue
            definition = dict(api)
            definition["file"] = relative_path
            frappe.get_doc(
                {
                    "doctype": "Commit Discovered API",
                    "snapshot": snapshot.name,
                    "api_path": api.get("api_path"),
                    "function_name": api.get("name"),
                    "file_path": relative_path,
                    "request_methods": api.get("request_types") or [],
                    "allow_guest": api.get("allow_guest", 0),
                    "xss_safe": api.get("xss_safe", 0),
                    "block_start": api.get("block_start"),
                    "block_end": api.get("block_end"),
                    "definition": definition,
                }
            ).insert(ignore_permissions=True)

        snapshot.status = "Completed"
        snapshot.completed_on = frappe.utils.now_datetime()
        snapshot.api_count = len(apis)
        snapshot.save(ignore_permissions=True)
        self.latest_scan_snapshot = snapshot.name
        self.scan_status = "Completed"

    def get_whitelisted_apis_code(self):
        apis = []
        apis_code = []

        if self.whitelisted_apis:
            if type(self.whitelisted_apis) == str:
                apis = json.loads(
                    self.whitelisted_apis if self.whitelisted_apis else ""
                ).get("apis", [])
            else:
                apis = (
                    self.whitelisted_apis.get("apis", [])
                    if self.whitelisted_apis
                    else []
                )

        for api in apis:
            # file_content =  get_file_content_from_path(self.name, api['file'], api['block_start'], api['block_end'], "project")
            file_content = get_code_from_file(
                api["file"], api["block_start"], api["block_end"]
            )

            content = file_content.get("file_content", [])
            content = "".join(content)
            apis_code.append(
                {
                    "file": api["file"],
                    "path": api["api_path"],
                    "function_name": api["name"],
                    "code": content,
                }
            )

        documentation = generate_docs_for_apis(apis_code)

        self.documentation = {"apis": documentation}

    def get_doctype_json(self, doctype_name):
        if self.doctype_module_map:
            doctype_module_map = json.loads(self.doctype_module_map)
            module = doctype_module_map.get(doctype_name)
            if module:
                return get_doctype_json(
                    self.path_to_folder, self.app_name, module, doctype_name
                )
        return None

    def get_doctypes_in_module(self, module):
        if self.module_doctypes_map:
            module_doctypes_map = json.loads(self.module_doctypes_map)
            return module_doctypes_map.get(module, {}).get("doctype_names", [])

    def on_trash(self):
        # Delete the folder
        if self.path_to_folder and os.path.exists(self.path_to_folder):
            shutil.rmtree(self.path_to_folder)


def get_code_from_file(file_path: str, block_start: int, block_end: int):
    if os.path.isfile(file_path):
        with open(file_path, encoding="utf-8") as source_file:
            file_content = source_file.readlines()
        # fetch the block
        file_content = file_content[block_start:block_end]
        return {"file_content": file_content}
    else:
        frappe.throw("File not found")


def background_fetch_process(project_branch, force_fetch=False, initiated_by=None):
    initiated_by = initiated_by or frappe.session.user
    try:
        doc = frappe.get_cached_doc("Commit Project Branch", project_branch)
        doc.scan_status = "Running"
        doc.db_set("scan_status", "Running", update_modified=False)
        frappe.publish_realtime(
            "commit_branch_clone_repo",
            {
                "branch_name": doc.branch_name,
                "project": doc.project,
                "text": "Cloning repository...",
                "is_completed": False,
            },
            user=initiated_by,
        )

        if force_fetch or (Path(doc.path_to_folder) / ".git").is_dir():
            changed = doc.fetch_repo()
        else:
            doc.clone_repo()
            changed = True
        frappe.publish_realtime(
            "commit_branch_get_modules",
            {
                "branch_name": doc.branch_name,
                "project": doc.project,
                "text": "Getting all modules for your app...",
                "is_completed": False,
            },
            user=initiated_by,
        )

        if changed:
            doc.get_modules()

        frappe.publish_realtime(
            "commit_branch_find_apis",
            {
                "branch_name": doc.branch_name,
                "project": doc.project,
                "text": "Finding all APIs...",
                "is_completed": False,
            },
            user=initiated_by,
        )

        if changed:
            doc.find_all_apis()

        # doc.get_whitelisted_apis_code()
        doc.save()

        frappe.publish_realtime(
            "commit_project_branch_created",
            {
                "name": doc.name,
                "branch_name": doc.branch_name,
                "project": doc.project,
                "text": "Branch created successfully.",
                "is_completed": True,
            },
            user=initiated_by,
        )

    except Exception:
        # throw the error and delete the document
        messages = [
            json.dumps({"message": "There was an error while fetching branch repo."})
        ]
        frappe.clear_messages()
        frappe.publish_realtime(
            "commit_branch_creation_error",
            {
                "branch_name": doc.branch_name,
                "project": doc.project,
                "error": {
                    "exception": frappe.get_traceback(),
                    "_server_messages": json.dumps(messages),
                },
                # 'response': handle_exception(e),
                "is_completed": False,
            },
            user=initiated_by,
        )

        if "doc" in locals():
            doc.db_set("scan_status", "Failed", update_modified=False)
            if doc.commit_hash:
                frappe.get_doc(
                    {
                        "doctype": "Commit Scan Snapshot",
                        "project_branch": doc.name,
                        "commit_hash": doc.commit_hash,
                        "status": "Failed",
                        "initiated_by": initiated_by,
                        "started_on": frappe.utils.now_datetime(),
                        "completed_on": frappe.utils.now_datetime(),
                        "error": frappe.get_traceback()[-10000:],
                    }
                ).insert(ignore_permissions=True)
        frappe.log_error(frappe.get_traceback(), "Commit branch scan failed")

        # raise e


@frappe.whitelist(methods=["POST"])
def fetch_repo(doc, name=None):
    if name:
        project_branch = get_permitted_doc("Commit Project Branch", name, "write")
    else:
        doc = json.loads(doc)
        project_branch = get_permitted_doc(
            "Commit Project Branch", doc.get("name"), "write"
        )
    project_branch.db_set("scan_status", "Queued", update_modified=False)
    frappe.enqueue(
        method=background_fetch_process,
        queue="long",
        enqueue_after_commit=True,
        deduplicate=True,
        project_branch=project_branch.name,
        force_fetch=True,
        initiated_by=frappe.session.user,
        job_name=f"Commit branch fetch {project_branch.name}",
    )
    return {"queued": True, "project_branch": project_branch.name}


def generate_branch_documentation(project_branch):
    frappe.publish_realtime(
        "commit_branch_generate_documentation",
        {
            "branch_name": project_branch,
            "text": "Generating documentation...",
            "is_completed": False,
        },
        user=frappe.session.user,
    )

    doc = frappe.get_cached_doc("Commit Project Branch", project_branch)
    doc.get_whitelisted_apis_code()
    doc.save()

    frappe.publish_realtime(
        "commit_branch_generate_documentation",
        {
            "branch_name": doc.branch_name,
            "project": doc.project,
            "text": "Documentation generated successfully.",
            "is_completed": True,
        },
        user=frappe.session.user,
    )
    return "Documentation generated successfully"


@frappe.whitelist()
def get_module_doctype_map_for_branches(branches: str):
    branches = json.loads(branches)
    module_doctypes_map = {}
    for branch in branches:
        project_branch = get_permitted_doc("Commit Project Branch", branch)
        module_doctypes_map[branch] = json.loads(project_branch.module_doctypes_map)
    return module_doctypes_map
