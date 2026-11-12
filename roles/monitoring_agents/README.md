# monitoring_agents

**Status: scaffolded, not implemented.**

General-purpose fleet-wide monitoring-agent installer: rolls out
Promtail and node-exporter to every manageable host, feeding the existing
central Loki/Grafana stack (see the homelab-infrastructure skill's
`references/logging-monitoring.md` for the real deployment/relabeling
details already learned for that stack).

## Relationship to the audit-logging task (t_d72f45fd)

This role is **broader** than t_d72f45fd, which only ships ssh/sudo audit
logs. `monitoring_agents` is meant to be the general-purpose agent
installer (Promtail for logs, node-exporter for metrics) that
t_d72f45fd — and any future per-domain log-shipping need — should
eventually depend on/reuse rather than each task hand-rolling its own
installer. Don't duplicate t_d72f45fd's work here; when this role is
implemented, t_d72f45fd's audit-log shipping should become a
`monitoring_agents_promtail_jobs` entry (or similar) layered on top of
the base agent install, not a separate installation path.

## Intended scope (not yet implemented)

- Promtail: install as a container (preferred, consistent with the rest
  of the compose fleet) or system package per host type; configure
  `docker_sd_configs` service discovery for Docker-hosted log sources
  (per the logging-monitoring reference) and/or static scrape config for
  non-Docker hosts (bare LXC/VM syslog, journald).
- node-exporter: container or systemd service per host, scraped by the
  existing Prometheus/Grafana stack (verify which metrics backend is
  actually in place before assuming Prometheus specifically — needs
  confirming).
- Host coverage: `proxmox_host`, `lxc_guests`, `vm_guests`, `omv`. Explicitly
  NOT `appliances` (OPNsense/UniFi — see the logging-monitoring reference's
  notes on OPNsense's native syslog-forwarding API being the right
  mechanism there instead) and NOT HAOS (`vm101-homeassistant` — immutable
  appliance OS, no shell; see the reference's HAOS-specific
  WebSocket-based log-shipping workaround, which is a separate mechanism
  entirely, not something this role's generic agent install can reach).
- Windows (`cb-gaming`) coverage is an open question (see below).

## Open questions

- What metrics backend is actually running today (Prometheus? Something
  else?) — confirm before writing node-exporter scrape-config wiring.
- Does `cb-gaming` (Windows) get a monitoring agent at all, and if so
  which one (Windows doesn't have Promtail/node-exporter in the same
  Linux-native form)?
- Should this role deploy Promtail/node-exporter as yet more entries in
  the OMV compose fleet (via `roles/compose_stacks` once that exists) for
  saturn specifically, vs. a systemd-managed binary on the Proxmox
  host/LXC/VM guests? Likely different answers per host type — don't
  assume one mechanism fits all hosts.

## Variables

See `defaults/main.yml`.
