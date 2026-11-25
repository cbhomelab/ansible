#!/usr/bin/env python3
"""Generates the provisioned Grafana dashboards into ../files/*.json.
Run: python3 gen.py   (then re-run playbooks/grafana-dashboards.yml)."""
import json, os

PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "P8E80F9AEF21F6940"}
OUT = os.path.join(os.path.dirname(__file__), "..", "files")


class D:
    def __init__(self, uid, title, tags, variables=None, refresh="30s"):
        self.uid, self.title, self.tags = uid, title, tags
        self.vars = variables or []
        self.panels = []
        self.y = 0
        self.x = 0
        self.refresh = refresh
        self.id = 1

    def row(self, title):
        self._newline()
        self.panels.append({"type": "row", "title": title, "id": self._id(), "collapsed": False,
                            "gridPos": {"h": 1, "w": 24, "x": 0, "y": self.y}, "panels": []})
        self.y += 1

    def _id(self):
        self.id += 1
        return self.id

    def _newline(self):
        if self.x:
            self.x = 0
            self.y += self._lasth

    def _place(self, w, h):
        if self.x + w > 24:
            self._newline()
        pos = {"h": h, "w": w, "x": self.x, "y": self.y}
        self.x += w
        self._lasth = h
        if self.x >= 24:
            self.x = 0
            self.y += h
        return pos

    def _p(self, kind, title, targets, w, h, ds, unit=None, extra=None, opts=None, desc=None):
        p = {"id": self._id(), "type": kind, "title": title, "datasource": ds, "targets": targets,
             "gridPos": self._place(w, h),
             "fieldConfig": {"defaults": {"unit": unit} if unit else {}, "overrides": []},
             "options": opts or {}}
        if desc:
            p["description"] = desc
        if extra:
            for k, v in extra.items():
                if k == "defaults":
                    p["fieldConfig"]["defaults"].update(v)
                elif k == "overrides":
                    p["fieldConfig"]["overrides"] = v
                else:
                    p[k] = v
        self.panels.append(p)

    @staticmethod
    def pt(expr, legend="", instant=False, fmt=None):
        t = {"expr": expr, "legendFormat": legend, "refId": "A", "datasource": PROM}
        if instant:
            t["instant"] = True
        if fmt:
            t["format"] = fmt
        return t

    @staticmethod
    def lt(expr, legend="", logs=False):
        t = {"expr": expr, "refId": "A", "datasource": LOKI, "legendFormat": legend}
        if not logs:
            t["queryType"] = "range"
        return t

    def ts(self, title, exprs, unit=None, w=12, h=8, stack=False, desc=None, ds=PROM, min0=True):
        tg = []
        for i, (e, l) in enumerate(exprs):
            t = (self.pt if ds == PROM else self.lt)(e, l)
            t["refId"] = chr(65 + i)
            tg.append(t)
        d = {"custom": {"fillOpacity": 15 if stack else 10, "lineWidth": 1,
                        "stacking": {"mode": "normal" if stack else "none"}}}
        if min0:
            d["min"] = 0
        self._p("timeseries", title, tg, w, h, ds, unit, {"defaults": d}, {
            "legend": {"displayMode": "table", "placement": "bottom", "calcs": ["mean", "max"]},
            "tooltip": {"mode": "multi", "sort": "desc"}}, desc)

    def stat(self, title, expr, unit=None, w=4, h=4, thresholds=None, mappings=None, instant=True, desc=None, color_bg=False):
        d = {}
        if thresholds:
            d["thresholds"] = {"mode": "absolute", "steps": thresholds}
            d["color"] = {"mode": "thresholds"}
        if mappings:
            d["mappings"] = mappings
        self._p("stat", title, [self.pt(expr, "", instant)], w, h, PROM, unit, {"defaults": d}, {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "background" if color_bg else "value", "graphMode": "area" if not instant else "none"}, desc)

    def gauge(self, title, expr, unit="percent", w=4, h=5, mx=100, thresholds=None):
        d = {"min": 0, "max": mx, "thresholds": {"mode": "absolute", "steps": thresholds or [
            {"color": "green", "value": None}, {"color": "orange", "value": 70}, {"color": "red", "value": 90}]}}
        self._p("gauge", title, [self.pt(expr, "", True)], w, h, PROM, unit, {"defaults": d}, {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}})

    def table(self, title, exprs, w=24, h=8, unit=None, overrides=None, rename=None):
        tg = []
        for i, (e, l) in enumerate(exprs):
            t = self.pt(e, l, True, "table")
            t["refId"] = chr(65 + i)
            tg.append(t)
        tr = [{"id": "merge", "options": {}}]
        if rename:
            tr.append({"id": "organize", "options": {"excludeByName": rename.get("exclude", {}),
                                                    "renameByName": rename.get("rename", {})}})
        self._p("table", title, tg, w, h, PROM, unit, {"overrides": overrides or [], "transformations": tr},
                {"showHeader": True, "sortBy": rename.get("sort", []) if rename else []})
        self.panels[-1]["transformations"] = tr

    def logs(self, title, expr, w=24, h=10, desc=None):
        self._p("logs", title, [self.lt(expr, "", True)], w, h, LOKI, None, None, {
            "showTime": True, "wrapLogMessage": True, "sortOrder": "Descending", "enableLogDetails": True,
            "dedupStrategy": "none"}, desc)

    def build(self):
        self._newline()
        return {"uid": self.uid, "title": self.title, "tags": self.tags, "timezone": "browser", "schemaVersion": 39,
                "version": 1, "refresh": self.refresh, "time": {"from": "now-6h", "to": "now"},
                "editable": True, "graphTooltip": 1,
                "templating": {"list": self.vars}, "panels": self.panels,
                "annotations": {"list": []}}

    def save(self):
        with open(os.path.join(OUT, self.uid + ".json"), "w") as f:
            json.dump(self.build(), f, indent=1)
            f.write("\n")


