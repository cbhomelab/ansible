# system_baseline

**Status: implemented** (Nov 2026). Opt-in OS hygiene for Debian-family hosts.

## What it does (per host, each part toggleable)
- **Base packages** (`system_baseline_base_packages`): curl, vim, htop, rsync, tmux, jq, ca-certificates.
- **Timezone** `America/Los_Angeles` (`system_baseline_timezone`).
- **journald cap** `SystemMaxUse=200M` via drop-in `/etc/systemd/journald.conf.d/50-homelab.conf`.
- **Security-only unattended-upgrades**: only `origin=Debian,codename=<release>-security,label=Debian-Security`.
  Third-party repos (tailscale, openresty, corretto, UniFi, mongodb, ...) never match, so they are never auto-upgraded.
  Debian point updates (`-updates`) are NOT applied automatically. `#clear` directives replace the distro default origins.
  **No automatic reboots**; `/var/run/reboot-required` is left for a human.

The role never runs `apt upgrade` and never reboots anything.

## Scope / opt-in
`system_baseline_enabled` defaults to `false`. Enabled in `group_vars/lxc_guests.yml`, `group_vars/omv.yml`
and `host_vars/lxc107-unifi.yml` (UniFi is in `appliances` but is a normal Debian LXC; the playbook lists it explicitly).
- `playbooks/baseline.yml` targets `lxc_guests:omv:lxc107-unifi`.
- **Excluded by design:** neptune/`proxmox_host` (user decision, role asserts and refuses), HAOS, OPNsense,
  Windows, and lxc103 (Hermes itself, `system_baseline_enabled: false` in its host_vars).
- **saturn (OMV):** packages only. OMV manages its own updates, so unattended-upgrades, journald and timezone are off (its timezone is already `US/Pacific`).

## Notes
- The apt cache refresh tolerates errors (a broken third-party repo must not fail the run). On lxc107 `apt update`
  currently errors: the UniFi repo changed release name (unifi-8.0 -> unifi-10.5, needs explicit acceptance via
  `apt-get update --allow-releaseinfo-change`) and the old MongoDB 3.6 repo key is expired.
- Test: `ansible-playbook -i inventory/hosts.yml playbooks/baseline.yml --limit <host> --check --diff`, then a second real run must report `changed=0`.
- Non-security updates and the Java/UniFi/Minecraft restarts after library updates remain manual.
