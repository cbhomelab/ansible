# network_appliances

**Status: DHCP reservations — implemented, real `ansible.builtin.uri`
tasks, additive/idempotent, plan-only by default. Not yet executed
against the live router (no API credentials exist for it yet — see
"Credentials" below). UniFi config management and OPNsense firewall
rules/VLANs are still scaffolded/not implemented.**

API-based configuration management for OPNsense and UniFi — the two
hosts in the `appliances` inventory group. These are deliberately NOT
treated as generic SSH/Ansible targets (see `inventory/hosts.yml`:
`appliances` carries `ansible_connection: local`, same pattern already
used by `roles/webui_identity`). This role uses `ansible.builtin.uri`
against each appliance's REST API, never `ansible.builtin.user`-style
host-fact modules that assume a shell.

## Relationship to `roles/webui_identity`

`webui_identity` covers **account/identity provisioning** on these same
appliances (creating a `christian` WebUI login, `hermes` API keys) via
`playbooks/webui.yml`. `network_appliances` is a different concern:
**ongoing config management** of the network itself once an API identity
exists. The two roles compose (`network_appliances` uses credentials
`webui_identity` provisions/documents), not duplicate each other.

## DHCP reservations (implemented) — `tasks/dhcp_reservations.yml`

### Key finding: OPNsense has TWO DHCPv4 API surfaces, only one supports reservations

Verified against `docs.opnsense.org/development/api/` (Nov 2026), **not
guessed**:

| Backend | API prefix | Reservation CRUD? |
|---|---|---|
| Legacy ISC dhcpd (pre-24.1 default) | `/api/dhcpv4/...` | **No** — only `LeasesController` (search/del lease) and `ServiceController` (start/stop/restart/reconfigure) remain. Reservation CRUD was removed upstream; see `opnsense/core#4062` (closed "help wanted"/wontfix). Most blog posts/forum answers for "OPNsense DHCP API" predate this and are now wrong. |
| Kea (current default since OPNsense 24.1) | `/api/kea/dhcpv4/...` | **Yes** — `add_reservation` / `set_reservation` / `del_reservation` / `get_reservation` / `search_reservation`, plus `search_subnet` to resolve the subnet UUID a reservation belongs to (reservations are keyed to a subnet UUID, not a bare CIDR). Apply via `POST /api/kea/service/reconfigure` (a *different* service endpoint than the legacy one).

This role targets the **Kea** endpoints, since that's current-default.
It does **not** verify which backend this specific router instance
actually runs (that needs a live authenticated call this pass never
got — see "Known gap"). If this router is still on the legacy backend,
every call 404s cleanly rather than silently touching the wrong config.

### Design

