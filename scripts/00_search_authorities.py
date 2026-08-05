#!/usr/bin/env python3
"""Automated hierarchical web search for LCWIPs, supporting documents, and web pages per Transport Authority.

Reads:
  - data/lad_lookup_data.json (Transport Authority -> constituent districts & historical names)
  - results/results.json or scripts/documents.json (to prevent re-searching existing URLs)

Writes/Appends:
  - scripts/discovered_urls.txt (URL \t Note)

Usage:
  python3 scripts/00_search_authorities.py --sample 5
  python3 scripts/00_search_authorities.py --authorities "Devon" "Wiltshire"
"""
import urllib.parse, urllib.request, json, re, os, time, sys, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOKUP_PATH = os.path.join(ROOT, "data", "lad_lookup_data.json")
RESULTS_PATH = os.path.join(ROOT, "results", "results.json")
DOCS_PATH = os.path.join(ROOT, "scripts", "documents.json")
DISCOVERED_PATH = os.path.join(ROOT, "scripts", "discovered_urls.txt")

def norm_url(u):
    u = u.strip()
    u = re.sub(r"[?#].*$", "", u).rstrip("/")
    return u.lower()

def load_existing_urls():
    existing = set()
    if os.path.exists(RESULTS_PATH):
        try:
            res = json.load(open(RESULTS_PATH))
            for r in res:
                u = r.get("url") or r.get("pdf_url")
                if u:
                    existing.add(norm_url(u))
        except Exception:
            pass
    if os.path.exists(DOCS_PATH):
        try:
            docs = json.load(open(DOCS_PATH))
            for d in docs:
                u = d.get("url")
                if u:
                    existing.add(norm_url(u))
        except Exception:
            pass
    if os.path.exists(DISCOVERED_PATH):
        try:
            for line in open(DISCOVERED_PATH):
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("\t")
                    existing.add(norm_url(parts[0]))
        except Exception:
            pass
    return existing

def search_ddg(query):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0"}
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", errors="ignore")
        raw_links = re.findall(r"uddg=(https?%3A%2F%2F[^\s&\"']+)", html)
        links = []
        for l in raw_links:
            u = urllib.parse.unquote(l)
            if u.lower().endswith(".pdf") or "lcwip" in u.lower() or "active-travel" in u.lower() or "cycling" in u.lower():
                links.append(u)
        return links
    except Exception as e:
        print(f"    [Search Error]: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Search local authorities for LCWIP documents")
    parser.add_argument("--authorities", nargs="+", help="Specific authority names to search")
    parser.add_argument("--sample", type=int, default=0, help="Search first N sample authorities")
    args = parser.parse_args()

    if not os.path.exists(LOOKUP_PATH):
        print(f"Error: {LOOKUP_PATH} not found. Run update script first.")
        sys.exit(1)

    lookup = json.load(open(LOOKUP_PATH))
    existing_urls = load_existing_urls()
    print(f"Loaded {len(existing_urls)} existing URLs to exclude.")

    # Target 5 sample authorities if --sample 5 specified
    DEFAULT_SAMPLE = ["Devon", "West of England Combined Authority", "Cumberland", "Wiltshire", "Kent"]
    
    if args.authorities:
        target_auths = args.authorities
    elif args.sample > 0:
        target_auths = DEFAULT_SAMPLE[:args.sample]
    else:
        target_auths = list(lookup.keys())

    print(f"Targeting {len(target_auths)} Local Transport Authorities: {target_auths}")

    new_discoveries = []

    for ta in target_auths:
        districts = lookup.get(ta, [])
        district_names = [d["lad_name"] for d in districts]
        print(f"\n==========================================")
        print(f"Authority: {ta}")
        print(f"Constituent Districts: {district_names}")
        print(f"==========================================")

        queries = [
            f'"{ta}" "Local Cycling and Walking Infrastructure Plan" OR "LCWIP" filetype:pdf',
            f'"{ta}" "LCWIP" "appendix" OR "route selection" OR "network map"',
        ]

        # Add district specific queries
        for d in district_names:
            if d != ta:
                queries.append(f'"{d}" "LCWIP" OR "Cycling and Walking" filetype:pdf')
                
        # Add historical names queries
        for d in districts:
            for prev in d.get("previous_names", []):
                queries.append(f'"{prev}" "LCWIP" OR "Active Travel" filetype:pdf')

        # Limit queries per authority to avoid excess search requests
        queries = queries[:6]

        for q in queries:
            print(f"  Searching: {q}")
            found = search_ddg(q)
            count_new = 0
            for u in found:
                norm = norm_url(u)
                if norm not in existing_urls:
                    existing_urls.add(norm)
                    new_discoveries.append((u, f"{ta} - {q}"))
                    count_new += 1
                    print(f"    + Discovered: {u}")
            time.sleep(1.2)

    print(f"\n==========================================")
    print(f"Total New Discovered Candidate URLs: {len(new_discoveries)}")
    print(f"==========================================")

    if new_discoveries:
        os.makedirs(os.path.dirname(DISCOVERED_PATH), exist_ok=True)
        with open(DISCOVERED_PATH, "a") as f:
            for u, note in new_discoveries:
                f.write(f"{u}\t{note}\n")
        print(f"Appended {len(new_discoveries)} new candidates to {DISCOVERED_PATH}")

if __name__ == "__main__":
    main()
