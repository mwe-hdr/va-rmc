import pandas as pd
from pathlib import Path

# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

raw_path = r"C:\Users\medwards\OneDrive - HDR, Inc\Arch. Advisory Services - Clients\Virginia\Riverside\mwe.01\data\runs\run_20260526_134907\inputs\2023_2025_rmc_client_raw.csv"
hyper_path = r"C:\Users\medwards\OneDrive - HDR, Inc\Arch. Advisory Services - Clients\Virginia\Riverside\mwe.01\data\runs\run_20260526_134907\inputs\2023_2025_ed_uc Extract_Extract.csv"

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

raw = pd.read_csv(raw_path, low_memory=False)
hyper = pd.read_csv(hyper_path, low_memory=False)

print(f"RAW rows   : {len(raw):,}")
print(f"HYPER rows : {len(hyper):,}")

# --------------------------------------------------
# STANDARDIZE COLUMN NAMES
# --------------------------------------------------

raw.columns = raw.columns.str.strip().str.lower()
hyper.columns = hyper.columns.str.strip().str.lower().str.replace(" ", "_")

# --------------------------------------------------
# NORMALIZE KEY FIELDS
# --------------------------------------------------

# Keys
raw["hdr_mdr"] = raw["patient_id"].astype(str).str.strip()
raw["hdr_har"] = raw["encounter_id"].astype(str).str.strip()
raw["visit_dt"] = pd.to_datetime(raw["visit_dtm"]).dt.date

hyper["hdr_mdr"] = hyper["hdr_mdr"].astype(str).str.strip()
hyper["hdr_har"] = hyper["hdr_har"].astype(str).str.strip()
hyper["visit_dt"] = pd.to_datetime(hyper["visit_dt"]).dt.date

# --------------------------------------------------
# BASIC DEDUP CHECK
# --------------------------------------------------

raw_keys = raw[["hdr_mdr", "hdr_har", "visit_dt"]].drop_duplicates()
hyper_keys = hyper[["hdr_mdr", "hdr_har", "visit_dt"]].drop_duplicates()

print("\n--- DISTINCT KEY COUNTS ---")
print(f"RAW distinct keys   : {len(raw_keys):,}")
print(f"HYPER distinct keys : {len(hyper_keys):,}")

# --------------------------------------------------
# FIND MISSING RECORDS
# --------------------------------------------------

merged_keys = raw_keys.merge(
    hyper_keys,
    on=["hdr_mdr", "hdr_har", "visit_dt"],
    how="outer",
    indicator=True
)

missing_in_hyper = merged_keys[merged_keys["_merge"] == "left_only"]
missing_in_raw = merged_keys[merged_keys["_merge"] == "right_only"]

print("\n--- MISSING RECORDS ---")
print(f"In RAW but NOT in Hyper : {len(missing_in_hyper):,}")
print(f"In Hyper but NOT in RAW: {len(missing_in_raw):,}")

# Save for inspection
missing_in_hyper.to_csv("missing_in_hyper.csv", index=False)
missing_in_raw.to_csv("missing_in_raw.csv", index=False)

# --------------------------------------------------
# JOIN FULL DATA FOR FIELD COMPARISON
# --------------------------------------------------

cols_to_compare = [
    "arrival_method",
    "acuity_name",
    "gender",
    "patient_type",
    "patient_zipcode",
    "dss_entity",
    "discharge_status"
]

raw_subset = raw[[
    "hdr_mdr", "hdr_har", "visit_dt",
    "arrival_method",
    "acuity_level",
    "patient_gender",
    "patient_type",
    "patient_zipcode",
    "facility_name",
    "disch_disp_desc"
]].copy()

# Normalize to match hyper naming
raw_subset.rename(columns={
    "patient_gender": "gender",
    "facility_name": "dss_entity",
    "disch_disp_desc": "discharge_status"
}, inplace=True)

# Rebuild acuity exactly like your pipeline
raw_subset["acuity_name"] = (
    raw_subset["acuity_level"]
    .astype(str)
    .str.strip()
    .map({
        "Immediate": "1-Immediate",
        "Emergent": "2-Emergent",
        "Urgent": "3-Urgent",
        "Less Urgent": "4-Less Urgent",
        "Non-Urgent": "5-Non-Urgent"
    })
    .fillna("0-Unknown")
)

hyper_subset = hyper[[
    "hdr_mdr", "hdr_har", "visit_dt",
    "arrival_method",
    "acuity_name",
    "gender",
    "patient_type",
    "patient_zipcode",
    "dss_entity",
    "discharge_status"
]].copy()

# --------------------------------------------------
# MERGE FOR COMPARISON
# --------------------------------------------------

compare = raw_subset.merge(
    hyper_subset,
    on=["hdr_mdr", "hdr_har", "visit_dt"],
    how="inner",
    suffixes=("_raw", "_hyper")
)

print(f"\nJoined comparison rows: {len(compare):,}")

# --------------------------------------------------
# COLUMN-LEVEL MISMATCHS
# --------------------------------------------------

mismatch_summary = []

for col in cols_to_compare:
    col_raw = f"{col}_raw"
    col_hyper = f"{col}_hyper"

    mismatches = compare[
        (compare[col_raw].astype(str).fillna("NULL") !=
         compare[col_hyper].astype(str).fillna("NULL"))
    ]

    count = len(mismatches)
    mismatch_summary.append((col, count))

    if count > 0:
        mismatches.to_csv(f"mismatch_{col}.csv", index=False)

# --------------------------------------------------
# SUMMARY OUTPUT
# --------------------------------------------------

print("\n--- FIELD MISMATCH SUMMARY ---")
for col, count in mismatch_summary:
    print(f"{col:<20} : {count:,}")

# --------------------------------------------------
# QUICK HIGH-RISK CHECKS
# --------------------------------------------------

print("\n--- QUICK CHECKS ---")

# Encounter count differences
raw_count = len(raw_subset)
hyper_count = hyper["encounter_count"].sum()

print(f"RAW encounter count     : {raw_count:,}")
print(f"HYPER encounter sum     : {hyper_count:,}")

# Visit date distribution
print("\nTop visit date differences (RAW):")
print(raw_subset["visit_dt"].value_counts().head())

print("\nTop visit date differences (HYPER):")
print(hyper_subset["visit_dt"].value_counts().head())