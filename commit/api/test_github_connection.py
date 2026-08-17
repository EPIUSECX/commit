import base64
from unittest import TestCase
from unittest.mock import patch

from commit.api import github_connection


class TestGithubConnection(TestCase):
	@patch("commit.api.github_connection.frappe.utils.get_url", return_value="http://netcash.localhost")
	def test_local_manifest_uses_inactive_placeholder_webhook(self, _get_url):
		manifest = github_connection.build_manifest("abcdef123456")

		self.assertEqual(manifest["hook_attributes"]["url"], github_connection.PLACEHOLDER_WEBHOOK_URL)
		self.assertFalse(manifest["hook_attributes"]["active"])
		self.assertEqual(manifest["default_permissions"]["checks"], "write")
		self.assertEqual(manifest["default_permissions"]["contents"], "write")
		self.assertIn("oauth_callback", manifest["callback_urls"][0])

	@patch("commit.api.github_connection.frappe.utils.get_url", return_value="https://commit.example.com")
	def test_public_manifest_enables_real_webhook(self, _get_url):
		manifest = github_connection.build_manifest("abcdef123456")

		self.assertTrue(manifest["hook_attributes"]["active"])
		self.assertEqual(
			manifest["hook_attributes"]["url"],
			"https://commit.example.com/api/method/commit.api.github_webhook.github_webhook",
		)

	def test_public_url_detection_rejects_local_and_private_hosts(self):
		self.assertFalse(github_connection.is_public_https_url("http://commit.example.com/hook"))
		self.assertFalse(github_connection.is_public_https_url("https://site.localhost/hook"))
		self.assertFalse(github_connection.is_public_https_url("https://10.0.0.2/hook"))
		self.assertTrue(github_connection.is_public_https_url("https://commit.example.com/hook"))

	def test_manifest_can_be_created_for_personal_or_organization_owner(self):
		self.assertEqual(github_connection.manifest_create_url(), github_connection.MANIFEST_URL)
		self.assertEqual(
			github_connection.manifest_create_url("EPIUSECX"),
			"https://github.com/organizations/EPIUSECX/settings/apps/new",
		)

	@patch("commit.api.github_connection.github_request")
	def test_app_name_is_read_from_pyproject(self, github_request):
		github_request.return_value = {
			"content": base64.b64encode(b'[project]\nname = "netcash_connector"\n').decode()
		}
		repo = {"name": "netcash", "owner": {"login": "acme"}}

		self.assertEqual(github_connection._discover_app_name(repo), "netcash_connector")
		github_request.assert_called_once_with("GET", "/repos/acme/netcash/contents/pyproject.toml")
