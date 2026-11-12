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
  site.yml             Top-level playbook, imports the others below.
  access.yml           OS-level access control (users/SSH keys/sudoers) for
                        proxmox_host/lxc_guests/vm_guests/omv/windows.
  webui.yml            Per-service web UI/API account provisioning
                        (Proxmox PAM, OMV, UniFi, NPM, Home Assistant,
                        Grafana, OPNsense) - runs once from localhost,
                        driven entirely by group_vars/all.yml, not tied
                        to a specific inventory group.
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
placeholder item names in `group_vars/all.yml`. `inventory/hosts.yml`
reflects the current homelab topology; update it as hosts change.
