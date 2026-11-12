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

## Status

`access_control` has real tasks (users/ssh_keys/sudoers) wired up.
`webui_identity` has real per-service tasks for Proxmox, OMV, UniFi, NPM,
Home Assistant (manual-step note), Grafana, and OPNsense, plus a
documented no-op for Pi-hole (single shared admin password) - see
`roles/webui_identity/README.md`. Both roles are written and reviewable
now, but **executing `playbooks/webui.yml` for real must wait** until (1)
`access_control` has rolled out the `christian`/`hermes` OS users
fleet-wide, since the Proxmox `@pam` trick needs that system user to
exist, and (2) real secrets are populated in Bitwarden in place of the
placeholder item names in `group_vars/all.yml`.

`system_baseline`, `compose_stacks`, `monitoring_agents`, `backup`, and
`network_appliances` are scaffolded skeletons only (debug no-op
stubs) — see each role's README.md before implementing.
`inventory/hosts.yml` reflects the current homelab topology; update it
as hosts change.
