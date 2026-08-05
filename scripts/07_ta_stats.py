#!/usr/bin/env python3
"""Authority-level PCT usage stats, mapped to the 74 transport authorities (2026 definition).

Maps every document's authority label to one of the 74 transport authorities
(uktransportauthorities/transport_authorities_2026.geojson) using, in order:
  1. results/la_transport_authority_lookup.csv (curated district -> TA map)
  2. direct (normalised) name match against the 74 TA names
  3. curated alias map for common label variants / multi-authority labels
  4. difflib fuzzy fallback (reported, low confidence)

Outputs:
  - transport-authority-level PCT usage (primary metric)
  - local-authority (district)-level coverage (secondary)
  - lists of covered-but-no-PCT TAs and uncovered TAs
  - unmatched labels for manual review
"""
import csv, difflib, json, os, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UKTA = os.path.join(os.path.dirname(ROOT), "uktransportauthorities")

res = json.load(open(os.path.join(ROOT, "results", "results.json")))
ta_features = json.load(open(os.path.join(UKTA, "transport_authorities_2026.geojson")))["features"]
TA_NAMES = [f["properties"]["name"] for f in ta_features]
TA_LADS = {f["properties"]["name"]: (f["properties"].get("lad_lookup") or []) for f in ta_features}
TA_NORM = {re.sub(r"[^a-z0-9]+", " ", n.lower()).strip(): n for n in TA_NAMES}


def norm(n):
    return re.sub(r"[^a-z0-9]+", " ", (n or "").lower()).strip()


# 1. curated lookup csv (district label -> TA)
LOOKUP = {}
with open(os.path.join(ROOT, "results", "la_transport_authority_lookup.csv")) as f:
    for row in csv.DictReader(f):
        d, ta = row.get("local_authority_district"), row.get("transport_authority")
        if d and ta and ta in TA_NAMES:
            LOOKUP.setdefault(norm(d), ta)

# 3. curated aliases for label variants not covered by lookup / name match
ALIASES = {
    "BCP Council": "Bournemouth, Christchurch and Poole",
    "Brighton Hove City Council": "Brighton and Hove",
    "Hull City Council": "Kingston upon Hull",
    "Hull": "Kingston upon Hull",
    "Plymouth City Council": "Plymouth",
    "City of York Council": "York",
    "Suffolk County Council": "Suffolk",
    "Kent County Council": "Kent",
    "Norfolk County Council": "Norfolk",
    "Stoke on Trent City Council": "Stoke-on-Trent",
    "Swindon Borough Council": "Swindon",
    "Luton Council": "Luton",
    "Devon County Council": "Devon",
    "Staffordshire County Council": "Staffordshire",
    "Hertfordshire County Council": "Hertfordshire",
    "Wiltshire Council": "Wiltshire",
    "Somerset Council": "Somerset",
    "North Northamptonshire Council": "North Northamptonshire",
    "Oxfordshire County Council": "Oxfordshire",
    "Warwickshire County Council": "Warwickshire",
    "Surrey County Council": "Surrey",
    "West Sussex County Council": "West Sussex",
    "Shropshire Council": "Shropshire",
    "Thurrock Council": "Thurrock",
    "Torbay Council": "Torbay",
    "Portsmouth City Council": "Portsmouth",
    "Reading Borough Council": "Reading",
    "West Berkshire Council": "West Berkshire",
    "Bracknell Forest Council": "Bracknell Forest",
    "Buckinghamshire Council": "Buckinghamshire",
    "Cheshire East Council": "Cheshire East",
    "Cheshire West and Chester Council": "Cheshire West and Chester",
    "Herefordshire Council": "Herefordshire",
    "Cumberland Council": "Cumberland",
    "Westmorland and Furness Council": "Westmorland and Furness",
    "North Yorkshire Council": "North Yorkshire",
    "North Yorkshire County Council": "North Yorkshire",
    "Durham County Council": "North East Combined Authority",
    "Cumbria County Council": "Cumbria",
    "Cambridgeshire County Council": "Cambridgeshire and Peterborough Combined Authority",
    "Peterborough City Council": "Cambridgeshire and Peterborough Combined Authority",
    "Leicestershire County Council": "East Midlands Combined Authority",
    "Rutland County Council": "East Midlands Combined Authority",
    "Sunderland City Council": "North East Combined Authority",
    "St Helens Borough Council": "Liverpool City Region Combined Authority",
    "Knowsley Metropolitan Borough Council": "Liverpool City Region Combined Authority",
    "Ipswich Borough Council": "Suffolk",
    "Brentwood": "Essex",
    "St Albans District Council": "Hertfordshire",
    "Cornwall Council": "Cornwall",
    "Dorset Council": "Dorset",
    "Medway Council": "Medway",
    "Slough Borough Council": "Slough",
    "Wokingham Borough Council": "Wokingham",
    "Milton Keynes Council": "Milton Keynes",
    "Milton Keynes City Council": "Milton Keynes",
    "Borough Council of Kings Lynn and West Norfolk": "Norfolk",
    "Tunbridge Wells": "Kent",
    "South Oxfordshire District Council and Vale of White Horse District Council": "Oxfordshire",
    "South Hams District Council and West Devon Borough Council": "Devon",
    "Hart District Council and Hampshire County Council": "Hampshire",
    "Hampshire County Council Basingstoke and Deane Borough Council": "Hampshire",
    "Derby City Council Derbyshire County Council Nottingham City Council and Nottinghamshire County Council 3": "East Midlands Combined Authority",
    "West Yorkshire": "West Yorkshire Combined Authority",
    "West of England Combined Authority": "West of England Combined Authority",
    "Liverpool City Region Combined Authority (LCRCA), in partnership with Halton, Knowsley, Liverpool, Sefton, St Helens, and Wirral councils.[1]": "Liverpool City Region Combined Authority",
}
ALIAS_NORM = {norm(k): v for k, v in ALIASES.items()}

