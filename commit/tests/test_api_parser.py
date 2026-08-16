from unittest import TestCase

from commit.commit.code_analysis.apis import find_indexes_of_whitelist


class TestAPIParser(TestCase):
    def test_ast_ignores_comments_and_strings(self):
        source = '''
"""@frappe.whitelist()"""
# @frappe.whitelist()
@frappe.whitelist(methods=["POST"])
def real_endpoint(value: str = "x"):
    return value
'''
        indexes, lines, ignored, names, _ = find_indexes_of_whitelist(
            source, source.count("@frappe.whitelist")
        )

        self.assertEqual(len(indexes), 1)
        self.assertEqual(names, ["real_endpoint"])
        self.assertEqual(lines, [4])
        self.assertEqual(ignored, 2)

    def test_ast_supports_multiline_signature(self):
        source = '''
@frappe.whitelist()
def endpoint(
    first: str,
    second: int = 1,
):
    return first, second
'''
        result = find_indexes_of_whitelist(source, 1)
        self.assertEqual(result[3], ["endpoint"])
