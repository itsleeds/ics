#!/usr/bin/env python3
"""Download every candidate URL into data-govuk-2026-raw and produce a .md extract in data-govuk-2026-md.

Reads:
  - scripts/candidates.json

Outputs:
  - data-govuk-2026-raw/<id>.<ext>
  - data-govuk-2026-md/<id>.md
  - scripts/done_urls.txt

Run: python scripts/02_download_and_md.py
"""
import json, os, re, sys, time, html, io
from urllib.parse import urlparse, unquote
import requests
from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data-govuk-2026-raw")
MD = os.path.join(ROOT, "data-govuk-2026-md")
os.makedirs(RAW, exist_ok=True)
os.makedirs(MD, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

def norm(u):
    u = u.strip()
    u = re.sub(r"[?#].*$", "", u).rstrip("/")
    return u.lower()

def slugify(u, idx):
    p = urlparse(u)
    base = unquote(p.path.split("/")[-1] or p.netloc)
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base)[:40].strip("-")
    return f"{idx:04d}-{base}"

def pdf_text(raw):
    try:
        r = PdfReader(io.BytesIO(raw))
        txt = "\n".join((pg.extract_text() or "") for pg in r.pages)
        if len(txt.strip()) < 50:
            raise ValueError("too short, try pdfplumber")
        return txt, len(r.pages)
    except Exception:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                txt = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
            return txt, len(pdf.pages)
        except Exception:
            return "", 0

def html_text(raw):
    try:
        s = raw.decode("utf-8", "ignore")
    except Exception:
        s = str(raw)
    s = re.sub(r"(?is)<(script|style|head|noscript).*?</\1>", " ", s)
    s = re.sub(r"(?is)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s

MANIFEST = os.path.join(ROOT, "scripts", "done_urls.txt")
done_set = set()
if os.path.exists(MANIFEST):
    done_set = set(l.strip() for l in open(MANIFEST) if l.strip())

cands_path = os.path.join(ROOT, "scripts", "candidates.json")
if not os.path.exists(cands_path):
    print("candidates.json not found. Run scripts/01_build_candidates.py first.")
    sys.exit(1)

cands = json.load(open(cands_path))
total = len(cands)
new = 0
for i, c in enumerate(cands):
    u = c["url"]
    if norm(u) in done_set:
        continue
    idx = i + 1
    sid = slugify(u, idx)
    print(f"[{idx}/{total}] {u}", flush=True)
    try:
        r = requests.get(u, headers={"User-Agent": UA}, timeout=45)
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "")
        raw = r.content
    except Exception as e:
        print(f"   DOWNLOAD FAIL: {e}", flush=True)
        with open(os.path.join(MD, f"{sid}.md"), "w") as f:
            f.write(f"# {u}\n\nurl: {u}\nstatus: download_failed\nerror: {e}\nsource: {c['source']}\n")
        done_set.add(norm(u))
        continue

    is_pdf = ("pdf" in ctype.lower()) or u.lower().endswith(".pdf")
    if is_pdf:
        ext = "pdf"
        txt, npages = pdf_text(raw)
        meta = f"pages: {npages}\nbytes: {len(raw)}\ncontent_type: {ctype}"
    else:
        ext = "html"
        txt = html_text(raw)
        meta = f"bytes: {len(raw)}\ncontent_type: {ctype}"

    rawpath = os.path.join(RAW, f"{sid}.{ext}")
    with open(rawpath, "wb") as f:
        f.write(raw)

    mdpath = os.path.join(MD, f"{sid}.md")
    header = (f"# {u}\n\n"
              f"url: {u}\nsource: {c['source']}\nnote: {c.get('note','')}\n"
              f"doc_type_guess: \n{meta}\n\n---\n\n")
    body = txt if txt.strip() else f"[No extractable text; raw file: {os.path.basename(rawpath)}]"
    with open(mdpath, "w") as f:
        f.write(header + body[:200000])
    done_set.add(norm(u))
    new += 1
    if len(raw) < 500:
        time.sleep(0.3)

with open(MANIFEST, "w") as f:
    f.write("\n".join(sorted(done_set)) + "\n")
print(f"\nDONE. Newly downloaded this run: {new}. Total candidates: {total}")
