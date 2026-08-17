
app_name = "commit"
app_title = "commit"
app_publisher = "The Commit Company"
app_description = "The Commit Company"
app_email = "support@thecommit.company"
app_license = "AGPL-3.0-or-later"
app_logo_url = "/assets/commit/images/commit-logo.svg"
app_home = "/app/commit"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": "Commit",
		"route": app_home,
		"has_permission": "commit.permissions.has_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/commit/css/commit.css"
# app_include_js = "/assets/commit/js/commit.js"

# include js, css files in header of web template
# web_include_css = "/assets/commit/css/commit.css"
# web_include_js = "/assets/commit/js/commit.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "commit/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "commit.utils.jinja_methods",
# 	"filters": "commit.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "commit.install.before_install"
# after_install = "commit.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "commit.uninstall.before_uninstall"
# after_uninstall = "commit.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "commit.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Commit Project": "commit.intelligence.permissions.project_query",
	"Commit Project Branch": "commit.intelligence.permissions.branch_query",
	"Commit Scan Snapshot": "commit.intelligence.permissions.snapshot_query",
	"Commit Discovered Component": "commit.intelligence.permissions.component_query",
	"Commit Discovered API": "commit.intelligence.permissions.discovered_api_query",
	"Commit Snapshot Change": "commit.intelligence.permissions.change_query",
	"Commit Finding": "commit.intelligence.permissions.finding_query",
	"Commit API Collection": "commit.intelligence.permissions.api_collection_query",
	"Commit API Environment": "commit.intelligence.permissions.api_environment_query",
	"Commit Notification Endpoint": "commit.intelligence.permissions.notification_query",
	"Commit Policy": "commit.intelligence.permissions.policy_query",
	"Commit Audit Event": "commit.intelligence.permissions.audit_query",
	"Commit API Test Run": "commit.intelligence.permissions.test_run_query",
	"Commit Search Entry": "commit.intelligence.permissions.search_entry_query",
}

has_permission = {
	"Commit Project": "commit.intelligence.permissions.has_project_permission",
	"Commit Project Branch": "commit.intelligence.permissions.has_branch_permission",
	"Commit Scan Snapshot": "commit.intelligence.permissions.has_snapshot_permission",
	"Commit Discovered Component": "commit.intelligence.permissions.has_snapshot_child_permission",
	"Commit Discovered API": "commit.intelligence.permissions.has_snapshot_child_permission",
	"Commit Snapshot Change": "commit.intelligence.permissions.has_snapshot_child_permission",
	"Commit Finding": "commit.intelligence.permissions.has_finding_permission",
	"Commit API Collection": "commit.intelligence.permissions.has_project_link_permission",
	"Commit API Environment": "commit.intelligence.permissions.has_project_link_permission",
	"Commit Notification Endpoint": "commit.intelligence.permissions.has_project_link_permission",
	"Commit Policy": "commit.intelligence.permissions.has_project_link_permission",
	"Commit Search Entry": "commit.intelligence.permissions.has_search_entry_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"commit.tasks.all"
# 	],
	"daily": [
		"commit.tasks.refresh_scheduled_branches",
		"commit.tasks.run_daily_api_tests",
		"commit.tasks.maintain_intelligence_data"
	],
	"hourly": [
		"commit.tasks.run_hourly_api_tests"
	],
	"weekly": [
		"commit.tasks.run_weekly_api_tests"
	],
# 	"monthly": [
# 		"commit.tasks.monthly"
# 	],
}

# Testing
# -------

# before_tests = "commit.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "commit.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "commit.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["commit.utils.before_request"]
# after_request = ["commit.utils.after_request"]

# Job Events
# ----------
# before_job = ["commit.utils.before_job"]
# after_job = ["commit.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"commit.auth.validate"
# ]
fixtures = [{"doctype": "Server Script", "filters": [["module", "in", ("commit")]]}]

website_route_rules = [
    {"from_route": "/commit-docs/<path:app_path>", "to_route": "commit-docs"},
    {"from_route": "/commit/<path:app_path>", "to_route": "commit"},
]
