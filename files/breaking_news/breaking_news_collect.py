#!/usr/bin/env python3
"""Breaking-news collector (Hermes cron `script`, stdout becomes agent context).

Reads NEW FreshRSS entries (entry.id > watermark) for the watched categories,
applies a cheap high-recall keyword prefilter, and prints candidates for the
agent to judge. If nothing is new, prints {"wakeAgent": false} so no LLM run
happens. First run only sets the watermark (no backlog alerts).

FreshRSS lives on saturn (container `freshrss`); we query its SQLite via ssh.
"""
import json, re, subprocess, sys, time
from html import unescape
from pathlib import Path

STATE = Path.home() / ".hermes/cache/breaking_news_state.json"
DB = "/config/www/freshrss/data/users/christian/db.sqlite"
MAX_CANDIDATES = 60
RECENT_ALERT_HOURS = 48

# category -> prefilter regex (None = pass everything). High recall on purpose;
# the agent applies the real "is this big?" criteria.
NEWS = r"resign|step(s|ping)? down|fired|ousted|declar\w+ war|war on|invad|invasion|airstrike|missile|ceasefire|cease-fire|assassinat|coup|martial law|nuclear|attack|shoot|killed|dies|dead|death|projected|calls? the race|called the race|concede|wins (the )?(election|presidency|race)|election|white house|cabinet|secretary of|attorney general|impeach|supreme court|shutdown|indict|arrest|earthquake|hurricane|tsunami|pandemic|outbreak|sanction|treaty|breaking|crisis|emergency|explosion|crash"
SPORTS = r"injur|\bIR\b|out for|ruled out|season-ending|torn|trade|traded|fired|firing|hired|hires|hire\b|coordinator|head coach|general manager|\bGM\b|release[ds]?\b|waive|\bcut\b|cuts\b|bench|suspen|retire|holdout|extension|contract|rule change|rules? (change|proposal)|owners|drama|feud|quarterback|\bQB\b|blockbuster|sign(s|ed)\b"
F1 = r"driver|seat|sign(s|ed|ing)?\b|contract|replace|drop(s|ped)?\b|leav(e|es|ing)|depart|join(s|ed)?\b|team principal|team boss|\bboss\b|appoint|sack|fired|engine|power unit|supplier|new team|entry|entrant|grid|announce|confirm|2027|2028|2029|ban\b|penalt|regulation"
V8 = r"\bsign(s|ed|ing)?\b|join(s|ed)?\b|leav(e|es|ing)|depart|axed|sacked|co-driver|co driver|line-?up|202[7-9]|toyota|manufacturer|homologat|new team|franchise|licen[cs]e|\bsold\b|takeover|announce[sd]?\b|retire|return"
HOMELAB = r"releas|v?\d+\.\d+|security|vulnerab|CVE|critical|patch|deprecat|end[- ]of[- ]life|\bEOL\b|discontinu|abandon|archiv|acquir|shut(ting)? down|license|licence|breaking change|proxmox|home ?assistant|openmediavault|\bOMV\b|opnsense|plex|jellyfin|sonarr|radarr|lidarr|prowlarr|docker|frigate|tailscale|unifi|pi-?hole|nginx|gluetun|wireguard|qbittorrent|immich|navidrome|linkwarden|freshrss|syncthing|tdarr|mosquitto|grafana|loki|ansible|new|launch|introduc|announce"

WATCH = {
    "News": NEWS,
    "Sports": SPORTS,
    "Formula 1": F1,
    "V8 Supercars": V8,
    "Simracing": None,
    "Homelab": HOMELAB,
}


def sh_sqlite(sql):
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "saturn",
         f"docker exec -i freshrss sqlite3 -json {DB}"],
        input=sql, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return json.loads(r.stdout) if r.stdout.strip() else []


def load():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st))


def clean(s, n):
    s = re.sub(r"<[^>]+>", " ", unescape(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def main():
    st = load()
    if "last_id" not in st:
        mx = sh_sqlite("select max(id) m from entry;")[0]["m"]
        st = {"last_id": mx, "alerts": []}
        save(st)
        print("baseline set; no alerts this run")
        print(json.dumps({"wakeAgent": False}))
        return
    cats = ",".join("'%s'" % c.replace("'", "''") for c in WATCH)
    rows = sh_sqlite(
        "select e.id id, c.name cat, f.name feed, e.title title, e.link link, "
        "e.date date, substr(e.content,1,1500) content "
        "from entry e join feed f on f.id=e.id_feed join category c on c.id=f.category "
        f"where e.id > {int(st['last_id'])} and c.name in ({cats}) order by e.id;")
    top = sh_sqlite("select max(id) m from entry;")[0]["m"]
    if top:
        st["last_id"] = max(int(st["last_id"]), int(top))
    cutoff = time.time() - RECENT_ALERT_HOURS * 3600
    st["alerts"] = [a for a in st.get("alerts", []) if a.get("ts", 0) > cutoff]
    save(st)

    cands = []
    for r in rows:
        pat = WATCH[r["cat"]]
        text = (r["title"] or "") + " " + clean(r["content"], 400)
        if pat is None or re.search(pat, text, re.I):
            cands.append(r)
    if not cands:
        print(json.dumps({"wakeAgent": False}))
        return
    cands = cands[-MAX_CANDIDATES:]
    print(f"## New feed items since last check ({len(cands)})\n")
    for r in cands:
        age = int(time.time() - (r["date"] or 0)) // 60
        r["link"] = re.split(r"[?&]utm_", unescape(r["link"] or ""))[0]
        print(f"- [{r['cat']}] ({r['feed']}, {age}m old) {clean(r['title'], 200)}\n  url: {r['link']}\n  snippet: {clean(r['content'], 300)}")
    print("\n## Already alerted in the last 48h (do NOT re-alert these stories)\n")
    for a in st["alerts"][-40:]:
        print(f"- [{a.get('category')}] {a.get('headline')}")
    if not st["alerts"]:
        print("- (none)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # surface as a cron failure, not silent loss
        print(f"collector failed: {e}", file=sys.stderr)
        sys.exit(1)
