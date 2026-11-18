# compose_stacks

**Status: implemented (audit + opt-in pull/up/down), Option B.**

Run: `ansible-playbook playbooks/compose.yml -e '{"compose_stacks_enabled": true}' [--check]`
(the `-e` value must be JSON, a bare `true` string fails the `when`).

What it does today:
- Discovers `NN-name/NN-name.yml` under `/opt/docker-compose` on saturn, validates each project with
  `docker compose config -q` (read-only), compares defined vs running projects, and reports git state of the repo.
- Only projects listed in `compose_stacks_projects` (opt-in, with per-project pull/state) are changed, and never
  those in `compose_stacks_protected` (default `00-networks`, `00-ddns`) or ones that fail validation.
- Known state (2026-11-14): 33 defined, 31 running; `20-auto-m4b` (indentation bug fixed, not started) and
  `40-crafty` (abandoned, left alone) are the two not running.


Manages the ~29-project docker-compose media/automation stack on
`saturn` (OMV). This role is specifically about operating the many
already-running OMV-managed compose projects on saturn (start/stop,
pull+recreate on update, add/remove a project), not installing Docker
itself.

## VPN projects managed here (Proton, since 2026-11-17)

`20-qbittorrent` (gluetun_qbit + qbittorrent sharing its network namespace, forwarded port pushed into
qBittorrent by gluetun) and `20-vpn-la/co/au` (gluetun + SOCKS5 + Tailscale exit node for Los Angeles,
Denver, Stockholm) are in `compose_stacks_projects` in `inventory/group_vars/omv.yml`. They need
`PROTON_WG_PRIVATE_KEY` in saturn's `global.env`; the role fails early if it is missing
(`compose_stacks_required_global_vars`). `global.env` is OMV-managed and untracked, so set the key in
OMV (Compose > Global environment), never in this repo. The key's source of truth is the Bitwarden item
"Proton VPN WireGuard key (gluetun, saturn)"; the role (with `BW_SESSION` exported) fails if global.env
differs from it (`compose_stacks_global_env_bitwarden`). `up -d` only reports `changed` when compose
actually started/recreated/stopped something, so a second run shows `changed=0`.

### sabnzbd, arr apps and Dispatcharr (2026-11-18)

`20-sabnzbd` (gluetun_sab), `20-vpn-arr` (gluetun_arr, shared by prowlarr/sonarr/radarr/lidarr/bazarr/flaresolverr at
10.20.0.149) and `40-dispatcharr` (gluetun_dispatcharr at 10.40.0.17) follow the same pattern; the app projects
(`20-prowlarr`, `20-sonarr`, ...) use `network_mode: container:gluetun_arr`. gluetun's own DNS can't resolve other
containers, so gluetun_arr / gluetun_dispatcharr carry `extra_hosts` for the peers they need; add one when an app
must reach a new container by name. A cold start can fail once on gluetun's health wait: re-run `up -d`.
Proxy-host upstreams for these apps are enforced by the `npm` role (`npm_upstreams`).

## Two implementation options considered

**Option A — drive OMV's internal Compose RPC API directly** (`uri`
module against OMV's JSON-RPC backend: `Compose.doCommand`,
`Compose.setFile`/`deleteFile`, polling `Exec.getOutput` for async job
completion, as already documented in the homelab-infrastructure skill's
OMV reference notes). Pros: this is literally what the OMV web UI itself
calls, so behavior matches the UI exactly (project list, per-project
up/down/pull, file edits) and avoids needing SSH key provisioning beyond
what `access_control` already sets up for the `omv` host.  Cons: it's an
undocumented/internal API (session-cookie auth via `/rpc.php`, job IDs
that must be polled, no official stability guarantee across OMV
versions) — more fragile to version drift, and modeling async job polling
cleanly in Ansible tasks (register + until + retries loops) is more code
than a plain shell-out.

**Option B — SSH + `docker compose` CLI directly on saturn** (treat
saturn like any other SSH-managed host: `ansible.builtin.command`/`shell`
running `docker compose -f <project>/docker-compose.yml pull` /
`up -d`/`down` in each project's directory under OMV's
`/opt/docker-compose/<NN-name>/` convention, discovered via
`ansible.builtin.find` or an explicit project list var). Pros: simple,
uses the exact same SSH access `access_control` already provisions for
`omv`/saturn, no dependency on OMV's internal API staying stable, trivial
to reason about/debug (it's just the commands you'd type by hand over
SSH), and `docker compose` CLI output is directly idempotency-checkable
(`docker compose ps --format json`) without any OMV-specific polling
logic. Cons: changes made this way won't show up as "managed by OMV" in
its web UI compose-plugin project list in the same way a `Compose.*` RPC
call would (though OMV's compose plugin generally just execs `docker
compose` under the hood in the already-existing project directories, so
in practice this should still interoperate fine — needs confirming before
depending on it).

**Decision: Option B (SSH + `docker compose` CLI)**, pending re-confirmation
once this role is actually implemented. Reasoning: it reuses access this
repo already provisions (no new credential/API-key management), avoids
coupling to an undocumented API's stability, and is far simpler to write
correct/idempotent Ansible tasks against. Revisit if OMV's UI stops
reflecting CLI-driven changes correctly, or if finer per-project OMV
metadata (e.g. its auto-generated env/compose templates under
`/opt/docker-compose/`) turns out to need the RPC layer after all.

## Original scope notes (partly implemented, see status above)

- Per-project: `up -d` (ensure running), `down`, `pull` + recreate on
  image update, viewing `docker compose ps`/`logs` for drift detection.
- A project inventory (list of the ~29 project directory names) likely
  lives in `group_vars/omv.yml` or this role's `defaults/main.yml` once
  enumerated for real from `/opt/docker-compose/` on saturn — not guessed
  here.
- Respect the existing storage-placement lesson already captured in the
  homelab-infrastructure skill (new stateful services default to a disk
  with real headroom, never the main Array mergerfs pool) if this role
  ever creates new compose projects rather than just managing existing ones.

## Open questions

- Full enumeration of the ~29 projects and which ones are safe to
  pull/recreate unattended vs. need a maintenance window (e.g. Plex/arr
  stack active-stream awareness).
- Whether OMV's compose plugin UI needs to be told about CLI-driven
  changes (a refresh action) or just picks them up automatically next
  page load.

## Variables

See `defaults/main.yml`.
