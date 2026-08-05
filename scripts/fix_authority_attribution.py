#!/usr/bin/env python3
"""Fix local_authority_name / transport_authority for extracted docs by URL pattern.

Gemini Pass-3 hallucinates authority names for some documents. We know the true
authority for each URL we discovered this round, so override by URL pattern.
Also clears obviously-wrong author/authority assignments on known-good URLs.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "results", "extracted")

# (url_substring, local_authority_name, transport_authority)
OVERRIDES = [
    # Somerset district LCWIPs (all on somersetcc.sharepoint.com)
    ("somersetcc.sharepoint.com", "Somerset Council", "Somerset Council"),
    # Devon adopted LCWIPs (devoncc.sharepoint.com)
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/EQfXU7KHrKFKg8m3", "Exeter LCWIP / Devon County Council", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/ERZ8e2qsbJ9GjhUb", "Cullompton and Tiverton LCWIP / Devon County Council", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/ERuIoF-oOkpMoKd", "Barnstaple, Bideford and Northam LCWIP / Devon County Council", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/EeJwZo7atrNMu", "Countywide LCWIP / Devon County Council", "Devon County Council"),
    ("devoncc.sharepoint.com/:b:/s/PublicDocs/Highways/EU4nM80Nn0dJg", "Heart of Teignbridge LCWIP / Devon County Council", "Devon County Council"),
    ("devoncc.sharepoint.com/sites/PublicDocs/Corporate/HaveYourSay", "Clyst Valley LCWIP / Devon County Council", "Devon County Council"),
    # Wiltshire district LCWIPs
    ("wiltshire.gov.uk/media/19933", "Wiltshire Council", "Wiltshire Council"),
    ("wiltshire.gov.uk/media/19934", "Wiltshire Council", "Wiltshire Council"),
    ("wiltshire.gov.uk/media/19936", "Wiltshire Council", "Wiltshire Council"),
    ("wiltshire.gov.uk/media/9640", "Wiltshire Council", "Wiltshire Council"),
    # Norfolk main reports
    ("norfolk.gov.uk/media/33545", "Norfolk County Council", "Norfolk County Council"),
    ("norfolk.gov.uk/media/20116", "Norfolk County Council", "Norfolk County Council"),
    # Guildford main document
    ("guildford.gov.uk/media/36792", "Guildford Borough Council", "Surrey County Council"),
    ("guildford.gov.uk/media/36793", "Guildford Borough Council", "Surrey County Council"),
    # Luton
    ("luton.gov.uk/sites/default/files/2026-03", "Luton Council", "Luton Council"),
    # Lancashire Fylde Coast (Blackpool/Fylde/Wyre partnership)
    ("lancashire.gov.uk/media/kzqpnp05", "Lancashire County Council & Blackpool Council (Fylde, Wyre)", "Lancashire County Council"),
    # North Northamptonshire district LCWIPs
    ("northnorthants.moderngov.co.uk/documents/s21269", "North Northamptonshire Council", "North Northamptonshire Council"),
    ("ketteringtowncouncil.gov.uk/uploads/kettering-lcwip", "North Northamptonshire Council", "North Northamptonshire Council"),
    # Tunbridge Wells Phase 1
    ("tunbridgewells.gov.uk/__data/assets/pdf_file/0003/385329", "Tunbridge Wells Borough Council", "Kent County Council"),
    # Isles of Scilly stage documents
    ("scilly.gov.uk/sites/default/files/document/environment-transport", "Council of the Isles of Scilly", "Council of the Isles of Scilly"),
    # Hertfordshire district LCWIPs
    ("stevenage.gov.uk/documents/planning-policy/evidential-studies/transport-infrastructure", "Stevenage Borough Council", "Hertfordshire County Council"),
    ("watford.moderngov.co.uk/documents/s36726", "Watford Borough Council", "Hertfordshire County Council"),
    ("hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/dacorum", "Dacorum Borough Council", "Hertfordshire County Council"),
    ("hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/eastherts", "East Herts District Council", "Hertfordshire County Council"),
    ("hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/north-hertfordshire", "North Hertfordshire District Council", "Hertfordshire County Council"),
    ("hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/three-rivers", "Three Rivers District Council", "Hertfordshire County Council"),
    ("hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/welwyn-hatfield", "Welwyn Hatfield Borough Council", "Hertfordshire County Council"),
    ("hertfordshire.gov.uk/about-the-council/consultations/transport-and-highways/lcwips-2022/hertsmere", "Hertsmere Borough Council", "Hertfordshire County Council"),
    # West Northamptonshire
    ("brixworthparishcouncil.gov.uk", "West Northamptonshire Council", "West Northamptonshire Council"),
    ("westnorthants.moderngov.co.uk/documents/s23340", "West Northamptonshire Council", "West Northamptonshire Council"),
    # Cumberland
    ("cumberland.gov.uk/sites/default/files/2025-04/carlisle", "Cumberland Council", "Cumberland Council"),
    ("cumberland.gov.uk/sites/default/files/2025-04/workington", "Cumberland Council", "Cumberland Council"),
    ("legacy.cumberland.gov.uk/elibrary/Content/Internet/538/18110/38384/44819114227", "Cumberland Council", "Cumberland Council"),
    # Suffolk county LCWIP
    ("suffolk.gov.uk/asset-library", "Suffolk County Council", "Suffolk County Council"),
    # Westmorland and Furness Barrow
    ("westmorlandandfurness.gov.uk/sites/default/files/2026-06/barrow", "Westmorland and Furness Council", "Westmorland and Furness Council"),
    # Blackburn with Darwen
    ("democracy.blackburn.gov.uk/documents/s22790", "Blackburn with Darwen Borough Council", "Blackburn with Darwen Borough Council"),
    # Hull summary results
    ("data.hull.gov.uk/wp-content/uploads/lcwip-2025-summary-results", "Hull City Council", "Hull City Council"),
    # GMCA content platform + committee system (some extraction names were
    # hallucinated/mismatched against the URL — the URL is authoritative)
    ("assets.ctfassets.net/xfhv954w443t", "Greater Manchester Combined Authority", "Greater Manchester Combined Authority"),
    ("democracy.greatermanchester-ca.gov.uk", "Greater Manchester Combined Authority", "Greater Manchester Combined Authority"),
    # Devon Countywide LCWIP committee-system documents
    ("democracy.devon.gov.uk/documents/s50968", "Devon County Council", "Devon County Council"),
    ("democracy.devon.gov.uk/documents/s50969", "Devon County Council", "Devon County Council"),
    # Dover LCWIP report (Kent)
    ("moderngov.dover.gov.uk", "Dover District Council", "Kent County Council"),
    # West Yorkshire Combined Authority committee item
    ("westyorkshire.moderngov.co.uk", "West Yorkshire Combined Authority", "West Yorkshire Combined Authority"),
    # Swindon full LCWIP (re-extraction enforced nulls because regex scan was 0)
    ("swindon.gov.uk/download/downloads/id/8394", "Swindon Borough Council", "Swindon Borough Council"),
    # --- 2026 sweep discoveries ---
    ("cornwall.gov.uk/media/ldinn5mw", "Cornwall Council", "Cornwall Council"),
    ("slough.gov.uk/download/downloads/id/900", "Slough Borough Council", "Slough Borough Council"),
    ("milton-keynes.gov.uk/sites/default/files/2023-02", "Milton Keynes Council", "Milton Keynes Council"),
    ("eastsussex.gov.uk/roads-transport/cycling-walking-cycling-plans", "East Sussex County Council", "East Sussex County Council"),
    ("iow.moderngov.co.uk/documents/s21352", "Isle of Wight Council", "Isle of Wight Council"),
    ("dorsetatipdec2025.pdf", "Dorset Council", "Dorset Council"),
    ("medway.gov.uk/downloads/200761", "Medway Council", "Medway Council"),
    ("southampton-lwip-full-final", "Southampton City Council", "Southampton City Council"),
    ("warrington.gov.uk/sites/default/files/2023-04", "Warrington Borough Council", "Warrington Borough Council"),
    ("myjourneywokingham.com", "Wokingham Borough Council", "Wokingham Borough Council"),
    ("birmingham.gov.uk/download/downloads/id/28472", "Birmingham City Council", "West Midlands Combined Authority"),
    ("yoursay.southend.gov.uk", "Southend-on-Sea City Council", "Southend-on-Sea"),
    ("telford.gov.uk/roadworks-transport-and-streets/travel-telford/cycling", "Telford & Wrekin Council", "Telford and Wrekin"),
    ("sandwell.gov.uk/downloads/download/352", "West Midlands Combined Authority", "West Midlands Combined Authority"),
    ("d2n2-local-cycling-and-walking-infrastructure-plan", "East Midlands Combined Authority", "East Midlands Combined Authority"),
    ("ampthill", "Central Bedfordshire Council", "Central Bedfordshire"),
    ("teesvalley-ca.gov.uk/wp-content/uploads/2023/09", "Tees Valley Combined Authority", "Tees Valley Combined Authority"),
    ("southyorkshire-ca.gov.uk", "South Yorkshire Combined Authority", "South Yorkshire Combined Authority"),
    ("gloucestershire.gov.uk/media/ty0bvtuo", "Gloucestershire County Council", "Gloucestershire"),
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
    for sub, la, ta in OVERRIDES:
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

print(f"fixed {fixed} files")
