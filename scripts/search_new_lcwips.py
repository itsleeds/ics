#!/usr/bin/env python3
"""Search web for new LCWIP PDF candidate URLs not currently in documents.json.
"""
import urllib.parse, urllib.request, json, re, os, time
from typing import List, Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_PATH = os.path.join(ROOT, "scripts", "documents.json")
DISCOVERED_PATH = os.path.join(ROOT, "scripts", "discovered_urls.txt")

docs = json.load(open(DOCS_PATH))
existing_urls = set()
for d in docs:
    u = d.get("url", "").strip().lower()
    u = re.sub(r"[?#].*$", "", u).rstrip("/")
    if u:
        existing_urls.add(u)

queries = [
    'filetype:pdf "Local Cycling and Walking Infrastructure Plan" site:gov.uk',
    'filetype:pdf "LCWIP" "final report" site:gov.uk',
    'filetype:pdf "Local Cycling & Walking Infrastructure Plan" site:gov.uk',
    'filetype:pdf "LCWIP" council "2024" site:gov.uk',
    'filetype:pdf "LCWIP" council "2025" site:gov.uk',
    'filetype:pdf "LCWIP" council "2026" site:gov.uk',
    'filetype:pdf "Local Cycling and Walking Infrastructure Plan" "adopted"',
    'filetype:pdf "LCWIP" "Wiltshire" OR "Somerset" OR "Gloucestershire" OR "Dorset"',
    'filetype:pdf "LCWIP" "Cheshire" OR "Surrey" OR "Hampshire" OR "Kent" OR "Essex"'
]

headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"}

new_candidates = []

for q in queries:
    print(f"Searching: {q}...")
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        
        # Parse links
        raw_links = re.findall(r"uddg=(https?%3A%2F%2F[^\s&\"']+)", html)
        for l in raw_links:
            unquote_url = urllib.parse.unquote(l)
            if unquote_url.lower().endswith(".pdf") or "lcwip" in unquote_url.lower():
                norm = re.sub(r"[?#].*$", "", unquote_url.strip().lower()).rstrip("/")
                if norm not in existing_urls:
                    existing_urls.add(norm)
                    new_candidates.append({
                        "url": unquote_url,
                        "query": q
                    })
        time.sleep(1.5)
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n[Discovered] Found {len(new_candidates)} new LCWIP candidate URLs!")
for i, c in enumerate(new_candidates, 1):
    print(f"  {i:2d}. {c['url']}")
