# Commit Intelligence

## Scan model

Each successful branch scan creates a **Commit Scan Snapshot**. Components use
stable identities and SHA-256 fingerprints, allowing Commit to compare source
semantics rather than database row names. The inventory includes APIs, DocTypes,
hooks, Python and npm dependencies, portal routes, and frontend consumers.

Changes are classified as Added, Modified, or Removed. API arguments and methods,
DocType fields and permissions, guest access, and component removal contribute
to breaking-change and risk calculations.

## Policies and findings

Built-in policies identify guest mutations, missing rate limits, unsafe GET
mutations, permission bypasses, manual commits, filesystem/network access,
undocumented APIs, guest DocType permissions, and unbounded dependencies.

Custom **Commit Policy** records match a component type and a JSON condition:

```json
{"path": "allow_guest", "operator": "equals", "value": true}
```

Supported operators are `equals`, `contains`, and `exists`. Policies can be
global or project-specific and can block pull requests. Suppressions require a
reason and automatically expire.

## Access levels

- Viewer: read intelligence, architecture, tests, and findings.
- Editor: run tests, edit project artifacts, and update findings.
- Maintainer: refresh branches, export docs, publish PRs, and delete artifacts.
- Owner: full project access and organization governance.

System Managers retain global access. Frappe list and document permission hooks
apply these boundaries to Desk and API access.

## Delivery

Push and pull-request webhooks enqueue branch scans. Commit publishes a GitHub
Check with risk, breaking changes, findings, annotations, and a deep link to the
Intelligence workspace. Advisory projects report findings; Blocking projects
fail checks for breaking or blocking critical findings.

Notification endpoints support email and signed HTTPS webhooks. Configure event
names such as `scan.completed`, `scan.failed`, `finding.critical`, and
`docs.stale`. Signed payloads use the `X-Commit-Signature-256` header.

## GitHub onboarding

The Projects onboarding panel can create and install a private GitHub App with
GitHub's App Manifest flow. The System Manager starts once in Commit, chooses
the GitHub account and repositories, and authorizes the installation. Commit
stores the App ID, encrypted client secret, encrypted private key, encrypted
webhook secret, and verified installation ID. The temporary user OAuth token is
used only to prove access to that installation and is not stored.

For personal repositories, leave the optional organization field blank. For
organization repositories, enter the GitHub organization name so GitHub creates
the private App under that organization; this keeps the App dedicated to the
intended owner without making it publicly installable.

After connection, **Manage repositories** lists only repositories granted to
the installation. Importing creates the corresponding Commit Organization,
Commit Project, and default Commit Project Branch, then queues the initial
scan. Existing projects are detected and left intact.

GitHub can redirect a browser back to a local site, so App creation and import
work on `*.localhost`. GitHub cannot deliver webhooks to localhost or a private
network. Commit therefore creates the webhook inactive in local development;
manual scans remain available. Deploy behind a public HTTPS URL before enabling
push-triggered scans and checks.
