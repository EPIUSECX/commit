# Copyright (c) 2023, The Commit Company and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from commit.commit.doctype.commit_project_branch import (
    commit_project_branch as branch_module,
)


class TestCommitProjectBranch(FrappeTestCase):
    pass


class TestBranchScanQueue(TestCase):
    @patch.object(branch_module, "get_permitted_doc")
    @patch.object(branch_module.frappe, "enqueue")
    def test_manual_scan_uses_deduplication_job_id(self, enqueue, get_permitted_doc):
        branch = MagicMock(name="branch")
        branch.name = "Example-main"
        get_permitted_doc.return_value = branch

        with patch.object(branch_module.frappe, "session", SimpleNamespace(user="Administrator")):
            result = branch_module.fetch_repo({}, "Example-main")

        self.assertTrue(result["queued"])
        enqueue.assert_called_once()
        kwargs = enqueue.call_args.kwargs
        self.assertTrue(kwargs["deduplicate"])
        self.assertEqual(kwargs["job_id"], "commit-branch-fetch-Example-main")

    @patch.object(branch_module.frappe, "publish_realtime")
    @patch.object(branch_module.frappe, "get_cached_doc")
    def test_force_scan_runs_analysis_without_new_commit(self, get_cached_doc, _publish):
        branch = MagicMock(name="branch")
        branch.name = "Example-main"
        branch.project = "Example"
        branch.branch_name = "main"
        branch.path_to_folder = "/tmp/example-main"
        branch.fetch_repo.return_value = False
        get_cached_doc.return_value = branch
        path = MagicMock()
        path.__truediv__.return_value = path
        path.is_dir.return_value = True

        with (
            patch.object(branch_module, "Path", return_value=path),
            patch.object(branch_module.frappe, "session", SimpleNamespace(user="Administrator")),
        ):
            branch_module.background_fetch_process("Example-main", force_fetch=True)

        branch.get_modules.assert_called_once_with()
        branch.find_all_apis.assert_called_once_with()
