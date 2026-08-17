from __future__ import annotations

import frappe

APP_ROLES = {"System Manager", "Commit Project Member"}


def has_app_permission() -> bool:
	"""Return whether the current user should see Commit on the apps screen."""
	return bool(APP_ROLES.intersection(frappe.get_roles()))
