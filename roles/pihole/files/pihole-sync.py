#!/usr/bin/env python3
"""Pull a Teleporter export from the primary Pi-hole (v6 API) and import it locally.
Env: PRIMARY_URL PRIMARY_PASSWORD LOCAL_URL LOCAL_PASSWORD. Exits non-zero on any failure."""
import json, os, subprocess, sys, time, urllib.request, uuid

def call(base, path, method="GET", sid=None, body=None, headers=None):
    h = dict(headers or {})
    if sid:
        h["sid"] = sid
    req = urllib.request.Request(base + "/api" + path, data=body, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def login(base, pw):
    d = json.loads(call(base, "/auth", "POST", body=json.dumps({"password": pw}).encode(),
                        headers={"Content-Type": "application/json"}))
    if not d["session"]["valid"]:
        sys.exit(f"login failed on {base}")
    return d["session"]["sid"]

def logout(base, sid):
    try:
        call(base, "/auth", "DELETE", sid=sid)
    except Exception:
        pass

e = os.environ
STATE = "/var/lib/pihole-sync.lists"

def lists_fingerprint(base, sid):
    d = json.loads(call(base, "/lists", sid=sid))["lists"]
    return json.dumps(sorted((x["address"], x["enabled"], tuple(x.get("groups", []))) for x in d))

def blocked(base, sid):
    return json.loads(call(base, "/stats/summary", sid=sid))["gravity"]["domains_being_blocked"]

psid = login(e["PRIMARY_URL"], e["PRIMARY_PASSWORD"])
try:
    want = lists_fingerprint(e["PRIMARY_URL"], psid)
    blob = call(e["PRIMARY_URL"], "/teleporter", sid=psid)
finally:
    logout(e["PRIMARY_URL"], psid)
if not blob.startswith(b"PK"):
    sys.exit("primary did not return a zip")

for _ in range(12):  # FTL restarts after a config import / gravity run
    try:
        lsid = login(e["LOCAL_URL"], e["LOCAL_PASSWORD"])
        break
    except OSError:
        time.sleep(5)
else:
    sys.exit("local Pi-hole API not reachable")
try:
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"teleporter.zip\"\r\n"
            f"Content-Type: application/zip\r\n\r\n").encode() + blob + f"\r\n--{b}--\r\n".encode()
    out = json.loads(call(e["LOCAL_URL"], "/teleporter", "POST", sid=lsid, body=body,
                          headers={"Content-Type": f"multipart/form-data; boundary={b}"}))
    print("imported:", ", ".join(out.get("imported", [])) or out)
    # Teleporter copies the adlist definitions, not the compiled gravity: rebuild when counts differ.
    empty = blocked(e["LOCAL_URL"], lsid) < 1000
finally:
    logout(e["LOCAL_URL"], lsid)
# Teleporter copies adlist definitions, not compiled gravity: rebuild only when they changed
# (Pi-hole's own weekly timer refreshes list contents).
old = open(STATE).read() if os.path.exists(STATE) else None
if empty or old != want:
    print("adlists changed or gravity empty; running pihole -g")
    subprocess.run(["/usr/local/bin/pihole", "-g"], check=True, stdout=subprocess.DEVNULL)
    open(STATE, "w").write(want)
