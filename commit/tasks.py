import frappe
from frappe.utils import date_diff, getdate, nowdate


def refresh_scheduled_branches():
    """Queue due branch refreshes once daily without overlapping active scans."""
    intervals = {"Daily": 1, "Weekly": 7, "Monthly": 30}
    branches = frappe.get_all(
        "Commit Project Branch",
        filters={"frequency": ["in", list(intervals)]},
        fields=["name", "frequency", "last_fetched", "scan_status", "owner"],
    )
    for branch in branches:
        if branch.scan_status in {"Queued", "Running"}:
            continue
        elapsed = (
            date_diff(getdate(nowdate()), getdate(branch.last_fetched))
            if branch.last_fetched
            else intervals[branch.frequency]
        )
        if elapsed < intervals[branch.frequency]:
            continue
        frappe.db.set_value(
            "Commit Project Branch",
            branch.name,
            "scan_status",
            "Queued",
            update_modified=False,
        )
        frappe.enqueue(
            "commit.commit.doctype.commit_project_branch.commit_project_branch.background_fetch_process",
            queue="long",
            project_branch=branch.name,
            force_fetch=True,
            initiated_by=branch.owner,
            deduplicate=True,
            job_name=f"Scheduled Commit branch fetch {branch.name}",
        )
