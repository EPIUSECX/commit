from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from commit.commit.code_analysis.apis import find_all_occurrences_of_whitelist

API_CALL_PATTERN = re.compile(
    r"(?:call\.(?:get|post)|useFrappe(?:Get|Post)Call)\s*\(\s*['\"]([^'\"]+)"
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _component(kind: str, identity: str, name: str, path: str, definition: Any, line=0):
    return {
        "component_type": kind,
        "identity": identity,
        "display_name": name,
        "file_path": path,
        "line_number": line,
        "definition": definition,
        "fingerprint": fingerprint(definition),
    }


def scan_apis(root: Path, app_name: str) -> tuple[list[dict], list[dict]]:
    apis = find_all_occurrences_of_whitelist(str(root), app_name)
    components = []
    for api in apis:
        definition = dict(api)
        path = _relative(root, Path(api["file"]))
        definition["file"] = path
        try:
            lines = Path(api["file"]).read_text(encoding="utf-8").splitlines()
            definition["source"] = "\n".join(lines[max(0, api.get("block_start", 1) - 1):api.get("block_end")])
        except OSError:
            definition["source"] = ""
        identity = api.get("api_path") or f"{app_name}.{api.get('name')}"
        components.append(
            _component("API", identity, api.get("name") or identity, path, definition, api.get("block_start", 0))
        )
    return apis, components


def scan_doctypes(root: Path, app_name: str) -> list[dict]:
    components = []
    app_root = root / app_name
    for path in app_root.glob("**/doctype/*/*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("doctype") != "DocType" or not data.get("name"):
            continue
        definition = {
            "name": data["name"],
            "module": data.get("module"),
            "istable": bool(data.get("istable")),
            "issingle": bool(data.get("issingle")),
            "is_submittable": bool(data.get("is_submittable")),
            "fields": [
                {
                    key: field.get(key)
                    for key in ("fieldname", "fieldtype", "options", "reqd", "read_only", "unique")
                    if field.get(key) not in (None, 0, "")
                }
                for field in data.get("fields", [])
                if field.get("fieldname")
            ],
            "permissions": data.get("permissions", []),
        }
        components.append(_component("DocType", data["name"], data["name"], _relative(root, path), definition))
        guest_permissions = [permission for permission in data.get("permissions", []) if permission.get("role") == "Guest"]
        guest_methods = []
        if any(permission.get("read") for permission in guest_permissions):
            guest_methods.append("GET")
        if any(permission.get("create") for permission in guest_permissions):
            guest_methods.append("POST")
        if any(permission.get("write") for permission in guest_permissions):
            guest_methods.extend(["PUT", "PATCH"])
        if any(permission.get("delete") for permission in guest_permissions):
            guest_methods.append("DELETE")
        resource_definition = {
            "kind": "DocType Resource API",
            "doctype": data["name"],
            "request_types": ["GET", "POST", "PUT", "DELETE"],
            "allow_guest": any(permission.get("read") for permission in guest_permissions),
            "guest_methods": guest_methods,
            "permissions": data.get("permissions", []),
            "documentation": "Frappe-generated DocType resource API",
        }
        components.append(_component("API", f"/api/resource/{data['name']}", f"{data['name']} Resource API", _relative(root, path), resource_definition))
    return components


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return ast.unparse(node) if hasattr(ast, "unparse") else "dynamic"


def scan_hooks(root: Path, app_name: str) -> list[dict]:
    path = root / app_name / "hooks.py"
    if not path.exists():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    components = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if not isinstance(target, ast.Name):
            continue
        value = _literal(node.value)
        if target.id.startswith("_") or target.id in {"app_name", "app_title", "app_license"}:
            continue
        components.append(_component("Hook", target.id, target.id, _relative(root, path), value, node.lineno))
    return components


def scan_dependencies(root: Path) -> list[dict]:
    components = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        for match in re.finditer(r'^[ \t]*["\']([A-Za-z0-9_.-]+)([^"\']*)["\'][,]?[ \t]*$', text, re.MULTILINE):
            name, constraint = match.group(1), match.group(2).strip()
            definition = {"ecosystem": "python", "name": name, "constraint": constraint}
            components.append(_component("Dependency", f"python:{name.lower()}", name, "pyproject.toml", definition, text[:match.start()].count("\n") + 1))
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        for group in ("dependencies", "devDependencies"):
            for name, constraint in data.get(group, {}).items():
                definition = {"ecosystem": "npm", "name": name, "constraint": constraint, "group": group}
                components.append(_component("Dependency", f"npm:{name.lower()}", name, "package.json", definition))
    requirements = root / "requirements.txt"
    if requirements.exists():
        for line_number, line in enumerate(requirements.read_text(encoding="utf-8").splitlines(), 1):
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            name = re.split(r"[<>=!~\[]", value, 1)[0]
            definition = {"ecosystem": "python", "name": name, "constraint": value[len(name):]}
            identity = f"python:{name.lower()}"
            if not any(item["identity"] == identity for item in components):
                components.append(_component("Dependency", identity, name, "requirements.txt", definition, line_number))
    return components


def scan_frontend_consumers(root: Path) -> list[dict]:
    components = []
    for folder in (root / "dashboard" / "src", root / "docs" / "src"):
        if not folder.exists():
            continue
        for path in folder.glob("**/*"):
            if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in API_CALL_PATTERN.finditer(text):
                endpoint = match.group(1)
                definition = {"endpoint": endpoint, "consumer": _relative(root, path)}
                identity = f"{endpoint}:{_relative(root, path)}:{text[:match.start()].count(chr(10)) + 1}"
                components.append(_component("Consumer", identity, endpoint, _relative(root, path), definition, text[:match.start()].count("\n") + 1))
    return components


def scan_portal_routes(root: Path, app_name: str) -> list[dict]:
    components = []
    www = root / app_name / "www"
    if not www.exists():
        return components
    for path in www.glob("**/*"):
        if path.suffix not in {".py", ".html", ".md"} or path.name.startswith("_"):
            continue
        route = "/" + str(path.relative_to(www).with_suffix(""))
        definition = {"route": route, "kind": path.suffix.lstrip(".")}
        components.append(_component("Portal Route", route, route, _relative(root, path), definition))
    return components


def scan_commands(root: Path, app_name: str) -> list[dict]:
    components = []
    for path in (root / app_name).glob("**/commands.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = [ast.unparse(item) if hasattr(ast, "unparse") else "" for item in node.decorator_list]
            if not any("command" in item for item in decorators):
                continue
            definition = {"function": node.name, "decorators": decorators, "arguments": [argument.arg for argument in node.args.args]}
            components.append(_component("Command", f"{app_name}:{node.name}", node.name.replace("_", "-"), _relative(root, path), definition, node.lineno))
    return components


def scan_repository(root: str, app_name: str) -> dict:
    root_path = Path(root).resolve()
    apis, api_components = scan_apis(root_path, app_name)
    components = api_components
    components += scan_doctypes(root_path, app_name)
    components += scan_hooks(root_path, app_name)
    components += scan_dependencies(root_path)
    components += scan_frontend_consumers(root_path)
    components += scan_portal_routes(root_path, app_name)
    components += scan_commands(root_path, app_name)
    components.sort(key=lambda item: (item["component_type"], item["identity"]))
    return {"apis": apis, "components": components}
