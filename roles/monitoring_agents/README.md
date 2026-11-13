# monitoring_agents

**Status: implemented (Promtail applogs on LXC guests). Metrics: not implemented, by decision.**

Installs Promtail (pinned Debian package, systemd) on LXC guests and ships
**file-based application logs** straight to Loki. It is deliberately
complementary to what already exists:

| Source | Shipped by | Labels |
|---|---|---|
| journald/syslog/sshd/sudo on every guest + saturn | rsyslog `90-loki-forward.conf` -> saturn:1514 (Promtail syslog listener), i.e. `audit_log_shipping` | `job=syslog, host, app, severity, facility` |
| Docker container logs on saturn | Promtail container (`grafana/promtail:3.3.2`, docker_sd) | `compose_project, compose_service, container` |
| **File app logs on LXC guests (this role)** | Promtail systemd service -> Loki push API | `job=applogs, host, app` (+ `filename`) |

`host` is the short hostname, same as the syslog stream, so you can join
`{job="syslog",host="X"}` and `{job="applogs",host="X"}`.

## Scope

- Hosts: `lxc_guests` + `lxc107-unifi`, minus `lxc103-hermesagent` (see `playbooks/monitoring.yml`).
- **Excluded:** `proxmox_host` (hands-off, user decision), `omv`/saturn (has Promtail), HAOS, appliances.
- A host with an empty `monitoring_agents_promtail_jobs` is a no-op (e.g. lxc104-glance has no app logs outside syslog).
- journald is **not** scraped (would double-ship what rsyslog already sends).

Current jobs (host_vars): lxc102 NPM `npm-access`/`npm-error`; lxc105
`minecraft-server`/`minecraft-proxy` (promtail runs as `minecraft` because
`/var/lib/minecraft` is 0700); lxc107 `unifi-server` (group `unifi`);
lxc108 `pihole-dns`/`pihole-ftl` (group `pihole`).

## Loki endpoint

`http://10.20.0.160:3100/loki/api/v1/push`. Loki has its own address on
`mgmt_bridge`; port 3100 is **not** published on saturn's host IP
(10.20.0.2:3100 is closed). Reachability verified from all guests.

## Usage

```
ansible-playbook playbooks/monitoring.yml --check --diff
ansible-playbook playbooks/monitoring.yml --limit lxc105-minecraft
ansible-playbook playbooks/monitoring.yml --tags promtail
```

Idempotent (second run: changed=0). Check-mode safe; where Promtail is not
installed yet, config/service steps are skipped or tolerated in `--check`.

Add a log source: append `{app, paths: [globs]}` to the host's
`monitoring_agents_promtail_jobs`; grant read access via
`monitoring_agents_promtail_supplementary_groups` (or the `_user` override).
Verify: `curl -G http://10.20.0.160:3100/loki/api/v1/series --data-urlencode 'match[]={job="applogs"}'`.

## Gotchas

- The promtail deb creates user `promtail` with primary group `nogroup`
  (no `promtail` group), hence `monitoring_agents_promtail_group: nogroup`.
- First start on an existing log seeks from offset 0 (backfills the current file).

## Prometheus / node-exporter finding

**No Prometheus exists.** saturn's monitoring containers are only
`promtail`, `loki`, `grafana`; no prometheus, node-exporter or cadvisor.
Nothing metrics-related was installed and the scaffold's
`node_exporter_enabled` variable was removed. Adding metrics
(Prometheus + node-exporter) is a separate decision.

## Relationship to audit_log_shipping (t_d72f45fd)

`audit_log_shipping` ships ssh/sudo via rsyslog and does not need Promtail
on guests. If it later moves to Promtail jobs, add `monitoring_agents` as a
role dependency and express its sources as `monitoring_agents_promtail_jobs`
entries (use a different `job_label` to keep the `job=syslog` stream unchanged).
