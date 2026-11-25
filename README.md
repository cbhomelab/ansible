# ansible

Infrastructure-as-code for the CBHomelab: Proxmox host "neptune" and its
guests, OpenMediaVault "saturn", the Windows gaming PC, and the
OPNsense/UniFi appliances.

## Layout

```
inventory/hosts.yml   Inventory groups: proxmox_host, lxc_guests, vm_guests,
                       omv, windows, appliances (OPNsense/UniFi — API-managed
                       only, not generic SSH/Ansible targets).
group_vars/           Per-group vars. Secrets are pulled at runtime via the
                       community.general.bitwarden lookup plugin — nothing
                       plaintext is committed. Requires `bw` CLI unlocked
                       (or BW_SESSION exported) on the control node.
playbooks/
  site.yml             Top-level playbook, imports all domain playbooks below.
  access.yml           OS-level access control (users/SSH keys/sudoers) for
                        proxmox_host/lxc_guests/vm_guests/omv/windows.
  webui.yml            Per-service web UI/API account provisioning
                        (Proxmox PAM, OMV, UniFi, NPM, Home Assistant,
                        Grafana, OPNsense) - runs once from localhost,
                        driven entirely by group_vars/all.yml, not tied
                        to a specific inventory group.
  baseline.yml          OS baseline (patching, packages, timezone/locale) —
                        SCAFFOLDED, NOT IMPLEMENTED (no-op stub).
  compose.yml           OMV compose-fleet management on saturn —
                        SCAFFOLDED, NOT IMPLEMENTED (no-op stub).
  monitoring.yml        Fleet-wide Promtail/node-exporter rollout —
                        SCAFFOLDED, NOT IMPLEMENTED (no-op stub).
  backup.yml             Backup — SCAFFOLDED, NOT IMPLEMENTED (no-op stub);
                        no backup strategy decided yet.
  network.yml            OPNsense/UniFi API config management —
                        SCAFFOLDED, NOT IMPLEMENTED (no-op stub).
roles/
  access_control/       Users, SSH authorized_keys, sudoers.
  webui_identity/        Per-service account creation on app/appliance web UIs.
  common/                Generic host-prep (packages, hostfile, dirs, NFS
                        mounts, zsh). User/group/SSH management used to live
                        here too but has been consolidated into
                        access_control; common no longer touches
                        users/SSH.
  docker/, provision-vm/ Pre-existing roles, out of scope for the
                        access/permissions work — not yet reviewed/migrated.
  system_baseline/, compose_stacks/, monitoring_agents/, backup/,
  network_appliances/   Next-phase domain role skeletons — SCAFFOLDED, NOT
                        IMPLEMENTED. Each has its own README.md with
                        intended scope and open questions; see
                        references/ansible-iac-roadmap.md in the
                        homelab-infrastructure skill for the full roadmap.
```

## Usage

```
ansible-playbook playbooks/site.yml -i inventory/hosts.yml
# or a single domain:
ansible-playbook playbooks/access.yml -i inventory/hosts.yml
```

## Status (updated Nov 15 2026)

The original access/permissions work is in place, and the repo has since grown
into per-service roles that rebuild each guest from scratch. Every guest below
has a role, a playbook, a backup path and a health check.

### Access and identity
- `access_control`: users, SSH keys and sudoers across the fleet.
- `webui_identity`: per-service "christian" account on each web UI. Dry-run
  clean. The OPNsense entry is disabled because OPNsense 24.1.5 has no
  `core/user` API; revisit after an upgrade.
- `shell_config`, `audit_log_shipping`.

### Fleet roles
`system_baseline`, `compose_stacks` (saturn), `monitoring_agents`,
`prometheus_targets`, `backup` (borg on saturn), `network_appliances` (Kea
reservations, DNS/NPM sync), `proxmox_guests` (drift report plus update mode).
Neptune is excluded from automatic baseline patching on purpose. lxc103
(Hermes) is excluded from fleet runs.

### Per-service roles

| Guest | Role / playbook | Notes |
|---|---|---|
| lxc102 NPM | `npm` | nightly sqlite + cert backup |
| lxc104 Glance | `glance` | pinned v0.8.4, update path with rollback |
| saturn Glance (Docker) | `glance_dashboard` | pages in `files/config/*.yml`, hot-reloaded; secrets stay in appdata `.env` |
| saturn app configs (loki, promtail, pve-exporter, ddns, epgo, frigate, ytdl-sub) | `appdata_configs` | plain files + templates; secrets from untracked `appdata/.config-secrets.json` |
| saturn iRacing Team Manager (prod .162 / dev .163) | `iracing_tms_docker` | compose stacks on saturn, own Postgres 16 each, nightly `pg_dump`; LXC 106/111 on neptune retired |
| lxc107 UniFi | `unifi_controller` | pinned 8.0.24, update with rollback |
| lxc108 Pi-hole | `pihole` | v6, declarative, update via `--tags update` |
| lxc110 Forgejo | `forgejo` | 10.20.0.50, pinned binary, SQLite, nightly dump |
| saturn Minecraft | `minecraft_docker` / `minecraft-docker.yml` | live, see below |
| lxc105 Minecraft | `minecraft` | superseded, kept for rollback |

### Minecraft (moved to saturn, Nov 15)
- Compose stack in `/opt/minecraft` on saturn: `minecraft-proxy` (Velocity with
  vane-velocity) and `minecraft-server` (Paper, parked behind `start.block`
  until a player joins). Java 25. World data is a bind mount on the NVMe.
- OPNsense alias `minecraft_server` and NPM host `mc-map` point at saturn.
- LXC 105 is stopped with onboot off and is not destroyed. Restarting it is the
  rollback. Planned to be destroyed after about a week if nothing breaks.
- The role never writes into the data directory. The first import from LXC 105
  was a manual tar copy, documented at the top of `tasks/main.yml`.
- Not yet verified in production: a real player join, the BlueMap page, and the
  post-stop backup hook. The weekly backup (Sunday 04:15) has not run yet.
- Bedrock/Switch support (Geyser + Floodgate + BedrockConnect) is being tested
  separately and is not part of the role yet. Geyser needs Velocity 3.6.x or
  newer; production runs 3.4.0.

### Conventions and pitfalls
- Secrets come from Bitwarden at run time; nothing plaintext is committed.
- Read-only `uri` GET/login tasks need `check_mode: false`, or later tasks crash
  in check mode.
- Legacy roles `common`, `docker`, `provision-vm` and compose project
  `40-crafty` were removed.
- Roadmap and gotchas live in `references/ansible-iac-roadmap.md` in the
  homelab-infrastructure skill. Check `roles/<x>/README.md` and `git log` first.
