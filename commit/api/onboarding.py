from __future__ import annotations

import frappe


def _single_has_value(doctype: str, fields: tuple[str, ...]) -> bool:
	return any(bool(frappe.db.get_single_value(doctype, field)) for field in fields)


@frappe.whitelist()
def get_status():
	"""Return non-secret setup progress for the Commit onboarding checklist."""
	frappe.only_for("System Manager")

	github_settings = frappe.get_single("Github Settings")
	github_connected = bool(
		github_settings.installation_id
		and (
			github_settings.get_password("installation_token", raise_exception=False)
			or (
				github_settings.github_app_id
				and github_settings.get_password("private_key", raise_exception=False)
			)
		)
	)
	status = {
		"github": github_connected,
		"github_connected": github_connected,
		"github_app_created": bool(github_settings.github_app_id),
		"github_account": github_settings.installation_account,
		"github_account_type": github_settings.installation_account_type,
		"github_repository_selection": github_settings.installation_repository_selection,
		"github_webhooks_enabled": bool(github_settings.webhook_enabled),
		"commit_settings": True,
		"openai": _single_has_value("Open AI Settings", ("api_key",)),
		"organizations": frappe.db.count("Commit Organization"),
		"projects": frappe.db.count("Commit Project"),
		"branches": frappe.db.count("Commit Project Branch"),
		"policies": frappe.db.count("Commit Policy"),
		"notifications": frappe.db.count("Commit Notification Endpoint"),
		"environments": frappe.db.count("Commit API Environment"),
	}
	status["core_complete"] = bool(
		status["github"]
		and status["organizations"]
		and status["projects"]
		and status["branches"]
	)
	return status
