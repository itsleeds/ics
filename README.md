# Impact Case Study: Transforming Strategic Active Travel Network Planning Internationally

Research project to inform a Case Study for REF 2029 Submission.

This repository contains the code, documentation, and analysis for an impact case study examining the international influence of strategic active travel network planning tools (such as the Propensity to Cycle Tool, PCT) and evidence collection from Local Cycling and Walking Infrastructure Plans (LCWIPs).

---

## Repository Architecture: Code & Data Separation

To keep this repository lightweight, clean, and easy to maintain, **code and analysis scripts are tracked in Git**, while **large raw datasets and extracted document archives are published as GitHub Releases**.

### Accessing Datasets & Releases

You can download the full datasets (raw PDFs, extracted markdown text, and JSON extractions) directly from the [GitHub Releases Page](https://github.com/itsleeds/ics/releases/tag/2026) or via the GitHub CLI (`gh`):

```bash
# Download the 2026 dataset release assets
gh release download 2026
```

Available release assets include:
- `raw_data_v2026-07-23-1.zip`: Raw PDF and HTML documents collected (~670 MB).
- `md_data_v2026-07-23-1.zip`: Extracted markdown text per document (~2.89 MB).
- `results/results.json` / `results/results_flat.csv`: Merged database of LCWIP evidence, consultancies, and PCT mentions.

---

## Data Ingest & Extraction Pipeline

The pipeline is organized sequentially in `scripts/`:

1. **`python3 scripts/01_build_candidates.py`**: Assembles candidate document URLs from seed database and web search discoveries into `scripts/candidates.json`.
2. **`python3 scripts/02_download_and_md.py`**: Downloads raw PDFs/HTML to `data-govuk-2026-raw/` and converts them to text layers in `data-govuk-2026-md/`.
3. **`python3 scripts/03_build_documents.py`**: Indexes downloaded documents into `scripts/documents.json`.
4. **`python3 scripts/04_run_extract.py`**: Performs multi-pass modular extraction via Gemini Flash API into `results/extracted/*.json`.
5. **`python3 scripts/06_detect_multipart.py`**: Scans document text layers to detect multipart LCWIP packages (`is_multipart`, `linked_documents`) and consultancy/author signatures (`authors`).
6. **`python3 scripts/05_aggregate.py`**: Merges JSON extractions into `results/results.json` and `results/results_flat.csv`.
7. **`python3 scripts/package_release.py`**: Packages date-versioned zip archives for release upload via `gh release upload 2026`.

---

## Pipeline Safeguards, Fail-Fast Behavior & Resumability

- **Atomic Resumability**: Every document saves directly to `results/extracted/<idx:04d>.json`. If a run is interrupted or stopped, running the pipeline again automatically resumes from the exact file where it left off without re-extracting completed documents.
- **Fail-Fast & Graceful Pause**: If Google AI Studio API credits are exhausted or an HTTP 429/503 rate limit occurs, `call_gemini_direct_api` executes up to 10 exponential backoff retries and gracefully pauses without corrupting existing JSON files.
- **Strict Rate Limiting**: Inter-pass pacing (`time.sleep(4.5)`) maintains a steady ~13 RPM, staying strictly under Google AI Studio's 15 RPM free tier threshold.
- **Pre-Extraction Regex Scanner**: Non-PCT documents fast-track in ~0.1s by skipping LLM extraction passes, preserving API quota.

---

## Running Pipeline & Collecting More Data

### Scenario A: Adding New Candidate URLs (Incremental Run)
*Use this when adding new URLs to collect more data without re-processing existing documents.*

```bash
# 1. Add new candidate URLs to discovered_urls.txt
echo -e "https://council.gov.uk/lcwip.pdf\tCouncil Name LCWIP" >> scripts/discovered_urls.txt

# 2. Rebuild candidates and download text layers
python3 scripts/01_build_candidates.py
python3 scripts/02_download_and_md.py
python3 scripts/03_build_documents.py

# 3. Extract ONLY new documents (skips existing ones automatically)
python3 scripts/04_run_extract.py --engine gemini --model gemini-3.1-flash-lite

# 4. Detect multipart & aggregate results
python3 scripts/06_detect_multipart.py
python3 scripts/05_aggregate.py

# 5. Commit and push updated dataset to GitHub
git add results/results_flat.csv results/results.json scripts/documents.json
git commit -m "feat(data): incremental ingest of new LCWIP documents"
git push origin main
```

### Scenario B: Full Re-Extraction across All Documents (`--force`)
*Use this when schema fields or prompts are updated and all documents must be re-analyzed.*

```bash
python3 scripts/04_run_extract.py --engine gemini --model gemini-3.1-flash-lite --force
python3 scripts/06_detect_multipart.py
python3 scripts/05_aggregate.py
git add results/results_flat.csv results/results.json
git commit -m "feat(data): full re-extraction across all LCWIP documents"
git push origin main
```

### Scenario C: Targeting Specific Documents
*Use this to re-extract a single document (e.g. Document 7).*

```bash
python3 scripts/04_run_extract.py --engine gemini --model gemini-3.1-flash-lite --doc-idx 7 --force
python3 scripts/05_aggregate.py
```

---

## Local Development & Quarto Web Site

### Requirements

Install Python dependencies:

```bash
pip install -r requirements.txt
```

### Preview Quarto Site

```bash
quarto preview
```

### Deploying Updates

```bash
quarto publish gh-pages
```