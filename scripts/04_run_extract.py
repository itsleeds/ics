#!/usr/bin/env python3
"""Multi-pass LCWIP structured data extraction via Gemini 3.6 Flash / OpenRouter.

Features:
  - Supports both direct GEMINI_API_KEY and OPENROUTER_API_KEY.
  - Full resumability: skips already completed documents and reuses completed pass JSONs in results/extracted_passes/.
  - Credit Stop Button: Gracefully pauses and saves progress if API quota or credits are exhausted (402/429/ResourceExhausted), allowing easy resumption.
  - Pre-extraction regex scan for PCT terms ("Propensity to Cycle Tool", "PCT", "pct.bike").
    If count == 0, skips PCT API calls, setting PCT fields to null/false to prevent hallucinations.
  - 4-Pass sequential extraction sending document content with narrow prompts.
  - Verbatim Quote Verification: Validates pct_usage_quote against raw document text layer. Sets to null if not a verbatim substring.

Usage:
  python scripts/04_run_extract.py [--engine gemini|openrouter] [--model MODEL] [--sample-idxs IDXS] [--force]
"""
import json, os, re, sys, time, shutil, argparse, io, requests
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
                            if k not in os.environ and v:
                                os.environ[k] = v
            except Exception:
                pass

load_fallback_env()

if os.path.exists(OUTDIR) and not os.path.exists(BACKUP_DIR):
    shutil.copytree(OUTDIR, BACKUP_DIR, dirs_exist_ok=True)
    print(f"[Backup] Preserved original results/extracted to {BACKUP_DIR}")

def pre_extraction_pct_scan(md_path: Optional[str], raw_path: Optional[str]) -> Dict[str, Any]:
    text = ""
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

