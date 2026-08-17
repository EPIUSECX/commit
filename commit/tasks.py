import frappe
from frappe.utils import date_diff, getdate, nowdate

from commit.intelligence.api_testing import run_scheduled


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
            job_id=f"commit-scheduled-branch-fetch-{branch.name}",
        )


def run_hourly_api_tests():
    run_scheduled("Hourly")


def run_daily_api_tests():
    run_scheduled("Daily")


def run_weekly_api_tests():
    run_scheduled("Weekly")


def maintain_intelligence_data():
    """Expire temporary suppressions and age out low-value analytics events."""
    expired = frappe.get_all(
        "Commit Finding",
        filters={"status": "Suppressed", "suppression_expires_on": ["<", nowdate()]},
        pluck="name",
    )
    for finding in expired:
        frappe.db.set_value(
            "Commit Finding",
            finding,
            {"status": "Open", "suppression_reason": None, "suppression_expires_on": None},
        )
    cutoff = frappe.utils.add_days(nowdate(), -180)
    frappe.db.delete("Commit Analytics Event", {"creation": ["<", cutoff]})
