#!/usr/bin/env python3
"""Aggregate extracted JSON -> results.json (merged 2026 + existing 94) and
results.csv (flat). Also produces intermediate structures for the EDA qmd.

- Loads every results/extracted/<idx>.json (the 2026 Ollama extraction).
- Merges with the existing LCWIP_database.json (94 entries) so the release shows
  the GROWN dataset (per user instruction: option B).
- Deduplicates by normalised URL / report_name.
- Writes:
    results/results.json   (list of merged records, 2026 schema-ish)
    results/results.csv     (flat table)
    results/results_2026_only.json (the fresh 2026 set)
"""
import json, os, re, csv
from urllib.parse import urlparse, unquote

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
for fn in sorted(os.listdir(EXT)):
    if not fn.endswith(".json") or fn == "_progress.json":
        continue
    d = json.load(open(os.path.join(EXT, fn)))
    extracted.append(d)
print(f"2026 extracted records: {len(extracted)}")

# --- existing 94 DB ---
old = json.load(open(os.path.join(ROOT, "LCWIP_database.json")))
print(f"existing 94-DB records: {len(old)}")

# Build merged: key by (norm_url) else (norm_name)
merged = {}
order = []

def merge_fields(into, src):
    """Fill any empty/None field in `into` from `src` (non-destructive)."""
    for k, v in src.items():
        if k.startswith("_"):
            continue
        if (into.get(k) in (None, "", [], {})) and (v not in (None, "", [], {})):
            into[k] = v

def add(rec, source_tag):
    key = norm_url(rec.get("pdf_url") or rec.get("_url"))
    if not key:
        key = "name:" + norm_name(rec.get("report_name") or rec.get("local_authority_name") or f"rec{len(merged)}")
    if key in merged:
        existing = merged[key]
        # prefer 2026 as primary; fill missing fields from the other
        if source_tag == "2026" and existing.get("_source_tag") != "2026":
            rec = dict(rec); rec["_source_tag"] = "2026"; rec["_merged_with_existing"] = True
            merge_fields(rec, existing)
            merged[key] = rec
        else:
            merge_fields(existing, rec)
            existing["_also_in_2026"] = (source_tag == "2026")
    else:
        r = dict(rec); r["_source_tag"] = source_tag
        merged[key] = r
        order.append(key)

# Also build a name index for secondary dedup so 2026 and existing94 with
# different URLs but same report_name merge.
name_index = {}

for d in extracted:
    add(d, "2026")
for o in old:
    add(o, "existing94")

# secondary pass: collapse by normalised report_name if multiple entries
final = {}
seen_names = set()
for k in order:
    r = merged[k]
    nm = norm_name(r.get("report_name"))
    if nm and nm in seen_names:
        # find the existing record with this name and merge
        for fk, fr in final.items():
            if norm_name(fr.get("report_name")) == nm:
                if fr.get("_source_tag") != "2026" and r.get("_source_tag") == "2026":
                    merged_rec = dict(r); merge_fields(merged_rec, fr)
                    final[fk] = merged_rec
                else:
                    merge_fields(fr, r)
                break
    else:
        if nm:
            seen_names.add(nm)
        final[k] = r

records = list(final.values())
print(f"merged unique records: {len(records)}")

# --- normalise a few fields for CSV ---
def to_bool(v):
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.strip().lower() in ("true", "yes", "1")
    return None

def to_num(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r"[£,]", "", str(v))
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None

rows = []
for r in records:
    rows.append({
        "source_tag": r.get("_source_tag"),
        "report_name": r.get("report_name"),
        "local_authority_name": r.get("local_authority_name") or r.get("local_authority_name"),
        "combined_authority_name": r.get("combined_authority_name"),
        "region": r.get("region"),
        "doc_type": r.get("doc_type"),
        "date_published": r.get("date_published"),
        "mentions_pct": to_bool(r.get("mentions_pct")),
        "pct_scenarios_used": r.get("pct_scenarios_used"),
        "desire_lines_used": to_bool(r.get("desire_lines_used")),
        "prioritisation_integration": to_bool(r.get("prioritisation_integration")),
        "how_pct_was_used": r.get("how_pct_was_used"),
        "specific_evidence_of_impact": r.get("specific_evidence_of_impact"),
        "quotes_on_using_pct": r.get("quotes_on_using_pct"),
        "other_tools_used": r.get("other_tools_used"),
        "length_of_network_km": to_num(r.get("length_of_network_km")),
        "total_cost_pounds": to_num(r.get("total_cost_pounds")),
        "routes": to_num(r.get("routes")),
        "pdf_url": r.get("pdf_url") or r.get("_url"),
        "download_status": r.get("_download_status") or ("ok" if r.get("_source_tag")=="existing94" else ""),
    })

# write json
json.dump(records, open(os.path.join(OUT, "results.json"), "w"), indent=2)
json.dump([r for r in records if r.get("_source_tag")=="2026"],
          open(os.path.join(OUT, "results_2026_only.json"), "w"), indent=2)

# write csv (flatten lists to ; )
with open(os.path.join(OUT, "results.csv"), "w", newline="") as f:
    cols = list(rows[0].keys())
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for row in rows:
        flat = {}
        for k, v in row.items():
            if isinstance(v, list):
                flat[k] = "; ".join(str(x) for x in v)
            elif v is None:
                flat[k] = ""
            else:
                flat[k] = v
        w.writerow(flat)

print(f"wrote results.json ({len(records)} records), results.csv, results_2026_only.json")
# quick summary
pct = sum(1 for r in rows if r["mentions_pct"] is True)
print(f"mentions_pct=True: {pct} / {len(rows)}")
print(f"2026-only: {sum(1 for r in rows if r['source_tag']=='2026')}")
print(f"LCWIP docs: {sum(1 for r in rows if r['doc_type']=='LCWIP')}")
print(f"LCWIP-related: {sum(1 for r in rows if r['doc_type']=='LCWIP-related')}")
