#!/usr/bin/env python3
"""Dedupe results/extracted/*.json to one file per unique URL, re-keyed to documents.json idx.

- For each unique normalized URL, keep the max-idx file (this is the record
  05_aggregate.py would keep: merged[k] = e in sorted-filename order).
- Stray records (URLs not in documents.json) are kept as-is.
- Re-key survivors to the idx documents.json assigns to their URL, so
  04_run_extract.py's skip logic aligns.
"""
import json, os, shutil, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "results", "extracted")
DOCS = json.load(open(os.path.join(ROOT, "scripts", "documents.json")))

def norm_url(u):
    if not u:
        return ""
    return re.sub(r"[?#].*$", "", u).rstrip("/").lower()

url_to_idx = {}
for d in DOCS:
    url_to_idx.setdefault(norm_url(d.get("url")), d["idx"])

# 1) group files by normalized URL, keep max idx per URL
by_url = {}
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
    cur = by_url.get(u)
    if cur is None or fn > cur[0]:
        by_url[u] = (fn, path)

keep = set()
for fn, path in by_url.values():
    keep.add(fn)

# 2) move non-kept to a backup dir
BACKUP = os.path.join(ROOT, "results", "extracted_dups_backup")
os.makedirs(BACKUP, exist_ok=True)
removed = 0
for fn in sorted(os.listdir(EXT)):
    if re.match(r"^\d{4}\.json$", fn) and fn not in keep:
        shutil.move(os.path.join(EXT, fn), os.path.join(BACKUP, fn))
        removed += 1

# 3) re-key survivors to documents.json idx
for fn, path in list(by_url.values()):
    try:
        e = json.load(open(path))
    except Exception:
        continue
    u = norm_url(e.get("pdf_url") or e.get("url"))
    new_idx = url_to_idx.get(u)
    if new_idx is None:
        continue
    new_fn = f"{new_idx:04d}.json"
    if new_fn != fn:
        new_path = os.path.join(EXT, new_fn)
        if os.path.exists(new_path):
            os.replace(path, new_path)  # overwrite stale file at target slot
        else:
            shutil.move(path, new_path)
        # fix embedded idx field
        e["idx"] = new_idx
        json.dump(e, open(new_path, "w"), indent=2)

print(f"deduped: removed {removed} duplicate files, kept {len(by_url)} unique URLs")
