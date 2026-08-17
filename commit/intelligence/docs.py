from __future__ import annotations

import hashlib
import re
from pathlib import Path

import frappe
import git

from commit.intelligence.audit import record_event
from commit.intelligence.permissions import require_branch_access


def content_fingerprint(content: str) -> str:
    return hashlib.sha256((content or "").encode()).hexdigest()


def create_version(page, summary=None):
    if not page.name or not page.content:
        return None
    latest = frappe.db.get_value("Commit Docs Version", {"docs_page": page.name}, "max(version)") or 0
    version = frappe.get_doc({
        "doctype": "Commit Docs Version", "docs_page": page.name, "version": int(latest) + 1,
        "source_path": page.source_path, "source_identity": page.source_identity,
        "source_fingerprint": page.source_fingerprint, "status": page.review_status or "Draft",
        "content": page.content, "change_summary": summary,
    }).insert(ignore_permissions=True)
    page.db_set("current_version", version.version, update_modified=False)
    index_docs_page(page)
    return version


def index_docs_page(page):
    route = f"/commit-docs/{page.commit_docs}/{page.route}"
    existing = frappe.db.get_value("Commit Search Entry", {"source_doctype": "Commit Docs Page", "source_name": page.name})
    values = {
        "entry_type": "Documentation", "source_doctype": "Commit Docs Page", "source_name": page.name,
        "title": page.title, "content": re.sub(r"[`#*_>]", " ", page.content or "")[:10000],
        "route": route, "is_public": bool(page.published and page.allow_guest),
    }
    if existing:
        frappe.db.set_value("Commit Search Entry", existing, values)
    else:
        frappe.get_doc({"doctype": "Commit Search Entry", **values}).insert(ignore_permissions=True)


def import_markdown(project_branch: str, commit_docs: str):
    project = require_branch_access(project_branch, "Editor")
    branch = frappe.get_doc("Commit Project Branch", project_branch)
    project_doc = frappe.get_doc("Commit Project", project)
    docs_root = (Path(branch.path_to_folder) / (project_doc.docs_path or "docs")).resolve()
    docs_root.relative_to(Path(branch.path_to_folder).resolve())
    if not docs_root.exists():
        frappe.throw(f"Documentation path does not exist: {project_doc.docs_path or 'docs'}")
    imported = []
    parent = frappe.get_doc("Commit Docs", commit_docs)
    parent.check_permission("write")
    for path in sorted(docs_root.glob("**/*.md")):
        relative = str(path.relative_to(Path(branch.path_to_folder)))
        route = re.sub(r"[^a-z0-9-]+", "-", str(path.relative_to(docs_root).with_suffix("")).lower()).strip("-")
        page_name = frappe.db.get_value("Commit Docs Page", {"commit_docs": commit_docs, "source_path": relative})
        values = {"title": path.stem.replace("-", " ").replace("_", " ").title(), "commit_docs": commit_docs, "content": path.read_text(encoding="utf-8"), "source_path": relative, "review_status": "Needs Review", "stale": 0}
        if page_name:
            page = frappe.get_doc("Commit Docs Page", page_name)
            page.update(values)
            page.save()
        else:
            page = frappe.get_doc({"doctype": "Commit Docs Page", "route": f"{commit_docs}-{route}", **values}).insert()
            parent.append("sidebar", {"parent_label": "Documentation", "docs_page": page.name})
        imported.append(page.name)
    parent.save()
    record_event("docs.imported", project=project, project_branch=project_branch, details={"pages": imported})
    return imported


def export_markdown(project_branch: str, commit_docs: str):
    project = require_branch_access(project_branch, "Maintainer")
    branch = frappe.get_doc("Commit Project Branch", project_branch)
    project_doc = frappe.get_doc("Commit Project", project)
    root = Path(branch.path_to_folder).resolve()
    docs_root = (root / (project_doc.docs_path or "docs")).resolve()
    docs_root.relative_to(root)
    pages = frappe.get_all("Commit Docs Page", filters={"commit_docs": commit_docs}, fields=["name", "title", "route", "content", "source_path"])
    repo = git.Repo(root)
    original_branch = repo.active_branch.name
    branch_name = f"commit/docs-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}"
    repo.git.checkout("-B", branch_name)
    docs_root.mkdir(parents=True, exist_ok=True)
    written = []
    contents = {}
    try:
        for page in pages:
            target = (root / page.source_path).resolve() if page.source_path else docs_root / f"{page.route}.md"
            target.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            contents[str(target.relative_to(root))] = page.content or ""
            target.write_text(page.content or "", encoding="utf-8")
            written.append(str(target.relative_to(root)))
        repo.index.add(written)
        commit = repo.index.commit(f"docs: sync {commit_docs} from Commit")
    finally:
        repo.git.checkout(original_branch)
    record_event("docs.exported", project=project, project_branch=project_branch, details={"branch": branch_name, "commit": commit.hexsha, "files": written})
    return {"branch": branch_name, "commit": commit.hexsha, "files": written, "contents": contents}


def release_notes(snapshot: str) -> str:
    changes = frappe.get_all("Commit Snapshot Change", filters={"snapshot": snapshot}, fields=["severity", "change_type", "component_type", "identity", "summary", "breaking"], order_by="breaking desc, severity desc")
    if not changes:
        return "# Release notes\n\nNo externally visible component changes were detected."
    lines = ["# Release notes", ""]
    for title, predicate in (("Breaking changes", lambda item: item.breaking), ("Security-sensitive changes", lambda item: item.severity in {"Critical", "High"} and not item.breaking), ("Other changes", lambda item: not item.breaking and item.severity not in {"Critical", "High"})):
        selected = [item for item in changes if predicate(item)]
        if selected:
            lines += [f"## {title}", ""] + [f"- **{item.change_type} {item.component_type}:** `{item.identity}` — {item.summary}" for item in selected] + [""]
    return "\n".join(lines)