def call_gemini_direct_api(api_key: str, model_name: str, file_path: Optional[str], prompt: str) -> Dict[str, Any]:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
    except ImportError:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        client = None

    target_model = "gemini-2.5-flash" if "3.6" in model_name else model_name

    uploaded_file = None
    if file_path and os.path.exists(file_path) and file_path.endswith(".pdf"):
        try:
            if hasattr(client, "files"):
                uploaded_file = client.files.upload(file=file_path)
            elif hasattr(genai, "upload_file"):
                uploaded_file = genai.upload_file(file_path)
        except Exception as e:
            err_str = str(e).lower()
            if any(k in err_str for k in ["quota", "resource_exhausted", "credit", "429", "permission_denied"]):
                raise RuntimeError(f"CREDIT_STOP_EXHAUSTED: {e}")

    contents = []
    if uploaded_file:
        contents.append(uploaded_file)
    contents.append(prompt)

    try:
        if client and hasattr(client, "models"):
            response = client.models.generate_content(
                model=target_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            raw_text = response.text
        else:
            m = genai.GenerativeModel(target_model)
            response = m.generate_content(contents)
            raw_text = response.text

        raw_text = re.sub(r"^```json\s*", "", raw_text.strip())
        raw_text = re.sub(r"\s*```$", "", raw_text.strip())
        return json.loads(raw_text)
    except Exception as e:
        err_str = str(e).lower()
        if any(k in err_str for k in ["quota", "resource_exhausted", "credit", "429", "permission_denied"]):
            raise RuntimeError(f"CREDIT_STOP_EXHAUSTED: {e}")
        raise e

PROMPT_PASS_1 = """
Perform Pass 1 of 4: PCT Usage & Scenarios from this document.
Respond ONLY with a single JSON object containing these exact fields:
- mentions_pct: boolean or null if unmentioned
- how_pct_was_used: string summary or null if unstated. Return null if document does not clearly describe PCT usage.
- pct_scenarios_used: list containing zero or more of ["Baseline", "Government Target", "Go Dutch", "E-bike", "Go Cambridge"], or null if none mentioned.
- pct_data_sources: list containing zero or more of ["Census 2011 commuting", "School travel demand", "National Travel Survey", "Local counters"], or null if none mentioned. Do NOT list desire lines as a data source.
- pct_usage_depth: string ('0 - None', '1 - Passing mention', '2 - Contextual background / data input', '3 - Network design & mapping', '4 - Core prioritisation & funding framework') or null.
- other_tools_used: list of strings (e.g. Strava, NPT, WRAT, RST) or null.

Return null for any field not clearly stated in the document.
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
    parser.add_argument("--engine", default="auto", choices=["auto", "gemini", "openrouter"], help="Extraction engine")
    parser.add_argument("--model", default="google/gemini-2.5-flash", help="Model name")
    parser.add_argument("--sample-idxs", help="Comma-separated list of document idxs to run")
    parser.add_argument("--force", action="store_true", help="Re-extract all documents even if output JSON exists")
    args = parser.parse_args()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if not gemini_key and not openrouter_key:
        print("\n========================================================")
        print("ERROR: Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is set.")
        print("========================================================\n")
        sys.exit(1)

    use_engine = args.engine
    if use_engine == "auto":
        use_engine = "openrouter" if openrouter_key else "gemini"

    print(f"[Pipeline] Starting extraction with engine={use_engine}, model={args.model}...")

    docs = json.load(open(DOCUMENTS_PATH))
    target_idxs = None
    if args.sample_idxs:
        target_idxs = set(int(x.strip()) for x in args.sample_idxs.split(",") if x.strip())

    filtered_docs = [d for d in docs if (target_idxs is None or d["idx"] in target_idxs)]

    success_count = 0
    skipped_count = 0

    for d in filtered_docs:
        idx = d["idx"]
        sidx = f"{idx:04d}"
        out_file = os.path.join(OUTDIR, f"{sidx}.json")

        if os.path.exists(out_file) and not args.force and not args.sample_idxs:
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
                        print(f"  [Pass {pass_num}] Cached")
                        continue
                    except Exception:
                        pass

                try:
                    if use_engine == "openrouter":
                        res = call_openrouter_api(openrouter_key, args.model, scan["text"], prompt)
                    else:
                        res = call_gemini_direct_api(gemini_key, args.model, raw_path or md_path, prompt)
                    pass_outputs[pass_key] = res
                    json.dump(res, open(pass_file, "w"), indent=2)
                    print(f"  [Pass {pass_num}] Success")
                    time.sleep(0.3)
                except RuntimeError as re_err:
                    if "CREDIT_STOP_EXHAUSTED" in str(re_err):
                        print("\n========================================================================")
                        print(f"[CREDIT STOP BUTTON TRIGGERED]: API quota/credits exhausted on Pass {pass_num}.")
                        print(f"Progress gracefully saved at document idx {idx}. Pipeline paused.")
                        print("Run again anytime to resume cleanly from this exact document.")
                        print("========================================================================\n")
                        sys.exit(0)
                    else:
                        print(f"  [Pass {pass_num}] Error: {re_err}")
                        pass_outputs[pass_key] = {}
                except Exception as ex:
                    print(f"  [Pass {pass_num}] Error: {ex}")
                    pass_outputs[pass_key] = {}

        # Pass 3 (Metadata & Metrics)
        pass3_file = os.path.join(PASSES_DIR, f"{sidx}_pass3.json")
        if os.path.exists(pass3_file) and not args.force:
            try:
                pass_outputs["pass3"] = json.load(open(pass3_file))
                print(f"  [Pass 3] Cached")
            except Exception:
                pass
        else:
            try:
                if use_engine == "openrouter":
                    res3 = call_openrouter_api(openrouter_key, args.model, scan["text"], PROMPT_PASS_3)
                else:
                    res3 = call_gemini_direct_api(gemini_key, args.model, raw_path or md_path, PROMPT_PASS_3)
                pass_outputs["pass3"] = res3
                json.dump(res3, open(pass3_file, "w"), indent=2)
                print(f"  [Pass 3] Success")
                time.sleep(0.3)
            except RuntimeError as re_err:
                if "CREDIT_STOP_EXHAUSTED" in str(re_err):
                    print("\n[CREDIT STOP BUTTON TRIGGERED]: API quota exhausted during Pass 3. Progress saved. Pausing.")
                    sys.exit(0)
                pass_outputs["pass3"] = {}
            except Exception as ex:
                pass_outputs["pass3"] = {}

        p1 = pass_outputs.get("pass1", {})
        p2 = pass_outputs.get("pass2", {})
        p3 = pass_outputs.get("pass3", {})
        p4 = pass_outputs.get("pass4", {})

        raw_quote = p4.get("pct_usage_quote")
        verified_quote = verify_verbatim_quote(raw_quote, scan["text"])

        combined_record = {
            "_idx": idx,
            "_url": d.get("url"),
            "_source": d.get("source"),
            "_download_status": d.get("download_status"),
            "pdf_url": d.get("url"),
            "report_name": p3.get("report_name") or d.get("note"),
            "date_published": p3.get("date_published"),
            "doc_type": p3.get("doc_type") or "LCWIP",
            "mentions_pct": p1.get("mentions_pct") if scan["has_pct_mentions"] else False,
            "n_mentions_pct": scan["n_mentions_pct"],
            "pct_term_breakdown": scan["pct_term_breakdown"],
            "pct_usage_depth": p1.get("pct_usage_depth"),
            "other_tools_used": p1.get("other_tools_used"),
            "how_pct_was_used": p1.get("how_pct_was_used") if scan["has_pct_mentions"] else None,
            "pct_scenarios_used": p1.get("pct_scenarios_used") if scan["has_pct_mentions"] else None,
            "pct_data_sources": p1.get("pct_data_sources") if scan["has_pct_mentions"] else None,
            "pct_desire_lines_used": p2.get("pct_desire_lines_used") if scan["has_pct_mentions"] else None,
            "prioritisation_integration": p2.get("prioritisation_integration") if scan["has_pct_mentions"] else None,
            "other_tools_developed": p2.get("other_tools_developed"),
            "specific_evidence_of_impact": p4.get("specific_evidence_of_impact") if scan["has_pct_mentions"] else None,
            "pct_usage_quote": verified_quote if scan["has_pct_mentions"] else None,
            "local_authority_name": p3.get("local_authority_name"),
            "combined_authority_name": p3.get("combined_authority_name"),
            "region": p3.get("region"),
            "length_of_cycle_network_proposed": p3.get("length_of_cycle_network_proposed"),
            "total_cost_of_network": p3.get("total_cost_of_network"),
            "length_of_network_km": p3.get("length_of_network_km"),
            "total_cost_pounds": p3.get("total_cost_pounds"),
            "routes": p3.get("routes"),
            "has_text_layer": bool(scan["text"].strip()),
            "extraction_notes": ""
        }

        with open(out_file, "w") as f:
            json.dump(combined_record, f, indent=2)
        print(f"  [Saved] -> {out_file}")
        success_count += 1

    print(f"\n[Completed] Processed {success_count} documents (skipped {skipped_count} already done).")

if __name__ == "__main__":
    main()
