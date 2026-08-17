from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse

import frappe
import requests

from commit.intelligence.audit import record_event
from commit.intelligence.permissions import require_project_access
from commit.security import validate_public_https_url

VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


def _variables(environment):
    values = {}
    for row in environment.variables:
        values[row.key] = row.get_password("value") if row.value else ""
    return values


def _render(value, variables):
    if isinstance(value, str):
        return VARIABLE_PATTERN.sub(lambda match: str(variables.get(match.group(1), match.group(0))), value)
    if isinstance(value, dict):
        return {key: _render(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [_render(item, variables) for item in value]
    return value


def _json_path(data, path):
    value = data
    for part in (path or "").strip("$.").split("."):
        if not part:
            continue
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = value[part]
    return value


def _assertions(assertions, response, duration_ms):
    results = []
    try:
        response_json = response.json()
    except ValueError:
        response_json = None
    for assertion in assertions or []:
        kind = assertion.get("type")
        expected = assertion.get("expected")
        actual = None
        passed = False
        try:
            if kind == "status":
                actual, passed = response.status_code, response.status_code == int(expected)
            elif kind == "contains":
                actual, passed = expected in response.text, expected in response.text
            elif kind == "json_path":
                actual = _json_path(response_json, assertion.get("path"))
                passed = actual == expected
            elif kind == "latency":
                actual, passed = duration_ms, duration_ms <= int(assertion.get("max_ms") or expected)
        except (KeyError, IndexError, TypeError, ValueError):
            passed = False
        results.append({"type": kind, "passed": passed, "expected": expected, "actual": actual})
    return results


def execute_collection(collection_name, triggered_by=None):
    collection = frappe.get_doc("Commit API Collection", collection_name)
    require_project_access(collection.project, "Editor")
    if not collection.environment:
        frappe.throw("Choose an API environment before running this collection")
    environment = frappe.get_doc("Commit API Environment", collection.environment)
    if not environment.enabled:
        frappe.throw("The API environment is disabled")
    validate_public_https_url(environment.base_url)
    variables = _variables(environment)
    headers = {"Accept": "application/json"}
    if environment.auth_type == "Token":
        headers["Authorization"] = f"token {environment.get_password('api_key')}:{environment.get_password('api_secret')}"
    elif environment.auth_type == "Bearer":
        headers["Authorization"] = f"Bearer {environment.get_password('api_key')}"
    run = frappe.get_doc({"doctype": "Commit API Test Run", "collection": collection.name, "environment": environment.name, "status": "Running", "started_on": frappe.utils.now_datetime(), "triggered_by": triggered_by or frappe.session.user}).insert(ignore_permissions=True)
    started = time.monotonic()
    results = []
    try:
        for request in collection.requests:
            if not request.enabled:
                continue
            request_headers = {**headers, **_render(frappe.parse_json(request.headers) if request.headers else {}, variables)}
            parameters = _render(frappe.parse_json(request.parameters) if request.parameters else {}, variables)
            body = _render(frappe.parse_json(request.body) if request.body else None, variables)
            path = _render(request.path, variables).lstrip("/")
            url = urljoin(environment.base_url.rstrip("/") + "/", path)
            if urlparse(url).netloc != urlparse(environment.base_url).netloc:
                frappe.throw("Collection request cannot leave the configured environment host")
            request_started = time.monotonic()
            response = requests.request(request.method, url, headers=request_headers, params=parameters, json=body, timeout=(5, 30), allow_redirects=False)
            duration = round((time.monotonic() - request_started) * 1000)
            assertions = _assertions(frappe.parse_json(request.assertions) if request.assertions else [{"type": "status", "expected": 200}], response, duration)
            passed = all(item["passed"] for item in assertions)
            results.append({"request": request.request_name, "method": request.method, "url": url, "status_code": response.status_code, "duration_ms": duration, "passed": passed, "assertions": assertions, "response_preview": response.text[:2000]})
        run.passed = sum(item["passed"] for item in results)
        run.failed = len(results) - run.passed
        run.status = "Passed" if run.failed == 0 else "Failed"
        run.results = results
    except Exception:
        run.status = "Error"
        run.results = {"error": frappe.get_traceback()[-5000:], "completed_requests": results}
    run.completed_on = frappe.utils.now_datetime()
    run.duration_ms = round((time.monotonic() - started) * 1000)
    run.save(ignore_permissions=True)
    record_event("api-tests.completed", project=collection.project, details={"collection": collection.name, "run": run.name, "status": run.status})
    return run


def run_scheduled(frequency):
    for name in frappe.get_all("Commit API Collection", filters={"schedule": frequency}, pluck="name"):
        frappe.enqueue("commit.intelligence.api_testing.execute_collection", queue="long", collection_name=name, triggered_by="Administrator", deduplicate=True, job_name=f"Commit API tests {name}")
