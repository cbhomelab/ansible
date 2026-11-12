# access_control

Manages local OS-level access on homelab hosts: user accounts, SSH
authorized_keys, and sudoers entries.

Scope: `proxmox_host`, `lxc_guests`, `vm_guests`, `omv`, `windows` groups.
Does NOT cover `appliances` (OPNsense/UniFi) — those are managed via their
own web UIs/APIs, see `roles/webui_identity`.

## Variables (see defaults/main.yml)

- `access_control_users`: list of {name, groups, shell, ssh_authorized_keys}
- `access_control_sudoers`: list of {name, rule} sudoers.d drop-ins

Secrets (SSH public keys, if not committed in plaintext) should be sourced
from Bitwarden via `group_vars` lookups, not hardcoded here.
