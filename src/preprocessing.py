"""
Data cleaning + feature engineering.

Observed vs derived columns (never confuse the two):
  OBSERVED (from the raw file, unchanged): all original columns, order_date / ship_date (parsed).
  DERIVED:
    lead_time_days_raw        Ship Date - Order Date. Kept for audit only. NOT a lead time (904-1,642 days).
    lead_time_recovered_days  0-8 day lead time recovered by the date-forensics rule (see
                              src/data_validation.py). Derived, not measured. This is the ML target.
    lead_time_index           DEPRECATED (previous target: raw gap minus ship-mode median). Kept only so
                              older database columns stay populated; it mostly encodes the date disguise.
    distance_miles            straight-line miles, current factory -> destination state/province centroid.
    order_date_rebuilt        Order Date with the Order ID year (inferred original order date).

The raw CSV is never modified.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import RAW_DATA_PATH, DATE_FORMAT, PRODUCT_FACTORY_BASELINE, PROCESSED_DIR
from src.data_validation import (
    validate_schema, parse_date_column, recover_lead_time, run_quality_checks, NUMERIC_COLUMNS,
)
from src.geographic_engine import distances_for_rows, is_canadian

ARTIFACT_FEATURES = ["order_year", "order_dow"]  # calendar values of the disguised Order Date: do not model on them


def load_raw(path: Path | str = RAW_DATA_PATH) -> pd.DataFrame:
    """Read the raw CSV as strings (no type assumptions)."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def clean(df: pd.DataFrame, issues: list | None = None) -> pd.DataFrame:
    """
    Parse dates and numbers, recover lead time, drop only rows that cannot be used at all
    (unparseable dates or numbers). Every drop is recorded in `issues`.
    """
    validate_schema(df)
    issues = issues if issues is not None else []
    out = df.copy()

    out["order_date"] = parse_date_column(out["Order Date"], DATE_FORMAT)
    out["ship_date"] = parse_date_column(out["Ship Date"], DATE_FORMAT)
    for col in NUMERIC_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["lead_time_days_raw"] = (out["ship_date"] - out["order_date"]).dt.days
    out, _info = recover_lead_time(out)

    # Data-quality report is computed on everything we were given, before any row is dropped.
    issues.extend(run_quality_checks(df, out))

    unusable = out["order_date"].isna() | out["ship_date"].isna() | out[NUMERIC_COLUMNS].isna().any(axis=1)
    if unusable.any():
        issues.append({"issue_type": "rows_dropped_unusable",
                       "issue_description": "Rows dropped because a date or numeric field could not be parsed.",
                       "affected_records": int(unusable.sum()), "severity": "high", "evidence": {}})
    out = out[~unusable].copy()

    # Deprecated previous target, kept for backward compatibility only.
    out["lead_time_index"] = out["lead_time_days_raw"] - out.groupby("Ship Mode")["lead_time_days_raw"].transform("median")

    content_cols = [c for c in df.columns if c != "Row ID"]
    out["is_possible_duplicate"] = out.duplicated(subset=content_cols, keep="first")
    return out.reset_index(drop=True)


def engineer_features(df: pd.DataFrame, issues: list | None = None) -> pd.DataFrame:
    issues = issues if issues is not None else []
    df = df.copy()

    baseline_map = {p["product_name"]: p["factory_name"] for p in PRODUCT_FACTORY_BASELINE}
    df["current_factory"] = df["Product Name"].map(baseline_map)
    unmapped = df["current_factory"].isna()
    if unmapped.any():
        issues.append({"issue_type": "rows_dropped_unmapped_product",
                       "issue_description": "Rows dropped: product has no baseline factory.",
                       "affected_records": int(unmapped.sum()), "severity": "medium", "evidence": {}})
        df = df[~unmapped].copy()

    df["distance_miles"] = distances_for_rows(df["current_factory"], df["State/Province"])
    df["is_canada"] = df["State/Province"].map(is_canadian)

    # Month and day are preserved by the date disguise; weekday is only meaningful on the rebuilt date.
    df["order_month"] = df["order_date"].dt.month
    df["order_dow_rebuilt"] = df["order_date_rebuilt"].dt.dayofweek
    df["order_seq"] = (df["order_date_rebuilt"] - pd.Timestamp("2000-01-01")).dt.days  # chronological key
    # Calendar fields of the DISGUISED Order Date; kept for compatibility, excluded from models.
    df["order_dow"] = df["order_date"].dt.dayofweek
    df["order_year"] = df["order_date"].dt.year
    return df.reset_index(drop=True)


@lru_cache(maxsize=4)
def _cached_pipeline(path_str: str, mtime: float):
    raw = load_raw(path_str)
    issues: list = []
    cleaned = clean(raw, issues)
    featured = engineer_features(cleaned, issues)
    return featured, tuple(json.dumps(i, default=str) for i in issues)


def run_pipeline(raw_df: pd.DataFrame | None = None, path: Path | str = RAW_DATA_PATH):
    """
    Returns (featured_frame, issues). With raw_df=None the raw CSV is read (cached per file
    modification time). Callers always get fresh copies.
    """
    if raw_df is not None:
        issues: list = []
        featured = engineer_features(clean(raw_df, issues), issues)
        return featured, issues
    p = Path(path)
    featured, issues = _cached_pipeline(str(p), p.stat().st_mtime)
    return featured.copy(), [json.loads(i) for i in issues]


def write_outputs(featured: pd.DataFrame, issues: list) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    featured.to_csv(PROCESSED_DIR / "cleaned_featured.csv", index=False)
    with open(PROCESSED_DIR / "data_quality_logs.json", "w") as f:
        json.dump(issues, f, indent=2, default=str)


if __name__ == "__main__":
    featured, issues = run_pipeline()
    write_outputs(featured, issues)
    print(f"Processed {len(featured)} rows (from {len(load_raw())} raw rows).")
    print(f"Recovered lead time available for {featured['lead_time_recovered_days'].notna().sum()} rows.")
    for i in issues:
        print(f"[{i['severity'].upper():8}] {i['issue_type']}: n={i['affected_records']}")
