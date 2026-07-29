#!/usr/bin/env python3
"""Search brentwood.moderngov.co.uk for Appendix A, B, C, D PDFs.
"""
import urllib.request, urllib.parse, re

query_url = "https://brentwood.moderngov.co.uk/mgSearch.aspx?bkgd=0&q=LCWIP"
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

req = urllib.request.Request(query_url, headers=headers)
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")

pdf_matches = re.findall(r'href=["\'](documents/s\d+/[^"\']+)["\']', html, re.I)
print(f"Found {len(set(pdf_matches))} search results:")
for p in sorted(set(pdf_matches)):
    print("  https://brentwood.moderngov.co.uk/" + p)
