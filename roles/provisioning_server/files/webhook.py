#!/usr/bin/env python3
"""Windows provisioning webhook (stdlib only).

GET  /bootstrap.ps1  -> serves the bootstrap script (no secrets in it)
POST /provision      -> {"hostname": "...", "token": "..."}
    Verifies the token and that the hostname is in the ansible `windows` group
    (source IP is not checked: inter-VLAN traffic is source-NATed). Then runs
    playbooks/windows.yml --limit <host> (one run at a time) in the background.
"""
import hmac, json, os, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.environ["PROV_BASE"]
REPO = os.environ["PROV_REPO"]
TOKEN = os.environ["PROV_TOKEN"]
PORT = int(os.environ.get("PROV_PORT", "8765"))
BW_SESSION_FILE = os.path.expanduser("~/.config/bitwarden/session")
LOCK = threading.Lock()


def bw_env():
    env = dict(os.environ)
    try:
        env["BW_SESSION"] = open(BW_SESSION_FILE).read().strip()
    except OSError:
        pass
    return env


def windows_hosts():
    out = subprocess.run(["ansible-inventory", "--list"], cwd=REPO, env=bw_env(), capture_output=True, text=True, timeout=120).stdout
    inv = json.loads(out)
    return {h: inv["_meta"]["hostvars"][h].get("ansible_host") for h in inv.get("windows", {}).get("hosts", [])}


def run_playbook(host):
    log = os.path.join(BASE, "logs", f"{time.strftime('%Y%m%d-%H%M%S')}-{host}.log")
    with LOCK, open(log, "w") as f:
        env = bw_env()
        subprocess.run(["git", "pull", "-q", "--rebase"], cwd=REPO, stdout=f, stderr=f)
        # sshd may take a moment to be reachable right after bootstrap
        for attempt in range(1, 6):
            r = subprocess.run(["ansible-playbook", "playbooks/windows.yml", "--limit", host],
                               cwd=REPO, env=env, stdout=f, stderr=f)
            f.write(f"\n== attempt {attempt} rc={r.returncode} ==\n"); f.flush()
            if r.returncode == 0:
                break
            time.sleep(30)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="text/plain"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/bootstrap.ps1":
            with open(os.path.join(BASE, "www", "bootstrap.ps1"), "rb") as f:
                return self._send(200, f.read())
        self._send(404, b"not found\n")

    def do_POST(self):
        if self.path != "/provision":
            return self._send(404, b"not found\n")
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            host = str(data.get("hostname", "")).lower()
            if not hmac.compare_digest(str(data.get("token", "")), TOKEN):
                return self._send(403, b"bad token\n")
            hosts = windows_hosts()
            if host not in hosts:
                return self._send(404, b"unknown host\n")
        except Exception as e:
            return self._send(400, f"bad request: {e}\n".encode())
        threading.Thread(target=run_playbook, args=(host,), daemon=True).start()
        self._send(202, b"accepted\n")

    def log_message(self, fmt, *a):
        print(f"{self.client_address[0]} {fmt % a}", flush=True)


ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
