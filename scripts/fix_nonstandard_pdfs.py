#!/usr/bin/env python3
"""Automated Non-Standard PDF Repair Script.

Detects PDFs with broken CID font encodings, renders page images, and uses Gemini Vision
to generate clean, readable text layers.
"""
import os, sys, glob, re, json, time, base64, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data-govuk-2026-raw")
MD_DIR = os.path.join(ROOT, "data-govuk-2026-md")

# Load environment keys
for env_file in ["/mnt/secondary/home/robin/.srt/gemini.env", os.path.expanduser("~/.srt/gemini.env")]:
    if os.path.exists(env_file):
        for line in open(env_file):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k.strip()] = v.strip("\"'\n ")

api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

def repair_pdf(raw_pdf_path, md_file_path):
    print(f"\n[REPAIRING NON-STANDARD PDF] {os.path.basename(raw_pdf_path)}")
    prefix = os.path.basename(raw_pdf_path).replace(".pdf", "")
    tmp_pattern = f"/tmp/repair_{prefix}_page"
    
    # Render PNGs
    os.system(f"pdftoppm -png -r 125 '{raw_pdf_path}' '{tmp_pattern}'")
    pngs = sorted(glob.glob(f"{tmp_pattern}-*.png"))
    print(f"  Rendered {len(pngs)} pages to PNG.")
    
    cleaned_pages = []
    
    for i, png in enumerate(pngs, 1):
        with open(png, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": "Extract all readable text from this page accurately, preserving section headings and lists. Do not include markdown code fences."},
                        {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                    ]
                }
            ]
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                txt = res["candidates"][0]["content"]["parts"][0]["text"].strip()
                cleaned_pages.append(f"--- Page {i} ---\n" + txt)
                print(f"  Page {i}/{len(pngs)} OCR complete ({len(txt)} chars)")
                time.sleep(4.5)
        except Exception as e:
            print(f"  Page {i} error: {e}")
            time.sleep(2)
            
    full_clean_text = "\n\n".join(cleaned_pages)
    with open(md_file_path, "w") as f:
        f.write(full_clean_text)
    print(f"Successfully repaired {md_file_path} ({len(full_clean_text)} chars)")

# Audit all text layers
md_files = sorted(glob.glob(os.path.join(MD_DIR, "*.md")))

for mf in md_files:
    text = open(mf, errors="ignore").read()
    cid_count = len(re.findall(r"\(cid:\d+\)", text)) + len(re.findall(r"/\d+/\d+/\d+/\d+", text))
    if cid_count > 10 and not "combined.md" in mf:
        basename = os.path.basename(mf).replace(".md", ".pdf")
        raw_path = os.path.join(RAW_DIR, basename)
        if os.path.exists(raw_path):
            repair_pdf(raw_path, mf)
