#!/usr/bin/env python3
"""Retry the URLs that failed in the first download pass, with browser-like headers.
Reuses data-govuk-2026-raw / data-govuk-2026-md naming by slugifying.
Appends succesful downloads; updates done_urls.txt manifest + writes md.
"""
import json, os, re, io, time, html
from urllib.parse import urlparse, unquote
import requests
from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data-govuk-2026-raw")
MD = os.path.join(ROOT, "data-govuk-2026-md")
os.makedirs(RAW, exist_ok=True)
os.makedirs(MD, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.google.com/",
}

def norm(u):
    return re.sub(r"[?#].*$", "", u).rstrip("/").lower()

def slugify(u, idx):
    p = urlparse(u)
    base = unquote(p.path.split("/")[-1] or p.netloc)
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base)[:40].strip("-")
    return f"retry{idx:03d}-{base}"

def pdf_text(raw):
    try:
        r = PdfReader(io.BytesIO(raw))
        t = "\n".join((pg.extract_text() or "") for pg in r.pages)
        if len(t.strip()) < 50:
            raise ValueError
        return t, len(r.pages)
    except Exception:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                t = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
            return t, len(pdf.pages)
        except Exception:
            return "", 0

def html_text(raw):
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<(script|style|head|noscript).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s)

fails = []
for f in os.listdir(MD):
    if f.endswith(".md") and "status: download_failed" in open(os.path.join(MD, f)).read():
        m = re.search(r"^url:\s*(\S+)", open(os.path.join(MD, f)).read(), re.MULTILINE)
        if m:
            fails.append(m.group(1))

print(f"retrying {len(fails)} failed URLs")
success = 0
for i, u in enumerate(fails):
    sid = slugify(u, i)
    print(f"[{i+1}] {u}", flush=True)
    got = False
    for attempt in (u, u.replace("https://", "https://www."), u.replace("https://www.", "https://")):
        try:
            r = requests.get(attempt, headers=HEADERS, timeout=45)
            if r.status_code == 200 and len(r.content) > 1000:
                raw = r.content
                ctype = r.headers.get("Content-Type", "")
                is_pdf = ("pdf" in ctype.lower()) or attempt.lower().endswith(".pdf")
                if is_pdf:
                    txt, npages = pdf_text(raw)
                    ext, meta = "pdf", f"pages: {npages}\nbytes: {len(raw)}\ncontent_type: {ctype}"
                else:
                    txt = html_text(raw)
                    ext, meta = "html", f"bytes: {len(raw)}\ncontent_type: {ctype}"
                with open(os.path.join(RAW, f"{sid}.{ext}"), "wb") as fp:
                    fp.write(raw)
                with open(os.path.join(MD, f"{sid}.md"), "w") as fp:
                    fp.write(f"# {u}\n\nurl: {u}\nsource: retry\nstatus: ok\n{meta}\n\n---\n\n" + (txt[:200000] or "[no text]"))
                got = True
                success += 1
                break
        except Exception as e:
            continue
    if not got:
        print("   still failed", flush=True)
print(f"\nretry success: {success}/{len(fails)}")
