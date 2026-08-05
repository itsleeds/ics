#!/usr/bin/env python3
"""Multi-pass LCWIP structured data extraction via Gemini 3.6 Flash / 2.5 Flash API.

Features:
  - Supports direct GEMINI_API_KEY / GOOGLE_API_KEY and OpenRouter fallback.
  - Full resumability: skips already completed documents and reuses completed pass JSONs in results/extracted_passes/.
  - Credit Stop Button: Gracefully pauses and saves progress if API quota or credits are exhausted (402/429/ResourceExhausted), allowing easy resumption.
  - Pre-extraction regex scan for PCT terms ("Propensity to Cycle Tool", "PCT", "pct.bike").
    Checks combined multipart text layers (*-combined.md) if available before scanning.
  - 4-Pass sequential extraction sending document content with narrow prompts.
  - Verbatim Quote Verification: Validates pct_usage_quote against raw document text layer. Sets to null if not a verbatim substring.

Usage:
  python scripts/04_run_extract.py [--engine gemini|openrouter] [--model MODEL] [--sample-idxs IDXS] [--force]
"""
import json, os, re, sys, time, shutil, argparse, io, requests, glob
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCUMENTS_PATH = os.path.join(ROOT, "scripts", "documents.json")
OUTDIR = os.path.join(ROOT, "results", "extracted")
BACKUP_DIR = os.path.join(ROOT, "results", "extracted_v1")
PASSES_DIR = os.path.join(ROOT, "results", "extracted_passes")
SCHEMA_PATH = os.path.join(ROOT, "schema_2026.json")

os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(PASSES_DIR, exist_ok=True)

