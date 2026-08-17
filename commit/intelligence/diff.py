from __future__ import annotations

from typing import Any

SEVERITY_SCORE = {"Info": 0, "Low": 2, "Medium": 5, "High": 8, "Critical": 10}


def _arguments(definition: dict) -> dict:
    return {item.get("argument"): item for item in definition.get("arguments", []) if item.get("argument")}


def _fields(definition: dict) -> dict:
    return {item.get("fieldname"): item for item in definition.get("fields", []) if item.get("fieldname")}


def classify_change(kind: str, change_type: str, before: dict | None, after: dict | None) -> dict:
    breaking = change_type == "Removed" and kind in {"API", "DocType"}
    severity = "High" if breaking else "Info"
    reasons = []
    before = before or {}
    after = after or {}
    if kind == "API" and change_type == "Modified":
        old_args, new_args = _arguments(before), _arguments(after)
        required_added = [name for name, arg in new_args.items() if name not in old_args and not arg.get("default")]
        methods_removed = sorted(set(before.get("request_types") or []) - set(after.get("request_types") or []))
        if required_added:
            breaking, severity = True, "High"
            reasons.append(f"Required arguments added: {', '.join(required_added)}")
        if methods_removed:
            breaking, severity = True, "High"
            reasons.append(f"Request methods removed: {', '.join(methods_removed)}")
        if not before.get("allow_guest") and after.get("allow_guest"):
            severity = "Critical"
            reasons.append("Endpoint became guest-accessible")
    if kind == "DocType" and change_type == "Modified":
        old_fields, new_fields = _fields(before), _fields(after)
        removed = sorted(set(old_fields) - set(new_fields))
        required_added = sorted(name for name, field in new_fields.items() if name not in old_fields and field.get("reqd"))
        changed_types = sorted(name for name in set(old_fields) & set(new_fields) if old_fields[name].get("fieldtype") != new_fields[name].get("fieldtype"))
        if removed or required_added or changed_types:
            breaking, severity = True, "High"
            if removed:
                reasons.append(f"Fields removed: {', '.join(removed)}")
            if required_added:
                reasons.append(f"Required fields added: {', '.join(required_added)}")
            if changed_types:
                reasons.append(f"Field types changed: {', '.join(changed_types)}")
        if before.get("permissions") != after.get("permissions"):
            severity = "High"
            reasons.append("Permissions changed")
    return {"breaking": breaking, "severity": severity, "summary": "; ".join(reasons) or f"{kind} {change_type.lower()}"}


def compare_components(before_items: list[dict], after_items: list[dict]) -> list[dict[str, Any]]:
    before = {(item["component_type"], item["identity"]): item for item in before_items}
    after = {(item["component_type"], item["identity"]): item for item in after_items}
    changes = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if not old:
            change_type = "Added"
        elif not new:
            change_type = "Removed"
        elif old.get("fingerprint") == new.get("fingerprint"):
            continue
        else:
            change_type = "Modified"
        classification = classify_change(key[0], change_type, old and old.get("definition"), new and new.get("definition"))
        changes.append({
            "component_type": key[0], "identity": key[1], "change_type": change_type,
            "before": old and old.get("definition"), "after": new and new.get("definition"), **classification,
        })
    return changes


def risk_score(changes: list[dict], findings: list[dict] | None = None) -> int:
    score = sum(SEVERITY_SCORE.get(item.get("severity"), 0) for item in changes)
    score += sum(SEVERITY_SCORE.get(item.get("severity"), 0) for item in findings or [])
    return min(100, score)
