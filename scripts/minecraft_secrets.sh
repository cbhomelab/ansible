#!/bin/bash
# Run a command with the Minecraft role's secrets exported from Bitwarden.
#   scripts/minecraft_secrets.sh ansible-playbook playbooks/minecraft.yml
# Needs BW_SESSION (or ~/.config/bitwarden/session) and the item "minecraft-secrets".
set -euo pipefail
export BW_SESSION="${BW_SESSION:-$(cat "$HOME/.config/bitwarden/session")}"
ITEM=$(bw get item minecraft-secrets)
f() { echo "$ITEM" | python3 -c "import sys,json;print(next(x['value'] for x in json.load(sys.stdin)['fields'] if x['name']=='$1'))"; }
export MINECRAFT_FORWARDING_SECRET="$(f forwarding_secret)"
export MINECRAFT_DISCORD_BOT_TOKEN="$(f discord_bot_token)"
export MINECRAFT_MANAGEMENT_SECRET="$(f management_secret)"
exec "$@"
