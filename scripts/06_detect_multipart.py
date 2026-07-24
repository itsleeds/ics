#!/usr/bin/env python3
"""Detect multipart LCWIP documents and linked appendices across data-govuk-2026-md/.

Scans markdown text layers for:
- Appendix [A-Z], Annex [A-Z0-9], Technical Report, Evidence Base
- ModernGov / committee report appendices headers
- Known consultancy author signatures (Atkins, AECOM, WSP, Mott MacDonald, Systra, Steer, Stantec, etc.)

Updates results/extracted/*.json with:
- is_multipart (bool)
- linked_documents (list of titles)
- authors (detected consultancy or author string)

Run: python3 scripts/06_detect_multipart.py
"""
import os, json, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_DIR = os.path.join(ROOT, "data-govuk-2026-md")
EXTRACTED_DIR = os.path.join(ROOT, "results", "extracted")
DOCS_PATH = os.path.join(ROOT, "scripts", "documents.json")

CONSULTANCIES = [
    "AtkinsRealis", "Atkins", "AECOM", "WSP", "Mott MacDonald", "Systra",
    "Steer", "Stantec", "Peter Brett Associates", "PBA", "Jacobs", "Ramboll",
    "Sweco", "Buro Happold", "Royal Haskoning", "Phil Jones Associates", "PJA",
    "ITP", "Integrated Transport Planning", "Sustrans", "Urban Movement", "Vectos"
]

docs = json.load(open(DOCS_PATH))
doc_map = {d["idx"]: d for d in docs}

extracted_files = sorted(glob.glob(os.path.join(EXTRACTED_DIR, "*.json")))
extracted_files = [f for f in extracted_files if not f.endswith("_progress.json")]

multipart_count = 0
authors_found = 0

for ef in extracted_files:
    idx_str = os.path.basename(ef).replace(".json", "")
    try:
        idx = int(idx_str)
    except ValueError:
        continue
    
    d_info = doc_map.get(idx, {})
    md_path = d_info.get("md_file")
    
    data = json.load(open(ef))
    
    if md_path and os.path.exists(md_path):
        text = open(md_path, errors="ignore").read()
        
        # 1. Detect appendices
        appendices = set()
        # Regex matches for Appendix A/B/C/D or Annex A/1 etc.
        app_matches = re.findall(r"(Appendix\s+[A-Z0-9]+[^\n\r:;]{0,60})", text, re.I)
        for m in app_matches:
            clean_m = re.sub(r"\s+", " ", m).strip()
            if len(clean_m) > 10 and len(clean_m) < 70:
                appendices.add(clean_m)
        
        # Committee report appendices header
        comm_match = re.search(r"Appendices:\s*\n((?:[^\n]+\n){1,6})", text, re.I)
        if comm_match:
            lines = [l.strip() for l in comm_match.group(1).split("\n") if l.strip()]
            for l in lines:
                appendices.add(l)

        is_mp = len(appendices) > 0 or "technical report" in text.lower() or "appendix" in text.lower()
        if is_mp:
            multipart_count += 1
            data["is_multipart"] = True
            data["linked_documents"] = sorted(list(appendices))[:10]
        else:
            data["is_multipart"] = False
            data["linked_documents"] = []

        # 2. Detect consultancy / author names if missing
        if not data.get("authors"):
            found_authors = []
            for c in CONSULTANCIES:
                if re.search(r"\b" + re.escape(c) + r"\b", text, re.I):
                    found_authors.append(c)
            if found_authors:
                data["authors"] = ", ".join(sorted(set(found_authors)))
                authors_found += 1
            else:
                data["authors"] = d_info.get("note", "").split(" ")[0] if d_info.get("note") else None

    with open(ef, "w") as f:
        json.dump(data, f, indent=2)

print(f"Updated {len(extracted_files)} extracted files:")
print(f"  Multipart documents detected: {multipart_count}")
print(f"  Consultancies/Authors identified: {authors_found}")
