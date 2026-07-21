#!/usr/bin/env python3
"""Package the 2026 outputs for a GitHub release.

- Zips data-govuk-2026-raw -> data-govuk-2026-raw.zip
- Zips data-govuk-2026-md   -> data-govuk-2026-md.zip
- (Assumes results.json / results.csv already exist from scripts/aggregate.py.)
Run from repo root: python scripts/package_release.py
"""
import os, zipfile, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def zip_dir(src, dest):
    if not os.path.isdir(src):
        print(f"skip (missing): {src}")
        return
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        n = 0
        for root, _, files in os.walk(src):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, src))
                n += 1
        print(f"wrote {dest} ({n} files)")

zip_dir(os.path.join(ROOT, "data-govuk-2026-raw"), os.path.join(ROOT, "data-govuk-2026-raw.zip"))
zip_dir(os.path.join(ROOT, "data-govuk-2026-md"), os.path.join(ROOT, "data-govuk-2026-md.zip"))

print("\nTo create + populate the release, run:")
print("  gh release create 2026 \\")
print("    data-govuk-2026-raw.zip data-govuk-2026-md.zip \\")
print("    results/results.json results/results.csv results/results_2026_only.json \\")
print("    --title 'PCT/LCWIP data ingest 2026 (England)' \\")
print("    --notes '2026 re-run of the PCT/LCWIP evidence collection (England proof-of-concept).'")
