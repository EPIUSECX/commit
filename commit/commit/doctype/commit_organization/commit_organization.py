# Copyright (c) 2023, The Commit Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CommitOrganization(Document):
    def on_update(self):
        for member in self.members:
            if "Commit Project Member" not in frappe.get_roles(member.user):
                frappe.get_doc("User", member.user).add_roles("Commit Project Member")

    def on_trash(self):
        # find all project which are linked with this organisation
        # delete all projects
        projects = frappe.get_all(
            "Commit Project", filters={"org": self.name}, pluck="name"
        )
        for project in projects:
            frappe.db.delete("Commit Project", project)
