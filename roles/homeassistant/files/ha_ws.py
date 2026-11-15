#!/usr/bin/env python3
"""Minimal Home Assistant websocket client for the homeassistant role.
Usage: ha_ws.py report | backup NAME
Reads HA_HOST/HA_PORT/HA_TOKEN from the environment. Prints one JSON document."""
import asyncio, json, os, sys, time, datetime
import websockets

async def main():
    url = f"ws://{os.environ['HA_HOST']}:{os.environ['HA_PORT']}/api/websocket"
    async with websockets.connect(url, max_size=2**24) as w:
        await w.recv()
        await w.send(json.dumps({"type": "auth", "access_token": os.environ["HA_TOKEN"]}))
        if json.loads(await w.recv())["type"] != "auth_ok":
            sys.exit("HA auth failed")
        n = 0
        async def call(t, **k):
            nonlocal n; n += 1
            await w.send(json.dumps({"id": n, "type": t, **k}))
            while True:
                r = json.loads(await w.recv())
                if r.get("id") == n and r.get("type") == "result":
                    if not r["success"]: raise RuntimeError(f"{t}: {r['error']}")
                    return r["result"]
        sup = lambda ep: call("supervisor/api", endpoint=ep, method="get")

        async def backups():
            return (await call("backup/info"))["backups"]

        if sys.argv[1] == "report":
            core, osi, supi, host, addons, bk = (await sup("/core/info"), await sup("/os/info"),
                await sup("/supervisor/info"), await sup("/host/info"), await sup("/addons"), await backups())
            newest = max((b["date"] for b in bk), default=None)
            age = None
            if newest:
                age = round((datetime.datetime.now(datetime.timezone.utc) -
                             datetime.datetime.fromisoformat(newest)).total_seconds() / 3600, 1)
            print(json.dumps({
                "core": {"version": core["version"], "latest": core["version_latest"]},
                "os": {"version": osi["version"], "latest": osi["version_latest"]},
                "supervisor": {"version": supi["version"], "healthy": supi["healthy"], "supported": supi["supported"]},
                "disk_free_gb": host["disk_free"],
                "addons": [{"slug": a["slug"], "state": a["state"], "version": a["version"],
                            "latest": a["version_latest"],
                            "behind": a["version"] != a["version_latest"]} for a in addons["addons"]],
                "backups": {"count": len(bk), "newest": newest, "newest_age_hours": age},
            }))
        elif sys.argv[1] == "backup":
            before = {b["backup_id"] for b in await backups()}
            await call("backup/generate", name=sys.argv[2], agent_ids=["hassio.local"],
                       include_all_addons=True, include_database=True, include_homeassistant=True)
            for _ in range(120):
                await asyncio.sleep(5)
                new = [b for b in await backups() if b["backup_id"] not in before]
                if new:
                    b = new[0]
                    ok = not b.get("failed_addons") and not b.get("failed_agent_ids")
                    print(json.dumps({"backup_id": b["backup_id"], "name": b["name"], "addons": len(b.get("addons", [])),
                                      "ok": ok}))
                    sys.exit(0 if ok else 2)
            sys.exit("backup did not appear within 10 minutes")
asyncio.run(main())
