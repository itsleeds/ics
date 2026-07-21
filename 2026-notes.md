# 2026 Data Ingest — Notes, Lessons & Engine Switches

This file records provider limits, tool switches, and decisions made during the
2026 re-run of the PCT/LCWIP data ingest (England proof-of-concept).

## Engine 2: agy CLI (`agy -p --dangerously-skip-permissions`)
- Attempted as next engine after Claude session limit.
- **FAILED as batch engine:** agy does not execute the prompt. In every
  invocation it responds as a "help agent" explaining its own
  `--dangerously-skip-permissions` / `--print-timeout` flags instead of reading
  the PDF and extracting JSON. Even `-p` alone with a direct prompt timed out
  waiting for a response. The earlier single "success" was not reproducible.
- **DECISION:** abandon agy. Switch to Firecrawl (engine 3). Per consistency
  rule, ALL documents are re-run from doc 1 with the single chosen engine.

## Engine 3: Firecrawl (`/v2/scrape`, json format + schema)
- Chosen engine. Takes a URL directly (no local PDF needed) — robust against the
  10 download failures since it re-fetches server-side.
- Endpoint: POST https://api.firecrawl.dev/v2/scrape with
  Authorization: Bearer <key from firecrawl-search.js>,
  body {url, formats:[{type:"json", prompt, schema}]}.
- Tested on Redditch LCWIP PDF: returned clean JSON, 83 credits, ~79 pages.
- Cost note: ~80 credits/doc → ~80 docs ≈ 6,400 credits for the 2026 set.
- Single consistent tool for the full corpus (satisfies "all final results same
  tool").
- **CREDITS EXHAUSTED:** HTTP 402 "Insufficient credits" hit at doc 4
  (central-lancashire LCWIP). Firecrawl free/dev credit pool is spent. Also
  observed that for some docs Firecrawl returns scrape metadata WITHOUT the
  `data.json` extraction (transient backend drop), so even with credits the
  large 21-field schema occasionally yields empty extraction.
- **DECISION:** abandon Firecrawl. Remaining option per user instruction is the
  local path: liteparse/pypdf for PDF->text + a local LLM (Ollama Gemma4, per
  environment) for structured extraction. Fully reproducible, no API limit.
  If no local LLM is available, fall back to rule-based Python extraction
  (regex/keyword) over the locally-downloaded PDF text — still one consistent
  tool, fully reproducible.

## Engine 4 (FINAL): local Ollama (gemma4-12b-hermes) + pypdf
- **CHOSEN CONSISTENT ENGINE** for the whole 2026 corpus. No session/credit
  limits, fully reproducible.
- Ollama served at http://localhost:11434, model gemma4-12b-hermes:latest
  (11.9B Q4_K_M, ctx 262144). Pipeline: pypdf/pdfplumber text from local raw
  file -> Ollama /api/generate with schema prompt -> JSON (strip fences) ->
  results/extracted/<idx>.json.
- Validated on Redditch/Liverpool/Warwickshire/LTN1-20: clean JSON, correct
  doc_type, clean scenario enumeration. 12B local model is slightly less
  verbose than Claude on free-text "how_pct_was_used" but accurate on booleans,
  scenarios, doc_type, costs.
- Re-runs all 90 docs from doc 1 (satisfies "all final results same tool").
- The 10 docs that failed local download (no raw file) are recorded with
  mentions_pct=null + extraction_notes="no local content"; they are retained in
  the document list and results for completeness/transparency.
- Used as primary extraction engine (see scripts/run_extract.py).
- Method: for each downloaded PDF/HTML, sent the raw file path + schema prompt;
  Claude read the file and returned a JSON object. Output quality was excellent
  (rich PCT scenario/quote extraction).
- **LIMIT HIT:** "You've hit your session limit · resets 12:10am (Europe/London)"
  after only 1 successful extraction in the parallel run (doc 1 already done in
  the earlier serial test). Claude has a per-session usage cap that is quickly
  exhausted when fanning out many document extractions.
- **DECISION:** Per instructions, switch to the next engine (agy CLI) and
  RE-RUN ALL documents from doc 1 with that single tool for result consistency.
- Partial progress from claude (1-2 docs) was discarded to avoid mixing engines.

## 2026-07-20 session
- Repo: itsleeds/ics, branch 25-data-2026 (off 24-generalise-report).
- 90 seed documents built from existing LCWIP_database.json (94 DB entries,
  deduped to 90 unique URLs).
- Download pass: 80/90 raw files retrieved (10 hard-blocked: West Yorks CA 5
  PDFs now 404, plus Tunbridge Wells, Luton, Horsham, Leicestershire, Lancashire).
- Each doc gets a .md (extracted text) in data-govuk-2026-md and raw bytes in
  data-govuk-2026-raw. 10 failed downloads recorded as status: download_failed.
- Extended schema (schema_2026.json) adds doc_type (LCWIP vs LCWIP-related vs
  other), pct_scenarios_used, pct_data_sources, desire_lines_used,
  prioritisation_integration — the LCWIP vs related-material distinction the
  previous work lacked.

## Firecrawl limit/error at doc 4 (https://centrallocalplan.lancashire.gov.uk/media/2053/it03-central-lancashire-local-cycling-and-walking-infrastructure-plan.pdf)
{"success":false,"error":"Insufficient credits to perform this request. For more credits, you can upgrade your plan at https://firecrawl.dev/pricing or try changing the request limit to a lower value."}
