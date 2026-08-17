from __future__ import annotations

import re

DEFAULT_POLICIES = (
    ("guest-mutation", "Critical", "Guest endpoint permits mutation"),
    ("guest-no-rate-limit", "High", "Guest endpoint has no visible rate limit"),
    ("unsafe-get-mutation", "High", "Potentially mutating endpoint permits GET"),
    ("ignore-permissions", "Critical", "Source bypasses document permissions"),
    ("manual-commit", "Medium", "Endpoint performs a manual database commit"),
    ("filesystem-network", "Medium", "Endpoint performs filesystem or outbound network access"),
    ("undocumented-api", "Low", "API has no generated or curated documentation"),
)

MUTATION_WORDS = re.compile(r"(?:create|update|delete|save|insert|remove|publish|sync|fetch|set_)", re.I)


def evaluate_component(component: dict) -> list[dict]:
    definition = component.get("definition") or {}
    if component.get("component_type") == "DocType":
        findings = []
        for permission in definition.get("permissions", []):
            if permission.get("role") != "Guest":
                continue
            mutation = any(permission.get(action) for action in ("create", "write", "delete", "submit", "cancel"))
            findings.append({
                "rule": "guest-doctype-mutation" if mutation else "guest-doctype-read",
                "severity": "Critical" if mutation else "High",
                "title": "Guest role can mutate this DocType" if mutation else "Guest role can read this DocType",
                "evidence": str(permission),
                "identity": component["identity"],
            })
        return findings
    if component.get("component_type") == "Dependency":
        constraint = str(definition.get("constraint") or "")
        if constraint in {"", "*", "latest"}:
            return [{"rule": "unpinned-dependency", "severity": "Low", "title": "Dependency is not version constrained", "evidence": constraint or "No constraint", "identity": component["identity"]}]
        return []
    if component.get("component_type") != "API":
        return []
    source = definition.get("source") or definition.get("code") or ""
    methods = {str(method).upper() for method in definition.get("request_types") or []}
    guest_methods = {str(method).upper() for method in definition.get("guest_methods") or methods}
    guest = bool(definition.get("allow_guest"))
    decorators = " ".join(definition.get("other_decorators") or [])
    findings = []

    def add(rule, severity, title, evidence=""):
        findings.append({"rule": rule, "severity": severity, "title": title, "evidence": evidence, "identity": component["identity"]})

    if guest and guest_methods.intersection({"POST", "PUT", "PATCH", "DELETE"}):
        add(*DEFAULT_POLICIES[0], ", ".join(sorted(guest_methods)))
    if guest and "rate_limit" not in decorators:
        add(*DEFAULT_POLICIES[1])
    if (not methods or "GET" in methods) and MUTATION_WORDS.search(component.get("display_name", "")):
        add(*DEFAULT_POLICIES[2], component.get("display_name", ""))
    if "ignore_permissions=True" in source or "ignore_permissions = True" in source:
        add(*DEFAULT_POLICIES[3], "ignore_permissions=True")
    if "frappe.db.commit" in source:
        add(*DEFAULT_POLICIES[4], "frappe.db.commit")
    if any(token in source for token in ("requests.", "httpx.", "open(", "os.remove", "shutil.")):
        add(*DEFAULT_POLICIES[5])
    if not definition.get("documentation"):
        add(*DEFAULT_POLICIES[6])
    return findings


def evaluate_components(components: list[dict]) -> list[dict]:
    return [finding for component in components for finding in evaluate_component(component)]


def _path(value, path):
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def evaluate_custom_policies(project: str, components: list[dict]) -> list[dict]:
    import frappe

    policies = frappe.get_all("Commit Policy", filters={"enabled": 1}, or_filters=[["project", "=", project], ["project", "is", "not set"]], fields=["name", "rule_name", "component_type", "severity", "condition", "message", "remediation", "blocking"])
    findings = []
    for policy in policies:
        condition = frappe.parse_json(policy.condition)
        for component in components:
            if component["component_type"] != policy.component_type:
                continue
            actual = _path(component.get("definition") or {}, condition.get("path", ""))
            expected = condition.get("value")
            operator = condition.get("operator", "equals")
            matched = actual == expected if operator == "equals" else expected in actual if operator == "contains" and actual is not None else actual is not None if operator == "exists" else False
            if matched:
                findings.append({"rule": policy.rule_name, "severity": policy.severity, "title": policy.message, "evidence": f"{condition.get('path')}={actual}", "identity": component["identity"], "remediation": policy.remediation, "blocking": policy.blocking})
    return findings
