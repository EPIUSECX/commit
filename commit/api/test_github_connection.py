import base64
from unittest import TestCase
from unittest.mock import MagicMock, patch

from commit.api import github_connection
from commit.intelligence import github


class TestGithubConnection(TestCase):
	@patch("commit.api.github_connection.frappe.utils.get_url", return_value="http://netcash.localhost")
	def test_local_manifest_uses_inactive_placeholder_webhook(self, _get_url):
		manifest = github_connection.build_manifest("abcdef123456")

		self.assertEqual(manifest["hook_attributes"]["url"], github_connection.PLACEHOLDER_WEBHOOK_URL)
		self.assertFalse(manifest["hook_attributes"]["active"])
		self.assertEqual(manifest["default_permissions"]["checks"], "write")
		self.assertEqual(manifest["default_permissions"]["contents"], "write")
		self.assertIn("oauth_callback", manifest["callback_urls"][0])
		self.assertTrue(manifest["public"])

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

	def test_manifest_config_requires_private_key(self):
		with self.assertRaises(Exception):
			github_connection._validate_manifest_config(
				{"id": 1, "client_id": "client", "client_secret": "secret", "slug": "commit-test"}
			)

	def test_connected_installations_keeps_previous_and_current_accounts(self):
		settings = MagicMock(
			installations='[{"id":"111","account":"acme"}]',
			installation_id="222",
			installation_account="octocat",
			installation_account_type="User",
			installation_repository_selection="selected",
		)

		installations = github_connection._connected_installations(settings)

		self.assertEqual([item["id"] for item in installations], ["111", "222"])

	def test_connected_installations_are_serialized_for_frappe_json_field(self):
		settings = MagicMock()
		github_connection._store_connected_installations(
			settings, [{"id": "111", "account": "acme"}]
		)

		self.assertEqual(
			settings.installations, '[{"id": "111", "account": "acme"}]'
		)

	@patch("commit.api.github_connection.now_datetime", return_value="now")
	def test_primary_installation_uses_latest_connected_account(self, _now_datetime):
		settings = MagicMock()
		github_connection._set_primary_installation(
			settings,
			[
				{"id": "111", "account": "acme"},
				{
					"id": "222",
					"account": "octocat",
					"account_type": "User",
					"repository_selection": "selected",
				},
			],
		)

		self.assertEqual(settings.installation_id, "222")
		self.assertEqual(settings.installation_account, "octocat")
		self.assertEqual(settings.connected_on, "now")

	@patch("commit.intelligence.github.requests.post")
	@patch("commit.intelligence.github.app_jwt", return_value="app-jwt")
	@patch("commit.intelligence.github.frappe.get_single")
	def test_missing_manual_token_falls_back_to_github_app(
		self, get_single, _app_jwt, post
	):
		settings = MagicMock(github_app_id="123", installation_id="456")
		settings.get_password.side_effect = lambda field, **_kwargs: {
			"installation_token": None,
			"private_key": "private-key",
		}[field]
		get_single.return_value = settings
		post.return_value.json.return_value = {"token": "short-lived-token"}

		self.assertEqual(github.installation_token(), "short-lived-token")
		settings.get_password.assert_any_call(
			"installation_token", raise_exception=False
		)
		post.assert_called_once()

	@patch("commit.api.github_connection.github_request")
	def test_app_name_is_read_from_pyproject(self, github_request):
		github_request.return_value = {
			"content": base64.b64encode(b'[project]\nname = "netcash_connector"\n').decode()
		}
		repo = {"name": "netcash", "owner": {"login": "acme"}}

		self.assertEqual(github_connection._discover_app_name(repo), "netcash_connector")
		github_request.assert_called_once_with(
			"GET",
			"/repos/acme/netcash/contents/pyproject.toml",
			installation_id=None,
		)
