#!/usr/bin/env python3
"""Add-only refresh of hand-curated Plex collections (TV Shows library, section 1).
Also covers per-person Game Changer / Make Some Noise collections (by Plex cast tags).
Prints a line per added episode; silent when nothing changed. Never removes items."""
import re, requests, sys
env = dict(l.strip().split("=", 1) for l in open("/home/hermes/.config/plex/env") if "=" in l)
P = "http://10.20.0.2:32400"; H = {"X-Plex-Token": env["PLEX_TOKEN"], "Accept": "application/json"}
def g(u, **k):
    r = requests.get(P + u, headers=H, params=k, timeout=60); r.raise_for_status(); return r.json()["MediaContainer"]
MID = g("/identity")["machineIdentifier"]
def eps(show): return g(f"/library/metadata/{show}/allLeaves").get("Metadata", [])
def show_key(title):
    return next(d["ratingKey"] for d in g("/library/sections/1/all", title=title)["Metadata"] if d["title"] == title)
def bobs(e): return re.search(r"thanksgiving|turkey", e["title"] + " " + e.get("summary", ""), re.I)
def topgear(e): return e["parentIndex"] == 0 or re.search(r"\bspecial\b", e["title"], re.I)
def grandtour(e): return e["parentIndex"] in (4, 5, 6) or re.search(r"\bspecial\b", e["title"], re.I) or e.get("duration", 0) >= 80 * 60000
def tim_char(e): return e["grandparentTitle"] == "Netflix Presents: The Characters" and e["title"] == "Tim Robinson"
def always(e): return True
RULES = [
  ("Tim Robinson", [("I Think You Should Leave with Tim Robinson", always), ("Detroiters", always), ("Netflix Presents: The Characters", tim_char)]),
  ("Bob's Burgers Thanksgiving", [("Bob's Burgers", bobs)]),
  ("Top Gear & The Grand Tour Specials", [("Top Gear", topgear), ("The Grand Tour (2016)", grandtour)]),
]
PEOPLE = ["Brennan Lee Mulligan", "Vic Michaelis", "Jacob Wysocki", "Lisa Gilroy", "Jessica McKenna"]
PEOPLE_SHOWS = ["Game Changer", "Make Some Noise"]
SKIP = re.compile(r"archive footage|video footage", re.I)  # clips don't count as appearing
colls = {c["title"]: c["ratingKey"] for c in g("/library/sections/1/collections").get("Metadata", [])}
for name, parts in RULES:
    cid = colls[name]
    have = {e["ratingKey"] for e in g(f"/library/collections/{cid}/children").get("Metadata", [])}
    new = [(s, e) for s, f in parts for e in eps(show_key(s)) if f(e) and e["ratingKey"] not in have]
    if not new: continue
    uri = f"server://{MID}/com.plexapp.plugins.library/library/metadata/" + ",".join(e["ratingKey"] for _, e in new)
    requests.put(f"{P}/library/collections/{cid}/items", headers=H, params={"uri": uri}, timeout=60).raise_for_status()
    for s, e in new: print(f"Added to '{name}': {s} S{e['parentIndex']}E{e['index']} {e['title']}")

# People collections: any Game Changer / Make Some Noise episode where the person is cast
# (contestant, player, guest...), excluding archive/video-footage cameos.
cast = []
for sname in PEOPLE_SHOWS:
    for e in eps(show_key(sname)):
        roles = g(f"/library/metadata/{e['ratingKey']}")["Metadata"][0].get("Role", [])
        cast.append((e, [r for r in roles if not SKIP.search(r.get("role", ""))]))
for person in PEOPLE:
    name = f"Game Changer & Make Some Noise: {person}"
    cid = colls[name]
    have = {e["ratingKey"] for e in g(f"/library/collections/{cid}/children").get("Metadata", [])}
    new = [e for e, rs in cast if e["ratingKey"] not in have and any(r["tag"] == person for r in rs)]
    if not new: continue
    uri = f"server://{MID}/com.plexapp.plugins.library/library/metadata/" + ",".join(e["ratingKey"] for e in new)
    requests.put(f"{P}/library/collections/{cid}/items", headers=H, params={"uri": uri}, timeout=60).raise_for_status()
    for e in new: print(f"Added to '{name}': {e['grandparentTitle']} S{e['parentIndex']}E{e['index']} {e['title']}")
