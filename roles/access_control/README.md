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

## Fleet rollout status (t_6fe4b6c0, 2026-11-12)

`hermes` + sudo is live and SSH-key-verified (idempotent re-run = zero
changes) on: `neptune` (proxmox_host), `lxc102-intranet`, `lxc104-glance`,
`lxc105-minecraft`, `lxc107-unifi`, `lxc108-pihole`, `saturn` (omv).

`christian`'s account/sudoers also exist on all of the above, but his
`ssh_authorized_keys` resolve to an **empty list** everywhere — gated by
`access_control_christian_key_ready: false` in `inventory/group_vars/all.yml`
— because his real SSH pubkey is still not available (no Bitwarden
`homelab-ssh-christian` item, no user-supplied key). Flip that var to
`true` (and populate the Bitwarden item, or hardcode the key temporarily)
once it's supplied, re-run `playbooks/access.yml`, confirm christian's key
login on every host, and only then set `access_control_disable_password_auth:
true` per group/host — never before both accounts' key logins are verified
on that specific host.

Special-cased / out of scope for this role:
- `vm101-homeassistant` — genuine Home Assistant OS (HAOS), an immutable
  supervisor-managed appliance with no useradd/sudoers/sshd_config in the
  normal Linux sense (confirmed: SSH & Terminal add-on's port 22222 is
  closed, qemu-guest-agent only reports loopback). Identity here goes
  through the HA web UI / `roles/webui_identity`'s documented manual step.
- `vm100-opnsense` — BSD-based, API-managed only; see the webui_identity
  task's OPNsense handling.
- `lxc103-hermesagent` (this control node) — deliberately excluded from
  the fleet-rollout scope ("handle with care"); self-modifying the control
  node's own users/sudoers/sshd is tracked as separate follow-up work.
- `windows`/`cb-gaming` — not run through this role at all (no
  sudoers/sshd_config equivalent on Windows). Instead: christian's existing
  `~/.ssh/christian_windows` key (alias `windows-christian`) was confirmed
  working, and a **separate** `~/.ssh/hermes_windows` keypair was generated
  and appended to `C:/ProgramData/ssh/administrators_authorized_keys`
  (verified working as `christian_windows` and `hermes_windows` are
  independently rotatable). Note there is no distinct "hermes" Windows OS
  account on this single-admin-account PC — both keys authenticate into
  the same local admin account by Windows OpenSSH's admin-key-auth design;
  separation here is key-only, not account-only. A `windows-hermes` SSH
  config alias (mirroring `windows-christian`) was intended but blocked:
  writes to `~/.ssh/config` need interactive approval that single-query
  sessions don't have — add it manually:
  ```
  Host windows-hermes
      HostName 10.10.0.17
      User christian
      IdentityFile ~/.ssh/hermes_windows
      StrictHostKeyChecking accept-new
  ```

Structural fixes made along the way:
- `group_vars/` was moved to `inventory/group_vars/` — Ansible only
  auto-loads `group_vars`/`host_vars` beside the inventory file or beside
  the playbook being run, and this repo's playbooks live under
  `playbooks/` while the inventory lives under `inventory/`, so a
  repo-root `group_vars/` was silently never loaded by `ansible-playbook`
  (it only "worked" via bare `ansible host -m ...` ad-hoc commands run
  from the repo root, which use cwd as the search base — that masked the
  bug until this rollout ran the actual playbook and got `length() == 0`
  across the board).
- `.gitignore` had a blanket `host_vars` entry that silently excluded
  `inventory/host_vars/` (needed for the lxc107-unifi override) from
  version control — narrowed to just `hosts.yaml`.
- `inventory/hosts.yml`'s LXC `ansible_host` IPs were stale static
  guesses; replaced with the real DHCP-assigned addresses (confirmed via
  `pct exec <id> -- hostname -I` on neptune) since these containers don't
  have static IPs despite the original inventory's naming convention.
- `lxc107-unifi` sits in the `appliances` inventory group for
  `webui_identity` purposes but is a real Debian LXC underneath; added
  `inventory/host_vars/lxc107-unifi.yml` to override `ansible_connection`
  back to `ssh` and supply the proxmox-boundary access vars, and added it
  explicitly to `playbooks/access.yml`'s `hosts:` line.
- `sudo` wasn't installed at all on `lxc105-minecraft`, `lxc107-unifi`, or
  `neptune` itself (minimal images / bare PVE host) — installed manually
  before the sudoers task would succeed; the role doesn't install the
  `sudo` package itself, so a genuinely minimal future host will need the
  same manual step (or a follow-up task to add that as a role
  pre-requisite).
