# Tdarr flow: H265 Safe (video only)
Reference export of flow `h265safe01` (live in Tdarr appdata DB on saturn, not deployed by Ansible).
Restore: POST /api/v2/cruddb {"data":{"collection":"FlowsJSONDB","mode":"insert","docID":"h265safe01","obj":<json>}}.
HEVC QSV CQ20 slow, MKV, audio/subs copied; skips hevc/av1; gates: duration +-0.5%, size 20-95%, thorough health check before replacing the original.
Libraries Movies/TV: filterCodecsSkip=hevc,av1, global queueSortType=sortSizeLargest.
