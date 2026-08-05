#!/usr/bin/env python3
"""Cleanup pass: drop junk records, fix remaining attribution, fix Blackburn PCTx6."""
import json, os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "results", "extracted")

# 1) junk records to REMOVE entirely (no real document content)
JUNK_URL_SUBSTR = [
    "atkinsrealis.com",                      # homepage link, not a document
    "devoncc.sharepoint.com/sites/PublicDocs/Corporate/HaveYourSay/Forms/AllItems.aspx",  # HTML shell
    "tunbridgewells.gov.uk/__data/assets/pdf_file/0003/385329",  # 403-failed Phase 1
    "surreycc.gov.uk/transport-and-streets/road-safety-and-active-travel/active-travel-scheme",  # landing page
    "scilly.gov.uk/environment-transport/highways/local-cycling-walking-infrastructure-plan",  # landing page
]
removed = 0
for fn in sorted(os.listdir(EXT)):
    if not re.match(r"^\d{4}\.json$", fn):
        continue
    path = os.path.join(EXT, fn)
    try:
        e = json.load(open(path))
    except Exception:
        continue
    u = (e.get("pdf_url") or e.get("url") or "").lower()
    if any(s.lower() in u for s in JUNK_URL_SUBSTR):
        os.remove(path)
        removed += 1
        print(f"removed junk: {fn} {u[:70]}")
print(f"removed {removed} junk records\n")

# 2) attribution fixes on remaining records
FIXES = [
    # Luton old URL was misattributed to Hull
    ("luton.gov.uk/transport_and_streets", "Luton Council", "Luton Council"),
    # Devon labels roll up to Devon County Council
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/EQfXU7KHrKFKg8m3", "Devon County Council (Exeter LCWIP)", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/ERZ8e2qsbJ9GjhUb", "Devon County Council (Cullompton and Tiverton LCWIP)", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/ERuIoF-oOkpMoKd", "Devon County Council (Barnstaple, Bideford and Northam LCWIP)", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/EeJwZo7atrNMu", "Devon County Council (Countywide LCWIP)", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Highways/EU4nM80Nn0dJg", "Devon County Council (Heart of Teignbridge LCWIP)", "Devon County Council"),
    # Tunbridge Wells Phase 2 -> proper label
    ("tunbridgewells.gov.uk/__data/assets/pdf_file/0007/385333", "Tunbridge Wells Borough Council", "Kent County Council"),
    # Hull: the yoursay draft + summary
    ("yoursay.hull.gov.uk/42351", "Hull City Council", "Hull City Council"),
    ("data.hull.gov.uk/wp-content/uploads/lcwip-2025-summary-results", "Hull City Council", "Hull City Council"),
    # West of England
    ("s3-eu-west-1.amazonaws.com/travelwest", "Bath & North East Somerset, Bristol City, South Gloucestershire, North Somerset (West of England LCWIP)", "West of England Combined Authority"),
    ("westofengland-ca.gov.uk/wp-content/uploads/2021/09", "Bath & North East Somerset, Bristol City, South Gloucestershire, North Somerset (West of England LCWIP)", "West of England Combined Authority"),
]
fixed = 0
for fn in sorted(os.listdir(EXT)):
    if not re.match(r"^\d{4}\.json$", fn):
        continue
    path = os.path.join(EXT, fn)
    try:
        e = json.load(open(path))
    except Exception:
        continue
    u = (e.get("pdf_url") or e.get("url") or "").lower()
    for sub, la, ta in FIXES:
        if sub.lower() in u:
            changed = False
            if e.get("local_authority_name") != la:
                e["local_authority_name"] = la
                changed = True
            if e.get("transport_authority") != ta:
                e["transport_authority"] = ta
                changed = True
            if changed:
                json.dump(e, open(path, "w"), indent=2)
                fixed += 1
                print(f"fixed {fn}: {la}")
            break
print(f"fixed {fixed} records\n")

# 3) Blackburn: "Cycling demand (PCTx6)" is a real PCT mention missed by \bPCT\b regex
for fn in sorted(os.listdir(EXT)):
    if not re.match(r"^\d{4}\.json$", fn):
        continue
    path = os.path.join(EXT, fn)
    e = json.load(open(path))
    u = (e.get("pdf_url") or e.get("url") or "").lower()
    if "democracy.blackburn.gov.uk/documents/s22790" in u:
        md = e.get("md_file") or ""
        txt = open(md, errors="ignore").read() if md and os.path.exists(md) else ""
        if "PCTx" in txt or "PCT x" in txt:
            e["mentions_pct"] = True
            e["pct_mentioned"] = True
            e["n_mentions_pct"] = 1
            e["pct_term_breakdown"] = {"pct": 1, "propensity_to_cycle_tool": 0, "pct_bike": 0}
            e["pct_usage_depth"] = "2 - Contextual background / data input"
            e["how_pct_was_used"] = "PCT-derived cycling demand data (PCTx6) used in route prioritisation scoring criteria."
            e["pct_usage_quote"] = "Cycling demand (PCTx6)"
            json.dump(e, open(path, "w"), indent=2)
            print(f"fixed Blackburn PCT mention in {fn}")
        break
