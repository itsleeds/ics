#!/usr/bin/env python3
"""Batch structured extraction via LOCAL Ollama (gemma4-12b-hermes) + pypdf + OCR.

Consistent, unlimited, reproducible engine (no API session/credit limits).
Pipeline per document:
  1. Read local raw file (PDF -> pypdf/pdfplumber native text; if empty -> RapidOCR).
  2. Perform regex term counting for PCT mentions ('PCT', 'Propensity to Cycle Tool', 'pct.bike').
  3. Send text + schema prompt + pre-counted stats to Ollama /api/generate (gemma4-12b-hermes).
  4. Parse JSON (strip ``` fences), validate against schema, save
     results/extracted/<idx>.json.
Resumable via results/extracted/_progress.json.

Docs with download_status == 'failed' (no local raw) are recorded as
extraction-skipped with mentions_pct null (we cannot extract without content).

Run: python scripts/run_extract_ollama.py [--limit N] [--start N] [--model M] [--force-idx IDX]
"""
import json, os, re, io, time, argparse
import requests
import fitz
from pypdf import PdfReader
from rapidocr_onnxruntime import RapidOCR

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
    "- n_mentions_pct: total integer count of mentions of PCT / Propensity to Cycle Tool / pct.bike.\n"
    "- pct_term_breakdown: JSON object e.g. {\"pct\": N, \"propensity_to_cycle_tool\": N, \"pct_bike\": N}.\n"
    "- n_screenshots_pct: integer count of screenshots, maps, figures, or visual outputs from the PCT present in the report.\n"
    "- pct_usage_depth: assess depth of PCT usage: '0 - None', '1 - Passing mention', '2 - Contextual background / data input', '3 - Network design & mapping', or '4 - Core prioritisation & funding framework'.\n"
    "- has_text_layer: boolean, true if native text layer present, false if scanned/OCR.\n"
    "- If mentions_pct is false, set PCT-specific fields (how_pct_was_used, "
    "pct_scenarios_used, pct_data_sources, desire_lines_used, prioritisation_integration, "
    "specific_evidence_of_impact, quotes_on_using_pct, n_screenshots_pct) to empty string / empty array / false / 0 as appropriate.\n"
    "- pct_scenarios_used: list ONLY scenario NAMES from {Government Target, Go Dutch, "
    "E-bike, Go Cambridge, Dutch, Baseline/Current}. Do not include free text.\n"
    "- pct_data_sources: list from {Census 2011 commuting, school travel, desire lines, "
    "jittering, ORS}. Empty if not stated.\n"
    "- desire_lines_used / prioritisation_integration: booleans.\n"
    "- length_of_network_km, total_cost_pounds, routes: numeric or null.\n"
    "- extraction_notes: brief note if text unreadable/ambiguous, else empty string.\n"
)

_ocr_engine = None
def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine

def ocr_pdf(rf):
    try:
        engine = get_ocr_engine()
        doc = fitz.open(rf)
        full_text = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            result, _ = engine(img_bytes)
            if result:
                page_txt = " ".join([res[1] for res in result])
                full_text.append(page_txt)
        return "\n".join(full_text)
    except Exception as e:
        print(f"   OCR failed: {e}")
        return ""

def pdf_text_native(rf):
    raw = open(rf, "rb").read()
    try:
        r = PdfReader(io.BytesIO(raw))
        t = "\n".join((p.extract_text() or "") for p in r.pages)
        if len(t.strip()) >= 50:
            return t
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            t = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        if len(t.strip()) >= 50:
            return t
    except Exception:
        pass
    return ""

def html_text(raw):
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<(script|style|head|noscript).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    import html as h
    s = h.unescape(s)
    return re.sub(r"[ \t]+", " ", s)

