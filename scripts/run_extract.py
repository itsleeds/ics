#!/usr/bin/env python3
"""Batch LLM extraction of PCT/LCWIP fields from downloaded documents.

Primary engine: Claude CLI (`claude -p --dangerously-skip-permissions`).
Wrapper:
  - reads scripts/documents.json
  - for each doc with download_status == 'ok', sends the raw file (PDF/HTML) to
    Claude with the schema prompt and captures a JSON object
  - strips ```json fences if present, parses, validates, and writes
    results/extracted/<idx>.json
  - keeps a results/extracted/_progress.json mapping idx -> ok/error
  - resumes: skips idx already in _progress with ok
  - on repeated failure / provider error, writes a note to 2026-notes.md and
    signals the caller to switch engines (engine switch requires re-running all docs)

Run:  python scripts/run_extract.py [--engine claude] [--limit N] [--start N]
"""
import json, os, re, sys, subprocess, time, shutil, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCUMENTS = json.load(open(os.path.join(ROOT, "scripts", "documents.json")))
OUTDIR = os.path.join(ROOT, "results", "extracted")
PROGRESS = os.path.join(OUTDIR, "_progress.json")
NOTES = os.path.join(ROOT, "2026-notes.md")
os.makedirs(OUTDIR, exist_ok=True)

SCHEMA = json.load(open(os.path.join(ROOT, "schema_2026.json")))["fields"]
field_names = [f["name"] for f in SCHEMA]
field_block = "\n".join(f'- {f["name"]}: {f["prompt"]}' for f in SCHEMA)

PROMPT = f"""You are extracting structured data from a Local Cycling and Walking Infrastructure Plan (LCWIP) or related active-travel document in England.

Extract the following fields from the document. Output ONLY a single valid JSON object (no markdown code fences, no prose before or after). Use these exact keys:
{field_block}

Field guidance:
- doc_type: one of "LCWIP" (the plan or its technical/background report), "LCWIP-related" (other active-travel strategy, BSIP, cycling/walking delivery plan/consultation), or "other".
- mentions_pct: true only if the document explicitly names or clearly uses the Propensity to Cycle Tool (PCT) or its methodology (pct.bike). Mentions of "propensity to cycle" without the tool do NOT count.
- For PCT-related fields (how_pct_was_used, pct_scenarios_used, pct_data_sources, desire_lines_used, prioritisation_integration, specific_evidence_of_impact, quotes_on_using_pct): if mentions_pct is false, set them to empty string / empty array / false as appropriate.
- pct_scenarios_used: array of scenario names referenced (e.g. "Government Target", "Go Dutch", "E-bike", "Go Cambridge", "Dutch", "Current"/"Baseline").
- desire_lines_used / prioritisation_integration: booleans.
- length_of_network_km and total_cost_pounds: numeric (no commas/£), or null if not stated.
- routes: integer number of routes, or null.
- extraction_notes: brief note if pages unreadable, scanned image, or ambiguous.

Return the JSON object now."""

def strip_fences(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()

def call_claude(doc, raw_file):
    # Engine dispatch: claude or agy (both share `-p --dangerously-skip-permissions`)
    engine = os.environ.get("EXTRACT_ENGINE", "claude")
    file_hint = f"The document is at this local path: {raw_file}. Read it with the Read tool (it may be a PDF or HTML). "
    p = file_hint + PROMPT
    env = dict(os.environ)
    env["CLAUDE_LOG"] = "0"
    if engine == "agy":
        cmd = ["agy", "-p", "--dangerously-skip-permissions", p]
    else:
        cmd = ["claude", "-p", "--dangerously-skip-permissions", p]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    return proc.returncode, proc.stdout + proc.stderr

def validate(obj):
    # ensure all schema keys present
    for k in field_names:
        if k not in obj:
            obj[k] = None
    return obj

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="claude")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--slice", default=None, help="idx range e.g. 1-20 (inclusive) for parallel workers")
    args = ap.parse_args()

    progress = {}
    if os.path.exists(PROGRESS):
        progress = json.load(open(PROGRESS))

    todo = [d for d in DOCUMENTS if d["download_status"] == "ok"]
    if args.slice:
        a, b = [int(x) for x in args.slice.split("-")]
        todo = [d for d in todo if a <= d["idx"] <= b]
    else:
        todo = [d for d in todo if d["idx"] >= args.start]
    if args.limit:
        todo = todo[:args.limit]
    print(f"engine={args.engine} docs_to_process={len(todo)} (start={args.start})")

    n_ok = n_err = 0
    for d in todo:
        idx = d["idx"]
        if progress.get(str(idx)) == "ok":
            print(f"[{idx}] skip (already ok)")
            continue
        raw = d["raw_file"]
        if not raw or not os.path.exists(raw):
            print(f"[{idx}] SKIP no raw file: {d['url']}")
            progress[str(idx)] = "failed"
            json.dump(progress, open(PROGRESS, "w"))
            n_err += 1
            continue
        print(f"[{idx}] {d['url'][:90]}", flush=True)
        rc, out = call_claude(d, raw)
        if rc != 0:
            print(f"   claude rc={rc}; tail: {out[-300:]}")
            # transient? record error, continue
            progress[str(idx)] = "error"
            json.dump(progress, open(PROGRESS, "w"))
            n_err += 1
            # engine-limit signal?
            if "limit" in out.lower() or "quota" in out.lower() or "rate" in out.lower():
                with open(NOTES, "a") as nf:
                    nf.write(f"\n## Engine limit hit at doc {idx} ({d['url']})\n{(out or '')[-500]}\n")
                print("   >>> POSSIBLE ENGINE LIMIT - stopping for switch")
                break
            continue
        parsed = None
        try:
            parsed = json.loads(strip_fences(out))
        except Exception:
            # try to extract first {...}
            m = re.search(r"\{.*\}", out, re.DOTALL)
            if m:
                try: parsed = json.loads(strip_fences(m.group(0)))
                except Exception: parsed = None
        if not isinstance(parsed, dict):
            print(f"   parse fail; raw tail: {out[-300:]}")
            progress[str(idx)] = "parse_error"
            json.dump(progress, open(PROGRESS, "w"))
            n_err += 1
            continue
        parsed = validate(parsed)
        parsed["_idx"] = idx
        parsed["_url"] = d["url"]
        parsed["_source"] = d["source"]
        json.dump(parsed, open(os.path.join(OUTDIR, f"{idx:04d}.json"), "w"), indent=2)
        progress[str(idx)] = "ok"
        json.dump(progress, open(PROGRESS, "w"))
        n_ok += 1
        time.sleep(1.0)
    print(f"\nDONE this run: ok={n_ok} errors={n_err}")
    print(f"cumulative ok in progress: {sum(1 for v in progress.values() if v=='ok')}")

if __name__ == "__main__":
    main()
