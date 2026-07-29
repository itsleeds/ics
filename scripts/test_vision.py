#!/usr/bin/env python3
"""Test Gemini Vision API on Brentwood Appendix D pages using google.genai Client SDK.
"""
import os, glob, time, json
from google import genai
from google.genai import types
from PIL import Image

# Load environment keys
for env_file in ["/mnt/secondary/home/robin/.srt/gemini.env", os.path.expanduser("~/.srt/gemini.env")]:
    if os.path.exists(env_file):
        for line in open(env_file):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k.strip()] = v.strip("\"'\n ")

api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

png_files = sorted(glob.glob("/tmp/brentwood_app_d_page-*.png"))
print(f"Scanning {len(png_files)} page images for PCT mentions using google.genai Client...")

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
    try:
        img = Image.open(png)
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[prompt, img]
        )
        txt = response.text.strip()
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
        time.sleep(2.0)
    except Exception as e:
        print(f"Page {page_num} error: {e}")

pct_found = [r for r in results if r.get("has_pct")]
print(f"\nScan Complete: Found PCT mentions on {len(pct_found)} pages out of {len(png_files)} pages.")
with open("results/brentwood_vision_pct.json", "w") as f:
    json.dump(results, f, indent=2)
