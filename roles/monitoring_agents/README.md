# monitoring_agents

**Status: implemented (Promtail applogs on LXC guests + node_exporter metrics on guests and saturn).**

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

## Prometheus / node-exporter (t_299916fe, user approved)

- **node_exporter** 1.8.2 (pinned tarball, sha256-checked, systemd unit
  `node_exporter`, runs as user `node_exporter`) on lxc102/104/105/107/108
  and saturn, listening **only** on the host's MGMT address
  (`{{ ansible_host }}:9100`). Toggle: `monitoring_agents_node_exporter_enabled`.
  Idempotent (second run changed=0), check-mode safe. `playbooks/monitoring.yml`
  now also targets `omv`; saturn has no Promtail jobs so it only gets
  node_exporter. **Excluded:** `proxmox_host` (neptune, hands-off by user
  decision) and lxc103.
- **Prometheus** v3.0.1 is NOT part of this role: it is a separate OMV Compose
  project `90-metrics` on saturn (own file so the live `90-logging` project
  is never rewritten). Docker `docker` bridge network (a macvlan container
  could not scrape saturn's own :9100), UI `http://10.20.0.2:9090`, 30d
  retention, scrape config `<appdata>/prometheus/config/prometheus.yml`
  (static targets; keep in sync with inventory, then
  `curl -X POST http://10.20.0.2:9090/-/reload`).
- **Grafana**: datasource `Prometheus` (uid `prometheus`,
  `http://prometheus:9090`; provisioning file `prometheus.yaml` + API) and
  dashboard *Node Exporter Full* (grafana.com 1860).
- **Rollback:** `ansible-playbook playbooks/monitoring.yml --tags node_exporter`
  with the enabled flag false does NOT uninstall; to remove, `systemctl
  disable --now node_exporter` and delete the unit/binary. For Prometheus:
  OMV Compose `down` + `deleteFile` on project `90-metrics`; delete the
  Grafana datasource.
- **Neptune metrics: IMPLEMENTED (t_03920b33, 2026-11-13, user approved).**
  `prometheus-pve-exporter` (`prompve/prometheus-pve-exporter:3.11.0`)
  runs as service `pve-exporter` in the `90-metrics` compose project on
  saturn (docker bridge net, :9221 not published; Prometheus reaches it as
  `pve-exporter:9221`). Nothing is installed on neptune. Auth is a dedicated
  Proxmox user `prometheus@pve` + API token `exporter` (privsep=1), role
  built-in `PVEAuditor` at `/` granted to BOTH the user and the token
  (privsep tokens need their own ACL). Secret lives in Bitwarden
  (Homelab-Infra / `proxmox-prometheus-exporter`) and in a chmod 600 file
  `<APPDATA_DIR>/pve-exporter/pve.yml` on saturn (`verify_ssl: false`,
  neptune's cert is self-signed) -- never in compose or git. Scrape job `pve`
  (`/pve`, target 10.20.0.6, label host=neptune) in
  `<APPDATA_DIR>/prometheus/config/prometheus.yml`, applied with
  `POST :9090/-/reload`. Grafana dashboard "Proxmox via Prometheus"
  (grafana.com 10347, uid Dp7Cd57Zza) against datasource `prometheus`.
  Not Ansible-managed yet (hand-built via OMV RPC/ssh).
  **Rollback:** on neptune `pveum user token remove prometheus@pve exporter`
  ; `pveum acl delete / --users prometheus@pve --roles PVEAuditor` ;
  `pveum user delete prometheus@pve` (self-created objects only). On saturn
  remove the `pve-exporter` service from the 90-metrics compose (OMV
  Compose setFile + `up`), delete `appdata/pve-exporter`, remove the `pve`
  job from prometheus.yml and reload (backups: `/root/backups/t_03920b33/`),
  delete the Grafana dashboard and the Bitwarden item.

## Relationship to audit_log_shipping (t_d72f45fd)

`audit_log_shipping` ships ssh/sudo via rsyslog and does not need Promtail
on guests. If it later moves to Promtail jobs, add `monitoring_agents` as a
role dependency and express its sources as `monitoring_agents_promtail_jobs`
entries (use a different `job_label` to keep the `job=syslog` stream unchanged).
