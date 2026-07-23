# Impact Case Study: Transforming Strategic Active Travel Network Planning Internationally

Research project to inform a Case Study for REF 2029 Submission.

This repository contains the code, documentation, and analysis for an impact case study examining the international influence of strategic active travel network planning tools (such as the Propensity to Cycle Tool, PCT) and evidence collection from Local Cycling and Walking Infrastructure Plans (LCWIPs).

## Repository Architecture: Code & Data Separation

To keep this repository lightweight, clean, and easy to maintain, **code and analysis scripts are tracked in Git**, while **large raw datasets and extracted document archives are published as GitHub Releases**.

### Accessing Datasets & Releases

You can download the full datasets (raw PDFs, extracted markdown text, and JSON extractions) directly from the [GitHub Releases Page](https://github.com/itsleeds/ics/releases/tag/2026) or via the GitHub CLI (`gh`):

```bash
# Download the 2026 dataset release assets
gh release download 2026
```

Available release assets include:
- `data-govuk-2026-raw.zip`: Raw PDF and HTML documents collected (~680 MB).
- `data-govuk-2026-md.zip`: Extracted markdown text per document (~2.95 MB).
- `results.json` / `results.csv`: Merged database of LCWIP evidence and PCT mentions.
- `LCWIP_database.json`: Legacy 94-entry LCWIP database.

---

## Data Ingest & Extraction Pipeline

The pipeline is organized in `scripts/`:

1. **`python scripts/01_build_candidates.py`**: Assemble candidate document URLs from seed databases and web search discoveries.
2. **`python scripts/02_download_and_md.py`**: Download raw documents (`data-govuk-2026-raw/`) and convert to text/markdown (`data-govuk-2026-md/`).
3. **`python scripts/03_build_documents.py`**: Index all downloaded documents into `scripts/documents.json`.
4. **`python scripts/04_run_extract.py`**: Perform structured field extraction via local LLM (Ollama `gemma4-12b-hermes` by default) into `results/extracted/*.json`.
5. **`python scripts/05_aggregate.py`**: Merge extracted JSONs into `results/results.json` and `results/results_flat.csv`.
6. **`python scripts/package_release.py`**: Package zip archives for release upload via `gh release create 2026`.

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