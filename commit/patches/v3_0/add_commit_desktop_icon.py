from __future__ import annotations

import json

import frappe

COMMIT_ICON = {
	"label": "Commit",
	"bg_color": None,
	"link": None,
	"link_type": "Workspace Sidebar",
	"app": "commit",
	"icon_type": "Link",
	"parent_icon": "",
	"icon": "git-branch",
	"link_to": "Commit",
	"idx": 0,
	"standard": 1,
	"logo_url": "/assets/commit/images/commit-logo.svg",
	"hidden": 0,
	"name": "Commit",
	"restrict_removal": 0,
	"icon_image": None,
	"child_icons": [],
}


def execute():
	"""Add Commit to existing personalized desktops without changing their layout."""
	for name in frappe.get_all("Desktop Layout", pluck="name"):
		layout = frappe.parse_json(frappe.db.get_value("Desktop Layout", name, "layout")) or []
		if not isinstance(layout, list) or any(item.get("name") == "Commit" for item in layout):
			continue
		layout.append(COMMIT_ICON.copy())
		frappe.db.set_value(
			"Desktop Layout",
			name,
			"layout",
			json.dumps(layout),
			update_modified=False,
		)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
