# audit_log_shipping

Ships sshd (logins) and sudo (privilege use) audit events from every
in-scope Linux host into the existing central Loki/Promtail/Grafana stack
(the `90-logging` OMV compose project on saturn — see the
homelab-infrastructure skill's `references/logging-monitoring.md`).

## How it works

Reuses the syslog-ingest pattern already live for OPNsense/UniFi rather
than installing a Promtail agent on every host: each target host gets an
`rsyslog` drop-in (`/etc/rsyslog.d/60-audit-log-forward.conf`) that
forwards the `auth` and `authpriv` facilities (sshd login/failure
messages, sudo invocation messages — both are logged via these
facilities on Debian) over TCP to Promtail's existing `syslog` scrape
listener on saturn (`10.20.0.2:1514`, RFC5424/`RSYSLOG_SyslogProtocol23Format`).

No Promtail/node-exporter install needed on any host for this — that
broader agent-rollout is `roles/monitoring_agents` (scaffolded, not
implemented). This role is intentionally narrow: ssh/sudo audit only, via
the mechanism the stack already supports. If/when `monitoring_agents`
is implemented, this forwarding rule can be folded into it as a
`monitoring_agents_promtail_jobs`-style entry; until then it stands alone
per the monitoring_agents README's own note not to block this task on
that one.

Promtail's existing `syslog` scrape job already relabels
`__syslog_message_hostname` → `host` and `__syslog_message_app_name` →
`app` for every line it receives on 1514 — no promtail-config.yaml change
was needed. In Grafana/Loki, each forwarded line carries:
- `host` = the real hostname of the box that sent it (neptune, saturn,
  intranet, glance, minecraft, unifi, pihole)
- `app` = `sshd` or `sudo` (the syslog tag)
- `job` = `syslog` (shared with OPNsense/UniFi lines — filter on `app`/`host`)

## Scope

Applied to: `proxmox_host`, `lxc_guests` (minus `lxc103-hermesagent`,
excluded same as `access_control`), `lxc107-unifi` (real Debian LXC
underneath its appliance-group identity, same as `access_control`), `omv`.

Deliberately NOT applied to:
- `vm101-homeassistant` — HAOS, no shell/rsyslog surface at all.
- `vm100-opnsense` / rest of `appliances` — already forwards its own
  router syslog over the same port via its native syslog API; sshd/sudo
  on an appliance OS isn't a meaningful concept here.
- `windows`/`cb-gaming` — Windows auth events live in the Security Event
  Log, not syslog; out of scope for this role (separate follow-up if
  wanted, needs a Windows Event Log → Loki shipper, e.g. promtail's
  windows_events stage or NXLog).
- `lxc103-hermesagent` — excluded for the same "handle with care" reason
  access_control excludes it.

## Connection vars

This role's play sets `ansible_user`/`ansible_ssh_private_key_file`
directly per trust boundary (same `hermes_proxmox` / `hermes_saturn`
dedicated keypairs access_control provisioned) rather than relying on
`group_vars`, to avoid touching those files — see `playbooks/audit_logging.yml`.

## Variables (see defaults/main.yml)

- `audit_log_shipping_loki_syslog_host`: Promtail's syslog-listener host
  (saturn, `10.20.0.2`).
- `audit_log_shipping_loki_syslog_port`: `1514` (same port OPNsense/UniFi
  already forward to).
- `audit_log_shipping_rsyslog_conf_path`: drop-in file path.

## Idempotency

`ansible.builtin.copy` with fixed content — re-running reports
`changed: false` once the file matches. The handler only fires on an
actual content change, so a converged host's re-run doesn't bounce
`rsyslog`.

## Verified (2026-11-12)

- Confirmed `rsyslog` package installed + `active` on all 7 target hosts
  before writing the role (`neptune`, `intranet`, `glance`, `minecraft`,
  `unifi`, `pihole`, `saturn`).
- Confirmed Promtail's syslog listener (port 1514/tcp) is bound on
  saturn's host network (`0.0.0.0:1514`, `docker-proxy`) — reachable from
  every other host on the LAN, including saturn itself (self-forward
  works, same as an external host would see it).
- Applied the role fleet-wide and confirmed each host's forwarded `sudo`
  test event landed in Loki labeled with the correct real `host` name.
