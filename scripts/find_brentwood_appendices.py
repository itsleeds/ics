#!/usr/bin/env python3
"""Find and download all Brentwood LCWIP Appendix files (Appendix A, B, C, D) from moderngov.
"""
import urllib.request, re, os, urllib.parse

url = "https://brentwood.moderngov.co.uk/ieListDocuments.aspx?CId=420&MId=2483"
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"}

req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")

pdf_matches = re.findall(r'href=["\'](documents/s\d+/[^"\']+\.pdf)["\']', html, re.I)

print(f"Found {len(set(pdf_matches))} PDF links on agenda page:\n")
full_urls = []
for p in sorted(set(pdf_matches)):
    full = "https://brentwood.moderngov.co.uk/" + p
    full_urls.append(full)
    print("  ", full)
