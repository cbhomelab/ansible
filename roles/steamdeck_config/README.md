# steamdeck_config

Manages the Steam Deck (SteamOS 3.x, immutable root) at user level only.

- **Flatpaks:** pinned list, system install from flathub (needs sudo; password from Bitwarden `homelab-ssh-deck`).
- **Decky plugins:** verify presence/version only (no stable CLI); install via Decky Store.
- **chezmoi:** reports drift from cbhomelab/dotfiles; `--tags chezmoi_apply` applies (scripts excluded).

Not managed on purpose: pacman/system files (wiped by SteamOS updates), Steam's own state (shortcuts.vdf, controller layouts), CryoUtilities/swap, SLSsteam.

Connectivity: host `steamdeck` has two DNS names (Unbound): `cb-steamdeck-dock.cbhomelab.net` (10.10.0.11) and `cb-steamdeck-wifi.cbhomelab.net` (10.10.0.13). `playbooks/steamdeck.yml` probes port 22 on each and uses the first that answers. The Deck sleeps/leaves the LAN: run on demand only.
