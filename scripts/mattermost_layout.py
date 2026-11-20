#!/usr/bin/env python3
"""Replicate the Discord channel layout + per-channel Hermes prompts on Mattermost (CT 111).

Idempotent. Creates missing channels in team `cbhomelab` through Mattermost's local-mode socket
(admin, no password), adds users hermes+christian, then writes mattermost.* gateway config via
`hermes config set`. Channel->prompt mapping comes from the live discord.* config, so nothing is retyped.
Run on the Hermes host:  python3 scripts/mattermost_layout.py [--dry-run]
"""
import json, subprocess, sys, yaml, os
SSH = ["ssh", "-i", os.path.expanduser("~/.ssh/hermes_proxmox"), "-o", "IdentitiesOnly=yes", "root@10.20.0.51"]
TEAM = "cbhomelab"
DRY = "--dry-run" in sys.argv
# discord channel id -> (mattermost name, display name, purpose)
LAYOUT = {
    "1568010171861442763": ("general", "general", ""),
    "1568010626792423575": ("hermes", "hermes", "Hermes home channel: general control and notifications"),
    "1571029254081351741": ("alerts", "alerts", "Alerts and notifications"),
    "1572100332454940812": ("dev-iracing-tms", "dev-iracing-tms", "iRacing Team Manager development"),
    "1572100352537526382": ("home-assistant", "home-assistant", "Home Assistant"),
    "1572100373601062942": ("opnsense-and-network", "opnsense-and-network", "OPNsense, UniFi and the wider network"),
    "1572100390923669504": ("openmediavault", "openmediavault", "OpenMediaVault 'saturn'"),
    "1572100399652016208": ("proxmox", "proxmox", "Proxmox host 'neptune'"),
    "1572122932564463676": ("gaming-pc", "gaming-pc", "CB-GAMING Windows PC"),
    "1572149984688869376": ("video-archiving", "video-archiving", "Find, download, organize and display videos on Plex from user lists"),
    "1572153297190527067": ("music-download", "music-download", "Find Tidal albums for artist lists and download them via tiddl on CB-GAMING"),
    "1572431244606836906": ("steam-deck", "steam-deck", "Steam Deck setup, reinstall plan and saved resources"),
}
REMOTE = r'''
import json,subprocess,sys
req=__REQ__
pid=subprocess.check_output(["docker","inspect","-f","{{.State.Pid}}","mattermost-mattermost-1"],text=True).strip()
import os; os.chdir(f"/proc/{pid}/root/var/tmp")
def api(m,p,b=None):
    c=["curl","-s","--unix-socket","./mattermost_local.socket","-X",m,"-H","Content-Type: application/json","http://l/api/v4"+p]
    if b is not None: c+=["-d",json.dumps(b)]
    return json.loads(subprocess.check_output(c,text=True) or "null")
team=api("GET","/teams/name/"+req["team"])["id"]
users=[api("GET","/users/username/"+u)["id"] for u in req["users"]]
out={}
for did,(name,disp,purpose) in req["layout"].items():
    ch=api("GET",f"/teams/{team}/channels/name/{name}")
    if "id" not in ch or ch.get("status_code")==404:
        ch=api("POST","/channels",{"team_id":team,"name":name,"display_name":disp,"purpose":purpose,"type":"O"})
    for u in users: api("POST",f"/channels/{ch['id']}/members",{"user_id":u})
    out[did]=ch["id"]
print(json.dumps(out))
'''
REQ = {"team": TEAM, "users": ["hermes", "christian"], "layout": LAYOUT}
r = subprocess.run(SSH + ["python3", "-"], input=REMOTE.replace("__REQ__", repr(REQ)), capture_output=True, text=True)
if r.returncode: sys.exit(r.stderr)
idmap = json.loads(r.stdout.strip().splitlines()[-1])
d = yaml.safe_load(open(os.path.expanduser("~/.hermes/config.yaml")))["discord"]
skills = {b["id"]: b["skills"] for b in d.get("channel_skill_bindings", [])}
sets = {}
for did, prompt in d.get("channel_prompts", {}).items():
    if did in idmap:
        s = skills.get(did)
        if s:  # channel_skill_bindings is Discord/Slack only; fold into the prompt instead
            prompt = prompt.rstrip() + "\n\nAt the start of any task here, load these skills with skill_view: " + ", ".join(s) + "."
        sets[idmap[did]] = prompt
free = [idmap[c.strip()] for c in str(d.get("free_response_channels", "")).split(",") if c.strip() in idmap]
cmds = [("mattermost.channel_prompts." + k, v) for k, v in sets.items()]
cmds += [("mattermost.free_response_channels", ", ".join(free)), ("mattermost.require_mention", "false")]
for k, v in cmds:
    print("set", k, f"({len(v)} chars)")
    if not DRY: subprocess.run(["hermes", "config", "set", k, v], check=True, capture_output=True)
home = idmap["1568010626792423575"]
if not DRY:
    lines = [l for l in open(os.path.expanduser("~/.hermes/.env")).read().splitlines() if not l.startswith("MATTERMOST_HOME_CHANNEL=")]
    open(os.path.expanduser("~/.hermes/.env"), "w").write("\n".join(lines) + f"\nMATTERMOST_HOME_CHANNEL={home}\n")
print(json.dumps(idmap, indent=1))
