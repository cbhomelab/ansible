# backup

**Status: scaffolded, not implemented.**

**No backup strategy is assumed to exist yet.** This role is a deliberate
placeholder with open questions rather than a guessed implementation —
do not fill in real backup logic without first getting answers from the
user to the questions below.

## Open questions (must be answered before real implementation)

- **What gets backed up?** Candidates, none confirmed yet: Proxmox
  VM/LXC config + disk snapshots (`vzdump`?), OMV appdata/config
  directories (per-compose-project persistent volumes), Ansible
  control-node state (this repo is already in git, so that's covered
  separately), Home Assistant config, the Frigate config git repo
  (already covered — see `cbhomelab/frigate` on GitHub), Bitwarden vault
  (external SaaS, likely out of scope here), Pi-hole config, UniFi/OPNsense
  config exports.
- **Where to?** Candidates: a second disk on saturn (which one — check
  real headroom first per the storage-placement lesson already captured
  in the logging-monitoring reference, don't default onto the Array
  mergerfs pool), off-site/cloud target (none configured currently?),
  another host entirely for 3-2-1 redundancy.
- **Retention?** No policy decided. Needs a number (days/weeks/versions)
  per backup target, not a single fleet-wide default — a compose
  project's appdata and a Proxmox VM snapshot likely warrant very
  different retention.
- **Mechanism?** Candidates: `vzdump` (Proxmox-native, handles VM/LXC
  backups to a Proxmox storage target), `restic`/`borg` (file-level,
  dedup+encryption, works well for OMV appdata directories), plain
  `rsync`/`tar` snapshots (simplest, no dedup). Not decided — depends on
  answers above.
- **Verification/alerting?** How will a failed or silently-corrupt backup
  be noticed? (Could eventually tie into `roles/monitoring_agents` once
  that exists, rather than inventing a separate notification path.)

## Intended scope once answered

A per-target backup task set (likely one task file per mechanism: Proxmox
`vzdump`, OMV appdata via restic/borg, config-export jobs for
Pi-hole/UniFi/OPNsense) driven by a `backup_targets` variable listing
what/where/retention per item — structure to be finalized once the open
questions above have real answers, not guessed now.

## Variables

See `defaults/main.yml` — intentionally empty/disabled.
