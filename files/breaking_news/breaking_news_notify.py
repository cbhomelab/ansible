#!/usr/bin/env python3
"""Send one breaking-news alert: Home Assistant phone push (tap opens the article)
+ a rich Mattermost post in the private #breaking-news channel (no @mention, so
the user is pinged once, by the phone push).

Usage: echo '{"category":..,"headline":..,"summary":..,"url":..,"source":..,"importance":2|3}' | breaking_news_notify.py
importance 3 = time-sensitive push, 2 = normal push.
Records the alert in the collector's state file (dedupe + 48h "already alerted" list).
"""
import json, re, sys, time, urllib.request
from pathlib import Path

STATE = Path.home() / ".hermes/cache/breaking_news_state.json"
CHAN = (Path.home() / ".hermes/cache/breaking_news_channel.txt").read_text().strip()
EMOJI = {"News": "📰", "Sports": "🏈", "Formula 1": "🏎️", "V8 Supercars": "🏁",
         "Simracing": "🎮", "Homelab": "🖥️"}


def envfile(path):
    d = {}
    for l in Path(path).expanduser().read_text().splitlines():
        if "=" in l and not l.lstrip().startswith("#"):
            k, v = l.split("=", 1)
            d[k.strip()] = v.strip().strip("\"'")
    return d


def og_image(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=8).read(200000).decode("utf-8", "ignore")
        m = (re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
             or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', html, re.I))
        return m.group(1) if m and m.group(1).startswith("http") else None
    except Exception:
        return None


def post(url, body, headers):
    r = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    return urllib.request.urlopen(r, timeout=20).read()


def main():
    a = json.load(sys.stdin)
    st = json.loads(STATE.read_text()) if STATE.exists() else {"alerts": []}
    st.setdefault("alerts", [])
    if any(x.get("url") == a["url"] for x in st["alerts"]):
        print("duplicate url, skipped")
        return
    cat, imp = a.get("category", "News"), int(a.get("importance", 2))
    title = f"{EMOJI.get(cat, '🔔')} {cat}: {a['headline']}"[:200]
    img = og_image(a["url"])

    ha = envfile("~/.config/homeassistant/env")
    data = {"tag": re.sub(r"\W+", "-", a["headline"].lower())[:60], "group": "breaking-news",
            "url": a["url"], "clickAction": a["url"], "ttl": 0, "priority": "high",
            "push": {"interruption-level": "time-sensitive" if imp >= 3 else "active"}}
    if img:
        data["image"] = img
    try:
        post(ha["HA_URL"].rstrip("/") + "/api/services/notify/mobile_app_christian_s_phone",
             {"title": title, "message": a.get("summary", "")[:400], "data": data},
             {"Authorization": "Bearer " + ha["HA_TOKEN"], "Content-Type": "application/json"})
        pushed = True
    except Exception as e:
        pushed = False
        print("push failed:", e)

    env = envfile("~/.hermes/.env")
    msg = f"### {title}\n{a.get('summary', '')}\n\n[Read article ({a.get('source', 'source')})]({a['url']})"
    if img:
        msg += f"\n\n![]({img})"
    try:
        post(env["MATTERMOST_URL"].rstrip("/") + "/api/v4/posts", {"channel_id": CHAN, "message": msg},
             {"Authorization": "Bearer " + env["MATTERMOST_TOKEN"], "Content-Type": "application/json"})
    except Exception as e:
        print("mattermost failed:", e)
        if not pushed:
            sys.exit(1)

    st["alerts"].append({"ts": time.time(), "category": cat, "headline": a["headline"], "url": a["url"]})
    STATE.write_text(json.dumps(st))
    print("alert sent:", a["headline"])


if __name__ == "__main__":
    main()
