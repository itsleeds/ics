#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

LOGFILE="$ROOT/logs/full_update_$(date +%Y%m%d_%H%M%S).log"

echo "=== Starting Full Corpus Extraction & Ingest Run at $(date) ===" | tee -a "$LOGFILE"
echo "Target Model: gemini-3.1-flash-lite" | tee -a "$LOGFILE"
echo "Schema Version: 2026.3 (with authors & multipart metadata)" | tee -a "$LOGFILE"

# 1. Automatically repair non-standard / custom font encoded PDFs via Gemini Vision OCR
python3 scripts/fix_nonstandard_pdfs.py 2>&1 | tee -a "$LOGFILE"

# 2. Prioritize Multipart Detection & Appendix Ingestion across zero-mention docs BEFORE extraction
python3 scripts/06_detect_multipart.py 2>&1 | tee -a "$LOGFILE"

# 3. Run 4-pass extraction across all documents (evaluating combined text layers for multipart packages)
python3 scripts/04_run_extract.py --engine gemini --model gemini-3.1-flash-lite --force 2>&1 | tee -a "$LOGFILE"

# 4. Aggregate flat CSV and merged JSON
python3 scripts/05_aggregate.py 2>&1 | tee -a "$LOGFILE"

# 5. Commit and push updated dataset to main
git add results/results_flat.csv results/results.json results/extracted/[0-9]*.json data-govuk-2026-md/*.md
git commit -m "feat(pipeline): complete full-corpus re-extraction run with prioritized multipart detection & non-standard PDF repair (schema 2026.3)" || true
git push origin main || true

echo "=== Finished Full Corpus Extraction Run at $(date) ===" | tee -a "$LOGFILE"
