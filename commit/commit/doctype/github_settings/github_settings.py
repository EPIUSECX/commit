# Copyright (c) 2023, The Commit Company and contributors
# For license information, please see license.txt

import secrets
from urllib.parse import urlencode

import frappe
import requests
from frappe.model.document import Document


class GithubSettings(Document):
    pass


session = requests.Session()
session.headers.update({"Accept": "application/json"})


@frappe.whitelist(allow_guest=True)
def authenticate_user(code, state=None):
    """API to authenticate the user with GitHub"""
    if not state or not frappe.cache().get_value(f"commit:github_oauth:{state}"):
        frappe.throw("Invalid or expired OAuth state", frappe.AuthenticationError)
    frappe.cache().delete_value(f"commit:github_oauth:{state}")
    response = get_access_token(code)
    if response.get("access_token"):
        user_data = get_user_details(response.get("access_token"))
        if user_data:
            user = create_user(user_data)
            frappe.local.login_manager.login_as(user.name)
            return {"user": user.name}
    frappe.throw(response.get("error_description") or "GitHub authentication failed")


@frappe.whitelist()
def get_authorization_url():
    """Create a short-lived, single-use OAuth state and return GitHub's URL."""
    settings = frappe.get_single("Github Settings")
    settings.check_permission("read")
    state = secrets.token_urlsafe(32)
    frappe.cache().set_value(
        f"commit:github_oauth:{state}", frappe.session.user, expires_in_sec=600
    )
    query = urlencode(
        {
            "client_id": settings.client_id,
            "redirect_uri": settings.redirect_uri,
            "scope": settings.scopes or "read:user user:email",
            "state": state,
        }
    )
    return f"{settings.authorization_uri}?{query}"


def get_access_token(code):
    """Get the access token from GitHub"""
    """
    1. Make a POST request to GitHub to get the access token
    2. Return the access token
    """
    github_settings = frappe.get_cached_doc("Github Settings")
    client_id = github_settings.client_id
    client_secret = github_settings.get_password("client_secret")
    token_url = github_settings.token_uri
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    }
    headers = {"Accept": "application/json"}

    response = requests.post(token_url, data=data, headers=headers, timeout=(5, 20))
    response.raise_for_status()
    return response.json()


def get_user_details(access_token):
    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": "Bearer " + access_token},
        timeout=(5, 20),
    )
    user_data = {}
    if user_response.status_code == 200 and user_response.json():
        email_response = requests.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": "Bearer " + access_token},
            timeout=(5, 20),
        )
        email_response.raise_for_status()
        user_data = {
            "user_details": user_response.json(),
            "email_details": email_response.json(),
        }

    return user_data


def create_user(user_data):
    """Create a user in the system"""
    """
	1. Get the user details from GitHub
	2. Create a user in the system
	3. Return the user details
	"""

    details = user_data["user_details"]
    emails = user_data["email_details"]
    email = next(
        (item["email"] for item in emails if item.get("primary") and item.get("verified")),
        None,
    )
    if not email:
        frappe.throw("GitHub must provide a verified primary email")
    if frappe.db.exists("User", email):
        return frappe.get_doc("User", email)

    names = (details.get("name") or details.get("login") or "GitHub User").split(maxsplit=1)
    user = frappe.new_doc("User")
    user.first_name = names[0]
    user.last_name = names[1] if len(names) > 1 else ""
    user.email = email
    user.username = details.get("login")
    user.user_image = details.get("avatar_url")
    user.bio = details.get("bio")
    user.location = details.get("location")
    user.new_password = frappe.generate_hash()
    user.enabled = 1
    user.user_type = "Website User"
    user.insert(ignore_permissions=True)
    return user
