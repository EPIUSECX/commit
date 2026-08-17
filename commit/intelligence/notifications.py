import hashlib
import hmac
import json

import frappe
import requests

from commit.security import validate_public_https_url


def notify(project, event, payload):
    endpoints = frappe.get_all("Commit Notification Endpoint", filters={"project": project, "enabled": 1}, pluck="name")
    for name in endpoints:
        try:
            endpoint = frappe.get_doc("Commit Notification Endpoint", name)
            configured = {item.strip() for item in (endpoint.events or "").split(",") if item.strip()}
            if configured and event not in configured:
                continue
            if endpoint.channel == "Email" and endpoint.email_recipients:
                frappe.sendmail(recipients=[item.strip() for item in endpoint.email_recipients.split(",")], subject=f"Commit: {event}", message=f"<pre>{frappe.as_json(payload, indent=2)}</pre>")
            elif endpoint.webhook_url:
                validate_public_https_url(endpoint.webhook_url)
                body = json.dumps({"event": event, "payload": payload}, default=str).encode()
                headers = {"Content-Type": "application/json"}
                secret = endpoint.get_password("secret")
                if secret:
                    headers["X-Commit-Signature-256"] = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
                requests.post(endpoint.webhook_url, data=body, headers=headers, timeout=(5, 15), allow_redirects=False).raise_for_status()
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Commit notification delivery failed: {name}")
