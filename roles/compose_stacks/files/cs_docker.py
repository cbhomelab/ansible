#!/usr/bin/env python3
"""Helper for compose_stacks update.yml (runs on the docker host).

  cs_docker.py state  <project>            JSON list of the project's containers
  cs_docker.py changed <project>           running containers whose image tag now points at a
                                           different image ID than the one they run (JSON list,
                                           each with new_image_id)
  cs_docker.py stale  <project>            containers of the project with network_mode container:<id> where
                                           that container no longer exists (JSON list)
  cs_docker.py verify <timeout> <settle> <name> [<name> ...]
        Wait until every container is running (and healthy when it has a
        healthcheck), then require it to stay that way for <settle> seconds with
        an unchanged RestartCount. Prints JSON; exit 1 on any failure.
"""
import json
import subprocess
import sys
import time


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True)


def inspect(names):
    r = sh("docker", "inspect", *names)
    if r.returncode != 0 and not r.stdout.strip():
        return []
    return json.loads(r.stdout or "[]")


def summarize(c):
    st = c["State"]
    return {
        "name": c["Name"].lstrip("/"),
        "id": c["Id"],
        "service": c["Config"]["Labels"].get("com.docker.compose.service"),
        "image_ref": c["Config"]["Image"],
        "image_id": c["Image"],
        "netmode": c["HostConfig"].get("NetworkMode", ""),
        "running": st["Running"],
        "restarting": st.get("Restarting", False),
        "health": (st.get("Health") or {}).get("Status"),
        "restarts": c.get("RestartCount", 0),
        "status": st["Status"],
    }


def cmd_state(project):
    r = sh("docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}")
    ids = r.stdout.split()
    print(json.dumps([summarize(c) for c in inspect(ids)] if ids else []))


def cmd_changed(project):
    r = sh("docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project}")
    ids = r.stdout.split()
    out = []
    for s in ([summarize(c) for c in inspect(ids)] if ids else []):
        i = sh("docker", "image", "inspect", "--format", "{{.Id}}", s["image_ref"])
        new = i.stdout.strip() if i.returncode == 0 else None
        if new and new != s["image_id"]:
            s["new_image_id"] = new
            out.append(s)
    print(json.dumps(out))


def cmd_stale(project):
    allids = set(sh("docker", "ps", "-aq", "--no-trunc").stdout.split())
    r = sh("docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}")
    ids = r.stdout.split()
    out = []
    for s in ([summarize(c) for c in inspect(ids)] if ids else []):
        nm = s["netmode"]
        if nm.startswith("container:") and nm.split(":", 1)[1] not in allids:
            out.append(s)
    print(json.dumps(out))


def bad(s):
    if not s["running"] or s["restarting"]:
        return f"{s['status']}"
    if s["health"] == "unhealthy":
        return "unhealthy"
    if s["health"] == "starting":
        return "health starting"
    return None


def cmd_verify(timeout, settle, names):
    deadline = time.time() + timeout
    problems = {}
    while True:
        states = [summarize(c) for c in inspect(names)]
        seen = {s["name"] for s in states}
        problems = {n: "missing" for n in names if n not in seen}
        problems.update({s["name"]: bad(s) for s in states if bad(s)})
        if not problems:
            break
        if time.time() > deadline:
            print(json.dumps({"ok": False, "problems": problems}))
            sys.exit(1)
        time.sleep(3)
    base = {s["name"]: s["restarts"] for s in states}
    time.sleep(settle)
    states = [summarize(c) for c in inspect(names)]
    problems = {s["name"]: bad(s) or "restarted during settle window"
                for s in states if bad(s) or s["restarts"] != base.get(s["name"])}
    ok = not problems and len(states) == len(names)
    print(json.dumps({"ok": ok, "problems": problems}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "state":
        cmd_state(args[0])
    elif mode == "stale":
        cmd_stale(args[0])
    elif mode == "changed":
        cmd_changed(args[0])
    elif mode == "verify":
        cmd_verify(float(args[0]), float(args[1]), args[2:])
    else:
        sys.exit(2)
