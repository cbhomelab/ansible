# access_control

Manages local OS-level access on homelab **Linux** hosts: user accounts,
SSH `authorized_keys`, sudoers entries, and (opt-in) SSH password-auth
hardening.

Scope: `proxmox_host`, `lxc_guests`, `vm_guests`, `omv` groups.
Does NOT cover:
- `appliances` (OPNsense/UniFi) — managed via their own web UIs/APIs, see
  `roles/webui_identity`.
- `windows` — already handled by the pre-existing `christian_windows`
  SSH-key pattern; sudoers/sshd_config don't map the same way on Windows,
  so it's deliberately out of this role rather than silently half-applied.
- Service accounts (existing per-app Docker users) — explicitly out of
  scope, don't touch.

## The 3-tier model

- **christian**: exists on every in-scope host, sudo via
  `/etc/sudoers.d/christian-nopasswd` (`NOPASSWD:ALL`, can be scoped down
  later), SSH key-only, `authorized_keys` populated from christian's
  personal keypair(s).
- **hermes**: exists on every in-scope host, sudo via
  `/etc/sudoers.d/hermes-nopasswd` (`NOPASSWD:ALL` for now, confirmed by
  user), SSH key-only, with a **separate dedicated keypair per logical
  trust boundary** rather than one key everywhere:
  - `~/.ssh/hermes_proxmox` — proxmox_host + lxc_guests + vm_guests (all on
    neptune, same trust zone)
  - `~/.ssh/hermes_saturn` — omv (saturn)
  - mirrors the existing pattern already used for Windows CB-GAMING
    (`~/.ssh/christian_windows`, alias `windows-christian`)
  - Private keys live ONLY on the Hermes host, never committed to this repo.
- **SSH password auth**: disabled host-by-host only once keys are
  confirmed working, via `access_control_disable_password_auth: true` in
  that group's/host's vars. Defaults to `false` everywhere so it can never
  be flipped on by accident before key auth is verified.

## Variables (see defaults/main.yml)

- `access_control_groups`: list of `{name, gid, system}`
- `access_control_users`: list of `{name, groups, shell, uid, system,
  create_home, ssh_authorized_keys, ssh_exclusive}`
- `access_control_sudoers`: list of `{name, rule}` — always written to
  `/etc/sudoers.d/<name>-nopasswd` regardless of the rule text, so scoping
  a rule down later overwrites the same file instead of leaving an
  orphaned drop-in.
- `access_control_disable_password_auth`: bool, default `false`. Set to
  `true` per group/host once key-based login is verified for every account.

## Secrets / Bitwarden migration status

- `christian`'s `ssh_authorized_keys` already reference the
  `community.general.bitwarden` lookup (`homelab-ssh-christian`). This will
  fail until task **t_eab3e60d** (Bitwarden secrets backend) is unblocked —
  that task is currently `blocked/needs_input` waiting on the user to do
  org/API-key/master-password setup in the Bitwarden web UI.
- `hermes`'s public keys are plain values in `group_vars/*.yml` for now
  (marked `TODO(bitwarden-migration)` at each site) since there's no
  working secrets backend yet. Once t_eab3e60d lands, move these to
  Bitwarden lookups and delete the plaintext pubkeys from group_vars —
  pubkeys aren't sensitive on their own, but centralizing them in Bitwarden
  keeps one rotation story for the whole fleet.

## Idempotency

Every task in this role is a native Ansible module (`user`, `group`,
`ansible.posix.authorized_key`, `copy` with `validate`, `lineinfile`) —
running the role twice against an already-converged host reports zero
changes. The sudoers filename convention (fixed per-user, not per-rule-text)
and the `exclusive` authorized_keys flag (opt-in per user, off by default)
are both chosen specifically to keep repeated runs idempotent rather than
accumulating drop-ins or keys.
