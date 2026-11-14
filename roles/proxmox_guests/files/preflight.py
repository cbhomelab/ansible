#!/usr/bin/env python3
"""Pre-flight IP check for proxmox_guests. Reads JSON list from stdin:
[{"id": "149 ci-lxc", "ip": "10.20.0.50/24", "exists": false}, ...]
Env: OPN_HOST OPN_KEY OPN_SECRET (OPNsense Kea read access), PVE_* not needed.
Fails (exit 1) if a static IP is inside a DHCP pool, has a DHCP reservation,
or (for guests that do not exist yet) already answers ping. Existing guests
are only checked against pool/reservation, since they naturally answer ping."""
import ipaddress, json, os, ssl, subprocess, sys, base64, urllib.request

host, key, sec = (os.environ.get(k, "") for k in ("OPN_HOST", "OPN_KEY", "OPN_SECRET"))
if not (host and key and sec):
    sys.exit("preflight: OPN_HOST/OPN_KEY/OPN_SECRET not set (source ~/.config/opnsense/env)")
ctx = ssl._create_unverified_context()
auth = "Basic " + base64.b64encode(f"{key}:{sec}".encode()).decode()

def api(path):
    r = urllib.request.Request(f"https://{host}/api/kea/dhcpv4/{path}", headers={"Authorization": auth})
    return json.load(urllib.request.urlopen(r, context=ctx, timeout=20))

guests = [g for g in json.load(sys.stdin) if g["ip"] and g["ip"] != "dhcp"]
if not guests:
    print("preflight: no static IPs to check"); sys.exit(0)

subnets = {}
for row in api("search_subnet")["rows"]:
    s = api("get_subnet/" + row["uuid"])["subnet4"]
    pools = []
    for p in str(s.get("pools", "")).replace(",", "\n").splitlines():
        p = p.strip()
        if "-" in p:
            a, b = (ipaddress.ip_address(x.strip()) for x in p.split("-"))
            pools.append((a, b))
    subnets[ipaddress.ip_network(row["subnet"])] = pools
reserved = {r["ip_address"]: r.get("hostname") or r.get("hw_address") for r in api("search_reservation")["rows"]}

PROBE = os.environ.get("PREFLIGHT_PROBE_SSH", "neptune")  # ping from a host on the same L2 (controller may lack raw-socket rights)

def probe(ip):
    """0 = answers, 1 = silent, anything else = probe failed (fail closed)."""
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", PROBE, "ping", "-c1", "-W1", ip] if PROBE else ["ping", "-c1", "-W1", ip]
    return subprocess.run(cmd, capture_output=True).returncode

errs = []
for g in guests:
    ip = ipaddress.ip_interface(g["ip"]).ip
    net = next((n for n in subnets if ip in n), None)
    if net is None:
        errs.append(f'{g["id"]}: {ip} is not in any Kea-managed subnet (unknown network)'); continue
    if any(a <= ip <= b for a, b in subnets[net]):
        errs.append(f'{g["id"]}: {ip} is inside the DHCP pool of {net}')
    if str(ip) in reserved:
        errs.append(f'{g["id"]}: {ip} has a DHCP reservation ({reserved[str(ip)]})')
    if not g.get("exists"):
        rc = probe(str(ip))
        if rc == 0:
            errs.append(f'{g["id"]}: {ip} already answers ping (in use by something else)')
        elif rc != 1:
            errs.append(f'{g["id"]}: could not probe {ip} (rc={rc}); refusing to assume it is free')
if errs:
    print("preflight FAILED:\n  " + "\n  ".join(errs)); sys.exit(1)
print(f"preflight OK: {len(guests)} static IP(s) checked")
