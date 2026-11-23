# Tdarr Windows NVENC node: tb-simrig (10.10.0.99, RTX 5070)

Manual setup (not yet automated; ansible has no Windows inventory). Secrets are NOT in this repo.

- SSH: `Administrator@10.10.0.99` (hermes key in `C:\ProgramData\ssh\administrators_authorized_keys`; default shell is cmd).
- OMV user `tdarrnode` (group `users`, nologin), rw privilege on the `media` SMB share. Password in `~/.config/tdarr-node/env` on the Hermes host.
- Node 3.08.00 (must match server version) unzipped to `C:\Tdarr_Node` from `https://storage.tdarr.io/versions/<ver>/win32_x64/Tdarr_Node.zip`.
- IMPORTANT: the node reads its config from `C:\configs\Tdarr_Node_Config.json` (RootDataPath is `C:\`), not `C:\Tdarr_Node\configs`. Logs: `C:\logs`.
- Scheduled task `tdarr-node` (SYSTEM, ONSTART) runs `C:\Tdarr_Node\run-tdarr-node.cmd`, which mounts the share then starts the node. Both files ACL'd to SYSTEM/Administrators.
- Server-side worker limits (per node ID): transcodegpu=1, everything else 0.
- To free the GPU for sim use: `schtasks /End /TN tdarr-node` then kill `Tdarr_Node*` and `ffmpeg` (`taskkill /f /im ffmpeg.exe`). Restart with `schtasks /Run /TN tdarr-node`.
- Pilot (V for Vendetta 4 min clip, 1080p h264): hevc_nvenc p6 -qp 20 -> 20% of source size, SSIM 0.9866 (QSV pilot was 0.986). `-cq 20` would give 53% / 0.990. Flow plugin picks NVENC automatically with `-qp`.
