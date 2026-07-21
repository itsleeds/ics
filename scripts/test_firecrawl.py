#!/usr/bin/env python3
"""Test Firecrawl v2/scrape with json format + schema on a PCT LCWIP PDF URL."""
import json, re, os
import requests

js = open(os.path.join(os.path.dirname(__file__), "..", "firecrawl-search.js")).read()
API_KEY = re.search(r"fc-[A-Za-z0-9]+", js).group(0)

url = "https://www.worcestershire.gov.uk/sites/default/files/2025-10/redditch_lcwip_final.pdf"
prompt = ("Extract from this LCWIP document: report_name, local_authority_name, "
          "date_published, whether it mentions the Propensity to Cycle Tool (PCT) "
          "(mentions_pct boolean), how_pct_was_used, and pct_scenarios_used (list).")

body = {
    "url": url,
    "formats": [{
        "type": "json",
        "prompt": prompt,
        "schema": {
            "type": "object",
            "properties": {
                "report_name": {"type": "string"},
                "local_authority_name": {"type": "string"},
                "date_published": {"type": "string"},
                "mentions_pct": {"type": "boolean"},
                "how_pct_was_used": {"type": "string"},
                "pct_scenarios_used": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["report_name", "mentions_pct"],
        },
    }],
}
r = requests.post("https://api.firecrawl.dev/v2/scrape",
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    json=body, timeout=180)
print("status:", r.status_code)
try:
    j = r.json()
    print(json.dumps(j, indent=2)[:2000])
except Exception:
    print(r.text[:1500])
