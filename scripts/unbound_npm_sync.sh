#!/usr/bin/env bash
# Keep OPNsense Unbound host overrides in sync with NPM proxy hosts.
# Runs roles/network_appliances unbound_dns with apply=true (never prune).
# Meant for cron on the Hermes host; creds come from the existing env files
# (not Bitwarden, which is locked/unattended-unfriendly):
#   ~/.config/opnsense/env  (OPN_HOST OPN_KEY OPN_SECRET)
#   ~/.config/npm/env       (NPM_HOST NPM_PORT NPM_EMAIL NPM_PASS)
# Logs only the plan line + failures to ~/.cache/unbound_npm_sync.log.
set -uo pipefail
REPO="${ANSIBLE_REPO:-$HOME/ansible}"
LOG="$HOME/.cache/unbound_npm_sync.log"
exec 9>"$HOME/.cache/unbound_npm_sync.lock"; flock -n 9 || exit 0
cd "$REPO" || exit 1
git pull -q --ff-only 2>>"$LOG" || echo "$(date -Is) WARN git pull failed, using checked-out revision" >>"$LOG"
set -a; . "$HOME/.config/opnsense/env"; . "$HOME/.config/npm/env"; set +a
CREDS="$(mktemp)"; trap 'rm -f "$CREDS"' EXIT; chmod 600 "$CREDS"
python3 - "$CREDS" <<'PY'
import json,os,sys
e=os.environ
json.dump({"network_appliances_unbound_apply":True,
 "network_appliances_opnsense":{"api_base_url":"https://"+e["OPN_HOST"],"api_key":e["OPN_KEY"],"api_secret":e["OPN_SECRET"]},
 "network_appliances_npm":{"host":f'{e["NPM_HOST"]}:{e["NPM_PORT"]}',"identity":e["NPM_EMAIL"],"secret":e["NPM_PASS"]}},open(sys.argv[1],"w"))
PY
OUT="$(ansible-playbook playbooks/network.yml --tags unbound_dns --limit vm100-opnsense -e @"$CREDS" 2>&1)"; RC=$?
PLAN="$(grep -o 'Unbound cbhomelab.net -> [^"]*' <<<"$OUT" | head -1)"
if [ $RC -ne 0 ]; then
  echo "$(date -Is) FAIL rc=$RC $PLAN" >>"$LOG"; tail -15 <<<"$OUT" >>"$LOG"; exit $RC
fi
# log only when something was created/corrected
grep -q 'create=0 set=0' <<<"$PLAN" || echo "$(date -Is) CHANGED $PLAN" >>"$LOG"
