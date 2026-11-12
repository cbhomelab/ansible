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
