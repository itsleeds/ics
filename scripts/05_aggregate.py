#!/usr/bin/env python3
"""Aggregate extracted JSONs into results/results.json and results/results_flat.csv.

Reads:
  - results/extracted/*.json
  - data/LCWIP_database.json (or LCWIP_database.json)

Outputs:
  - results/results.json (merged 2026 + existing 94)
  - results/results_flat.csv (flat table for analysis)
  - results/results_2026_only.json (2026 extraction set)

Run: python scripts/05_aggregate.py
"""
import json, os, re, csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "results", "extracted")
OUT = os.path.join(ROOT, "results")
os.makedirs(OUT, exist_ok=True)

def norm_url(u):
    if not u: return ""
    u = re.sub(r"[?#].*$", "", u or "").rstrip("/").lower()
    return u

def norm_name(n):
    return re.sub(r"\s+", " ", (n or "").lower()).strip()

# --- 2026 extracted ---
extracted = []
if os.path.exists(EXT):
    for fn in sorted(os.listdir(EXT)):
        if not fn.endswith(".json") or fn == "_progress.json":
            continue
        d = json.load(open(os.path.join(EXT, fn)))
        extracted.append(d)
print(f"2026 extracted records: {len(extracted)}")

# --- existing 94 DB ---
db_path = os.path.join(ROOT, "data", "LCWIP_database.json")
if not os.path.exists(db_path):
    db_path = os.path.join(ROOT, "LCWIP_database.json")

if os.path.exists(db_path):
    old = json.load(open(db_path))
    print(f"existing 94-DB records: {len(old)}")
else:
    old = []
    print("existing 94-DB records: 0 (file not found)")

merged = {}
order = []

for e in extracted:
    u = norm_url(e.get("pdf_url") or e.get("url"))
    n = norm_name(e.get("report_name"))
    k = u or n
    if not k:
        k = f"idx_{e.get('idx')}"
    e["_source_tag"] = "2026"
    merged[k] = e
    order.append(k)

for o in old:
    u = norm_url(o.get("pdf_url"))
    n = norm_name(o.get("report_name"))
    k = u or n
    if not k:
        continue
    if k in merged:
        m = merged[k]
        for field in ("local_authority_name", "date_published", "year_published"):
            if not m.get(field) and o.get(field):
                m[field] = o[field]
        if not m.get("pct_mentioned") and o.get("pct_mentioned"):
            m["pct_mentioned"] = o["pct_mentioned"]
    else:
        rec = {
            "_source_tag": "existing94",
            "report_name": o.get("report_name"),
            "local_authority_name": o.get("local_authority_name"),
            "transport_authority": o.get("transport_authority"),
            "region": o.get("region"),
            "doc_type": "LCWIP",
            "date_published": o.get("date_published"),
            "year_published": o.get("year_published"),
            "pct_mentioned": o.get("pct_mentioned"),
            "pct_scenarios": o.get("pct_scenarios"),
            "pct_usage_quote": o.get("pct_usage_quote"),
            "pdf_url": o.get("pdf_url"),
            "download_status": "ok" if o.get("pdf_url") else "missing"
        }
        merged[k] = rec
        order.append(k)

final_list = [merged[k] for k in order]

with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(final_list, f, indent=2)

with open(os.path.join(OUT, "results_2026_only.json"), "w") as f:
    json.dump(extracted, f, indent=2)

# Write flat CSV
all_keys = set()
for r in final_list:
    all_keys.update(r.keys())

preferred_cols = [
    "_source_tag", "idx", "report_name", "local_authority_name", "transport_authority",
    "region", "doc_type", "date_published", "year_published", "pct_mentioned",
    "n_pct_mentions", "n_mentions_pct", "pct_used_for_prioritisation",
    "pct_scenarios", "pct_usage_quote", "download_status", "pdf_url"
]
other_cols = sorted(list(all_keys - set(preferred_cols)))
cols = [c for c in preferred_cols if c in all_keys] + other_cols

with open(os.path.join(OUT, "results_flat.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=cols)
    writer.writeheader()
    for r in final_list:
        row = {}
        for k in cols:
            val = r.get(k)
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            row[k] = val
        writer.writerow(row)

print(f"Wrote {os.path.join(OUT, 'results.json')} ({len(final_list)} merged records)")
print(f"Wrote {os.path.join(OUT, 'results_flat.csv')}")
