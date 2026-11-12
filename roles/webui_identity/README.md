# webui_identity

Manages per-service account creation/identity for homelab web UIs and
appliance APIs that aren't plain OS accounts — e.g. OPNsense, UniFi
Controller, OMV web UI, Proxmox API users/tokens, and self-hosted app
admin accounts (Plex, Jellyfin, arr-stack, Frigate, etc).

Unlike `access_control`, this role mostly drives REST APIs (`ansible.builtin.uri`,
community modules) rather than SSH shell tasks, since appliances in the
`appliances` inventory group have no generic SSH access.

## Variables (see defaults/main.yml)

- `webui_identity_accounts`: list of {service, username, role, api_base_url}

Credentials should come from Bitwarden via `group_vars` lookups.
