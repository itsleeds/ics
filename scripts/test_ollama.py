#!/usr/bin/env python3
"""Test: extract text from Redditch PDF via pypdf, then ask Ollama gemma4-12b
to return structured JSON for the 2026 schema (subset)."""
import json, io
from pypdf import PdfReader
import requests

# 1) text
raw = open("/mnt/secondary/home/robin/github/itsleeds/ics/scripts/test_pdfs/redditch.pdf", "rb").read()
txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
print("text chars:", len(txt))
txt = txt[:16000]  # fit context

# 2) ollama
prompt = (
    "You are extracting structured data from a Local Cycling and Walking "
    "Infrastructure Plan (LCWIP) document. Return ONLY a single valid JSON object "
    "(no markdown fences) with these keys: "
    '{"report_name": string, "date_published": string, "local_authority_name": string, '
    '"doc_type": "LCWIP"|"LCWIP-related"|"other", "mentions_pct": boolean, '
    '"how_pct_was_used": string, "pct_scenarios_used": array_of_strings, '
    '"desire_lines_used": boolean, "prioritisation_integration": boolean, '
    '"quotes_on_using_pct": string, "total_cost_pounds": number_or_null}. '
    "If PCT is not mentioned set mentions_pct false and PCT fields to empty. "
    "Document text:\n\n" + txt
)
r = requests.post("http://localhost:11434/api/generate",
    json={"model": "gemma4-12b-hermes:latest", "prompt": prompt, "stream": False,
          "options": {"temperature": 0, "num_ctx": 32768}},
    timeout=300)
print("status:", r.status_code)
j = r.json()
print("response:")
print(j.get("response", "")[:1500])
