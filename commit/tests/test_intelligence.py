from unittest import TestCase

from commit.intelligence.diff import classify_change, compare_components, risk_score
from commit.intelligence.policy import evaluate_component


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