def var_query(name, label, query, multi=True, include_all=True, ds=PROM, regex=None):
    v = {"name": name, "label": label, "type": "query", "datasource": ds, "query": {"query": query, "refId": "v"},
         "refresh": 2, "multi": multi, "includeAll": include_all, "sort": 1,
         "current": {"selected": True, "text": "All", "value": "$__all"} if include_all else {}}
    if ds == PROM:
        v["definition"] = query
    if regex:
        v["regex"] = regex
    if include_all:
        v["allValue"] = ".+"
    return v


GREEN_RED = [{"color": "red", "value": None}, {"color": "green", "value": 1}]
UPDOWN = [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}, "1": {"text": "UP", "color": "green"}}}]
OKBAD = [{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 10}]
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- iRacing Team Manager
cl = 'name=~"iracing-tms-$env(-db|-mumble|-pg-exporter)?"'
d = D("iracing-tms", "iRacing Team Manager", ["iracing", "apps"], [
    {"name": "env", "label": "Environment", "type": "custom", "multi": False, "includeAll": False,
     "query": "prod,dev", "current": {"text": "prod", "value": "prod"}, "options": []},
])
app = 'name="iracing-tms-$env"'
db = 'name="iracing-tms-$env-db"'
pgx = 'instance_name="iracing-tms-$env"'
d.row("Health")
d.stat("App", f'time() - container_last_seen{{{app}}} < bool 60', w=4, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Database", f'time() - container_last_seen{{{db}}} < bool 60', w=4, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Postgres reachable (pg_up)", f'pg_up{{{pgx}}}', w=4, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("App uptime", f'time() - container_start_time_seconds{{{app}}}', unit="s", w=4)
d.stat("Errors in logs (1h)", f'sum(count_over_time({{container="iracing-tms-$env"}} |~ "(?i)(error|exception|traceback|critical)" [1h]))'.replace('sum(', 'sum(') , w=4, thresholds=OKBAD) if False else None
# Loki stat panel
d._p("stat", "Error log lines (1h)", [d.lt('sum(count_over_time({container="iracing-tms-$env"} |~ "(?i)(error|exception|traceback|critical)" [1h]))')], 4, 4, LOKI, None,
     {"defaults": {"thresholds": {"mode": "absolute", "steps": OKBAD}, "color": {"mode": "thresholds"}, "noValue": "0"}},
     {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background", "graphMode": "none"})
d.stat("Restarts (24h)", f'changes(container_start_time_seconds{{{app}}}[24h])', w=4, thresholds=OKBAD)
d.row("App container")
d.ts("CPU (cores)", [(f'sum by(name)(rate(container_cpu_usage_seconds_total{{{cl}}}[5m]))', "{{name}}")], unit="short")
d.ts("Memory (working set)", [(f'container_memory_working_set_bytes{{{cl}}}', "{{name}}")], unit="bytes")
d.ts("Network", [(f'sum by(name)(rate(container_network_receive_bytes_total{{{cl}}}[5m]))', "rx {{name}}"),
                  (f'-sum by(name)(rate(container_network_transmit_bytes_total{{{cl}}}[5m]))', "tx {{name}}")], unit="Bps", min0=False)
d.ts("Disk IO", [(f'sum by(name)(rate(container_fs_reads_bytes_total{{{cl}}}[5m]))', "read {{name}}"),
                  (f'sum by(name)(rate(container_fs_writes_bytes_total{{{cl}}}[5m]))', "write {{name}}")], unit="Bps")
d.row("PostgreSQL")
d.ts("Connections", [(f'sum by(datname)(pg_stat_database_numbackends{{{pgx}}})', "{{datname}}"),
                      (f'sum(pg_stat_activity_count{{{pgx}}})', "all sessions")], unit="short")
d.ts("Database size", [(f'pg_database_size_bytes{{{pgx},datname!~"template.*|postgres"}}', "{{datname}}")], unit="bytes")
d.ts("Transactions / s", [(f'sum(rate(pg_stat_database_xact_commit{{{pgx}}}[5m]))', "commit"),
                           (f'sum(rate(pg_stat_database_xact_rollback{{{pgx}}}[5m]))', "rollback")], unit="ops")
d.ts("Cache hit ratio", [(f'sum(rate(pg_stat_database_blks_hit{{{pgx}}}[5m])) / (sum(rate(pg_stat_database_blks_hit{{{pgx}}}[5m])) + sum(rate(pg_stat_database_blks_read{{{pgx}}}[5m])))', "hit ratio")], unit="percentunit")
d.ts("Tuples / s", [(f'sum(rate(pg_stat_database_tup_returned{{{pgx}}}[5m]))', "returned"),
                     (f'sum(rate(pg_stat_database_tup_fetched{{{pgx}}}[5m]))', "fetched"),
                     (f'sum(rate(pg_stat_database_tup_inserted{{{pgx}}}[5m]))', "inserted"),
                     (f'sum(rate(pg_stat_database_tup_updated{{{pgx}}}[5m]))', "updated"),
                     (f'sum(rate(pg_stat_database_tup_deleted{{{pgx}}}[5m]))', "deleted")], unit="ops")
d.ts("Locks / deadlocks / dead tuples", [(f'sum(pg_locks_count{{{pgx}}})', "locks"),
                                          (f'sum(increase(pg_stat_database_deadlocks{{{pgx}}}[5m]))', "deadlocks (5m)"),
                                          (f'sum(pg_stat_user_tables_n_dead_tup{{{pgx}}})', "dead tuples")], unit="short")
d.table("Largest tables", [(f'topk(15, pg_stat_user_tables_size_bytes{{{pgx}}})', ""), ], h=7, unit="bytes",
        rename={"exclude": {"Time": True, "__name__": True, "env": True, "host": True, "instance": True, "job": True, "instance_name": True, "datname": True},
                "rename": {"relname": "Table", "schemaname": "Schema", "Value": "Size"}})
d.row("Logs")
d.ts("Log volume by level (app)", [(f'sum by(level)(count_over_time({{container="iracing-tms-$env"}} | detected_level != "" [5m]))', "{{level}}")], ds=LOKI, stack=True, w=12, h=7)
d.ts("Error lines (app + db)", [(f'sum by(container)(count_over_time({{container=~"iracing-tms-$env(-db)?"}} |~ "(?i)(error|exception|traceback|fatal|critical)" [5m]))', "{{container}}")], ds=LOKI, stack=True, w=12, h=7)
d.logs("App errors / warnings", '{container="iracing-tms-$env"} |~ "(?i)(error|exception|traceback|warn|critical)"', h=9)
d.logs("App log (all)", '{container="iracing-tms-$env"}', h=10)
d.logs("Database log", '{container="iracing-tms-$env-db"}', h=7)
d.save()

# ---------------------------------------------------------------- Media servers & arr
media = "plex|jellyfin|tautulli|seerr|sonarr|radarr|lidarr|bazarr|prowlarr|whisparr|huntarr-.*|lidarr-hunter|sabnzbd|qbittorrent|gluetun.*|tdarr.*|tidarr|aurral|tunarr|dispatcharr|ytdl-sub|flaresolverr|romm|stash|socks5_.*"
d = D("media-arr", "Media Servers & Arr Stack", ["media", "arr", "saturn"], [
    var_query("container", "Container", f'label_values(container_last_seen{{name=~"{media}"}}, name)'),
])
sel = 'name=~"$container"'
m = f'name=~"{media}"'
d.row("Status")
d.stat("Plex", 'time() - container_last_seen{name="plex"} < bool 60', w=3, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Jellyfin", 'time() - container_last_seen{name="jellyfin"} < bool 60', w=3, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Sonarr", 'time() - container_last_seen{name="sonarr"} < bool 60', w=3, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Radarr", 'time() - container_last_seen{name="radarr"} < bool 60', w=3, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Prowlarr", 'time() - container_last_seen{name="prowlarr"} < bool 60', w=3, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Downloaders", 'count(time() - container_last_seen{name=~"sabnzbd|qbittorrent"} < 60)', w=3, thresholds=GREEN_RED, color_bg=True, desc="Number of downloader containers (sabnzbd, qbittorrent) running")
d.stat("Containers running", f'count(time() - container_last_seen{{{m}}} < 60)', w=3)
d.stat("Restarts (24h)", f'sum(changes(container_start_time_seconds{{{m}}}[24h]))', w=3, thresholds=OKBAD)
d.row("Plex / Jellyfin")
pj = 'name=~"plex|jellyfin|tautulli"'
d.ts("CPU (cores)", [(f'sum by(name)(rate(container_cpu_usage_seconds_total{{{pj}}}[5m]))', "{{name}}")], unit="short", w=8)
d.ts("Memory", [(f'container_memory_working_set_bytes{{{pj}}}', "{{name}}")], unit="bytes", w=8)
d.ts("Network (streaming egress = tx)", [(f'sum by(name)(rate(container_network_transmit_bytes_total{{{pj}}}[5m]))', "tx {{name}}"),
                                         (f'sum by(name)(rate(container_network_receive_bytes_total{{{pj}}}[5m]))', "rx {{name}}")], unit="Bps", w=8)
d.row("Arr stack & downloaders")
d.ts("CPU (cores)", [(f'sum by(name)(rate(container_cpu_usage_seconds_total{{{sel},{m}}}[5m]))', "{{name}}")], unit="short")
d.ts("Memory", [(f'container_memory_working_set_bytes{{{sel},{m}}}', "{{name}}")], unit="bytes")
d.ts("Network rx", [(f'sum by(name)(rate(container_network_receive_bytes_total{{{sel},{m}}}[5m]))', "{{name}}")], unit="Bps")
d.ts("Disk write", [(f'sum by(name)(rate(container_fs_writes_bytes_total{{{sel},{m}}}[5m]))', "{{name}}")], unit="Bps")
d.row("Transcoding (Tdarr)")
td = 'name=~"tdarr.*"'
d.ts("Tdarr CPU (cores)", [(f'sum by(name)(rate(container_cpu_usage_seconds_total{{{td}}}[5m]))', "{{name}}")], unit="short", w=8)
d.ts("Tdarr memory", [(f'container_memory_working_set_bytes{{{td}}}', "{{name}}")], unit="bytes", w=8)
d.ts("Tdarr disk IO", [(f'sum by(name)(rate(container_fs_reads_bytes_total{{{td}}}[5m]))', "read {{name}}"),
                       (f'sum by(name)(rate(container_fs_writes_bytes_total{{{td}}}[5m]))', "write {{name}}")], unit="Bps", w=8)
d.row("saturn host")
d.gauge("CPU", '100 - avg(rate(node_cpu_seconds_total{instance="10.20.0.2:9100",mode="idle"}[5m])) * 100', w=4)
d.gauge("Memory", '100 * (1 - node_memory_MemAvailable_bytes{instance="10.20.0.2:9100"} / node_memory_MemTotal_bytes{instance="10.20.0.2:9100"})', w=4)
d.gauge("Array (mergerfs) used", '100 * (1 - node_filesystem_avail_bytes{instance="10.20.0.2:9100",mountpoint="/srv/mergerfs/Array"} / node_filesystem_size_bytes{instance="10.20.0.2:9100",mountpoint="/srv/mergerfs/Array"})', w=4,
        thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 85}, {"color": "red", "value": 95}])
d.gauge("Appdata disk used", '100 * (1 - node_filesystem_avail_bytes{instance="10.20.0.2:9100",mountpoint=~"/srv/dev-disk-by-uuid-f09af9c4.*"} / node_filesystem_size_bytes{instance="10.20.0.2:9100",mountpoint=~"/srv/dev-disk-by-uuid-f09af9c4.*"})', w=4)
d.gauge("Root disk used", '100 * (1 - node_filesystem_avail_bytes{instance="10.20.0.2:9100",mountpoint="/"} / node_filesystem_size_bytes{instance="10.20.0.2:9100",mountpoint="/"})', w=4)
d.stat("Load (5m)", 'node_load5{instance="10.20.0.2:9100"}', w=4, h=5)
d.ts("Data disks usage", [('100 * (1 - node_filesystem_avail_bytes{instance="10.20.0.2:9100",fstype=~"xfs|ext4|fuse.mergerfs",mountpoint=~"/srv/.*"} / node_filesystem_size_bytes{instance="10.20.0.2:9100",fstype=~"xfs|ext4|fuse.mergerfs",mountpoint=~"/srv/.*"})', "{{mountpoint}}")], unit="percent", w=12, h=9, desc="Per-disk fill; array members are the /srv/dev-disk-by-uuid-* xfs disks.")
d.ts("saturn network", [('rate(node_network_receive_bytes_total{instance="10.20.0.2:9100",device=~"enp.*|br0.*"}[5m])', "rx {{device}}"),
                         ('-rate(node_network_transmit_bytes_total{instance="10.20.0.2:9100",device=~"enp.*|br0.*"}[5m])', "tx {{device}}")], unit="Bps", w=12, h=9, min0=False)
d.ts("Disk throughput (all disks)", [('sum by(device)(rate(node_disk_read_bytes_total{instance="10.20.0.2:9100",device=~"sd.*|nvme.*"}[5m]))', "read {{device}}"),
                                      ('-sum by(device)(rate(node_disk_written_bytes_total{instance="10.20.0.2:9100",device=~"sd.*|nvme.*"}[5m]))', "write {{device}}")], unit="Bps", w=12, h=8, min0=False)
d.ts("Disk temperatures", [('node_hwmon_temp_celsius{instance="10.20.0.2:9100"}', "{{chip}} {{sensor}}")], unit="celsius", w=12, h=8)
d.row("Logs")
d.ts("Error lines by container (5m)", [(f'sum by(container)(count_over_time({{container=~"$container"}} |~ "(?i)(error|exception|fatal|critical)" [5m]))', "{{container}}")], ds=LOKI, stack=True, w=24, h=7)
d.logs("Errors / warnings", '{container=~"$container"} |~ "(?i)(error|exception|fatal|critical|warn)"', h=12)
d.logs("Plex / Jellyfin / Tautulli", '{container=~"plex|jellyfin|tautulli"}', h=10)
d.save()

# ---------------------------------------------------------------- Network
d = D("network-overview", "Network", ["network", "opnsense", "unifi", "dns"], [
    var_query("iface", "Firewall interface", 'label_values(up, job)', ds=PROM) if False else
    {"name": "fwiface", "label": "Firewall interface", "type": "custom", "multi": True, "includeAll": True,
     "allValue": ".+", "query": "igc0,igc1,igc2,igc3,vlan.*", "current": {"selected": True, "text": "All", "value": "$__all"}, "options": []},
])
FW = '{host="router.lan.cbho.me",app="filterlog"}'
PARSE = ('| regexp `^[^,]*,[^,]*,[^,]*,[^,]*,(?P<iface>[^,]*),[^,]*,(?P<action>[^,]*),(?P<dir>[^,]*),4,(?:[^,]*,){7}(?P<proto>[^,]*),[^,]*,'
         '(?P<src>[^,]*),(?P<dst>[^,]*),(?P<sport>[^,]*),(?P<dport>[^,]*)`')
d.row("Hosts & links")
d.stat("Router (syslog, last 10m)", 'count_over_time({host="router.lan.cbho.me"}[10m]) > bool 0', w=4, h=4) if False else None
d._p("stat", "OPNsense log lines (5m)", [d.lt('sum(count_over_time({host="router.lan.cbho.me"}[5m]))')], 4, 4, LOKI, None,
     {"defaults": {"thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}, "color": {"mode": "thresholds"}}},
     {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background", "graphMode": "none"}, "0 = router has stopped shipping logs")
d.stat("Node exporters up", 'count(up{job="node"} == 1)', w=4)
d.stat("Node exporters DOWN", 'count(up{job="node"} == 0) or vector(0)', w=4, thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}], color_bg=True)
d.stat("Proxmox node", 'pve_up{id="node/neptune"}', w=4, thresholds=GREEN_RED, mappings=UPDOWN, color_bg=True)
d.stat("Guests running", 'count(pve_up{id=~"qemu/.*|lxc/.*"} == 1)', w=4)
d.stat("Guests stopped", 'count(pve_up{id=~"qemu/.*|lxc/.*"} == 0) or vector(0)', w=4)
d.row("Firewall (OPNsense filterlog)")
d.ts("Blocked vs passed (events/s)", [(f'sum by(action)(rate({FW} {PARSE} | iface=~"$fwiface" [5m]))', "{{action}}")], ds=LOKI, w=12, stack=False)
d.ts("Blocked by interface (events/s)", [(f'sum by(iface)(rate({FW} {PARSE} | action="block" | iface=~"$fwiface" [5m]))', "{{iface}}")], ds=LOKI, w=12, stack=True)
d._p("bargauge", "Top blocked sources (1h)", [d.lt(f'topk(10, sum by(src)(count_over_time({FW} {PARSE} | action="block" | iface=~"$fwiface" [1h])))')], 8, 9, LOKI, "short",
     {"defaults": {"min": 0}}, {"reduceOptions": {"calcs": ["lastNotNull"]}, "orientation": "horizontal", "displayMode": "gradient"})
d._p("bargauge", "Top blocked destination ports (1h)", [d.lt(f'topk(10, sum by(dport)(count_over_time({FW} {PARSE} | action="block" | iface=~"$fwiface" [1h])))')], 8, 9, LOKI, "short",
     {"defaults": {"min": 0}}, {"reduceOptions": {"calcs": ["lastNotNull"]}, "orientation": "horizontal", "displayMode": "gradient"})
d._p("bargauge", "Top blocked protocols (1h)", [d.lt(f'topk(8, sum by(proto)(count_over_time({FW} {PARSE} | action="block" | iface=~"$fwiface" [1h])))')], 8, 9, LOKI, "short",
     {"defaults": {"min": 0}}, {"reduceOptions": {"calcs": ["lastNotNull"]}, "orientation": "horizontal", "displayMode": "gradient"})
d.logs("Recent blocks", f'{FW} |= ",block," ', h=9)
d.row("Traffic by link (node_exporter)")
d.ts("saturn NICs", [('rate(node_network_receive_bytes_total{instance="10.20.0.2:9100",device=~"enp.*"}[5m])*8', "rx {{device}}"),
                      ('-rate(node_network_transmit_bytes_total{instance="10.20.0.2:9100",device=~"enp.*"}[5m])*8', "tx {{device}}")], unit="bps", w=12, min0=False)
d.ts("Proxmox guest network (pve exporter)", [('sum by(name)(rate(pve_network_receive_bytes_total[5m]) * on(id) group_left(name) pve_guest_info)', "rx {{name}}"),
                                              ('-sum by(name)(rate(pve_network_transmit_bytes_total[5m]) * on(id) group_left(name) pve_guest_info)', "tx {{name}}")], unit="Bps", w=12, min0=False)
d.ts("Per-host network (LXC/VM node exporters)", [('sum by(host)(rate(node_network_receive_bytes_total{device!~"lo|veth.*|br-.*|docker.*"}[5m]))', "rx {{host}}"),
                                                   ('-sum by(host)(rate(node_network_transmit_bytes_total{device!~"lo|veth.*|br-.*|docker.*"}[5m]))', "tx {{host}}")], unit="Bps", w=24, min0=False)
d.ts("Network errors / drops", [('sum by(host)(rate(node_network_receive_errs_total{device!~"lo|veth.*"}[5m]) + rate(node_network_receive_drop_total{device!~"lo|veth.*"}[5m]))', "rx {{host}}"),
                                ('sum by(host)(rate(node_network_transmit_errs_total{device!~"lo|veth.*"}[5m]) + rate(node_network_transmit_drop_total{device!~"lo|veth.*"}[5m]))', "tx {{host}}")], unit="pps", w=24, h=6)
d.row("DHCP & DNS")
d.ts("DHCP ACK / DISCOVER (events/min)", [('sum(count_over_time({app="kea-dhcp4"} |= "DHCPACK" [5m])) / 5', "ACK"), ('sum(count_over_time({app="kea-dhcp4"} |= "DHCPDISCOVER" [5m])) / 5', "DISCOVER")], ds=LOKI, w=12, h=7)
d.ts("Log volume: unbound / pihole / kea", [('sum by(app)(count_over_time({host=~"router.lan.cbho.me|pihole",app=~"unbound|pihole-ftl|kea-dhcp4|pihole-dns"}[5m]))', "{{app}}")], ds=LOKI, w=12, h=7, stack=True)
d.logs("DHCP: new leases / NAKs / declines", '{app="kea-dhcp4"} |~ "DHCP4_LEASE_ALLOC|DHCPNAK|DHCPDECLINE|DHCP4_LEASE_ALLOC_FAIL"', h=8)
d.logs("Pi-hole / unbound warnings", '{app=~"pihole-ftl|unbound"} |~ "(?i)(warn|error|fail|servfail)"', h=8)
d.row("UniFi / Wi-Fi")
d.ts("UniFi controller log levels", [('sum by(level)(count_over_time({host="unifi",app="unifi-server"} | detected_level != "" [5m]))', "{{level}}")], ds=LOKI, w=12, h=7)
d.ts("UniFi host log volume by app", [('sum by(app)(count_over_time({host="unifi"}[5m]))', "{{app}}")], ds=LOKI, w=12, h=7, stack=True)
d.logs("UniFi warnings / errors", '{host="unifi"} |~ "(?i)(error|warn)" != "PageNotFound"', h=8)
d.logs("Tailscale", '{app="tailscaled"}', h=7)
d.save()
print("ok")
