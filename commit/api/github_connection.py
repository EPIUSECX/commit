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


def _public_base_url(candidate: str | None = None) -> str:
	"""Prefer the browser's public HTTPS origin when Commit runs behind a tunnel."""
	candidate = (candidate or "").strip().rstrip("/")
	if candidate:
		parsed = urlparse(candidate)
		origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
		if origin and is_public_https_url(origin):
			return origin
	return frappe.utils.get_url().rstrip("/")


def _site_url(path: str = "", base_url: str | None = None) -> str:
	return f"{_public_base_url(base_url)}/{path.lstrip('/')}"


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


def build_manifest(state: str, base_url: str | None = None) -> dict[str, Any]:
	base_url = _public_base_url(base_url)
	webhook_url = _site_url(
		"api/method/commit.api.github_webhook.github_webhook", base_url
	)
	webhook_public = is_public_https_url(webhook_url)
	host = re.sub(r"[^a-z0-9-]+", "-", (urlparse(base_url).hostname or "site").lower()).strip("-")
	name = f"Commit {host[:18]} {state[:6]}"[:34]
	return {
		"name": name,
		"url": base_url,
		"description": "Repository intelligence, API documentation, checks, and policy automation from Commit.",
		"redirect_url": _site_url(
			"api/method/commit.api.github_connection.manifest_callback", base_url
		),
		"callback_urls": [
			_site_url("api/method/commit.api.github_connection.oauth_callback", base_url)
		],
		"setup_url": _site_url(
			"api/method/commit.api.github_connection.install_callback", base_url
		),
		"setup_on_update": True,
		# Public controls who may install the App, not repository visibility. It is
		# required for one Commit site to connect a personal account and multiple orgs.
		"public": True,
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


def _installation_url(settings, user: str, public_base_url: str | None = None) -> str:
	state = _new_state("install", user, public_base_url=public_base_url)
	base = settings.github_app_html_url or f"https://github.com/apps/{settings.github_app_slug}"
	return f"{base.rstrip('/')}/installations/new?{urlencode({'state': state})}"


@frappe.whitelist(methods=["POST"])
def start_connection(
	force_new_app: bool = False,
	organization: str | None = None,
	public_base_url: str | None = None,
):
	frappe.only_for("System Manager")
	public_base_url = _public_base_url(public_base_url)
	settings = frappe.get_single("Github Settings")
	configured_app = bool(
		settings.github_app_id
		and settings.client_id
		and settings.get_password("client_secret", raise_exception=False)
		and settings.get_password("private_key", raise_exception=False)
		and (settings.github_app_html_url or settings.github_app_slug)
	)
	if configured_app and not frappe.utils.cint(force_new_app):
		return {
			"kind": "redirect",
			"url": _installation_url(settings, frappe.session.user, public_base_url),
		}

	state = _new_state(
		"manifest", frappe.session.user, public_base_url=public_base_url
	)
	return {
		"kind": "manifest",
		"action": manifest_create_url(organization),
		"state": state,
		"manifest": build_manifest(state, public_base_url),
	}


@frappe.whitelist(allow_guest=True)
def manifest_callback(code: str | None = None, state: str | None = None):
	payload = _consume_state(state, "manifest")
	public_base_url = payload.get("public_base_url")
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
	settings.redirect_uri = _site_url(
		"api/method/commit.api.github_connection.oauth_callback", public_base_url
	)
	settings.webhook_enabled = is_public_https_url(
		_site_url(
			"api/method/commit.api.github_webhook.github_webhook", public_base_url
		)
	)
	settings.setup_source = "GitHub App Manifest"
	settings.installation_id = None
	settings.installation_account = None
	_store_connected_installations(settings, [])
	settings.connected_on = None
	settings.save(ignore_permissions=True)
	if not settings.get_password("private_key", raise_exception=False):
		frappe.throw("The GitHub App private key could not be stored securely. Please start again.")
	record_event("github.app-created", details={"app_id": settings.github_app_id}, user=payload["user"])
	# This callback is a GET redirect. Commit before sending the browser to GitHub,
	# otherwise Frappe rolls back the credentials at the end of the request.
	frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
	_redirect(_installation_url(settings, payload["user"], public_base_url))


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
		public_base_url=payload.get("public_base_url"),
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


def _connected_installations(settings=None) -> list[dict[str, Any]]:
	settings = settings or frappe.get_single("Github Settings")
	items = frappe.parse_json(settings.installations) if settings.installations else []
	items = items if isinstance(items, list) else []
	if settings.installation_id and not any(
		str(item.get("id")) == str(settings.installation_id) for item in items
	):
		items.append(
			{
				"id": str(settings.installation_id),
				"account": settings.installation_account,
				"account_type": settings.installation_account_type,
				"repository_selection": settings.installation_repository_selection,
			}
		)
	return [item for item in items if item.get("id")]


def _store_connected_installations(settings, installations: list[dict[str, Any]]) -> None:
	"""Store JSON fields in the serialized form Frappe Document.save expects."""
	settings.installations = json.dumps(installations)


def _set_primary_installation(settings, installations: list[dict[str, Any]]) -> None:
	primary = installations[-1] if installations else {}
	settings.installation_id = primary.get("id")
	settings.installation_account = primary.get("account")
	settings.installation_account_type = primary.get("account_type")
	settings.installation_repository_selection = primary.get("repository_selection")
	settings.connected_on = now_datetime() if primary else None


def _clear_installation_organizations(installation_id: str | None = None) -> None:
	filters = {"github_installation_id": installation_id} if installation_id else {
		"github_installation_id": ["is", "set"]
	}
	for organization in frappe.get_all("Commit Organization", filters=filters, pluck="name"):
		frappe.db.set_value(
			"Commit Organization",
			organization,
			"github_installation_id",
			None,
			update_modified=False,
		)


@frappe.whitelist()
def list_installations():
	"""Return non-secret GitHub App installation information for account management."""
	frappe.only_for("System Manager")
	settings = frappe.get_single("Github Settings")
	installations = _connected_installations(settings)
	for installation in installations:
		installation["project_count"] = frappe.db.count(
			"Commit Organization",
			{"github_installation_id": str(installation["id"])},
		)
	return {
		"app_name": settings.github_app_name,
		"app_url": settings.github_app_html_url,
		"app_created": bool(settings.github_app_id),
		"installations": installations,
	}


@frappe.whitelist(methods=["POST"])
def disconnect_installation(installation_id: str):
	"""Forget one installation locally while leaving projects and the GitHub App intact."""
	frappe.only_for("System Manager")
	installation_id = str(installation_id or "").strip()
	settings = frappe.get_doc("Github Settings")
	installations = _connected_installations(settings)
	removed = next(
		(item for item in installations if str(item.get("id")) == installation_id),
		None,
	)
	if not removed:
		frappe.throw("That GitHub installation is not connected to this Commit site.")
	remaining = [
		item for item in installations if str(item.get("id")) != installation_id
	]
	_store_connected_installations(settings, remaining)
	_set_primary_installation(settings, remaining)
	settings.save(ignore_permissions=True)
	_clear_installation_organizations(installation_id)
	record_event(
		"github.disconnected",
		details={"installation_id": installation_id, "account": removed.get("account")},
	)
	return {"disconnected": removed.get("account"), "remaining": len(remaining)}


@frappe.whitelist(methods=["POST"])
def reset_connection():
	"""Forget the generated App and all installations so setup can start cleanly."""
	frappe.only_for("System Manager")
	settings = frappe.get_doc("Github Settings")
	previous_app = settings.github_app_name
	for field in (
		"github_app_name",
		"github_app_id",
		"github_app_slug",
		"github_app_html_url",
		"client_id",
		"client_secret",
		"private_key",
		"webhook_secret",
		"installation_token",
		"installation_id",
		"installation_account",
		"installation_account_type",
		"installation_repository_selection",
		"connected_on",
		"setup_source",
	):
		settings.set(field, None)
	_store_connected_installations(settings, [])
	settings.webhook_enabled = 0
	settings.save(ignore_permissions=True)
	_clear_installation_organizations()
	record_event("github.connection-reset", details={"app": previous_app})
	return {"reset": True}


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
	connected_installations = _connected_installations(settings)
	connected_installations = [
		item for item in connected_installations if str(item.get("id")) != installation_id
	]
	connected_installations.append(
		{
			"id": installation_id,
			"account": account.get("login"),
			"account_type": account.get("type"),
			"repository_selection": installation.get("repository_selection"),
		}
	)
	settings.installation_id = installation_id
	settings.installation_account = account.get("login")
	settings.installation_account_type = account.get("type")
	settings.installation_repository_selection = installation.get("repository_selection")
	_store_connected_installations(settings, connected_installations)
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
	_redirect(
		_site_url("commit?github=connected", payload.get("public_base_url"))
	)


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


def _repo_summary(repo: dict[str, Any], installation_id: str) -> dict[str, Any]:
	owner = repo.get("owner") or {}
	return {
		"id": repo.get("id"),
		"installation_id": installation_id,
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
	for installation in _connected_installations():
		installation_id = str(installation["id"])
		for page in range(1, 11):
			result = github_request(
				"GET",
				f"/installation/repositories?per_page=100&page={page}",
				installation_id=installation_id,
			)
			batch = result.get("repositories", [])
			repositories.extend(
				_repo_summary(repo, installation_id) for repo in batch
			)
			if len(batch) < 100:
				break
	return repositories


@frappe.whitelist()
def connection_health():
	"""Verify installation credentials without exposing repository details."""
	frappe.only_for("System Manager")
	settings = frappe.get_single("Github Settings")
	configured = {
		"github_app_id": bool(settings.github_app_id),
		"installation_id": bool(settings.installation_id),
		"private_key": bool(settings.get_password("private_key", raise_exception=False)),
	}
	if not all(configured.values()):
		return {
			"connected": False,
			"account": settings.installation_account,
			"configuration": configured,
		}
	installations = _connected_installations(settings)
	counts = []
	for installation in installations:
		result = github_request(
			"GET",
			"/installation/repositories?per_page=1",
			installation_id=str(installation["id"]),
		)
		counts.append(result.get("total_count", len(result.get("repositories", []))))
	return {
		"connected": True,
		"account": settings.installation_account,
		"installation_count": len(installations),
		"repository_count": sum(counts),
	}


def _selected_repositories(repository_ids: list[int]) -> list[dict[str, Any]]:
	try:
		wanted = {int(value) for value in repository_ids}
	except (TypeError, ValueError):
		frappe.throw("Repository IDs must be numeric.")
	available: list[dict[str, Any]] = []
	for installation in _connected_installations():
		installation_id = str(installation["id"])
		for page in range(1, 11):
			result = github_request(
				"GET",
				f"/installation/repositories?per_page=100&page={page}",
				installation_id=installation_id,
			)
			batch = result.get("repositories", [])
			for repo in batch:
				if int(repo.get("id") or 0) in wanted:
					repo["installation_id"] = installation_id
					available.append(repo)
			if len(batch) < 100 or len(available) == len(wanted):
				break
		if len(available) == len(wanted):
			break
	if {int(repo["id"]) for repo in available} != wanted:
		frappe.throw("One or more selected repositories are not accessible to this installation.")
	return available


def _discover_app_name(repo: dict[str, Any]) -> str:
	owner = (repo.get("owner") or {}).get("login")
	name = repo.get("name")
	for path in ("pyproject.toml", "setup.py"):
		try:
			content = github_request(
				"GET",
				f"/repos/{owner}/{name}/contents/{path}",
				installation_id=repo.get("installation_id"),
			)
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
					"github_installation_id": repo.get("installation_id"),
				}
			).insert()
		else:
			frappe.db.set_value(
				"Commit Organization",
				owner_login,
				"github_installation_id",
				repo.get("installation_id"),
			)
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
