# Commit 2.0 migration

Commit 2.0 hardens repository inspection and public documentation. Review these
changes before upgrading a production site.

## Upgrade

1. Back up the site and files.
2. Update the app and run `bench --site <site> migrate`.
3. Open **Open AI Settings** and set an API model identifier available to your
   OpenAI project. Existing API keys remain encrypted in Frappe.
4. If remote image conversion is required, add an explicit list of public hosts
   to `site_config.json` as `commit_allowed_image_hosts`.
5. Rebuild assets and restart web, queue, scheduler, and socket workers.
6. Trigger one refresh for each active project branch. This creates the first
   queryable **Commit Scan Snapshot** and **Commit Discovered API** records.

## Breaking security changes

- Project, branch, source, schema, OpenAPI, and Bruno endpoints require login.
- Branch refresh is POST-only, queued, permission checked, and deduplicated.
- Cloned `commands.py` modules are never imported or executed.
- Public pages require a published parent, a published page, and guest access.
- Published content is sanitized Markdown. Executable MDX, imports, exports,
  and arbitrary JSX are no longer supported.
- GitHub OAuth starts through `get_authorization_url` and uses a short-lived,
  single-use `state` value.
- Remote images are disabled until an allowlist is configured.

## Rollback

The legacy branch JSON fields remain populated during the 2.0 transition. A
code rollback can therefore continue reading existing `whitelisted_apis` and
`documentation` values. New snapshot records are additive and can remain in
the database during rollback.
