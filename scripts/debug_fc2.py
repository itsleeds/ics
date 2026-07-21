#!/usr/bin/env python3
import json, re, requests
JS = open("firecrawl-search.js").read()
KEY = re.search(r"fc-[A-Za-z0-9]+", JS).group(0)
url = "https://api.warwickshire.gov.uk/documents/WCCC-1615347118-1427"
body = {"url": url, "formats": [{"type": "json", "prompt": "Return report_name (string) and mentions_pct (boolean).",
        "schema": {"type": "object", "properties": {"report_name": {"type": "string"}, "mentions_pct": {"type": "boolean"}}, "required": ["report_name"]}}]}
r = requests.post("https://api.firecrawl.dev/v2/scrape",
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}, json=body, timeout=240)
print("status:", r.status_code)
j = r.json()
print("data keys:", list(j.get("data", {}).keys()))
print(json.dumps(j, indent=2)[:2000])