# Documents produced jointly by more than one transport authority.
# Keyed by normalized URL (norm() strips query strings and trailing slash).
MULTI_TAS = {
    norm("https://www.lancashire.gov.uk/media/kzqpnp05/fylde-coast.pdf"): ["Lancashire", "Blackpool"],
}


def match_tas(r):
    """Return list of TA names for a document record (joint docs -> multiple)."""
    u = norm(r.get("pdf_url") or r.get("url"))
    if u in MULTI_TAS:
        return MULTI_TAS[u]
    # West of England LCWIP documents are partnership products of WECA + the 4
    # unitary councils; North Somerset is a separate 2026 TA covered by them.
    lab = r.get("transport_authority") or r.get("local_authority_name") or ""
    rep = str(r.get("report_name") or "")
    if ("Bath & North East Somerset" in lab) or ("West of England" in lab and "LCWIP" in rep):
        return ["West of England Combined Authority", "North Somerset"]
    m = match_ta(lab)
    return [m] if m else []


def match_ta(label):
    """Return TA name for a document authority label, or None."""
    l = norm(label)
    if not l:
        return None
    # Multi-authority labels (contain commas/semicolons) must not be
    # contains-matched against single-authority aliases/TA names — e.g. the
    # West of England 4-council label must not match the "Somerset" alias.
    # Check the RAW label: norm() strips the punctuation away.
    is_multi = ("," in (label or "")) or (";" in (label or ""))
    # 1. exact matches first (TA names, then lookup keys, then aliases)
    if l in TA_NORM:
        return TA_NORM[l]
    if l in LOOKUP:
        return LOOKUP[l]
    if l in ALIAS_NORM:
        return ALIAS_NORM[l]
    # 2. contains matches against aliases (curated, safest). Skip multi-
    #    authority labels (see is_multi above).
    if not is_multi:
        for k, ta in ALIAS_NORM.items():
            if k and (k in l or l in k):
                return ta
    # 3. contains matches against lookup csv keys (curated district labels)
    for k, ta in LOOKUP.items():
        if k and (k in l or l in k):
            return ta
    # 4. contains match against full TA names, only for reasonably long
    #    names (avoids "York" matching inside "North Yorkshire", "Kent" etc.)
    if not is_multi:
        for k, n in sorted(TA_NORM.items(), key=lambda kv: -len(kv[0])):
            if len(k) >= 8 and (k in l or l in k):
                return n
    return None


doc_ta = []      # (ta_name, mentions_pct, label)
unmatched = []
for r in res:
    label = r.get("transport_authority") or r.get("local_authority_name") or r.get("combined_authority_name")
    tas = match_tas(r)
    if tas:
        for t in tas:
            doc_ta.append((t, r.get("mentions_pct") is True, label))
    else:
        unmatched.append((label, r.get("idx"), r.get("report_name")))

print(f"documents: {len(res)}, matched to a TA: {len(doc_ta)}, unmatched: {len(unmatched)}")
if unmatched:
    print("  unmatched labels (idx | label | report):")
    for label, idx, name in sorted(unmatched, key=lambda x: str(x[0])):
        print(f"    {idx} | {label} | {name}")

ta_docs = defaultdict(list)
for ta_name, mentions, label in doc_ta:
    ta_docs[ta_name].append((mentions, label))

pct_yes = sorted(n for n, ms in ta_docs.items() if any(m for m, _ in ms))
pct_no = sorted(n for n, ms in ta_docs.items() if not any(m for m, _ in ms))
uncovered = sorted(set(TA_NAMES) - set(ta_docs))

print()
print(f"Transport authorities WITH a PCT-mentioning document: {len(pct_yes)} / {len(TA_NAMES)} "
      f"({100 * len(pct_yes) / len(TA_NAMES):.1f}%)")
print(f"Transport authorities covered by dataset: {len(ta_docs)} / {len(TA_NAMES)}")
print(f"Of covered, PCT-using: {len(pct_yes)} / {len(ta_docs)} ({100 * len(pct_yes) / len(ta_docs):.1f}%)")
print()
print("=== PCT-USING TRANSPORT AUTHORITIES ===")
print("  " + ", ".join(pct_yes))
print()
print("=== COVERED BUT NO PCT-MENTIONING DOCUMENT ===")
for n in pct_no:
    labels = sorted({lab for _, lab in ta_docs[n]})
    print(f"  {n}: {len(ta_docs[n])} docs | labels: {labels}")
print()
print("=== NOT COVERED (no documents in dataset) ===")
for n in uncovered:
    print(f"  {n}")

# Secondary: local-authority (district/LAD) level coverage
lad_docs = defaultdict(list)   # LAD name -> list of mentions_pct
for ta_name, mentions, label in doc_ta:
    # label itself is the best LAD proxy; also map via lookup district column
    lad_docs[label].append(mentions)
lad_yes = sorted(k for k, v in lad_docs.items() if any(v))
lad_all = sorted(lad_docs)
print()
print(f"=== SECONDARY: distinct local-authority labels covered = {len(lad_all)}, "
      f"with PCT mention = {len(lad_yes)} ({100 * len(lad_yes) / len(lad_all):.1f}%) ===")
for k in sorted(set(lad_all) - set(lad_yes)):
    print(f"  no PCT: {k} ({len(lad_docs[k])} docs)")