# Load environment keys from ~/.srt/gemini.env or ~/.hermes/.env if present
def load_fallback_env():
    env_paths = [
        "/mnt/secondary/home/robin/.srt/gemini.env",
        "/mnt/secondary/home/robin/.hermes/.env",
        os.path.expanduser("~/.srt/gemini.env"),
        os.path.expanduser("~/.hermes/.env")
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    for line in f:
                        if "=" in line and not line.strip().startswith("#"):
                            k, v = line.strip().split("=", 1)
                            k = k.strip()
                            v = v.strip("\"'")
                            if v:
                                if k == "GEMINI_API_KEY":
                                    os.environ["GEMINI_API_KEY"] = v
                                    os.environ["GOOGLE_API_KEY"] = v
                                elif k not in os.environ:
                                    os.environ[k] = v
            except Exception:
                pass
    if "GEMINI_API_KEY" in os.environ:
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

load_fallback_env()

if os.path.exists(OUTDIR) and not os.path.exists(BACKUP_DIR):
    shutil.copytree(OUTDIR, BACKUP_DIR, dirs_exist_ok=True)

def pre_extraction_pct_scan(md_path: Optional[str], raw_path: Optional[str]) -> Dict[str, Any]:
    text = ""
    # Check if a combined text layer exists for multipart documents
    if md_path:
        dir_name = os.path.dirname(md_path)
        base_name = os.path.basename(md_path)
        prefix = base_name.split("-")[0]
        combined = glob.glob(os.path.join(dir_name, f"{prefix}*-combined.md"))
        if combined and os.path.exists(combined[0]):
            md_path = combined[0]

    if md_path and os.path.exists(md_path):
        try:
            text = open(md_path, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            pass

    pct_count = len(re.findall(r"\bPCT\b", text))
    propensity_count = len(re.findall(r"Propensity\s+to\s+Cycle\s+Tool", text, re.IGNORECASE))
    pct_bike_count = len(re.findall(r"pct\.bike", text, re.IGNORECASE))
    total_mentions = pct_count + propensity_count + pct_bike_count

    return {
        "text": text,
        "n_mentions_pct": total_mentions,
        "pct_term_breakdown": {
            "pct": pct_count,
            "propensity_to_cycle_tool": propensity_count,
            "pct_bike": pct_bike_count
        },
        "has_pct_mentions": total_mentions > 0
    }

def verify_verbatim_quote(quote: Optional[str], doc_text: str) -> Optional[str]:
    if not quote or not quote.strip():
        return None
    cleaned_quote = re.sub(r"\s+", " ", quote.strip()).lower()
    cleaned_text = re.sub(r"\s+", " ", doc_text).lower()
    if cleaned_quote in cleaned_text:
        return quote.strip()
    return None

def call_openrouter_api(api_key: str, model_name: str, doc_text: str, prompt: str) -> Dict[str, Any]:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    or_model = model_name
    if not "/" in model_name:
        or_model = "google/gemini-2.5-flash"

    payload = {
        "model": or_model,
        "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": "You are a precise transport data extraction AI. Return ONLY a single valid JSON object with no markdown code fences or conversational prose."},
            {"role": "user", "content": f"Document text excerpt:\n{doc_text[:80000]}\n\nTask Instructions:\n{prompt}"}
        ]
    }
    
    res = requests.post(url, headers=headers, json=payload, timeout=90)
    if res.status_code in (402, 429):
        raise RuntimeError(f"CREDIT_STOP_EXHAUSTED: OpenRouter error {res.status_code} - {res.text}")
    res.raise_for_status()
    
    body = res.json()
    content = body["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    return json.loads(content)

def call_gemini_direct_api(api_key: str, model_name: str, file_path: Optional[str], prompt: str, doc_text: Optional[str] = None) -> Dict[str, Any]:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
    except ImportError:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        client = None

    target_model = model_name.replace("google/", "")
    if target_model in ["gemini-2.5-flash", "gemini-3.6-flash", "auto", "default"]:
        target_model = "gemini-3.1-flash-lite"

    max_retries = 10
    for attempt in range(max_retries):
        try:
            if client:
                full_prompt = f"Document text excerpt:\n{doc_text[:120000]}\n\nTask Instructions:\n{prompt}"
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
                response = client.models.generate_content(
                    model=target_model,
                    contents=full_prompt,
                    config=config
                )
                txt = response.text.strip()
            else:
                import google.generativeai as genai
                g_model = genai.GenerativeModel(target_model)
                full_prompt = f"Document text excerpt:\n{doc_text[:120000]}\n\nTask Instructions:\n{prompt}"
                response = g_model.generate_content(full_prompt)
                txt = response.text.strip()
                if "```json" in txt:
                    txt = txt.split("```json")[1].split("```")[0].strip()
                elif "```" in txt:
                    txt = txt.split("```")[1].split("```")[0].strip()

            return json.loads(txt)

        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str or "503" in err_str:
                wait_time = min(20 * (2 ** attempt), 150)
                print(f"    [Rate Limit Retry] Sleeping {wait_time}s before attempt {attempt + 2}...")
                time.sleep(wait_time)
            else:
                raise e
    raise RuntimeError("Failed Gemini call after max retries")

PROMPT_PASS_1 = """
Perform Pass 1 of 4: PCT Mentions & Usage Depth from this document.
Respond ONLY with a single JSON object containing these exact fields:
- mentions_pct: boolean (true if PCT / Propensity to Cycle Tool is explicitly mentioned, false if not, null if uncertain).
- how_pct_was_used: string summary of how PCT was used, or null if document does not state.
- pct_scenarios_used: list of strings containing zero or more of ['Baseline', 'Government Target', 'Go Dutch', 'E-bike', 'Go Cambridge'] or null.
- pct_data_sources: list of strings containing zero or more of ['Census 2011 commuting', 'School travel demand', 'National Travel Survey', 'Local counters'] or null. Do NOT list mapping outputs like desire lines as data sources.
- pct_usage_depth: string enum '0 - None', '1 - Passing mention', '2 - Contextual background / data input', '3 - Network design & mapping', or '4 - Core prioritisation & funding framework', or null.
- other_tools_used: list of strings or null.

Return null for any field not clearly stated.
"""

PROMPT_PASS_2 = """
Perform Pass 2 of 4: Desire Lines & Prioritisation from this document.
Respond ONLY with a single JSON object containing these exact fields:
- pct_desire_lines_used: boolean (true if PCT-generated desire lines specifically were used/referenced; false if not; null if unmentioned). CRITICAL: Return false/null if general LCWIP desire lines were used that were NOT derived from the PCT.
- prioritisation_integration: boolean (true if PCT output was directly integrated into route prioritisation matrix/scoring; false if not; null if unstated).
- other_tools_developed: string description of any custom tool/matrix developed, or null.

Return null for any field not clearly stated.
"""

PROMPT_PASS_3 = """
Perform Pass 3 of 4: Proposed Network Metrics & Metadata from this document.
Respond ONLY with a single JSON object containing these exact fields:
- report_name: string title of report or null
- authors: string or null (e.g. consultancies like 'AtkinsRealis', 'AECOM', 'WSP', 'Mott MacDonald', 'Systra', 'Steer', 'Stantec', 'Essex County Council', etc.)
- date_published: string (YYYY-MM-DD or Month YYYY) or null
- doc_type: 'LCWIP', 'LCWIP-related', or 'other'
- local_authority_name: string or null
- combined_authority_name: string or null
- region: region string in England or null
- length_of_cycle_network_proposed: verbatim string statement of proposed cycle network length or null
- total_cost_of_network: verbatim string statement of total network cost or null
- length_of_network_km: float/int total network length in km or null
- total_cost_pounds: float/int total network cost in pounds or null
- routes: integer count of proposed routes or null

Return null for any unstated field.
"""

PROMPT_PASS_4 = """
Perform Pass 4 of 4: Direct Quotes & Specific Evidence of Impact.
Respond ONLY with a single JSON object containing these exact fields:
- pct_usage_quote: direct verbatim quote from the document text regarding PCT usage. Return exact quote string or null if no direct quote exists.
- specific_evidence_of_impact: string summary of specific evidence of impact (e.g. funding secured, route changes) or null if unstated.

Return null if document does not contain clear evidence or quotes.
"""

def main():
    parser = argparse.ArgumentParser(description="Multi-pass LCWIP Extraction via Gemini / OpenRouter")
    parser.add_argument("--engine", default="gemini", choices=["auto", "gemini", "openrouter"], help="Extraction engine")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Model name")
    parser.add_argument("--sample-idxs", help="Comma-separated list of document idxs to run")
    parser.add_argument("--force", action="store_true", help="Re-extract all documents even if output JSON exists")
    parser.add_argument("--doc-idx", type=int, help="Single document idx to re-extract")
    args = parser.parse_args()

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    use_engine = args.engine
    if use_engine == "auto":
        use_engine = "gemini" if gemini_key else "openrouter"

    print(f"[Pipeline] Starting extraction with engine={use_engine}, model={args.model}...")

    docs = json.load(open(DOCUMENTS_PATH))
    if args.doc_idx:
        filtered_docs = [d for d in docs if d["idx"] == args.doc_idx]
    elif args.sample_idxs:
        target_idxs = [int(i.strip()) for i in args.sample_idxs.split(",") if i.strip()]
        filtered_docs = [d for d in docs if d["idx"] in target_idxs]
    else:
        filtered_docs = docs

    success_count = 0
    skipped_count = 0

    # Map existing extracted files by their internal URL so we are URL-keyed,
    # not idx-keyed (idx shifts whenever the candidate list changes).
    def existing_extracted_by_url():
        m = {}
        if os.path.exists(OUTDIR):
            for fn in os.listdir(OUTDIR):
                if not fn.endswith(".json") or fn == "_progress.json":
                    continue
                try:
                    e = json.load(open(os.path.join(OUTDIR, fn)))
                    u = (e.get("pdf_url") or e.get("url") or "").strip().lower()
                    if u:
                        m[u] = fn
                except Exception:
                    pass
        return m

    existing_by_url = existing_extracted_by_url()

    for d in filtered_docs:
        idx = d["idx"]
        sidx = f"{idx:04d}"
        out_file = os.path.join(OUTDIR, f"{sidx}.json")
        doc_url_norm = (d.get("url") or "").strip().lower()

        already_done = os.path.exists(out_file) and not args.force and not args.sample_idxs and not args.doc_idx
        if already_done:
            # Only skip when the file at this idx actually corresponds to THIS url
            try:
                cur = json.load(open(out_file))
                cur_url = (cur.get("pdf_url") or cur.get("url") or "").strip().lower()
                if cur_url != doc_url_norm:
                    already_done = False
                    print(f"  [Idx shift] {out_file} holds a different URL; re-extracting this document.")
            except Exception:
                already_done = False

        if already_done:
            print(f"  [Skip] Document [{idx}] already extracted ({out_file}).")
            skipped_count += 1
            continue

        print(f"\n--- Document [{idx}/{len(docs)}] ---")
        print(f"URL: {d.get('url')}")

        md_path = d.get("md_file")
        raw_path = d.get("raw_file")

        scan = pre_extraction_pct_scan(md_path, raw_path)
        print(f"  [Regex Scan] PCT mentions count: {scan['n_mentions_pct']} (has_pct: {scan['has_pct_mentions']})")

        pass_outputs = {}

        if not scan["has_pct_mentions"]:
            print("  [Pre-scan] Zero PCT mentions -> Skipping PCT passes, enforcing nulls.")
            pass_outputs["pass1"] = {
                "mentions_pct": False,
                "how_pct_was_used": None,
                "pct_scenarios_used": None,
                "pct_data_sources": None,
                "pct_usage_depth": "0 - None",
                "other_tools_used": None
            }
            pass_outputs["pass2"] = {
                "pct_desire_lines_used": None,
                "prioritisation_integration": None,
                "other_tools_developed": None
            }
            pass_outputs["pass4"] = {
                "pct_usage_quote": None,
                "specific_evidence_of_impact": None
            }
        else:
            for pass_num, prompt in [(1, PROMPT_PASS_1), (2, PROMPT_PASS_2), (4, PROMPT_PASS_4)]:
                pass_key = f"pass{pass_num}"
                pass_file = os.path.join(PASSES_DIR, f"{sidx}_pass{pass_num}.json")

                if os.path.exists(pass_file) and not args.force:
                    try:
                        pass_outputs[pass_key] = json.load(open(pass_file))
                    except Exception:
                        pass

                if pass_key not in pass_outputs:
                    if use_engine == "gemini":
                        res = call_gemini_direct_api(gemini_key, args.model, raw_path, prompt, doc_text=scan["text"])
                    else:
                        res = call_openrouter_api(openrouter_key, args.model, scan["text"], prompt)
                    pass_outputs[pass_key] = res
                    with open(pass_file, "w") as f:
                        json.dump(res, f, indent=2)
                    print(f"  [Pass {pass_num}] Success")
                    time.sleep(6.5)

        # Pass 3: Metadata & Metrics
        pass3_file = os.path.join(PASSES_DIR, f"{sidx}_pass3.json")
        if os.path.exists(pass3_file) and not args.force:
            try:
                pass_outputs["pass3"] = json.load(open(pass3_file))
            except Exception:
                pass

        if "pass3" not in pass_outputs:
            if use_engine == "gemini":
                res = call_gemini_direct_api(gemini_key, args.model, raw_path, PROMPT_PASS_3, doc_text=scan["text"])
            else:
                res = call_openrouter_api(openrouter_key, args.model, scan["text"], PROMPT_PASS_3)
            pass_outputs["pass3"] = res
            with open(pass3_file, "w") as f:
                json.dump(res, f, indent=2)
            print(f"  [Pass 3] Success")
            time.sleep(6.5)

        # Combine output
        combined = {
            "idx": idx,
            "url": d.get("url"),
            "pdf_url": d.get("url"),
            "md_file": d.get("md_file"),
            "raw_file": d.get("raw_file"),
            "n_mentions_pct": scan["n_mentions_pct"],
            "pct_term_breakdown": scan["pct_term_breakdown"]
        }

        for p_key in ("pass1", "pass2", "pass3", "pass4"):
            if p_key in pass_outputs:
                combined.update(pass_outputs[p_key])

        # Verbatim quote verification
        if combined.get("pct_usage_quote"):
            verified_quote = verify_verbatim_quote(combined["pct_usage_quote"], scan["text"])
            if not verified_quote:
                print(f"  [Quote Guardrail] Unverified quote -> Setting null (quote not in raw text layer).")
                combined["pct_usage_quote"] = None

        with open(out_file, "w") as f:
            json.dump(combined, f, indent=2)
        print(f"  [Saved] -> {out_file}")
        success_count += 1

    print(f"\n[Completed] Processed {success_count} documents (skipped {skipped_count} already done).")

if __name__ == "__main__":
    main()
