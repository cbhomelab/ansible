# roles/shell_config

Deploys the cbhomelab/dotfiles chezmoi-managed shell configuration for the
`christian` and `hermes` accounts fleet-wide.

## What it does

- **Linux** (`shell_config_linux_accounts`, default: christian + hermes):
  installs `chezmoi` once system-wide to `/usr/local/bin` (as root),
  ensures `git`/`curl`/`ca-certificates`, optionally ensures `zsh` is
  installed, then runs `chezmoi init --apply` **as each account** via
  `become_user`.
- **Windows** (`shell_config_windows_accounts`, default: christian only):
  installs `chezmoi.exe` to `%LOCALAPPDATA%\chezmoi` if missing, then runs
  `chezmoi init --apply` over the existing OpenSSH connection
  (`ansible_shell_type: powershell`) — no winrm / `ansible.windows`
  collection dependency.

Branches on inventory `group_names` (`'windows' in group_names`), not
gathered facts — more reliable for the SSH+powershell Windows connection.

## Why hermes isn't a Windows account

hermes has no separate Windows OS account on CB-GAMING. It reaches that
host over SSH using its own key (`hermes_windows`) authorized into
**christian's** `administrators_authorized_keys` (see t_6fe4b6c0). There
is nothing OS-level to apply a distinct shell profile to there, so
`shell_config_windows_accounts` only lists christian.

## Profile pare-down (hermes vs christian)

This is implemented inside cbhomelab/dotfiles itself via a `profile`
chezmoi data variable, not by this role — see that repo's README
"Profiles: christian vs hermes" section. This role just supplies
`--promptString profile=<x>[,name=...,email=...]` per account from
`shell_config_linux_accounts[].profile` / `.extra_prompts`.

Decision (2026-11-12, user): hermes is an automation account — pared-down
profile (bash+Starship only, no git identity, no git porcelain aliases),
not an identical copy of christian's dotfiles.

## Idempotency

`chezmoi init --apply` is safe to re-run: if the source dir already exists
and points at the same remote, chezmoi updates it (git pull) and
re-applies rather than re-cloning. The `changed_when` on the apply task is
best-effort (chezmoi doesn't have a clean "nothing changed" exit
signal distinct from "something changed" via stdout alone) — treat
`changed: true` on every run as expected/benign, not a bug.

## Requirements

- `git`, `curl` on Linux targets (installed by this role if missing).
- Outbound HTTPS access to github.com from every target (the dotfiles repo
  is cloned over anonymous HTTPS — it's a public repo, no deploy key
  needed).
- christian + hermes OS accounts must already exist (roles/access_control,
  t_6fe4b6c0) before this role runs.

## OPNsense (FreeBSD) prerequisites

`tasks/freebsd.yml` runs over SSH as `christian` (play in `playbooks/shell.yml`,
tag `opnsense`) and installs Starship, `starship.toml` and the `~/.bashrc` /
`~/.bash_profile` hooks. It does NOT create anything on the router itself.
These must exist first (currently manual, in the OPNsense UI):

1. **User `christian`** (System > Access > Users), with a shell of
   `/usr/local/bin/bash`.
2. **Package `bash`**: `pkg install bash` or System > Firmware > Packages.
   (FreeBSD 13.2 `/bin/sh` can't render the prompt: libedit strips ESC bytes.)
3. **Authorized keys on `christian`**: the user's own key plus Hermes's
   (`~/.ssh/id_ed25519.pub`, saved in Bitwarden as `homelab-ssh-hermes`).
   The play connects with that key; `hermes` itself has no sudo on the router.
4. The router is `connection: local` in the inventory, so the play builds a
   temporary `opnsense-shell` host from `vm100-opnsense`'s `ansible_host`.

### Automation status (OPNsense 24.1.5)

- Package install: the firmware API (`core/firmware/*`, key `homelab-opnsense-api`)
  works and reports `bash` installed, so an API task for it is feasible
  (not yet implemented or tested).
- User, shell and authorized keys: 24.1 has no REST API for users
  (`core/user` returns "controller not found"), so these can't be set via API.
  Options: upgrade to a release with the user API, or edit `config.xml`
  (restore via the config API, risky), or keep it manual.