1. Build a plan from inventory: every host in `lxc_guests` + `vm_guests`
   with `dhcp_reservation: true` and `mac` set in `inventory/hosts.yml`
   (see that file's comment block — this intentionally excludes hosts
   whose IP is pinned at the Proxmox guest-config level instead, since
   OPNsense's DHCP server never sees a request from them).
2. Resolve the Kea subnet UUID for `network_appliances_dhcp_subnet_cidr`
   (default `10.20.0.0/24`) via `search_subnet`. **Fails loudly** (no
   guessing) if no matching subnet is found.
3. Fetch existing reservations via `search_reservation` and classify each
   planned entry:
   - `unchanged` — a reservation for that MAC already points at the
     desired IP. No-op.
   - `conflict` — the MAC already has a *different* IP reserved, OR the
     desired IP is already reserved to a *different* MAC. **Not
     auto-resolved** — reported via `debug` and left out of any write,
     per the task's "flag conflicts rather than silently pick one".
   - `create` — no reservation exists yet for that MAC/IP pair.
4. **Plan-only by default** (`network_appliances_dhcp_apply: false`):
   `create` entries are reported via `debug` ("WOULD CREATE...") and
   nothing is written. Review the plan, then set
   `network_appliances_dhcp_apply: true` to actually `add_reservation`
   and `kea/service/reconfigure`.
5. Additive only — this role never calls `del_reservation` or `set` on
   anything it didn't just create; it does not touch unrelated existing
   OPNsense DHCP config.

### Pilot findings (this pass, verified via `pct exec <vmid> -- ip addr`
### on neptune / Proxmox guest-agent — real live data, not assumed)

`inventory/hosts.yml` has been corrected to the **actual** live IP for
every host below (see its comment block for the audit trail of what was
wrong before). This is the IP-drift fix referenced in the task; the DHCP
reservation pins each corrected IP so it stops drifting again.

| Host | Assumed (wrong) | Actual (live) | Mechanism | `dhcp_reservation` |
|---|---|---|---|---|
| lxc102-intranet | 10.20.0.102 | **10.20.0.4** | DHCP | `true` |
| lxc103-hermesagent | 10.20.0.103 | **10.20.0.21** | DHCP | `true` |
| lxc104-glance | 10.20.0.104 | **10.20.0.202** | DHCP | `true` (matches the drift already surfaced by t_34f25463) |
| lxc105-minecraft | 10.20.0.105 | **10.20.0.130** | static `ip=` in Proxmox LXC net0 (not DHCP) | `false` — reservation would be a no-op; see "Open follow-up" |
| lxc108-pihole | 10.20.0.108 | **10.20.0.8** | static `ip=` in Proxmox LXC net0 (not DHCP) | `false` — same as above |
| vm101-homeassistant | 10.20.0.5 | 10.20.0.5 (already correct) | DHCP | `true` — reservation just pins what's already correct |

So the drift wasn't limited to glance (the example in the task body) —
**3 of 5 LXC guests** had a wrong `ansible_host` before this pass.

### Open follow-up (not done here, flagging per task step 6)

`lxc105-minecraft` and `lxc108-pihole` pin their IP at the Proxmox
guest-config level (static `ip=` in LXC net0), not via DHCP. A DHCP
reservation can't fix drift there since OPNsense's DHCP server is never
involved. Two real options exist — migrate them to DHCP + a reservation
(consistency with everything else) or leave them static but make sure
their static IPs are excluded from OPNsense's DHCP pool/range (so DHCP
never hands `.130` or `.8` to something else). Either is a deliberate,
separate change — not bundled into this pass.

## Credentials

**Known gap: no OPNsense API key with DHCP-write privilege exists in
Bitwarden yet**, so this role has not been executed against the live
router. Checked (Nov 2026): neither `homelab-opnsense-api` nor
`homelab-webui-christian-opnsense` (referenced by `group_vars/all.yml`'s
`webui_identity_accounts`) exist as real Bitwarden items — `webui_identity`
hasn't been run for real either, per the IaC roadmap. The *existing*
`homelab-opnsense-api` item referenced in `group_vars/appliances.yml` is
documented there as `role: readonly` (for status/syslog reads) — **not
sufficient** for DHCP writes even once it exists, since OPNsense privilege
is assigned per user/group and a readonly group has no page access to
Services: DHCPv4 / Services: Kea DHCP.

This role expects a **separate**, write-capable key as Bitwarden item
`homelab-opnsense-dhcp-api` (`username` field = API key, `password`
field = API secret) belonging to an OPNsense user/group with at least
"Services: Kea DHCP" + "Services: DHCPv4" page privileges. To create
one: log into the OPNsense WebUI as an existing admin, create a
dedicated group with just those privileges, add a user in it, and
generate an API key for that user (System > Access > Users > *user* >
API keys) — the secret is shown once and can't be retrieved later, so
it goes straight into Bitwarden. **No admin login for this OPNsense
instance was available to this pass either** (checked Bitwarden; none
found) — creating the key above needs a human with existing admin
access.

## UniFi (still scaffolded, not implemented)

- `ansible.builtin.uri` against the controller's REST API
  (`https://10.20.0.107/...`) — session-cookie auth is typical for the
  UniFi controller API (not a static API key like OPNsense), so task
  design needs a login step before any config call, registering/reusing
  the session cookie across subsequent `uri` tasks.

## Open questions

- Firewall rules and VLANs (OPNsense) — explicitly deferred (user
  decision, Nov 2026): come after DHCP reservations land for real, order
  between them TBD when reached. Each has meaningfully higher blast
  radius on a live router than a DHCP reservation.
- UniFi config management — not yet started, no credentials either.

## Variables

See `defaults/main.yml`.
