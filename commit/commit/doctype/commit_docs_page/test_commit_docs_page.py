# Copyright (c) 2024, The Commit Company and Contributors
# See license.txt

# import frappe
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record depdendencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class TestCommitDocsPageUnit(UnitTestCase):
    """
    Unit tests for CommitDocsPage.
    Use this class for testing individual functions and methods.
    """

    @patch("commit.commit.doctype.commit_docs_page.commit_docs_page.frappe.get_cached_doc")
    def test_guest_cannot_read_unpublished_page(self, get_cached_doc):
        from commit.commit.doctype.commit_docs_page.commit_docs_page import (
            get_commit_docs_page,
        )

        get_cached_doc.return_value = SimpleNamespace(
            published=0,
            allow_guest=1,
            commit_docs="public-docs",
        )
        previous_user = frappe.session.user
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                get_commit_docs_page("secret-page")
        finally:
            frappe.set_user(previous_user)

    @patch("commit.commit.doctype.commit_docs_page.commit_docs_page.frappe.get_cached_doc")
    def test_guest_cannot_read_page_without_guest_access(self, get_cached_doc):
        from commit.commit.doctype.commit_docs_page.commit_docs_page import (
            get_commit_docs_page,
        )

        get_cached_doc.return_value = SimpleNamespace(
            published=1,
            allow_guest=0,
            commit_docs="public-docs",
        )
        previous_user = frappe.session.user
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                get_commit_docs_page("members-only-page")
        finally:
            frappe.set_user(previous_user)


class TestCommitDocsPageIntegration(IntegrationTestCase):
    """
    Integration tests for CommitDocsPage.
    Use this class for testing interactions between multiple components.
    """

    pass
