#!/usr/bin/env python3
"""Re-parse all extraction JSONs to add n_mentions_propensity_to_cycle.

Scans each document's md body (header stripped, like pre_extraction_pct_scan)
for the generic phrase 'propensity to cycle' (case-insensitive, including
occurrences inside 'Propensity to Cycle Tool'). Regex-only - no LLM calls.
"""
import json, os, re, glob, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, "results", "extracted")
DOCS_PATH = os.path.join(ROOT, "scripts", "documents.json")

def body_text(md_path):
    if not md_path or not os.path.exists(md_path):
        return ""
    try:
        text = open(md_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    sep = text.find("\n---\n")
    if sep != -1:
        text = text[sep + 5:]
    return text

def combined_md_for(md_path):
    """Return combined md if it exists (mirrors pre_extraction_pct_scan)."""
    if not md_path:
        return md_path
    dir_name = os.path.dirname(md_path)
    prefix = os.path.basename(md_path).split("-")[0]
    comb = glob.glob(os.path.join(dir_name, f"{prefix}*-combined.md"))
    return comb[0] if comb and os.path.exists(comb[0]) else md_path

n_ok = n_skip = 0
for fp in sorted(glob.glob(os.path.join(EXTRACTED, "*.json"))):
    d = json.load(open(fp))
    md = combined_md_for(d.get("md_file"))
    text = body_text(md)
    generic = len(re.findall(r"propensity\s+to\s+cycle", text, re.IGNORECASE))
    d["n_mentions_propensity_to_cycle"] = generic
    tb = d.get("pct_term_breakdown")
    if isinstance(tb, dict):
        tb["propensity_generic"] = generic
        d["pct_term_breakdown"] = tb
    json.dump(d, open(fp, "w"), indent=2)
    n_ok += 1

print(f"re-parsed {n_ok} extraction JSONs (regex 'propensity to cycle' count added)")
