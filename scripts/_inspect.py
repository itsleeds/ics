import json, re, pandas as pd
df = pd.DataFrame(json.load(open("results/results.json")))
mask94 = df["_source_tag"] == "existing94"
mask2026 = df["_source_tag"] == "2026"
print("existing94 with NaN report_name:", (mask94 & df["report_name"].isna()).sum())
print("existing94 total:", mask94.sum())
print("2026 with NaN report_name:", (mask2026 & df["report_name"].isna()).sum())
print("existing94 doc_type nulls:", df[mask94]["doc_type"].isna().sum(), "/", mask94.sum())
# duplicate report_names?
dup = df["report_name"].dropna().duplicated().sum()
print("duplicate report_names:", dup)
# show the existing94 ones with NaN report_name
print("\nexisting94 NaN report_name rows:")
print(df[mask94 & df["report_name"].isna()][["_idx","local_authority_name","mentions_pct"]].to_string())
