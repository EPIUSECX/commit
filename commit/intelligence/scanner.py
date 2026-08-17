from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    import tomli as tomllib

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
    path_counts: dict[str, int] = {}
    for api in apis:
        path = api.get("api_path") or f"{app_name}.{api.get('name')}"
        path_counts[path] = path_counts.get(path, 0) + 1
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
        if path_counts[identity] > 1:
            identity = f"{identity}#L{api.get('block_start', 0)}"
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
        if not isinstance(data, dict) or data.get("doctype") != "DocType" or not data.get("name"):
            continue
        fields = data.get("fields") if isinstance(data.get("fields"), list) else []
        permissions = data.get("permissions") if isinstance(data.get("permissions"), list) else []
        fields = [field for field in fields if isinstance(field, dict)]
        permissions = [permission for permission in permissions if isinstance(permission, dict)]
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
                for field in fields
                if field.get("fieldname")
            ],
            "permissions": permissions,
        }
        components.append(_component("DocType", data["name"], data["name"], _relative(root, path), definition))
        guest_permissions = [permission for permission in permissions if permission.get("role") == "Guest"]
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
            "permissions": permissions,
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
        try:
            pyproject_data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            pyproject_data = {}

        requirements: list[tuple[str, str]] = []
        project = pyproject_data.get("project", {})
        requirements.extend((item, "runtime") for item in project.get("dependencies", []) if isinstance(item, str))
        for group, items in project.get("optional-dependencies", {}).items():
            requirements.extend((item, f"optional:{group}") for item in items if isinstance(item, str))
        for group, items in pyproject_data.get("dependency-groups", {}).items():
            requirements.extend((item, f"group:{group}") for item in items if isinstance(item, str))
        for name, constraint in pyproject_data.get("tool", {}).get("bench", {}).get("dev-dependencies", {}).items():
            requirements.append((f"{name}{constraint}", "bench:dev"))

        seen = set()
        for requirement, group in requirements:
            match = re.match(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(.*)$", requirement)
            if not match:
                continue
            name, constraint = match.group(1), match.group(2).strip()
            identity = f"python:{name.lower()}"
            if identity in seen:
                continue
            seen.add(identity)
            definition = {"ecosystem": "python", "name": name, "constraint": constraint, "group": group}
            marker = text.find(f'"{requirement}"')
            line_number = text[:marker].count("\n") + 1 if marker >= 0 else 0
            components.append(_component("Dependency", identity, name, "pyproject.toml", definition, line_number))
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
    www = root / app_name / "www"
    if not www.exists():
        return []
    routes: dict[str, list[dict]] = {}
    for path in www.glob("**/*"):
        if path.suffix not in {".py", ".html", ".md"} or path.name.startswith("_"):
            continue
        route = "/" + str(path.relative_to(www).with_suffix(""))
        routes.setdefault(route, []).append({"path": _relative(root, path), "kind": path.suffix.lstrip(".")})
    return [
        _component(
            "Portal Route",
            route,
            route,
            sorted(files, key=lambda item: item["path"])[0]["path"],
            {"route": route, "files": sorted(files, key=lambda item: item["path"])},
        )
        for route, files in sorted(routes.items())
    ]


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
