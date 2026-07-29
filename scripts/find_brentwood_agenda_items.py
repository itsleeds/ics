#!/usr/bin/env python3
"""Find the exact meeting ID and PDF attachments for Brentwood 19 Nov 2025.
"""
import urllib.request, re

headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

for mid in range(2400, 2600):
    url = f"https://brentwood.moderngov.co.uk/ieListDocuments.aspx?MId={mid}"
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=3).read().decode("utf-8", errors="ignore")
        if "19th November 2025" in html or "s29126" in html or "Local Cycling" in html:
            print(f"FOUND MATCH at MId={mid}!")
            pdf_matches = re.findall(r'href=["\'](documents/s\d+/[^"\']+\.pdf)["\']', html, re.I)
            for p in pdf_matches:
                print("  https://brentwood.moderngov.co.uk/" + p)
            break
    except Exception:
        pass
