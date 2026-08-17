#!/usr/bin/env python3
"""Test SharePoint :b: guest link download patterns for Somerset/Devon."""
import sys, io, requests

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

TEST_URLS = [
    # Somerset Chard LCWIP (1.6MB)
    "https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EQUkjhzzB71HhgCuaPSNSdAB_h-dvao7hjBFam3yLlFazQ?e=TNMmo1",
    # Somerset Taunton LCWIP (4.29MB)
    "https://somersetcc.sharepoint.com/:b:/s/SCCPublic/EVjxZcxHLRlKm7g40uVhezEBMgppAX3EjtdKwtimpg9HoQ?e=1070c6",
    # Devon Countywide LCWIP (adopted March 2025)
    "https://devoncc.sharepoint.com/:b:/s/PublicDocs/Corporate/EeJwZo7atrNMu-Wm_PxK4P8B4pL3khBvIRz5qhepIyE82w?e=WVORrm",
    # Norfolk main Countywide report
    "https://www.norfolk.gov.uk/media/33545/Countywide-Local-Cycling-and-Walking-Infrastructure-Plan---main-report---February-2024/pdf/hmCountywide_LCWIP_2024_Accessible.pdf?m=1718357720090",
    # Guildford Chapter 1 main doc
    "https://www.guildford.gov.uk/media/36792/Guildford-LCWIP-Chapter-1/pdf/Guildford_LCWIP_Chapter_1.pdf?m=1746179679717",
]

def probe(u, label):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    try:
        r = s.get(u, allow_redirects=True, timeout=45)
        ctype = r.headers.get("Content-Type", "")
        is_pdf = r.content.startswith(b"%PDF")
        print(f"[{label}] {u}")
        print(f"   status={r.status_code} bytes={len(r.content)} ctype={ctype} pdf={is_pdf} final_url={r.url[:110]}")
        if is_pdf:
            return r.content
        if len(r.content) < 5000:
            print(f"   body: {r.content[:400]}")
        # try download=1
        if ":b:/" in u or "/:b:/" in u:
            dl = u + ("&" if "?" in u else "?") + "download=1"
            r2 = s.get(dl, allow_redirects=True, timeout=45)
            is_pdf2 = r2.content.startswith(b"%PDF")
            print(f"   download=1 -> status={r2.status_code} bytes={len(r2.content)} pdf={is_pdf2}")
            if is_pdf2:
                return r2.content
    except Exception as e:
        print(f"[{label}] ERROR: {e}")
    return None

for item in TEST_URLS:
    u = item if isinstance(item, str) else item[0]
    label = "t" if isinstance(item, str) else item[1]
    probe(u, label)
    print()
