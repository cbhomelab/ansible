# system_baseline

**Status: scaffolded, not implemented.**

Fleet-wide OS baseline for homelab Linux hosts: patching/updates, base
package set, timezone/locale, and unattended-upgrades (or the Debian
equivalent). Intended scope: `proxmox_host`, `lxc_guests`, `vm_guests`,
`omv` — the same Linux-host groups `access_control` targets.

## Relationship to `roles/common`

`roles/common` already does generic host-prep (Debian package install via
`os_pkg`, hostfile entries, directory creation, NFS mounts, zsh setup).
This role is NOT meant to duplicate that. Once implemented, the intent is:

- `system_baseline` absorbs/extends the **patching and OS-hygiene** half of
  host-prep (apt upgrade policy, unattended-upgrades, timezone/locale,
  reboot-after-kernel-update handling) — concerns `common` doesn't currently
  cover at all.
- `common`'s existing package-install/dirs/NFS/hostfile/zsh tasks stay where
  they are; this role does not touch them.
- A future cleanup pass may rename/fold `common`'s `debian.yaml` package
  install into `system_baseline` if that turns out to be a cleaner home for
  "base package set" too — deferred until this role is actually implemented
  (don't guess the merge now).

## Intended scope (not yet implemented)

- OS patching: `apt upgrade`/`apt full-upgrade` on a schedule or on-demand,
  with a `system_baseline_autoupdate_enabled` style toggle per host/group.
- `unattended-upgrades` package install + config (security-only vs. all
  updates, auto-reboot window) on Debian-family hosts.
- Base package set distinct from per-role packages (e.g. `curl`, `vim`,
  `htop`, `ca-certificates`) — currently every host gets whatever `os_pkg`
  happens to be set to in `common`; this role's job is to define a sane
  fleet-wide floor that doesn't depend on a per-host var being set correctly.
- Timezone (`community.general.timezone` or `timedatectl`) and locale
  consistency across the fleet.

## Open questions

- Should Proxmox host itself (`proxmox_host` group) auto-update, or does
  that need to stay manual/scheduled-maintenance-window only given it hosts
  every other guest? Needs a user decision before `system_baseline_autoupdate_enabled`
  defaults to `true` anywhere.
- Does OMV (saturn) manage its own updates via its web UI already, making
  this role redundant/conflicting there? Needs verification before enabling.
- HAOS (vm101-homeassistant) is an immutable appliance OS — this role
  should explicitly exclude it (no generic apt/shell access), same caveat
  as noted elsewhere in this repo for appliance-style hosts.

## Variables

See `defaults/main.yml`. All default to a no-op/disabled state — enabling
real patching behavior per host/group is a deliberate future change, not
something this scaffold should turn on by default.
