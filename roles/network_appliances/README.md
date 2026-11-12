# network_appliances

**Status: scaffolded, not implemented.**

API-based configuration management for OPNsense and UniFi — the two
hosts in the `appliances` inventory group. These are deliberately NOT
treated as generic SSH/Ansible targets (see `inventory/hosts.yml`:
`appliances` carries `ansible_connection: local`, same pattern already
used by `roles/webui_identity`). This role uses `ansible.builtin.uri`
against each appliance's REST API, never `ansible.builtin.user`-style
host-fact modules that assume a shell.

## Relationship to `roles/webui_identity`

`webui_identity` already covers **account/identity provisioning** on
these same appliances (creating an `automation` API user/role on
OPNsense/UniFi) via `playbooks/webui.yml`. `network_appliances` is a
different concern: **ongoing config management** of the network itself
once an API identity exists — firewall rules, VLANs, DHCP reservations,
syslog/forwarding settings (OPNsense already has a documented
`/api/syslog/settings/addDestination` pattern — see the
logging-monitoring reference), UniFi device/network provisioning. The
two roles should compose (`network_appliances` uses credentials
`webui_identity` provisions), not duplicate each other.

## Intended scope (not yet implemented)

- OPNsense: `ansible.builtin.uri` calls against `https://10.20.0.1/api/...`
  using API key/secret (Bitwarden-sourced, same pattern as other secrets
  in this repo) — e.g. firewall rule management (`/api/firewall/filter/...`),
  syslog forwarding (`/api/syslog/...`), DHCP (`/api/dhcpv4/...`). Most
  OPNsense API endpoints need a `POST .../reconfigure` or `/apply` call
  after a settings change — don't assume a `set` call alone takes effect.
- UniFi: `ansible.builtin.uri` against the controller's REST API
  (`https://10.20.0.107/...`) — session-cookie auth is typical for the
  UniFi controller API (not a static API key like OPNsense), so task
  design needs a login step before any config call, registering/reusing
  the session cookie across subsequent `uri` tasks.
- Idempotency: both APIs generally return current state on a GET, so each
  config task should compare desired vs. actual before issuing a
  write — don't blindly POST every run.

## Open questions

- Real OPNsense API key/secret and UniFi controller credentials — sourced
  via Bitwarden once populated (see `webui_identity_accounts` in
  `group_vars/appliances.yml`); not present as real values anywhere in
  this repo.
- Scope of "config management" to actually automate first — firewall
  rules, VLANs, and DHCP reservations all have very different
  blast-radius if a task gets it wrong on a live router; needs explicit
  prioritization from the user before writing real tasks here, not an
  assumed order.

## Variables

See `defaults/main.yml`.
