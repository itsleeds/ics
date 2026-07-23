#!/usr/bin/env python3
"""Search specific English local authorities for published LCWIP PDF files not in database.
"""
import urllib.parse, urllib.request, json, re, os, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_PATH = os.path.join(ROOT, "scripts", "documents.json")

docs = json.load(open(DOCS_PATH))
existing = set()
for d in docs:
    u = d.get("url", "").strip().lower()
    u = re.sub(r"[?#].*$", "", u).rstrip("/")
    if u:
        existing.add(u)

councils = [
    "Wiltshire Amesbury LCWIP pdf",
    "Wiltshire Devizes LCWIP pdf",
    "Wiltshire Trowbridge LCWIP pdf",
    "Wiltshire Warminster LCWIP pdf",
    "Cheshire West and Chester LCWIP pdf",
    "Dorset Council Active Travel Plan pdf",
    "Somerset Taunton LCWIP pdf",
    "Slough LCWIP pdf",
    "Reading LCWIP pdf",
    "Wokingham LCWIP pdf",
    "West Berkshire LCWIP pdf",
    "Guildford LCWIP pdf",
    "Woking LCWIP pdf",
    "Reigate Banstead LCWIP pdf",
    "Elmbridge LCWIP pdf",
    "Maidstone LCWIP pdf",
    "Canterbury LCWIP pdf",
    "Thanet LCWIP pdf",
    "Dover LCWIP pdf",
    "Folkestone LCWIP pdf",
    "Swindon LCWIP pdf",
    "Plymouth LCWIP pdf",
    "Exeter LCWIP pdf",
    "Torbay LCWIP pdf",
    "North Somerset LCWIP pdf",
    "South Gloucestershire LCWIP pdf"
]

found = []
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"}

for c in councils:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(c + " site:gov.uk filetype:pdf")
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
        raw_links = re.findall(r"uddg=(https?%3A%2F%2F[^\s&\"']+)", html)
        for l in raw_links:
            u = urllib.parse.unquote(l)
            if u.lower().endswith(".pdf"):
                norm = re.sub(r"[?#].*$", "", u.lower()).rstrip("/")
                if norm not in existing:
                    existing.add(norm)
                    found.append((c, u))
        time.sleep(0.8)
    except Exception as e:
        pass

print(f"\n=== Discovered {len(found)} New Specific Council LCWIP PDFs ===")
for c, u in found:
    print(f"[{c:35s}] -> {u}")

# Append discovered URLs to scripts/discovered_urls.txt
disc_path = os.path.join(ROOT, "scripts", "discovered_urls.txt")
with open(disc_path, "a") as f:
    for c, u in found:
        f.write(f"{u}\t{c}\n")

print(f"Appended new candidates to {disc_path}")
