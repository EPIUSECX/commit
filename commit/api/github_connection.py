from __future__ import annotations

import base64
import ipaddress
import json
import re
import secrets
from typing import Any
from urllib.parse import urlencode, urlparse

import frappe
import requests
from frappe.utils import now_datetime

from commit.intelligence.audit import record_event
from commit.intelligence.github import GITHUB, app_jwt, github_request

API_VERSION = "2022-11-28"
MANIFEST_URL = "https://github.com/settings/apps/new"
MANIFEST_ORGANIZATION_URL = "https://github.com/organizations/{organization}/settings/apps/new"
OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
PLACEHOLDER_WEBHOOK_URL = "https://example.com/commit-webhook-placeholder"
STATE_TTL = 15 * 60


def _headers(token: str | None = None) -> dict[str, str]:
	headers = {
		"Accept": "application/vnd.github+json",
		"X-GitHub-Api-Version": API_VERSION,
	}
	if token:
		headers["Authorization"] = f"Bearer {token}"
	return headers


def _site_url(path: str = "") -> str:
	return f"{frappe.utils.get_url().rstrip('/')}/{path.lstrip('/')}"


def _redirect(location: str) -> None:
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location


def _state_key(state: str) -> str:
	return f"commit:github-connect:{state}"


def _new_state(stage: str, user: str, **values: Any) -> str:
	state = secrets.token_urlsafe(32)
	payload = {"stage": stage, "user": user, **values}
	frappe.cache().set_value(_state_key(state), payload, expires_in_sec=STATE_TTL)
	return state


def _consume_state(state: str | None, stage: str) -> dict[str, Any]:
	if not state:
		frappe.throw("The GitHub connection state is missing. Please start again.")
	key = _state_key(state)
	payload = frappe.cache().get_value(key)
	frappe.cache().delete_value(key)
	if not payload or payload.get("stage") != stage:
		frappe.throw("The GitHub connection has expired or is invalid. Please start again.")
	user = payload.get("user")
	if not user or user == "Guest" or not frappe.db.exists("User", {"name": user, "enabled": 1}):
		frappe.throw("The Commit administrator account is no longer available.", frappe.PermissionError)
	if "System Manager" not in frappe.get_roles(user):
		frappe.throw("Only a System Manager can connect GitHub.", frappe.PermissionError)
	return payload


def is_public_https_url(url: str) -> bool:
	parsed = urlparse(url)
	if parsed.scheme != "https":
		return False
	host = (parsed.hostname or "").lower()
	if not host or host == "localhost" or host.endswith((".localhost", ".local")):
		return False
	try:
		return ipaddress.ip_address(host).is_global
	except ValueError:
		return True


def build_manifest(state: str) -> dict[str, Any]:
	base_url = frappe.utils.get_url().rstrip("/")
	webhook_url = _site_url("api/method/commit.api.github_webhook.github_webhook")
	webhook_public = is_public_https_url(webhook_url)
	host = re.sub(r"[^a-z0-9-]+", "-", (urlparse(base_url).hostname or "site").lower()).strip("-")
	name = f"Commit {host[:18]} {state[:6]}"[:34]
	return {
		"name": name,
		"url": base_url,
		"description": "Repository intelligence, API documentation, checks, and policy automation from Commit.",
		"redirect_url": _site_url("api/method/commit.api.github_connection.manifest_callback"),
		"callback_urls": [_site_url("api/method/commit.api.github_connection.oauth_callback")],
		"setup_url": _site_url("api/method/commit.api.github_connection.install_callback"),
		"setup_on_update": True,
		"public": False,
		"hook_attributes": {
			"url": webhook_url if webhook_public else PLACEHOLDER_WEBHOOK_URL,
			"active": webhook_public,
		},
		"default_events": ["push", "pull_request"],
		"default_permissions": {
			"checks": "write",
			"contents": "write",
			"metadata": "read",
			"pull_requests": "write",
		},
	}


def manifest_create_url(organization: str | None = None) -> str:
	organization = (organization or "").strip()
	if not organization:
		return MANIFEST_URL
	if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", organization):
		frappe.throw("Enter a valid GitHub organization name.")
	return MANIFEST_ORGANIZATION_URL.format(organization=organization)


