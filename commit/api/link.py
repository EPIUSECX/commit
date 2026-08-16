import frappe


@frappe.whitelist()
def get_link_title(doctype, docname):
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("read")
	meta = doc.meta
	if meta.title_field:
		return doc.get(meta.title_field)
	return docname
