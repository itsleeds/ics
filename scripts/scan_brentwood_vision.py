#!/usr/bin/env python3
"""Scan rendered page images of Brentwood Appendix D via direct Gemini API to find PCT mentions.
"""
import os, glob, time, json, base64, urllib.request

# Load Gemini API key from gemini.env
for env_file in ["/mnt/secondary/home/robin/.srt/gemini.env", os.path.expanduser("~/.srt/gemini.env")]:
    if os.path.exists(env_file):
        for line in open(env_file):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k] = v.strip()

api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

png_files = sorted(glob.glob("/tmp/brentwood_app_d_page-*.png"))
print(f"Scanning {len(png_files)} page images for PCT mentions using key {api_key[:8]}...")

prompt = """
Examine this page from the LCWIP Technical Report carefully.
Does this page mention the "Propensity to Cycle Tool", "PCT", or "pct.bike"?

Respond in JSON format:
{
  "has_pct": true or false,
  "verbatim_quote": "exact quote where PCT or Propensity to Cycle Tool is mentioned",
  "section": "section or heading name",
  "context_summary": "short summary of how PCT is mentioned on this page"
}
"""

results = []

for png in png_files:
    page_num = int(os.path.basename(png).replace("brentwood_app_d_page-", "").replace(".png", ""))
    
    with open(png, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": img_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {"temperature": 0.0}
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            txt = res["candidates"][0]["content"]["parts"][0]["text"].strip()
            if "```json" in txt:
                txt = txt.split("```json")[1].split("```")[0].strip()
            elif "```" in txt:
                txt = txt.split("```")[1].split("```")[0].strip()
            data = json.loads(txt)
            data["page_num"] = page_num
            if data.get("has_pct"):
                print(f"\n[FOUND PCT MATCH on Page {page_num}]")
                print(f"  Section: {data.get('section')}")
                print(f"  Quote:   {data.get('verbatim_quote')}")
                print(f"  Context: {data.get('context_summary')}\n")
            else:
                print(f"Page {page_num}: No PCT")
            results.append(data)
            time.sleep(4.5)
    except Exception as e:
        print(f"Page {page_num} error: {e}")

pct_found = [r for r in results if r.get("has_pct")]
print(f"\nScan Complete: Found PCT mentions on {len(pct_found)} pages out of {len(png_files)} pages.")
with open("results/brentwood_vision_pct.json", "w") as f:
    json.dump(results, f, indent=2)
