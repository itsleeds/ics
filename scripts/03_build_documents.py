#!/usr/bin/env python3
"""Build the master list of documents to extract.

Reads:
  - scripts/candidates.json
  - data-govuk-2026-md/*.md

Outputs:
  - scripts/documents.json

Run: python scripts/03_build_documents.py
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "data-govuk-2026-md")

def norm(u):
    return re.sub(r"[?#].*$", "", u or "").rstrip("/").lower()

docs = {}
if os.path.exists(MD):
    for fn in sorted(os.listdir(MD)):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(MD, fn)
        txt = open(path).read()
        m = re.search(r"^url:\s*(\S+)", txt, re.MULTILINE)
        if not m:
            continue
        url = m.group(1)
        status = "ok" if "status: download_failed" not in txt else "failed"
        stem = fn[:-3]
        raw_file = None
        for ext in ("pdf", "html"):
            cand = os.path.join(ROOT, "data-govuk-2026-raw", stem + "." + ext)
            if os.path.exists(cand):
                raw_file = cand
                break
        source = ""
        ms = re.search(r"^source:\s*(\S+)", txt, re.MULTILINE)
        if ms: source = ms.group(1)
        note = ""
        mn = re.search(r"^note:\s*(.*)$", txt, re.MULTILINE)
        if mn: note = mn.group(1)
        docs[norm(url)] = {
            "url": url, "md_file": path, "raw_file": raw_file,
            "download_status": status, "source": source, "note": note,
        }

cands_path = os.path.join(ROOT, "scripts", "candidates.json")
if os.path.exists(cands_path):
    cands = json.load(open(cands_path))
    for c in cands:
        k = norm(c["url"])
        if k not in docs:
            docs[k] = {
                "url": c["url"], "md_file": None, "raw_file": None,
                "download_status": "missing", "source": c.get("source",""),
                "note": c.get("note","")
            }

ordered = sorted(docs.values(), key=lambda d: d["url"])
out = []
for i, d in enumerate(ordered, 1):
    d["idx"] = i
    out.append(d)

json.dump(out, open(os.path.join(ROOT, "scripts", "documents.json"), "w"), indent=2)
print(f"documents.json: {len(out)} docs")
print("  ok:", sum(1 for d in out if d['download_status']=='ok'))
print("  failed:", sum(1 for d in out if d['download_status']=='failed'))
print("  missing:", sum(1 for d in out if d['download_status']=='missing'))
