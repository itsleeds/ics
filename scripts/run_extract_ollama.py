#!/usr/bin/env python3
"""Batch structured extraction via LOCAL Ollama (gemma4-12b-hermes) + pypdf.

Consistent, unlimited, reproducible engine (no API session/credit limits).
Pipeline per document:
  1. Read local raw file (PDF -> pypdf/pdfplumber text; HTML -> strip tags).
  2. Send text + schema prompt to Ollama /api/generate (gemma4-12b-hermes).
  3. Parse JSON (strip ``` fences), validate against schema, save
     results/extracted/<idx>.json.
Resumable via results/extracted/_progress.json.

Docs with download_status == 'failed' (no local raw) are recorded as
extraction-skipped with mentions_pct null (we cannot extract without content).

Run: python scripts/run_extract_ollama.py [--limit N] [--start N] [--model M]
"""
import json, os, re, io, time, argparse
import requests
from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCUMENTS = json.load(open(os.path.join(ROOT, "scripts", "documents.json")))
OUTDIR = os.path.join(ROOT, "results", "extracted")
PROGRESS = os.path.join(OUTDIR, "_progress.json")
NOTES = os.path.join(ROOT, "2026-notes.md")
os.makedirs(OUTDIR, exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4-12b-hermes:latest"

SCHEMA_FIELDS = json.load(open(os.path.join(ROOT, "schema_2026.json")))["fields"]
field_names = [f["name"] for f in SCHEMA_FIELDS]

PROMPT_HEAD = (
    "You are extracting structured data from a Local Cycling and Walking "
    "Infrastructure Plan (LCWIP) or related active-travel document from England.\n"
    "Return ONLY a single valid JSON object (no markdown code fences, no prose).\n"
    "Use exactly these keys:\n"
)
field_block = "\n".join(f'- {f["name"]}: {f["prompt"]}' for f in SCHEMA_FIELDS)
GUIDANCE = (
    "\nStrict rules:\n"
    "- doc_type: one of 'LCWIP', 'LCWIP-related', 'other'.\n"
    "- mentions_pct: true ONLY if the document explicitly names or clearly uses the "
    "Propensity to Cycle Tool (PCT) or pct.bike. Generic 'propensity to cycle' without "
    "the tool does NOT count.\n"
    "- If mentions_pct is false, set PCT-specific fields (how_pct_was_used, "
    "pct_scenarios_used, pct_data_sources, desire_lines_used, prioritisation_integration, "
    "specific_evidence_of_impact, quotes_on_using_pct) to empty string / empty array / false.\n"
    "- pct_scenarios_used: list ONLY scenario NAMES from {Government Target, Go Dutch, "
    "E-bike, Go Cambridge, Dutch, Baseline/Current}. Do not include free text.\n"
    "- pct_data_sources: list from {Census 2011 commuting, school travel, desire lines, "
    "jittering, OSR}. Empty if not stated.\n"
    "- desire_lines_used / prioritisation_integration: booleans.\n"
    "- length_of_network_km, total_cost_pounds, routes: numeric or null.\n"
    "- extraction_notes: brief note if text unreadable/ambiguous, else empty string.\n"
)

def pdf_text(raw):
    try:
        r = PdfReader(io.BytesIO(raw))
        t = "\n".join((p.extract_text() or "") for p in r.pages)
        if len(t.strip()) < 50:
            raise ValueError
        return t
    except Exception:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                t = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
            return t
        except Exception:
            return ""

def html_text(raw):
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<(script|style|head|noscript).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    import html as h
    s = h.unescape(s)
    return re.sub(r"[ \t]+", " ", s)

def get_text(doc):
    rf = doc.get("raw_file")
    if not rf or not os.path.exists(rf):
        return None
    raw = open(rf, "rb").read()
    if rf.endswith(".pdf"):
        return pdf_text(raw)
    return html_text(raw)

def strip_fences(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()

def ask_ollama(text):
    prompt = PROMPT_HEAD + field_block + GUIDANCE + "\n\nDOCUMENT TEXT:\n" + text[:60000]
    r = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt,
        "stream": False, "options": {"temperature": 0, "num_ctx": 65536}}, timeout=600)
    r.raise_for_status()
    return r.json().get("response", "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--model", default="gemma4-12b-hermes:latest")
    args = ap.parse_args()
    global MODEL
    MODEL = args.model

    progress = {}
    if os.path.exists(PROGRESS):
        progress = json.load(open(PROGRESS))

    todo = [d for d in DOCUMENTS if d["idx"] >= args.start]
    if args.limit:
        todo = todo[:args.limit]
    print(f"Ollama engine ({MODEL}); docs_to_process={len(todo)} (start={args.start})")

    n_ok = n_err = n_skip = 0
    for d in todo:
        idx = d["idx"]
        if progress.get(str(idx)) == "ok":
            print(f"[{idx}] skip (already ok)")
            continue
        text = get_text(d)
        if text is None or len(text.strip()) < 30:
            # no local content (failed download) -> record skipped
            obj = {k: None for k in field_names}
            obj.update({"_idx": idx, "_url": d["url"], "_source": d["source"],
                        "_download_status": d["download_status"],
                        "mentions_pct": None,
                        "extraction_notes": "No local content: download failed; extraction skipped."})
            json.dump(obj, open(os.path.join(OUTDIR, f"{idx:04d}.json"), "w"), indent=2)
            progress[str(idx)] = "ok"
            json.dump(progress, open(PROGRESS, "w"))
            n_skip += 1
            print(f"[{idx}] skip (no local content)")
            continue
        print(f"[{idx}] {d['url'][:90]}  ({len(text)} chars)", flush=True)
        out = ask_ollama(text)
        parsed = None
        try:
            parsed = json.loads(strip_fences(out))
        except Exception:
            m = re.search(r"\{.*\}", out, re.DOTALL)
            if m:
                try: parsed = json.loads(strip_fences(m.group(0)))
                except Exception: parsed = None
        if not isinstance(parsed, dict):
            print(f"   parse fail; tail: {out[-300:]}")
            progress[str(idx)] = "parse_error"
            json.dump(progress, open(PROGRESS, "w"))
            n_err += 1
            continue
        for k in field_names:
            if k not in parsed:
                parsed[k] = None
        parsed["_idx"] = idx
        parsed["_url"] = d["url"]
        parsed["_source"] = d["source"]
        parsed["_download_status"] = d["download_status"]
        json.dump(parsed, open(os.path.join(OUTDIR, f"{idx:04d}.json"), "w"), indent=2)
        progress[str(idx)] = "ok"
        json.dump(progress, open(PROGRESS, "w"))
        n_ok += 1
        time.sleep(0.5)
    print(f"\nDONE this run: ok={n_ok} skipped(no-content)={n_skip} errors={n_err}")
    print(f"cumulative ok+skip: {sum(1 for v in progress.values() if v=='ok')}")

if __name__ == "__main__":
    main()