def _validate_manifest_config(config: dict[str, Any]) -> None:
	required = {
		"id": config.get("id"),
		"client_id": config.get("client_id"),
		"client_secret": config.get("client_secret"),
		"pem": config.get("pem"),
		"slug": config.get("slug"),
	}
	missing = [field for field, value in required.items() if not value]
	if missing:
		frappe.throw(
			"GitHub returned an incomplete App configuration. Missing: " + ", ".join(missing)
		)


def _installation_url(settings, user: str) -> str:
	state = _new_state("install", user)
	base = settings.github_app_html_url or f"https://github.com/apps/{settings.github_app_slug}"
	return f"{base.rstrip('/')}/installations/new?{urlencode({'state': state})}"


@frappe.whitelist(methods=["POST"])
def start_connection(force_new_app: bool = False, organization: str | None = None):
	frappe.only_for("System Manager")
	settings = frappe.get_single("Github Settings")
	configured_app = bool(
		settings.github_app_id
		and settings.client_id
		and settings.get_password("client_secret", raise_exception=False)
		and settings.get_password("private_key", raise_exception=False)
		and (settings.github_app_html_url or settings.github_app_slug)
	)
	if configured_app and not frappe.utils.cint(force_new_app):
		return {"kind": "redirect", "url": _installation_url(settings, frappe.session.user)}

	state = _new_state("manifest", frappe.session.user)
	return {
		"kind": "manifest",
		"action": manifest_create_url(organization),
		"state": state,
		"manifest": build_manifest(state),
	}


@frappe.whitelist(allow_guest=True)
def manifest_callback(code: str | None = None, state: str | None = None):
	payload = _consume_state(state, "manifest")
	if not code:
		frappe.throw("GitHub did not return an App manifest code.")
	response = requests.post(
		f"{GITHUB}/app-manifests/{code}/conversions",
		headers=_headers(),
		timeout=(5, 30),
	)
	response.raise_for_status()
	config = response.json()
	_validate_manifest_config(config)
	settings = frappe.get_doc("Github Settings")
	settings.github_app_name = config.get("name")
	settings.github_app_id = str(config.get("id") or "")
	settings.github_app_slug = config.get("slug")
	settings.github_app_html_url = config.get("html_url")
	settings.client_id = config.get("client_id")
	settings.client_secret = config.get("client_secret")
	settings.private_key = config.get("pem")
	settings.webhook_secret = config.get("webhook_secret")
	settings.authorization_uri = OAUTH_AUTHORIZE_URL
	settings.token_uri = OAUTH_TOKEN_URL
	settings.redirect_uri = _site_url("api/method/commit.api.github_connection.oauth_callback")
	settings.webhook_enabled = is_public_https_url(
		_site_url("api/method/commit.api.github_webhook.github_webhook")
	)
	settings.setup_source = "GitHub App Manifest"
	settings.installation_id = None
	settings.installation_account = None
	settings.connected_on = None
	settings.save(ignore_permissions=True)
	if not settings.get_password("private_key", raise_exception=False):
		frappe.throw("The GitHub App private key could not be stored securely. Please start again.")
	record_event("github.app-created", details={"app_id": settings.github_app_id}, user=payload["user"])
	# This callback is a GET redirect. Commit before sending the browser to GitHub,
	# otherwise Frappe rolls back the credentials at the end of the request.
	frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
	_redirect(_installation_url(settings, payload["user"]))


def _app_installation(installation_id: str) -> dict[str, Any]:
	response = requests.get(
		f"{GITHUB}/app/installations/{installation_id}",
		headers=_headers(app_jwt()),
		timeout=(5, 30),
	)
	response.raise_for_status()
	return response.json()


@frappe.whitelist(allow_guest=True)
def install_callback(installation_id: str | None = None, state: str | None = None, setup_action: str | None = None, **_kwargs):
	payload = _consume_state(state, "install")
	if not installation_id:
		frappe.throw("GitHub did not return an installation ID.")
	settings = frappe.get_single("Github Settings")
	if not settings.github_app_id or not settings.get_password("private_key", raise_exception=False):
		_redirect(_site_url("commit?github=restart_required"))
		return
	installation = _app_installation(str(installation_id))
	if str(installation.get("app_id")) != str(settings.github_app_id):
		frappe.throw("That installation does not belong to this Commit GitHub App.", frappe.PermissionError)
	oauth_state = _new_state(
		"oauth",
		payload["user"],
		installation_id=str(installation_id),
		setup_action=setup_action,
	)
	params = urlencode(
		{
			"client_id": settings.client_id,
			"redirect_uri": settings.redirect_uri,
			"state": oauth_state,
		}
	)
	_redirect(f"{OAUTH_AUTHORIZE_URL}?{params}")


