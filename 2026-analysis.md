# PCT / LCWIP Data Ingest 2026 — Exploratory Analysis

2026-07-21

- [<span class="toc-section-number">1</span> Overview](#overview)
- [<span class="toc-section-number">2</span> Methods](#methods)
- [<span class="toc-section-number">3</span> Corpus
  composition](#corpus-composition)
- [<span class="toc-section-number">4</span> PCT
  mentions](#pct-mentions)
  - [<span class="toc-section-number">4.1</span> PCT mentions by
    document type](#pct-mentions-by-document-type)
- [<span class="toc-section-number">5</span> Scenario
  usage](#scenario-usage)
- [<span class="toc-section-number">6</span> Geographic
  coverage](#geographic-coverage)
- [<span class="toc-section-number">7</span> Cost and network
  length](#cost-and-network-length)
- [<span class="toc-section-number">8</span> Illustrative
  examples](#illustrative-examples)
- [<span class="toc-section-number">9</span> Limitations & next
  steps](#limitations--next-steps)

# Overview

This document reports the results of the **2026 re-run** of the
data-ingest process that collects evidence of the Propensity to Cycle
Tool (PCT) and related active-travel planning tools in English Local
Cycling and Walking Infrastructure Plans (LCWIPs) and related documents.

The 2026 run is a **proof-of-concept for England** (the first stage
before an international roll-out). It improves on the previous (~2024)
work in three ways:

1.  **Distinction between LCWIP reports and related material** — each
    document is classified `LCWIP`, `LCWIP-related`, or `other`, a
    distinction the previous work did not make.
2.  **Richer “how PCT was used” detail** — explicit scenario usage
    (`Go Dutch`, `Government Target`, `E-bike`, `Go Cambridge`), data
    sources, desire-line usage and prioritisation-integration flags.
3.  **Reproducible pipeline** — every web page / PDF is downloaded to
    `data-govuk-2026-raw` and a `.md` text extract written to
    `data-govuk-2026-md`; structured fields are extracted with a single,
    unlimited local engine (Ollama `gemma4-12b-hermes`) so the results
    are fully reproducible without paid API credits.

The headline dataset merges the fresh 2026 collection with the existing
94-entry database (`LCWIP_database.json`), so the release shows **how
the evidence base has grown**.

# Methods

- **Discovery.** Seed URLs came from the existing 94-entry database,
  supplemented by web searches for 2024–2026 LCWIPs and related
  active-travel strategies, plus the Transport for the South East (TfSE)
  Regional Active Travel Strategy and Action Plan (RATSAP) Evidence Base
  (June 2025), which contains a 64-LCWIP status log for the South East.
- **Download.** Each candidate URL was fetched and stored as a raw file
  (`data-govuk-2026-raw`) with a text/markdown extract
  (`data-govuk-2026-md`).
- **Extraction.** A 21-field schema (`schema_2026.json`) was applied per
  document via a local LLM. Outputs are in `results/extracted/`.
- **Aggregation.** Extracted records were merged with the 94-entry
  database by URL/name and written to `results.json` and a flat
  `results.csv`.

# Corpus composition

``` python
import json, os, pandas as pd
res = json.load(open("results/results.json"))
df = pd.DataFrame(res)
print(f"Total merged records: {len(df)}")
print(f"  2026-only: {(df['_source_tag']=='2026').sum()}")
print(f"  from existing 94-DB: {(df['_source_tag']=='existing94').sum()}")
print()
print("Document type:")
print(df['doc_type'].fillna('(unknown)').value_counts())
```

    Total merged records: 111
      2026-only: 109
      from existing 94-DB: 2

    Document type:
    doc_type
    LCWIP            85
    (unknown)        15
    LCWIP-related    10
    other             1
    Name: count, dtype: int64

# PCT mentions

The central finding for the REF case study is the share of documents
that explicitly mention the Propensity to Cycle Tool.

``` python
import json, os, pandas as pd
res = json.load(open("results/results.json"))
df = pd.DataFrame(res)
pct = df['mentions_pct']
n = pct.notna().sum()
mentioned = (pct == True).sum()
print(f"Documents with a usable mentions_pct flag: {n}")
print(f"Mention PCT: {mentioned} ({mentioned/n*100:.1f}%)")
print(f"Do not mention PCT: {(pct==False).sum()} ({ (pct==False).sum()/n*100:.1f}%)")
print(f"Unknown (no content / failed download): {pct.isna().sum()}")
```

    Documents with a usable mentions_pct flag: 111
    Mention PCT: 77 (69.4%)
    Do not mention PCT: 34 (30.6%)
    Unknown (no content / failed download): 0

## PCT mentions by document type

``` python
import json, os, pandas as pd
res = json.load(open("results/results.json"))
df = pd.DataFrame(res)
ct = pd.crosstab(df['doc_type'].fillna('unknown'), df['mentions_pct'].fillna('unknown'))
print(ct)
```

    mentions_pct   False  True 
    doc_type                   
    LCWIP             25     60
    LCWIP-related      8      2
    other              1      0
    unknown            0     15

# Scenario usage

Among documents that mention the PCT, which future scenarios are
referenced?

``` python
import json, os, pandas as pd
from collections import Counter
res = json.load(open("results/results.json"))
c = Counter()
for r in res:
    if r.get('mentions_pct') is True:
        for s in (r.get('pct_scenarios_used') or []):
            c[str(s).strip()] += 1
sc = pd.Series(dict(c)).sort_values(ascending=False)
print("Scenario mentions (across PCT-mentioning docs):")
print(sc.to_string())
```

    Scenario mentions (across PCT-mentioning docs):
    Go Dutch             29
    Government Target    20
    E-bike               13
    Go Cambridge          2
    Current/Baseline      1
    Baseline              1
    Baseline/Current      1
    Dutch                 1

# Geographic coverage

Coverage against the higher-tier authorities in
[uktransportauthorities](https://github.com/itsleeds/uktransportauthorities)
(ATF allocations) gives a sense of how much of England is represented.

``` python
import json, os, pandas as pd
res = json.load(open("results/results.json"))
df = pd.DataFrame(res)
print("Records by region (England):")
print(df['region'].fillna('(not stated)').value_counts().to_string())
print()
print("Records with a combined authority named:")
print(df['combined_authority_name'].notna().sum())
```

    Records by region (England):
    region
    South East                  32
    North West                  16
    (not stated)                15
    East of England             12
    West Midlands                8
    Yorkshire and The Humber     7
    South West                   6
                                 5
    East Midlands                5
    North East                   4
    England                      1

    Records with a combined authority named:
    81

# Cost and network length

Where stated, LCWIPs propose substantial networks and investment.

``` python
import json, os, pandas as pd
res = json.load(open("results/results.json"))
df = pd.DataFrame(res)
cost = pd.to_numeric(df['total_cost_pounds'], errors='coerce')
km = pd.to_numeric(df['length_of_network_km'], errors='coerce')
print(f"Documents stating a total cost: {cost.notna().sum()}")
print(f"Total stated investment (£): {cost.sum():,.0f}")
print(f"Median stated investment (£): {cost.median():,.0f}")
print(f"Documents stating network length (km): {km.notna().sum()}")
print(f"Total stated network length (km): {km.sum():,.0f}")
```

    Documents stating a total cost: 11
    Total stated investment (£): 11,669,280,000
    Median stated investment (£): 110,000,000
    Documents stating network length (km): 8
    Total stated network length (km): 6,708

# Illustrative examples

A sample of LCWIPs that mention the PCT, with how it was used:

``` python
import json, os, pandas as pd
res = json.load(open("results/results.json"))
df = pd.DataFrame(res)
ex = df[(df['mentions_pct']==True) & (df['doc_type']=='LCWIP')].head(10)
for _, r in ex.iterrows():
    print(f"### {r.get('report_name')} ({r.get('local_authority_name')})")
    print(f"- Date: {r.get('date_published')}")
    print(f"- Scenarios: {r.get('pct_scenarios_used')}")
    print(f"- How used: {(r.get('how_pct_was_used') or '')[:300]}")
    print()
```

    ### Liverpool City Region Combined Authority Local Cycling and Walking Infrastructure Plan (LCWIP) (Halton, Knowsley, Liverpool, Sefton, St Helens, Wirral)
    - Date: 2019
    - Scenarios: ['Government Target', 'Go Dutch']
    - How used: Used to identify existing patterns of walking and cycling, potential new journeys, and to highlight areas with low current cycling levels but high opportunity for change when compared against various scenarios.

    ### Warwickshire Local Cycling and Walking Infrastructure Plan | PART 1 (Warwickshire)
    - Date: February 2024
    - Scenarios: []
    - How used: The Propensity to Cycle Tool (PCT) is listed as one of the assessment and audit tools used by Warwickshire County Council to review existing and planned facilities.

    ### Banbury Local Cycling and Walking Infrastructure Plan (LCWIP) (Cherwell District Council; Oxfordshire County Council)
    - Date: 2023-07
    - Scenarios: ['E-bike', 'Go Dutch']
    - How used: Used to identify preferred routes for cycling journeys, model commuting cycle route networks under different scenarios (E-bike, Go Dutch), and determine school cycling route network flows.

    ### Herefordshire Local Cycling and Walking Infrastructure Plan (Herefordshire)
    - Date: November 2023
    - Scenarios: ['E-bike']
    - How used: Used to identify where increases in the rates of cycling can be expected through the provision of better infrastructure by analyzing commuting trips.

    ### Crawley Local Cycling and Walking Infrastructure Plan – 2021 (Crawley Borough Council)
    - Date: March 2021
    - Scenarios: ['Government Target', 'Go Dutch']
    - How used: Used to identify likely route corridors where cycling has the greatest potential to grow and provide estimated figures for their use by linking census data to employment locations or schools.

    ### Carlisle Local Cycling and Walking Infrastructure Plan (LCWIP) 2022 - 2037 (Carlisle)
    - Date: March 2022
    - Scenarios: []
    - How used: Used to provide evidence of existing and future potential demand for cycling and walking.

    ### Workington Local Cycling and Walking Infrastructure Plan (2022 – 2037) (Cumbria County Council)
    - Date: June 2022
    - Scenarios: []
    - How used: Used as a tool for network planning to identify origin and destination points and cycle flows.

    ### LOCAL CYCLING AND WALKING INFRASTRUCTURE PLAN - Durham City (Durham County Council)
    - Date: January 2021
    - Scenarios: []
    - How used: Used as a key dataset in the evidence-based approach during Stage 2 (Information Gathering) to inform network planning for cycling and walking.

    ### LOCAL CYCLING AND WALKING INFRASTRUCTURE PLAN Peterlee (Durham County Council)
    - Date: September 2022
    - Scenarios: ['Government Target']
    - How used: Used to assess the 'Effectiveness' of desire lines within a prioritization matrix and for validating initial key desire lines against existing data.

    ### LOCAL CYCLING AND WALKING INFRASTRUCTURE PLAN Shildon (Durham County Council)
    - Date: September 2022
    - Scenarios: ['Government Target']
    - How used: The Propensity to Cycle Tool (PCT) was used as a key dataset in Stage 2 (Information Gathering) and integrated into the Prioritisation Framework (Table 4-1) to assess 'Propensity to Cycle' based on forecast numbers of journeys to work.

# Limitations & next steps

- This 2026 run covers **England only**; the international tools (NPT
  Scotland, CRUSE Ireland, biclaR Portugal, Norway PCT) are the next
  stage.
- `doc_type` and free-text fields are model-extracted; treat as
  indicative and spot-check before citation.
- 10 candidate URLs could not be downloaded (blocked/relocated); their
  records are retained with `download_status: failed` for transparency.
- Reproducibility: re-run `scripts/run_extract_ollama.py` against the
  downloaded corpus; no paid API credits are required.
