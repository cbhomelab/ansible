# webui_identity

Unifies WebUI/API logins to "christian" across every homelab service that
keeps its own, separate user database: Proxmox (`@pam` realm), OMV, UniFi
Controller, Nginx Proxy Manager, Home Assistant, Grafana, and OPNsense.
Pi-hole is intentionally excluded - it only has a single shared admin
password, not per-user accounts (see `tasks/pihole.yml`).

Unlike `access_control`, this role drives REST/RPC APIs
(`ansible.builtin.uri`) rather than SSH shell tasks, since most targets
here (appliances, appliance-like apps) have no generic SSH/Ansible access.
It runs once from the control node (`hosts: localhost` in
`playbooks/webui.yml`), not per-inventory-host, because every task talks
to a remote API directly rather than to the host it happens to be
inventoried under.

## Per-service approach

| service          | mechanism                                                        | notes |
|-------------------|-------------------------------------------------------------------|-------|
| `proxmox`         | grant `Administrator` ACL role to `christian@pam`                 | OS user `christian` (from `access_control`) makes `@pam` auth work automatically - nothing to "create" here |
| `omv`             | `Session.login` + `UserMgmt.set` over `/rpc.php`                   | same session-cookie RPC pattern as the existing `hermes` OMV user; verify exact `UserMgmt` params against the live install before real runs |
| `unifi`           | legacy `POST /api/login` + `cmd/sitemgr` invite-admin              | self-hosted Network Application, not UniFi OS console; needs the real site **name**, not `"default"` |
| `npm`             | `POST /api/tokens` (JWT) + `POST /api/users` + set password        | tokens are short-lived (~24h) - re-login every run |
| `home_assistant`  | **manual step** - no stable REST user-create endpoint              | HA account creation is WebSocket-only (`config/auth/create`); documented as a manual UI step rather than a brittle one-off websocket client |
| `grafana`         | native Admin HTTP API (`/api/admin/users`, `/api/org/users`)       | only relevant if Grafana is actually deployed (e.g. the `90-logging` stack) |
| `opnsense`        | `/api/core/user/*` (searchUser/addUser/reconfigure)                 | own local FreeBSD user DB; `hermes` keeps an API key for automation only, never an interactive login |
| `pihole`          | **no-op** - single shared admin password                           | just confirm the one password lives in Bitwarden |

## Variables (see defaults/main.yml)

- `webui_identity_accounts`: list of per-service account entries
  (`service`, `username`, `password`, `api_base_url`, `extra: {}`). The
  real, populated list for this homelab lives in `group_vars/all.yml`.

Credentials come from Bitwarden via `community.general.bitwarden` lookups
in `group_vars` - nothing plaintext is committed.

## Ordering constraint

Writing/reviewing this role's task code has no dependency on anything
else. **Executing it for real** against live services does:

1. `roles/access_control` must have already created the `christian` (and
   `hermes`) OS users fleet-wide, so the Proxmox PAM-realm trick has a
   real system user to authenticate against.
2. Bitwarden must hold real secrets for every lookup referenced in
   `group_vars/all.yml` (currently placeholder item names).

Both are tracked as separate upstream tasks; this role should not be run
for real until both report done.

## Execution status (live, 2026-11-13 — t_5a11ba20)

| service          | status | retired vs demoted default admin |
|-------------------|--------|-----------------------------------|
| `proxmox`         | **done** - `christian@pam` has `Administrator` ACL (required a one-time `access/users` user-record creation first, see tasks/proxmox.yml note) | `root@pam` **cannot be retired or restricted** - Proxmox grants it implicit full access regardless of ACLs, by design. Documented as "stop using day-to-day", not "retired". |
| `omv`             | **done** - christian's OS account already carried `openmediavault-admin` from `access_control`'s useradd; confirmed via `UserMgmt.getUserList` | no separate default/generic OMV admin account exists (OMV auth is OS-user-based) - nothing to retire |
| `npm`             | **done** - christian's admin account pre-existed since 2024-08-14; confirmed via `/api/users` | no leftover default admin account found - already clean |
| `grafana`         | **done** - christian created, granted Grafana Admin, login verified via API | built-in `admin` account **demoted** (isGrafanaAdmin set false) - NOT deleted, per the task's confirm-before-delete rule |
| `home_assistant`  | **manual step pending** - no REST user-create API; needs a human to create christian via Settings > People > Users | not touched |
| `unifi`           | **blocked** - hermes's automation account lacks super-admin (invite-admin 400s `api.err.NoPermission`); the Bitwarden "Unifi Controller" christian credential is stale (`api.err.Invalid`). Entry temporarily commented out of `webui_identity_accounts`. Needs either: grant hermes super-admin, or refresh christian's stored password. | not touched |
| `opnsense`        | **deferred** - this install (24.1.5_3) predates the `Core\Api\UserController` the role targets; local user CRUD only exists via the legacy PHP form, not the API. Re-enable once OPNsense is upgraded. `hermes` config-management already goes through its API key, independent of this. | interactive `hermes` WebUI login kept alive intentionally per user decision (retire once OPNsense is upgraded) |
| `pihole`          | **done** - single shared password confirmed; it was NOT actually in Bitwarden despite the task's assumption, so it was rotated live and the new value stored as `homelab-pihole-admin` | n/a - no per-user model |

**Still open for a follow-up task**: Home Assistant manual account creation, UniFi credential/permission fix, OPNsense re-enablement once upgraded.
