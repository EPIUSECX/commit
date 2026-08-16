from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import frappe

from commit.security import resolve_path_within


class TestPathContainment(TestCase):
    def test_accepts_file_inside_repository(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app" / "api.py"
            source.parent.mkdir()
            source.write_text("pass\n", encoding="utf-8")

            self.assertEqual(resolve_path_within(str(root), str(source)), source)

    def test_rejects_file_outside_repository(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as outside:
            source = Path(outside) / "secret.py"
            source.write_text("secret\n", encoding="utf-8")

            with self.assertRaises(frappe.PermissionError):
                resolve_path_within(directory, str(source))
