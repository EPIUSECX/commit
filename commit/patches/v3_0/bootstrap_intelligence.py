import frappe

from commit.intelligence.docs import create_version, index_docs_page


def execute():
    for organization_name in frappe.get_all("Commit Organization", pluck="name"):
        organization = frappe.get_doc("Commit Organization", organization_name)
        known_users = {member.user for member in organization.members}
        project_owners = set(frappe.get_all("Commit Project", filters={"org": organization.name}, pluck="owner"))
        for user in project_owners - known_users:
            organization.append("members", {"user": user, "access_level": "Owner"})
        if project_owners - known_users:
            organization.save(ignore_permissions=True)

    for name in frappe.get_all("Commit Docs Page", pluck="name"):
        page = frappe.get_doc("Commit Docs Page", name)
        index_docs_page(page)
        if page.content and not frappe.db.exists("Commit Docs Version", {"docs_page": page.name}):
            create_version(page, "Imported during Commit Intelligence migration")
