import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from commit.intelligence.diff import classify_change, compare_components, risk_score
from commit.intelligence.policy import evaluate_component
from commit.intelligence.scanner import (
    scan_apis,
    scan_dependencies,
    scan_doctypes,
    scan_portal_routes,
)
from commit.intelligence.service import _json, _json_string


class TestIntelligenceDiff(TestCase):
    def test_required_api_argument_is_breaking(self):
        result = classify_change(
            "API",
            "Modified",
            {"arguments": [{"argument": "name", "default": "Guest"}]},
            {"arguments": [{"argument": "name", "default": "Guest"}, {"argument": "company"}]},
        )
        self.assertTrue(result["breaking"])
        self.assertEqual(result["severity"], "High")

    def test_removed_doctype_field_is_breaking(self):
        result = classify_change(
            "DocType",
            "Modified",
            {"fields": [{"fieldname": "customer", "fieldtype": "Link"}]},
            {"fields": []},
        )
        self.assertTrue(result["breaking"])
        self.assertIn("customer", result["summary"])

    def test_stable_fingerprint_is_ignored(self):
        before = [{"component_type": "API", "identity": "app.ping", "fingerprint": "same", "definition": {}}]
        self.assertEqual(compare_components(before, list(before)), [])

    def test_risk_score_is_bounded(self):
        changes = [{"severity": "Critical"}] * 20
        self.assertEqual(risk_score(changes), 100)


class TestDefaultPolicies(TestCase):
    def test_guest_mutation_is_critical(self):
        findings = evaluate_component(
            {
                "component_type": "API",
                "identity": "app.delete_everything",
                "display_name": "delete_everything",
                "definition": {"allow_guest": True, "request_types": ["POST"]},
            }
        )
        self.assertIn("guest-mutation", {item["rule"] for item in findings})

    def test_guest_doctype_permission_is_detected(self):
        findings = evaluate_component(
            {
                "component_type": "DocType",
                "identity": "Secret",
                "definition": {"permissions": [{"role": "Guest", "read": 1}]},
            }
        )
        self.assertEqual(findings[0]["rule"], "guest-doctype-read")


class TestIntelligenceScanner(TestCase):
    def test_doctype_scan_skips_json_arrays(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            fixture = root / "sample_app" / "module" / "doctype" / "sample" / "fixtures.json"
            fixture.parent.mkdir(parents=True)
            fixture.write_text(json.dumps([{"name": "fixture"}]), encoding="utf-8")

            self.assertEqual(scan_doctypes(root, "sample_app"), [])

    def test_doctype_scan_ignores_malformed_field_and_permission_entries(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            doctype = root / "sample_app" / "module" / "doctype" / "sample" / "sample.json"
            doctype.parent.mkdir(parents=True)
            doctype.write_text(
                json.dumps(
                    {
                        "doctype": "DocType",
                        "name": "Sample",
                        "fields": [None, "invalid", {"fieldname": "title", "fieldtype": "Data"}],
                        "permissions": [None, {"role": "System Manager", "read": 1}],
                    }
                ),
                encoding="utf-8",
            )

            components = scan_doctypes(root, "sample_app")

            self.assertEqual(len(components), 2)
            self.assertEqual(components[0]["definition"]["fields"], [{"fieldname": "title", "fieldtype": "Data"}])

    def test_json_fields_are_serialized_and_round_trip(self):
        value = {"methods": ["GET", "POST"], "enabled": True}

        serialized = _json_string(value)

        self.assertIsInstance(serialized, str)
        self.assertEqual(_json(serialized), value)
        self.assertEqual(_json(_json_string("frappe.utils.install.after_install")), "frappe.utils.install.after_install")

    def test_dependency_scan_reads_only_dependency_tables(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "pyproject.toml").write_text(
                """[project]
dependencies = ["requests~=2.32", "bleach[css]>=6"]
[project.optional-dependencies]
dev = ["pytest"]
[tool.example]
skip_namespaces = ["frappe.utils", "not-a-dependency"]
""",
                encoding="utf-8",
            )

            dependencies = scan_dependencies(root)

            self.assertEqual(
                {item["identity"] for item in dependencies},
                {"python:requests", "python:bleach", "python:pytest"},
            )

    def test_portal_route_combines_python_and_html_files(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            www = root / "sample_app" / "www"
            www.mkdir(parents=True)
            (www / "login.py").write_text("", encoding="utf-8")
            (www / "login.html").write_text("", encoding="utf-8")

            components = scan_portal_routes(root, "sample_app")

            self.assertEqual(len(components), 1)
            self.assertEqual(components[0]["identity"], "/login")
            self.assertEqual(len(components[0]["definition"]["files"]), 2)

    @mock.patch("commit.intelligence.scanner.find_all_occurrences_of_whitelist")
    def test_duplicate_api_paths_receive_stable_line_identities(self, find_apis):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "sample_app" / "api.py"
            source.parent.mkdir(parents=True)
            source.write_text("def ping():\n    pass\n\ndef ping():\n    pass\n", encoding="utf-8")
            find_apis.return_value = [
                {"api_path": "sample_app.api.ping", "name": "ping", "file": str(source), "block_start": 1, "block_end": 2},
                {"api_path": "sample_app.api.ping", "name": "ping", "file": str(source), "block_start": 4, "block_end": 5},
            ]

            _, components = scan_apis(root, "sample_app")

            self.assertEqual(
                {item["identity"] for item in components},
                {"sample_app.api.ping#L1", "sample_app.api.ping#L4"},
            )
