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
  webui.yml            Per-service web UI/API account provisioning for the
                        appliances group (OPNsense, UniFi, ...).
roles/
  access_control/       Users, SSH authorized_keys, sudoers.
  webui_identity/        Per-service account creation on app/appliance web UIs.
  common/, docker/, provision-vm/  Pre-existing roles (legacy layout, still
                        driven by the root main.yaml).
main.yaml               Legacy top-level playbook (pre-dates playbooks/;
                        kept as-is, not yet migrated).
```

## Usage

```
ansible-playbook playbooks/site.yml -i inventory/hosts.yml
# or a single domain:
ansible-playbook playbooks/access.yml -i inventory/hosts.yml
```

## Status

`access_control` and `webui_identity` are scaffolded skeletons (stub tasks)
pending the Bitwarden control-node integration and real per-host variable
values. `inventory/hosts.yml` reflects the current homelab topology; update
it as hosts change.