def get_document_content(doc):
    rf = doc.get("raw_file")
    if not rf or not os.path.exists(rf):
        return None, False, 0, {}, 0

    has_text_layer = True
    text = ""
    if rf.endswith(".pdf"):
        text = pdf_text_native(rf)
        if len(text.strip()) < 50:
            print("   -> No native text layer found. Running OCR...", flush=True)
            has_text_layer = False
            text = ocr_pdf(rf)
    else:
        raw = open(rf, "rb").read()
        text = html_text(raw)

    if not text or len(text.strip()) < 30:
        return None, has_text_layer, 0, {}, 0

    pct_count = len(re.findall(r"\bPCT\b", text))
    full_name_count = len(re.findall(r"propensity\s+to\s+cycle\s+tool", text, re.IGNORECASE))
    url_count = len(re.findall(r"pct\.bike", text, re.IGNORECASE))

    total_mentions = pct_count + full_name_count + url_count
    term_breakdown = {
        "pct": pct_count,
        "propensity_to_cycle_tool": full_name_count,
        "pct_bike": url_count
    }

    return text, has_text_layer, total_mentions, term_breakdown, len(text)

def strip_fences(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()

def ask_ollama(text, total_mentions, term_breakdown, has_text_layer):
    stats_hint = (
        f"\nDocument Stats:\n"
        f"- Native text layer present: {has_text_layer}\n"
        f"- Text regex mention count: {total_mentions} (Breakdown: {json.dumps(term_breakdown)})\n"
    )
    prompt = PROMPT_HEAD + field_block + GUIDANCE + stats_hint + "\n\nDOCUMENT TEXT:\n" + text[:60000]
    r = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt,
        "stream": False, "options": {"temperature": 0, "num_ctx": 65536}}, timeout=600)
    r.raise_for_status()
    return r.json().get("response", "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--model", default="gemma4-12b-hermes:latest")
    ap.add_argument("--force-idx", type=int, default=0, help="Force re-extraction for a single idx")
    args = ap.parse_args()
    global MODEL
    MODEL = args.model

    progress = {}
    if os.path.exists(PROGRESS):
        progress = json.load(open(PROGRESS))

    todo = [d for d in DOCUMENTS if d["idx"] >= args.start]
    if args.force_idx > 0:
        todo = [d for d in DOCUMENTS if d["idx"] == args.force_idx]
    elif args.limit:
        todo = todo[:args.limit]

    print(f"Ollama engine ({MODEL}); docs_to_process={len(todo)} (start={args.start})")

    n_ok = n_err = n_skip = 0
    for d in todo:
        idx = d["idx"]
        if args.force_idx == 0 and progress.get(str(idx)) == "ok":
            print(f"[{idx}] skip (already ok)")
            continue

        text, has_text_layer, total_mentions, term_breakdown, text_len = get_document_content(d)
        if text is None or len(text.strip()) < 30:
            obj = {k: None for k in field_names}
            obj.update({"_idx": idx, "_url": d["url"], "_source": d["source"],
                        "_download_status": d["download_status"],
                        "mentions_pct": None,
                        "n_mentions_pct": 0,
                        "pct_term_breakdown": {"pct": 0, "propensity_to_cycle_tool": 0, "pct_bike": 0},
                        "has_text_layer": False,
                        "extraction_notes": "No local content: download failed; extraction skipped."})
            json.dump(obj, open(os.path.join(OUTDIR, f"{idx:04d}.json"), "w"), indent=2)
            progress[str(idx)] = "ok"
            json.dump(progress, open(PROGRESS, "w"))
            n_skip += 1
            print(f"[{idx}] skip (no local content)")
            continue

        print(f"[{idx}] {d['url'][:90]}  ({text_len} chars, has_text_layer={has_text_layer}, mentions={total_mentions})", flush=True)
        out = ask_ollama(text, total_mentions, term_breakdown, has_text_layer)
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

        # Override/ensure deterministic pre-counted stats
        parsed["n_mentions_pct"] = total_mentions
        parsed["pct_term_breakdown"] = term_breakdown
        parsed["has_text_layer"] = has_text_layer
        if total_mentions > 0 and parsed.get("mentions_pct") is not False:
            parsed["mentions_pct"] = True

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
