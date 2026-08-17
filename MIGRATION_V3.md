# Commit 3 migration

Commit 3 introduces repository intelligence, project-level teams, GitHub checks,
versioned docs-as-code, unified search, and scheduled API verification.

## Upgrade

1. Back up the database, public/private files, and `site_config.json`.
2. Update the app and install Python requirements.
3. Run `bench --site <site> migrate`.
4. Build assets with `bench build --app commit` and restart web, queue,
   scheduler, and realtime processes.
5. Open each **Commit Organization** and confirm the migrated owner membership.
   Add other users with Viewer, Editor, Maintainer, or Owner access.
6. Refresh every tracked branch twice. The first scan establishes a baseline;
   the second can classify changes against it.

The migration indexes existing documentation, creates initial documentation
versions, and adds existing project owners to their organization as Owners.

## GitHub App

Configure **Github Settings** with:

- GitHub App ID, installation ID, and an RSA private key; or a temporary
  installation token.
- A webhook secret and **Enable GitHub Webhooks**.
- Webhook URL:
  `/api/method/commit.api.github_webhook.github_webhook`

Recommended repository permissions are Metadata read, Contents read/write,
Checks read/write, and Pull requests read/write. Subscribe to push and pull
request events. Set a project to **Blocking** policy mode only after reviewing
its initial findings.

## Docs as code

Set **Documentation Path** on each Commit Project. Import reads Markdown from
that path. Export creates a local `commit/docs-*` branch; **Open PR** publishes
the files and opens a GitHub pull request. Published pages continue to use safe,
sanitized Markdown.

## API collections

Create a **Commit API Environment** with a public HTTPS base URL and encrypted
credentials. Add requests and assertions to a **Commit API Collection**, then
choose Manual, Hourly, Daily, or Weekly execution. Collection requests cannot
leave the configured environment host and redirects are disabled.

## Rollback

Commit 3 tables are additive. Existing API JSON, documentation, project, and
branch records remain populated. A code rollback to Commit 2 can ignore the new
records. Restore the pre-upgrade backup if schema rollback is also required.
