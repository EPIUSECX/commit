import frappe
from frappe.model.document import Document


class CommitFinding(Document):
    def validate(self):
        if self.status == "Suppressed" and not self.suppression_reason:
            frappe.throw("A suppression reason is required")
