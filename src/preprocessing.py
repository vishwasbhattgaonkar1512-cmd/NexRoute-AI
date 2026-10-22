"""
Phase 3: data cleaning + feature engineering pipeline.
Documented strategy for the date-quality issue found in Phase 1 (see DEVELOPMENT_PROGRESS.md).
"""
import pandas as pd
import numpy as np
from src.config import RAW_DATA_PATH, DATE_FORMAT, PRODUCT_FACTORY_BASELINE
from src.geographic_engine import distance_factory_to_state

DATA_QUALITY_LOG = []  # list of dicts, written to data_quality_logs table


def _log(issue_type, description, affected_records, severity):
    DATA_QUALITY_LOG.append({
        "source_file": str(RAW_DATA_PATH),
        "issue_type": issue_type,
        "issue_description": description,
        "affected_records": affected_records,
        "severity": severity,
    })


def load_raw():
    df = pd.read_csv(RAW_DATA_PATH, dtype=str)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- dates ---
    df["order_date"] = pd.to_datetime(df["Order Date"], format=DATE_FORMAT, errors="coerce")
    df["ship_date"] = pd.to_datetime(df["Ship Date"], format=DATE_FORMAT, errors="coerce")
    bad_dates = df["order_date"].isna() | df["ship_date"].isna()
    if bad_dates.any():
        _log("invalid_date_format", "Rows where Order Date or Ship Date failed to parse",
             int(bad_dates.sum()), "high")
    df = df[~bad_dates].copy()

    df["lead_time_days_raw"] = (df["ship_date"] - df["order_date"]).dt.days

    neg = (df["lead_time_days_raw"] < 0).sum()
    if neg:
        _log("negative_lead_time", "Ship Date before Order Date", int(neg), "high")
    df = df[df["lead_time_days_raw"] >= 0].copy()

    # CRITICAL finding from Phase 1: lead time is 900-1640+ days and uncorrelated with Ship Mode.
    # This is logged as a critical, surfaced data-quality issue (not silently fixed or hidden).
    extreme = (df["lead_time_days_raw"] > 365).sum()
    _log(
        "systemic_lead_time_anomaly",
        "Ship Date - Order Date ranges ~900-1640 days across the ENTIRE dataset and does not vary "
        "meaningfully by Ship Mode (Same Day mean ~1333 days vs Standard Class ~1314 days). This is "
        "inconsistent with real shipping lead times and indicates Ship Date was generated/shifted "
        "independently of the rest of the record (e.g. a synthetic dataset). The raw field is retained "
        "for transparency but is NOT treated as a valid real-world delivery-duration signal. The model "
        "target used downstream is a de-trended relative index, documented in prediction_engine.py.",
        int(extreme),
        "critical",
    )

    # De-trended target: subtract the per-ship-mode median so the model learns RELATIVE variation
    # (across geography/product/region) rather than the corrupted absolute day-count.
    ship_mode_median = df.groupby("Ship Mode")["lead_time_days_raw"].transform("median")
    df["lead_time_index"] = df["lead_time_days_raw"] - ship_mode_median

    # --- numeric fields ---
    for col in ["Sales", "Units", "Gross Profit", "Cost"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    bad_numeric = df[["Sales", "Units", "Gross Profit", "Cost"]].isna().any(axis=1)
    if bad_numeric.any():
        _log("invalid_numeric", "Non-numeric Sales/Units/Gross Profit/Cost", int(bad_numeric.sum()), "medium")
    df = df[~bad_numeric].copy()

    # --- duplicates ---
    dup_rowid = df["Row ID"].duplicated()
    if dup_rowid.any():
        _log("duplicate_row_id", "Duplicate Row ID values", int(dup_rowid.sum()), "medium")
        df = df[~dup_rowid].copy()

    # --- product name consistency: baseline mapping check ---
    baseline_products = {p["product_name"] for p in PRODUCT_FACTORY_BASELINE}
    unexpected = set(df["Product Name"].unique()) - baseline_products
    if unexpected:
        _log("unexpected_product_names", f"Product names not in the 15-product baseline mapping: {sorted(unexpected)}",
             int(df["Product Name"].isin(unexpected).sum()), "low")

    return df.reset_index(drop=True)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    baseline_map = {p["product_name"]: p["factory_name"] for p in PRODUCT_FACTORY_BASELINE}
    df["current_factory"] = df["Product Name"].map(baseline_map)
    unmapped = df["current_factory"].isna()
    if unmapped.any():
        _log("unmapped_product_to_factory", "Products with no baseline factory mapping",
             int(unmapped.sum()), "medium")
        df = df[~unmapped].copy()

    # distance from CURRENT assigned factory to customer state centroid
    df["distance_miles"] = df.apply(
        lambda r: distance_factory_to_state(r["current_factory"], r["State/Province"]), axis=1
    )

    df["order_month"] = df["order_date"].dt.month
    df["order_dow"] = df["order_date"].dt.dayofweek
    df["order_year"] = df["order_date"].dt.year

    return df


def run_pipeline():
    raw = load_raw()
    cleaned = clean(raw)
    featured = engineer_features(cleaned)
    return featured, DATA_QUALITY_LOG


if __name__ == "__main__":
    from src.config import PROCESSED_DIR
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    featured, logs = run_pipeline()
    featured.to_csv(PROCESSED_DIR / "cleaned_featured.csv", index=False)
    import json
    with open(PROCESSED_DIR / "data_quality_logs.json", "w") as f:
        json.dump(logs, f, indent=2)
    print(f"Processed {len(featured)} rows (from {len(load_raw())} raw rows).")
    for l in logs:
        print(f"[{l['severity'].upper()}] {l['issue_type']}: {l['issue_description']} (n={l['affected_records']})")
