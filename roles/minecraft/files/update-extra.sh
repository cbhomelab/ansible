#!/bin/bash
# Extra plugins lxc105 carries on top of upstream update.sh (kept out of the
# tracked file so the git checkout stays clean). Run from the deploy dir.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
source contrib/utils.sh || exit 1
download_file "https://cdn.modrinth.com/data/52W2RPUh/versions/3N4S9Ppn/timber-1.8.2.jar" server/plugins/timber.jar
download_file "https://cdn.modrinth.com/data/1u6JkXh5/versions/YFnqiUlL/worldedit-bukkit-7.4.6.jar" server/plugins/worldedit.jar
download_file "https://download.discordsrv.com/v2/DiscordSRV/DiscordSRV/release/download/v1.30.4/DiscordSRV-Build-1.30.4.jar" server/plugins/discordsrv.jar
