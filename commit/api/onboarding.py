from __future__ import annotations

import frappe


def _single_has_value(doctype: str, fields: tuple[str, ...]) -> bool:
	return any(bool(frappe.db.get_single_value(doctype, field)) for field in fields)


@frappe.whitelist()
def get_status():
	"""Return non-secret setup progress for the Commit onboarding checklist."""
	frappe.only_for("System Manager")

	github_oauth = _single_has_value("Github Settings", ("client_id",))
	github_app = _single_has_value(
		"Github Settings", ("github_app_id", "installation_id", "installation_token")
	)
	status = {
		"github": github_oauth or github_app,
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
