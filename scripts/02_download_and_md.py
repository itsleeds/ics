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
import json, os, re, sys, time, html, io, urllib.parse
from urllib.parse import urlparse, unquote, parse_qs
import requests
from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data-govuk-2026-raw")
MD = os.path.join(ROOT, "data-govuk-2026-md")
os.makedirs(RAW, exist_ok=True)
os.makedirs(MD, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def norm(u):
    if not u:
        return ""
    u = u.strip()
    parsed = urllib.parse.urlparse(u)
    if any(k in parsed.query.lower() for k in ["id=", "doc=", "file=", "sourceurl=", "document=", "viewid=", "path=", "download="]):
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        clean_qs = {k: v for k, v in qs.items() if k.lower() not in ["utm_source", "utm_medium", "utm_campaign", "ga", "fbclid", "gclid"]}
        new_query = urllib.parse.urlencode(clean_qs, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=new_query)).lower()
    else:
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

def fetch_url(u):
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    # Special handling for SharePoint URLs
    if "sharepoint.com" in u.lower():
        try:
            # Guest file links of the form .../:b:/s/<site>/<fileid>?e=<token>
            # resolve to the file directly when "download=1" is appended.
            if ":b:/" in u.lower():
                sep = "&" if "?" in u else "?"
                r_dl = session.get(u + sep + "download=1", allow_redirects=True, timeout=45)
                if r_dl.status_code == 200 and (r_dl.content.startswith(b"%PDF") or "pdf" in r_dl.headers.get("Content-Type", "").lower()):
                    return r_dl.content, r_dl.headers.get("Content-Type", "application/pdf")
                # fall back to treating the redirect target as a normal download
            # If cccandpcc sharepoint, bootstrap guest session via guest link
            if "cccandpcc.sharepoint.com" in u.lower():
                session.get("https://cccandpcc.sharepoint.com/:f:/s/CCCwebsitedocumentlibrary/Eiw77HVjkSRMmX0mu09EqkYB-IkZrbyj2K5SFUl35nRx0w?e=TfzoCX", allow_redirects=True, timeout=30)
            else:
                session.get(u, allow_redirects=True, timeout=30)

            orig_parsed = urlparse(u)
            orig_qs = parse_qs(orig_parsed.query)
            file_path = orig_qs.get("id", [""])[0] or orig_qs.get("SourceUrl", [""])[0]

            if file_path:
                site_prefix = unquote(orig_parsed.path).split("/Shared Documents")[0]
                dl_url = f"{orig_parsed.scheme}://{orig_parsed.netloc}{site_prefix}/_layouts/15/download.aspx?SourceUrl={urllib.parse.quote(file_path, safe='/')}"
                r_dl = session.get(dl_url, allow_redirects=True, timeout=45)
                if r_dl.status_code == 200 and len(r_dl.content) > 1000 and (r_dl.content.startswith(b"%PDF") or "pdf" in r_dl.headers.get("Content-Type","").lower()):
                    return r_dl.content, r_dl.headers.get("Content-Type", "application/pdf")
        except Exception as e:
            print(f"   [SharePoint Fetch Warning]: {e}", flush=True)

    # Standard HTTP GET
    r = session.get(u, allow_redirects=True, timeout=45)
    r.raise_for_status()
    raw = r.content
    ctype = r.headers.get("Content-Type", "")

    # 2-Stage HTML Link Inspection for Embedded PDFs/SharePoint
    if "pdf" not in ctype.lower() and not u.lower().endswith(".pdf") and len(raw) < 500000:
        try:
            html_str = raw.decode("utf-8", "ignore")
            # Find embedded PDF links or SharePoint guest links
            found = re.findall(r'href=[\"\'](https?://[^\s\"\'<>]+|\/[^\s\"\'<>]+\.pdf)[\"\']', html_str, re.IGNORECASE)
            for link in found:
                if link.startswith("/"):
                    link = urllib.parse.urljoin(u, link)
                if link.lower().endswith(".pdf") or "sharepoint.com" in link.lower() or "lcwip" in link.lower():
                    if "sharepoint.com" in link.lower():
                        return fetch_url(link)
                    else:
                        r_sub = session.get(link, allow_redirects=True, timeout=30)
                        if r_sub.status_code == 200 and (("pdf" in r_sub.headers.get("Content-Type", "").lower()) or r_sub.content.startswith(b"%PDF")):
                            return r_sub.content, r_sub.headers.get("Content-Type", "application/pdf")
        except Exception:
            pass

    return raw, ctype

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
        raw, ctype = fetch_url(u)
    except Exception as e:
        print(f"   DOWNLOAD FAIL: {e}", flush=True)
        with open(os.path.join(MD, f"{sid}.md"), "w") as f:
            f.write(f"# {u}\n\nurl: {u}\nstatus: download_failed\nerror: {e}\nsource: {c['source']}\n")
        done_set.add(norm(u))
        continue

    is_pdf = ("pdf" in ctype.lower()) or u.lower().endswith(".pdf") or raw.startswith(b"%PDF")
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

