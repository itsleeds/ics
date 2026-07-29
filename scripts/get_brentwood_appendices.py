#!/usr/bin/env python3
"""Inspect and download Brentwood LCWIP Appendices s29120-s29132.
"""
import urllib.request, re, os

base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data-govuk-2026-raw")

headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"}

for sid in range(29120, 29135):
    url = f"https://brentwood.moderngov.co.uk/documents/s{sid}/"
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8", errors="ignore")
        matches = re.findall(r'href=["\'](/documents/s\d+/[^"\']+\.pdf)["\']', html, re.I)
        if matches:
            pdf_url = "https://brentwood.moderngov.co.uk" + matches[0]
            fn = os.path.basename(urllib.parse.unquote(pdf_url))
            print(f"s{sid} -> PDF: {fn}")
            print(f"       URL: {pdf_url}")
            
            # Download file
            dest = os.path.join(base_dir, f"0101-brentwood-appendix-s{sid}-{fn}")
            urllib.request.urlretrieve(pdf_url, dest)
            print(f"       Downloaded ({os.path.getsize(dest)/1024:.1f} KB) -> {dest}\n")
    except Exception as e:
        pass
