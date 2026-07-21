#!/usr/bin/env python3
"""Batch structured extraction of PCT/LCWIP fields from documents via Firecrawl.

Engine: Firecrawl /v2/scrape (json format + schema). Single consistent engine
for the whole corpus (satisfies "all final results use one tool").

For each document in scripts/documents.json, POST its URL to Firecrawl with the
2026 schema and save results/extracted/<idx>.json. Resumable via
results/extracted/_progress.json. On Firecrawl error/limit, appends to
2026-notes.md and stops (caller decides next step).

Run: python scripts/run_extract_firecrawl.py [--limit N] [--start N]
"""
import json, os, re, time, argparse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCUMENTS = json.load(open(os.path.join(ROOT, "scripts", "documents.json")))
OUTDIR = os.path.join(ROOT, "results", "extracted")
PROGRESS = os.path.join(OUTDIR, "_progress.json")
NOTES = os.path.join(ROOT, "2026-notes.md")
os.makedirs(OUTDIR, exist_ok=True)

# Firecrawl key from firecrawl-search.js
JS = open(os.path.join(ROOT, "firecrawl-search.js")).read()
API_KEY = re.search(r"fc-[A-Za-z0-9]+", JS).group(0)

SCHEMA_FIELDS = json.load(open(os.path.join(ROOT, "schema_2026.json")))["fields"]
# Build Firecrawl json schema (all strings/arrays/booleans/nullable)
prop_types = {
    "pdf_url": "string", "report_name": "string", "date_published": "string",
    "doc_type": "string", "mentions_pct": "boolean", "other_tools_used": "string",
    "how_pct_was_used": "string", "pct_scenarios_used": "array",
    "pct_data_sources": "array", "desire_lines_used": "boolean",
    "prioritisation_integration": "boolean", "other_tools_developed": "string",
    "specific_evidence_of_impact": "string", "quotes_on_using_pct": "string",
    "local_authority_name": "string", "combined_authority_name": "string",
    "region": "string", "length_of_cycle_network_proposed": "string",
    "total_cost_of_network": "string", "length_of_network_km": "number",
    "total_cost_pounds": "number", "routes": "number",
    "extraction_notes": "string",
}
schema_props = {f["name"]: {"type": prop_types.get(f["name"], "string")} for f in SCHEMA_FIELDS}
FC_SCHEMA = {"type": "object", "properties": schema_props,
             "required": ["report_name", "mentions_pct", "doc_type"]}

PROMPT = ("This is a Local Cycling and Walking Infrastructure Plan (LCWIP) or "
          "related active-travel document from England. Extract the following "
          "fields. For array fields return lists of strings; for boolean fields "
          "return true/false; for number fields return numbers or null. If a "
          "field is not applicable or not stated, return an empty string, empty "
          "array, false, or null as appropriate.\n"
          "Key guidance:\n"
          "- doc_type: 'LCWIP' (the plan or its technical/background report), "
          "'LCWIP-related' (other active-travel strategy, BSIP, cycling/walking "
          "delivery plan or consultation), or 'other'.\n"
          "- mentions_pct: true ONLY if the document explicitly names or clearly "
          "uses the Propensity to Cycle Tool (PCT) / pct.bike. Generic 'propensity "
          "to cycle' without the tool does NOT count.\n"
          "- If mentions_pct is false, set the PCT-specific fields "
          "(how_pct_was_used, pct_scenarios_used, pct_data_sources, "
          "desire_lines_used, prioritisation_integration, "
          "specific_evidence_of_impact, quotes_on_using_pct) to empty values.\n"
          "- pct_scenarios_used: list scenario names referenced (e.g. 'Government "
          "Target', 'Go Dutch', 'E-bike', 'Go Cambridge', 'Dutch', 'Baseline').\n"
          "- length_of_network_km and total_cost_pounds: numeric or null.\n"
          "- routes: integer or null.\n"
          "- extraction_notes: brief note if pages unreadable or ambiguous.")

def call_firecrawl(url):
    body = {"url": url, "formats": [{"type": "json", "prompt": PROMPT, "schema": FC_SCHEMA}]}
    last = None
    for attempt in range(3):
        r = requests.post("https://api.firecrawl.dev/v2/scrape",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=body, timeout=240)
        if r.status_code != 200:
            return r
        try:
            j = r.json()
            if j.get("success") and "json" in j.get("data", {}):
                return r
        except Exception:
            pass
        last = r
        time.sleep(5)
    return last

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=1)
    args = ap.parse_args()

    progress = {}
    if os.path.exists(PROGRESS):
        progress = json.load(open(PROGRESS))

    todo = [d for d in DOCUMENTS if d["idx"] >= args.start]
    if args.limit:
        todo = todo[:args.limit]
    print(f"Firecrawl engine; docs_to_process={len(todo)} (start={args.start})")

    n_ok = n_err = 0
    for d in todo:
        idx = d["idx"]
        if progress.get(str(idx)) == "ok":
            print(f"[{idx}] skip (already ok)")
            continue
        url = d["url"]
        print(f"[{idx}] {url[:95]}", flush=True)
        try:
            r = call_firecrawl(url)
        except Exception as e:
            print(f"   request exception: {e}")
            progress[str(idx)] = "error"
            json.dump(progress, open(PROGRESS, "w"))
            n_err += 1
            continue
        if r.status_code != 200:
            txt = r.text[:400]
            print(f"   HTTP {r.status_code}: {txt}")
            progress[str(idx)] = "error"
            json.dump(progress, open(PROGRESS, "w"))
            n_err += 1
            if "limit" in txt.lower() or "quota" in txt.lower() or "credit" in txt.lower():
                with open(NOTES, "a") as nf:
                    nf.write(f"\n## Firecrawl limit/error at doc {idx} ({url})\n{txt}\n")
                print("   >>> POSSIBLE FIRECRAWL LIMIT - stopping")
                break
            time.sleep(2)
            continue
        try:
            j = r.json()
            obj = j["data"]["json"]
        except Exception as e:
            print(f"   parse fail: {r.text[:300]}")
            progress[str(idx)] = "parse_error"
            json.dump(progress, open(PROGRESS, "w"))
            n_err += 1
            continue
        # normalise: ensure all schema keys present
        for f in SCHEMA_FIELDS:
            if f["name"] not in obj:
                obj[f["name"]] = None
        obj["_idx"] = idx
        obj["_url"] = url
        obj["_source"] = d["source"]
        obj["_download_status"] = d["download_status"]
        json.dump(obj, open(os.path.join(OUTDIR, f"{idx:04d}.json"), "w"), indent=2)
        progress[str(idx)] = "ok"
        json.dump(progress, open(PROGRESS, "w"))
        n_ok += 1
        time.sleep(1.5)
    print(f"\nDONE this run: ok={n_ok} errors={n_err}")
    print(f"cumulative ok: {sum(1 for v in progress.values() if v=='ok')}")

if __name__ == "__main__":
    main()
