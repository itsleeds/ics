#!/usr/bin/env python3
"""Download every candidate URL into data-govuk-2026-raw and produce a .md
file (raw text + metadata) in data-govuk-2026-md.

PDFs: extract text with pypdf (fast); if <50 chars, retry with pdfplumber.
HTML/web pages: fetch and extract <body> text with a lightweight regex/bs4-free
parser (html.unescape + strip tags).
Each download writes:
  data-govuk-2026-raw/<id>.<ext>      raw bytes
  data-govuk-2026-md/<id>.md          text + front-matter

<id> = zero-padded index + short slug.
Incremental: skips URLs already present (keyed by normalised URL list file).
"""
import json, os, re, sys, time, hashlib, html
from urllib.parse import urlparse, unquote
import requests
from pypdf import PdfReader
import io

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
        except Exception as e:
            return "", 0

def html_text(raw):
    try:
        s = raw.decode("utf-8", "ignore")
    except Exception:
        s = str(raw)
    # crude tag strip
    s = re.sub(r"(?is)<(script|style|head|noscript).*?</\1>", " ", s)
    s = re.sub(r"(?is)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s

# index of already-processed
done = {}
for fn in os.listdir(MD):
    if fn.endswith(".md"):
        # first line may be '# <url>'
        try:
            with open(os.path.join(MD, fn)) as f:
                first = f.readline()
            m = re.search(r"url:\s*(\S+)", open(os.path.join(MD, fn)).read())
        except Exception:
            pass
# Simpler: track by reading a manifest
MANIFEST = os.path.join(ROOT, "scripts", "done_urls.txt")
done_set = set()
if os.path.exists(MANIFEST):
    done_set = set(l.strip() for l in open(MANIFEST) if l.strip())

cands = json.load(open(os.path.join(ROOT, "scripts", "candidates.json")))
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
        # record failure in md so we know
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

    # save raw
    rawpath = os.path.join(RAW, f"{sid}.{ext}")
    with open(rawpath, "wb") as f:
        f.write(raw)
    # save md
    mdpath = os.path.join(MD, f"{sid}.md")
    header = (f"# {u}\n\n"
              f"url: {u}\nsource: {c['source']}\nnote: {c.get('note','')}\n"
              f"doc_type_guess: \n{meta}\n\n---\n\n")
    body = txt if txt.strip() else f"[No extractable text; raw file: {os.path.basename(rawpath)}]"
    with open(mdpath, "w") as f:
        f.write(header + body[:200000])  # cap 200k chars
    done_set.add(norm(u))
    new += 1
    if len(raw) < 500:
        time.sleep(0.3)

with open(MANIFEST, "w") as f:
    f.write("\n".join(sorted(done_set)) + "\n")
print(f"\nDONE. newly downloaded this run: {new}. total candidates: {total}")
