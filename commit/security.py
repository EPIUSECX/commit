"""Security helpers shared by Commit's whitelisted API methods."""

from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import frappe


def require_authenticated_user() -> None:
	if frappe.session.user == "Guest":
		frappe.throw("Authentication required", frappe.AuthenticationError)


def require_any_role(*roles: str) -> None:
	"""Require an authenticated user with at least one of the supplied roles."""
	require_authenticated_user()
	if not set(roles).intersection(frappe.get_roles()):
		frappe.throw("You do not have permission to perform this action", frappe.PermissionError)


def get_permitted_doc(doctype: str, name: str, permission_type: str = "read"):
	"""Return a document only after applying Frappe's document permissions."""
	require_authenticated_user()
	doc = frappe.get_doc(doctype, name)
	doc.check_permission(permission_type)
	return doc


def resolve_path_within(root: str, candidate: str) -> Path:
	"""Resolve candidate and reject paths outside root (including symlink escapes)."""
	root_path = Path(root).resolve(strict=True)
	candidate_path = Path(candidate)
	if not candidate_path.is_absolute():
		candidate_path = root_path / candidate_path
	resolved = candidate_path.resolve(strict=True)
	try:
		resolved.relative_to(root_path)
	except ValueError:
		raise frappe.PermissionError("Invalid file path") from None
	return resolved


def validate_public_https_url(url: str, allowed_hosts: set[str] | None = None) -> str:
	"""Reject credentials, non-HTTPS URLs, and hosts resolving to private networks."""
	parsed = urlparse(url)
	if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
		frappe.throw("Only public HTTPS URLs are allowed")

	host = parsed.hostname.lower().rstrip(".")
	if allowed_hosts and host not in allowed_hosts:
		frappe.throw("URL host is not allowed", frappe.PermissionError)

	try:
		addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443)}
	except socket.gaierror:
		frappe.throw("URL host could not be resolved")

	for address in addresses:
		ip = ipaddress.ip_address(address)
		if not ip.is_global:
			frappe.throw("Private or local network URLs are not allowed", frappe.PermissionError)
	return url


def get_allowed_image_hosts() -> set[str]:
	hosts = frappe.conf.get("commit_allowed_image_hosts", [])
	if isinstance(hosts, str):
		hosts = [host.strip() for host in hosts.split(",")]
	return {host.lower().rstrip(".") for host in hosts if host}


def safe_repository_relative_path(path: str) -> str:
	"""Normalize a stored repository path without exposing its server location."""
	return os.path.normpath(path).lstrip("/")
