#!/usr/bin/env python3
"""Delete youtube_new/.archive video copies whose library hardlink was replaced by a Tdarr transcode.

A .archive file is deleted only if ALL hold:
  - st_nlink == 1 (library hardlink is gone, so it is no longer shared)
  - a non-archive library file with the same [videoid] exists, is smaller, and is newer
Default is dry-run; pass --apply to delete.
"""
import os, re, sys, time
ROOT = "/srv/mergerfs/Array/media/youtube_new"
ARCH = os.path.join(ROOT, "__Motorsports", ".archive")
ID = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.(mkv|mp4)$")
apply = "--apply" in sys.argv
lib = {}
for d, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in (".archive", ".youtarr_tmp")]
    for f in files:
        m = ID.search(f)
        if m:
            lib.setdefault(m.group(1), []).append(os.path.join(d, f))
freed = n = 0
for d, _, files in os.walk(ARCH):
    for f in files:
        m = ID.search(f)
        if not m:
            continue
        p = os.path.join(d, f)
        st = os.stat(p)
        if st.st_nlink != 1:
            continue
        for q in lib.get(m.group(1), []):
            qs = os.stat(q)
            if qs.st_size < st.st_size and qs.st_mtime > st.st_mtime and time.time() - qs.st_mtime > 600:
                print(("DELETE " if apply else "would delete ") + p, st.st_size, "->", q, qs.st_size)
                if apply:
                    os.remove(p)
                freed += st.st_size - qs.st_size
                n += 1
                break
print(f"{n} archive files, net saved {freed/1e9:.1f} GB (apply={apply})")
