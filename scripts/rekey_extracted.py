#!/usr/bin/env python3
"""Two-phase re-key of results/extracted/*.json to documents.json idx (by URL).

Phase 1: stage every extracted file to results/extracted/.staging/<url-hash>.json
Phase 2: rename into the final idx slot assigned by documents.json.
Duplicate URLs -> keep the file with the freshest mtime (most recent extraction).
"""
import json, os, shutil, re, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "results", "extracted")
STAGE = os.path.join(EXT, ".staging")
DOCS = json.load(open(os.path.join(ROOT, "scripts", "documents.json")))

def norm_url(u):
    if not u:
        return ""
    return re.sub(r"[?#].*$", "", u).rstrip("/").lower()

url_to_idx = {}
for d in DOCS:
    url_to_idx.setdefault(norm_url(d.get("url")), d["idx"])

os.makedirs(STAGE, exist_ok=True)
# Phase 1: stage by URL, preferring freshest mtime
staged = {}
for fn in sorted(os.listdir(EXT)):
    if not re.match(r"^\d{4}\.json$", fn):
        continue
    path = os.path.join(EXT, fn)
    try:
        e = json.load(open(path))
    except Exception:
        continue
    u = norm_url(e.get("pdf_url") or e.get("url"))
    if not u:
        continue
    key = hashlib.md5(u.encode()).hexdigest() + ".json"
    spath = os.path.join(STAGE, key)
    if os.path.exists(spath):  # duplicate URL: keep fresher mtime
        if os.path.getmtime(path) > os.path.getmtime(spath):
            os.replace(path, spath)
        continue
    shutil.move(path, spath)
    staged[u] = spath

# Phase 2: rename staged files into final idx slots
moved = 0
for u, spath in staged.items():
    idx = url_to_idx.get(u)
    if idx is None:
        continue
    final = os.path.join(EXT, f"{idx:04d}.json")
    shutil.move(spath, final)
    try:
        e = json.load(open(final))
        e["idx"] = idx
        json.dump(e, open(final, "w"), indent=2)
    except Exception:
        pass
    moved += 1

leftover = os.listdir(STAGE)
print(f"re-keyed {moved} files; leftover staged: {len(leftover)}")
