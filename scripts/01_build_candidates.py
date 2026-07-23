#!/usr/bin/env python3
"""Build the initial candidate URL list from seed database and discovered URLs.

Reads:
  - data/LCWIP_database.json (or data/seed_urls_94.txt)
  - scripts/discovered_urls.txt (optional)

Writes:
  - scripts/candidates.json: list of {"url","source","note"}

Run: python scripts/01_build_candidates.py
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(u):
    u = u.strip()
    u = re.sub(r"[?#].*$", "", u).rstrip("/")
    return u.lower()

# --- seeds from database or txt file ---
seen = set()
seeds = []

db_path = os.path.join(ROOT, "data", "LCWIP_database.json")
seed_txt_path = os.path.join(ROOT, "data", "seed_urls_94.txt")

if os.path.exists(db_path):
    db = json.load(open(db_path))
    for e in db:
        u = e.get("pdf_url")
        if not u:
            continue
        key = norm(u)
        if key in seen:
            continue
        seen.add(key)
        seeds.append({
            "url": u,
            "source": "seed-94db",
            "note": (e.get("local_authority_name") or "")[:80]
        })
elif os.path.exists(seed_txt_path):
    for line in open(seed_txt_path):
        u = line.strip()
        if not u or u.startswith("#"):
            continue
        key = norm(u)
        if key in seen:
            continue
        seen.add(key)
        seeds.append({"url": u, "source": "seed-94db", "note": ""})

# --- discovered URLs ---
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