def _exchange_user_code(code: str, settings) -> str:
	response = requests.post(
		OAUTH_TOKEN_URL,
		headers={"Accept": "application/json"},
		data={
			"client_id": settings.client_id,
			"client_secret": settings.get_password("client_secret"),
			"code": code,
			"redirect_uri": settings.redirect_uri,
		},
		timeout=(5, 30),
	)
	response.raise_for_status()
	data = response.json()
	if not data.get("access_token"):
		frappe.throw(data.get("error_description") or "GitHub did not return a user access token.")
	return data["access_token"]


def _user_installations(token: str) -> list[dict[str, Any]]:
	installations: list[dict[str, Any]] = []
	for page in range(1, 11):
		response = requests.get(
			f"{GITHUB}/user/installations?per_page=100&page={page}",
			headers=_headers(token),
			timeout=(5, 30),
		)
		response.raise_for_status()
		batch = response.json().get("installations", [])
		installations.extend(batch)
		if len(batch) < 100:
			break
	return installations


@frappe.whitelist(allow_guest=True)
def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None, **_kwargs):
	payload = _consume_state(state, "oauth")
	if error or not code:
		_redirect(_site_url(f"commit?github=error&reason={error or 'authorization_cancelled'}"))
		return
	settings = frappe.get_doc("Github Settings")
	token = _exchange_user_code(code, settings)
	installation_id = str(payload["installation_id"])
	installations = _user_installations(token)
	installation = next((item for item in installations if str(item.get("id")) == installation_id), None)
	if not installation:
		frappe.throw(
			"The signed-in GitHub account cannot access that installation.",
			frappe.PermissionError,
		)
	if str(installation.get("app_id")) != str(settings.github_app_id):
		frappe.throw("The authorized installation belongs to a different GitHub App.", frappe.PermissionError)
	account = installation.get("account") or {}
	settings.installation_id = installation_id
	settings.installation_account = account.get("login")
	settings.installation_account_type = account.get("type")
	settings.installation_repository_selection = installation.get("repository_selection")
	settings.connected_on = now_datetime()
	settings.webhook_enabled = is_public_https_url(
		_site_url("api/method/commit.api.github_webhook.github_webhook")
	)
	settings.save(ignore_permissions=True)
	record_event(
		"github.connected",
		details={"installation_id": installation_id, "account": account.get("login")},
		user=payload["user"],
	)
	# Persist the verified installation before redirecting back to the SPA.
	frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
	_redirect(_site_url("commit?github=connected"))


@frappe.whitelist()
def search_organizations(query: str):
	"""Return public GitHub organizations matching the setup owner's search."""
	frappe.only_for("System Manager")
	query = (query or "").strip()
	if len(query) < 2:
		return []
	response = requests.get(
		f"{GITHUB}/search/users",
		headers=_headers(),
		params={"q": f"{query} type:org", "per_page": 8},
		timeout=(5, 20),
	)
	response.raise_for_status()
	return [
		{
			"login": item.get("login"),
			"avatar_url": item.get("avatar_url"),
			"html_url": item.get("html_url"),
		}
		for item in response.json().get("items", [])
		if item.get("login")
	]


def _repo_summary(repo: dict[str, Any]) -> dict[str, Any]:
	owner = repo.get("owner") or {}
	return {
		"id": repo.get("id"),
		"name": repo.get("name"),
		"full_name": repo.get("full_name"),
		"owner": owner.get("login"),
		"owner_type": owner.get("type"),
		"avatar_url": owner.get("avatar_url"),
		"private": bool(repo.get("private")),
		"archived": bool(repo.get("archived")),
		"description": repo.get("description"),
		"default_branch": repo.get("default_branch") or "main",
		"language": repo.get("language"),
		"imported": bool(
			frappe.db.exists(
				"Commit Project",
				{"org": owner.get("login"), "repo_name": repo.get("name")},
			)
		),
	}


