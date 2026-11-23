# Tdarr flow: H265 Safe (video only)
Reference export of flow `h265safe01` (live in Tdarr appdata DB on saturn, not deployed by Ansible).
Restore: POST /api/v2/cruddb {"data":{"collection":"FlowsJSONDB","mode":"insert","docID":"h265safe01","obj":<json>}}.
HEVC QSV CQ20 slow, MKV, audio/subs copied; skips hevc/av1; gates: duration +-0.5%, size 20-95%, thorough health check before replacing the original.
Libraries Movies/TV: filterCodecsSkip=hevc,av1, global queueSortType=sortSizeLargest.

## YouTube New library (id `yTnew0001`, `/media/youtube_new/`)
Cloned from TV settings (flow h265safe01). Ignores `.archive,.youtarr_tmp,.poster_backup_1116,orig-thumbs`. Library files under `__Motorsports/<Show>/Season NN/` are hardlinked to `.archive/`, so a transcode alone saves nothing: `files/tdarr/archive_cleanup.py` (installed hourly by `playbooks/tdarr-archive-cleanup.yml`) deletes archive copies once the library copy is a smaller, newer, unlinked file with the same `[videoid]`.
