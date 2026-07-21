#!/usr/bin/env python3
"""Build the initial candidate URL list from the existing 94-entry DB (seeds)
and merge with any discovered URLs found in scripts/discovered_urls.txt.
Writes scripts/candidates.json: list of {"url","source","note"}.
"""
import json, hashlib, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(u):
    u = u.strip()
    u = re.sub(r"[?#].*$", "", u)  # drop query/fragment for dedup key
    u = u.rstrip("/")
    return u.lower()

# --- seeds from existing DB ---
db = json.load(open(os.path.join(ROOT, "LCWIP_database.json")))
seeds = []
seen = set()
for e in db:
    u = e.get("pdf_url")
    if not u:
        continue
    key = norm(u)
    if key in seen:
        continue
    seen.add(key)
    seeds.append({"url": u, "source": "seed-94db",
                  "note": (e.get("local_authority_name") or "")[:80]})

# --- discovered (one URL per line, optional trailing tab/space + note) ---
disc = []
df = os.path.join(ROOT, "scripts", "discovered_urls.txt")
if os.path.exists(df):
    for line in open(df):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        u = parts[0].strip()
        note = parts[1].strip() if len(parts) > 1 else ""
        key = norm(u)
        if key in seen:
            continue
        seen.add(key)
        disc.append({"url": u, "source": "web-search", "note": note})

allc = seeds + disc
out = os.path.join(ROOT, "scripts", "candidates.json")
json.dump(allc, open(out, "w"), indent=2)
print(f"seeds={len(seeds)} discovered={len(disc)} total={len(allc)}")
print(f"wrote {out}")