@frappe.whitelist()
def list_repositories():
	frappe.only_for("System Manager")
	repositories: list[dict[str, Any]] = []
	for page in range(1, 11):
		result = github_request("GET", f"/installation/repositories?per_page=100&page={page}")
		batch = result.get("repositories", [])
		repositories.extend(batch)
		if len(batch) < 100:
			break
	return [_repo_summary(repo) for repo in repositories]


def _selected_repositories(repository_ids: list[int]) -> list[dict[str, Any]]:
	try:
		wanted = {int(value) for value in repository_ids}
	except (TypeError, ValueError):
		frappe.throw("Repository IDs must be numeric.")
	available: list[dict[str, Any]] = []
	for page in range(1, 11):
		result = github_request("GET", f"/installation/repositories?per_page=100&page={page}")
		batch = result.get("repositories", [])
		available.extend(repo for repo in batch if int(repo.get("id") or 0) in wanted)
		if len(batch) < 100 or len(available) == len(wanted):
			break
	if {int(repo["id"]) for repo in available} != wanted:
		frappe.throw("One or more selected repositories are not accessible to this installation.")
	return available


def _discover_app_name(repo: dict[str, Any]) -> str:
	owner = (repo.get("owner") or {}).get("login")
	name = repo.get("name")
	for path in ("pyproject.toml", "setup.py"):
		try:
			content = github_request("GET", f"/repos/{owner}/{name}/contents/{path}")
		except requests.HTTPError as exc:
			if exc.response is not None and exc.response.status_code == 404:
				continue
			raise
		text = base64.b64decode(content.get("content", "")).decode("utf-8", errors="replace")
		match = re.search(
			r"(?m)^\s*name\s*=\s*['\"]([^'\"]+)['\"]" if path == "pyproject.toml" else r"name\s*=\s*['\"]([^'\"]+)['\"]",
			text,
		)
		if match:
			return match.group(1)
	return re.sub(r"[^a-zA-Z0-9_]+", "_", name or "app").strip("_").lower()


@frappe.whitelist(methods=["POST"])
def import_repositories(repository_ids: str | list[int]):
	frappe.only_for("System Manager")
	if isinstance(repository_ids, str):
		repository_ids = json.loads(repository_ids)
	if not isinstance(repository_ids, list) or not repository_ids:
		frappe.throw("Select at least one repository to import.")
	if len(repository_ids) > 100:
		frappe.throw("Import no more than 100 repositories at a time.")
	results = []
	for repo in _selected_repositories(repository_ids):
		owner = repo.get("owner") or {}
		owner_login = owner.get("login")
		if not owner_login or not repo.get("name"):
			continue
		if not frappe.db.exists("Commit Organization", owner_login):
			frappe.get_doc(
				{
					"doctype": "Commit Organization",
					"organization_name": owner_login,
					"github_org": owner_login,
					"image": owner.get("avatar_url"),
					"about": f"Imported from GitHub ({owner.get('type') or 'account'})",
				}
			).insert()
		project_name = frappe.db.exists(
			"Commit Project", {"org": owner_login, "repo_name": repo["name"]}
		)
		created = not bool(project_name)
		if not project_name:
			project = frappe.get_doc(
				{
					"doctype": "Commit Project",
					"org": owner_login,
					"display_name": repo["name"],
					"repo_name": repo["name"],
					"description": repo.get("description"),
					"default_branch": repo.get("default_branch") or "main",
					"app_name": _discover_app_name(repo),
				}
			).insert()
			project_name = project.name
		branch_name = repo.get("default_branch") or "main"
		branch = frappe.db.exists(
			"Commit Project Branch", {"project": project_name, "branch_name": branch_name}
		)
		if not branch:
			branch = frappe.get_doc(
				{
					"doctype": "Commit Project Branch",
					"project": project_name,
					"branch_name": branch_name,
				}
			).insert().name
		results.append(
			{
				"repository": repo.get("full_name"),
				"project": project_name,
				"branch": branch,
				"created": created,
			}
		)
	record_event(
		"github.repositories-imported",
		details={"repositories": [item["repository"] for item in results]},
	)
	return {"repositories": results, "created": sum(1 for item in results if item["created"])}
