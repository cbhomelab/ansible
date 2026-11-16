# windows_baseline (CB-GAMING)

Windows 11 Pro over OpenSSH + PowerShell, no Python on the target, so only
`ansible.windows` / `community.windows` modules are used.

    ansible-playbook playbooks/windows.yml                 # idempotent config
    ansible-playbook playbooks/windows.yml --tags updates  # winget + Windows Update (opt-in)

Manages: sshd (key-only, validated with `sshd -t` before restart, admin key
file append-only + ACL), SMBv1 off, RDP NLA, built-in Administrator disabled,
firewall + Defender on, timezone, Ultimate Performance power plan / never sleep.

Deliberately NOT managed: UAC (EnableLUA is a REG_SZ here - audit first),
winget pins in `windows_baseline_winget_exclude` (ViGEm, WSL, Tailscale),
automatic restarts after updates (`windows_baseline_update_reboot: false`).
