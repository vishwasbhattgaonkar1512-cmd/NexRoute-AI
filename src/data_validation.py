"""
Data validation, date forensics and data-quality reporting.

Pure functions that take a raw DataFrame (all columns read as strings) and return findings.
Nothing here modifies the raw file. Derived values are always added as NEW columns.

Key finding (evidence in reports/PHASE1_AUDIT.md section 2):
  The raw gap Ship Date - Order Date (904-1,642 days) is not a lead time. The year of Order Date was
  relabelled (Order ID years 2021+2022 -> 2024, 2023+2024 -> 2025), and Ship Date is the original ship
  date shifted by a constant number of days (2,000). Rebuilding the original order date as
  (Order ID year, Order Date month and day) gives

      Ship Date - rebuilt order date = shift + k,   k = 0..8 days

  and k matches ship-mode semantics (Same Day ~0, First 1-3, Second 1-5, Standard 3-7).
  k is published as `lead_time_recovered_days`: a DERIVED value under a stated, testable rule,
  not a measured delivery duration.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    REQUIRED_COLUMNS, DATE_FORMAT, EXPECTED_DATE_SHIFT_DAYS, RECOVERED_LEAD_TIME_VALID_RANGE,
    PRODUCT_FACTORY_BASELINE, DESTINATION_CENTROIDS, CANADA_PROVINCE_CENTROIDS, MIN_SUPPORT_ROWS,
    SHIP_MODES, REGIONS,
)

NUMERIC_COLUMNS = ["Sales", "Units", "Gross Profit", "Cost"]
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class DataValidationError(ValueError):
    """Raised when the input cannot be processed at all (empty file, missing required columns)."""


def make_issue(issue_type, description, affected_records, severity, evidence=None):
    if severity not in SEVERITY_ORDER:
        raise ValueError(f"unknown severity {severity!r}")
    return {
        "issue_type": issue_type,
        "issue_description": description,
        "affected_records": int(affected_records),
        "severity": severity,
        "evidence": evidence or {},
    }


# --------------------------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------------------------
def validate_schema(df: pd.DataFrame) -> None:
    """Raise DataValidationError if the frame is unusable."""
    if df is None or len(df) == 0:
        raise DataValidationError("Input dataset is empty.")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"Input dataset is missing required columns: {missing}")


def missing_value_summary(df: pd.DataFrame) -> pd.DataFrame:
    s = df.isna().sum()
    blank = df.apply(lambda c: (c.astype(str).str.strip() == "").sum() if c.dtype == object else 0)
    out = pd.DataFrame({"missing": s, "blank_strings": blank})
    out["pct_missing"] = 100 * (out["missing"] + out["blank_strings"]) / max(len(df), 1)
    return out.reset_index().rename(columns={"index": "column"})


# --------------------------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------------------------
def parse_date_column(series: pd.Series, fmt: str = DATE_FORMAT) -> pd.Series:
    return pd.to_datetime(series, format=fmt, errors="coerce")


def order_id_year(order_ids: pd.Series) -> pd.Series:
    """Year embedded in Order IDs like 'US-2021-103800-CHO-MIL-31000' (NaN if absent)."""
    return pd.to_numeric(order_ids.astype(str).str.extract(r"^[A-Za-z]+-(\d{4})-")[0], errors="coerce")


def rebuild_original_order_date(order_date: pd.Series, oid_year: pd.Series) -> pd.Series:
    """Order Date with its year replaced by the Order ID year. NaT where impossible (e.g. 29 Feb)."""
    txt = oid_year.astype("Int64").astype(str) + "-" + order_date.dt.strftime("%m-%d")
    return pd.to_datetime(txt, format="%Y-%m-%d", errors="coerce")


def estimate_date_shift(ship_date: pd.Series, rebuilt_order: pd.Series, ship_mode: pd.Series) -> int | None:
    """
    Constant shift between Ship Date and the rebuilt order date.
    Estimated as the most common gap for 'Same Day' rows (lead time ~0 by definition); falls back to the
    minimum gap over all rows when no Same Day rows exist.
    """
    gap = (ship_date - rebuilt_order).dt.days
    same_day = gap[(ship_mode == "Same Day") & gap.notna()]
    if len(same_day):
        return int(same_day.mode().iloc[0])
    gap = gap.dropna()
    return int(gap.min()) if len(gap) else None


def eta_squared(values: pd.Series, groups: pd.Series) -> float:
    """Share of variance in `values` explained by `groups` (0..1)."""
    mask = values.notna() & groups.notna()
    v, g = values[mask].astype(float), groups[mask]
    if len(v) < 2 or v.var() == 0:
        return float("nan")
    between = ((v.groupby(g).transform("mean") - v.mean()) ** 2).sum()
    total = ((v - v.mean()) ** 2).sum()
    return float(between / total)


def date_forensics(df: pd.DataFrame) -> dict:
    """
    Recompute the full date evidence. Expects columns order_date, ship_date (parsed) and the raw columns.
    Returns a JSON-serialisable dict.
    """
    od, sd, mode = df["order_date"], df["ship_date"], df["Ship Mode"]
    raw_gap = (sd - od).dt.days
    oy = order_id_year(df["Order ID"])
    rebuilt = rebuild_original_order_date(od, oy)
    shift = estimate_date_shift(sd, rebuilt, mode)
    k = (sd - rebuilt).dt.days - shift if shift is not None else pd.Series(np.nan, index=df.index)

    ev = {
        "order_date_range": [str(od.min().date()) if od.notna().any() else None,
                             str(od.max().date()) if od.notna().any() else None],
        "ship_date_range": [str(sd.min().date()) if sd.notna().any() else None,
                            str(sd.max().date()) if sd.notna().any() else None],
        "raw_gap_days": {"min": _f(raw_gap.min()), "max": _f(raw_gap.max()), "mean": _f(raw_gap.mean())},
        "raw_gap_mean_by_ship_mode": _round_dict(raw_gap.groupby(mode).mean()),
        "eta2_ship_mode_on_raw_gap": _f(eta_squared(raw_gap, mode)),
        "order_id_year_vs_order_date_year": _crosstab(oy, od.dt.year),
        "order_id_year_vs_ship_date_year": _crosstab(oy, sd.dt.year),
        "estimated_shift_days": shift,
        "expected_shift_days": EXPECTED_DATE_SHIFT_DAYS,
        "recovered_lead_value_counts": {str(int(a)): int(b) for a, b in k.value_counts().sort_index().items()},
        "recovered_lead_mean_by_ship_mode": _round_dict(k.groupby(mode).mean()),
        "recovered_lead_range_by_ship_mode": {
            m: [_f(g.quantile(0.005)), _f(g.quantile(0.995))] for m, g in k.groupby(mode)
        },
        "eta2_ship_mode_on_recovered_lead": _f(eta_squared(k, mode)),
        "rebuilt_order_date_failures": int(rebuilt.isna().sum()),
        "corr_ship_date_vs_row_id": _f(np.corrcoef(
            pd.to_numeric(df["Row ID"], errors="coerce").fillna(0),
            (sd - sd.min()).dt.days.fillna(0))[0, 1]) if len(df) > 2 else None,
    }
    return ev


def recover_lead_time(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Adds columns:
      order_id_year, order_date_rebuilt, lead_time_recovered_days (NaN when implausible),
      lead_time_recovered_flag ('ok' | 'out_of_range' | 'unrebuildable').
    Returns (frame, info).
    """
    df = df.copy()
    df["order_id_year"] = order_id_year(df["Order ID"])
    df["order_date_rebuilt"] = rebuild_original_order_date(df["order_date"], df["order_id_year"])
    shift = estimate_date_shift(df["ship_date"], df["order_date_rebuilt"], df["Ship Mode"])
    k = (df["ship_date"] - df["order_date_rebuilt"]).dt.days - (shift if shift is not None else np.nan)
    lo, hi = RECOVERED_LEAD_TIME_VALID_RANGE
    flag = np.where(df["order_date_rebuilt"].isna() | k.isna(), "unrebuildable",
                    np.where((k < lo) | (k > hi), "out_of_range", "ok"))
    df["lead_time_recovered_flag"] = flag
    df["lead_time_recovered_days"] = k.where(flag == "ok")
    return df, {"shift_days": shift, "n_ok": int((flag == "ok").sum()),
                "n_out_of_range": int((flag == "out_of_range").sum()),
                "n_unrebuildable": int((flag == "unrebuildable").sum())}


# --------------------------------------------------------------------------------------------
# Full data-quality check
# --------------------------------------------------------------------------------------------
def run_quality_checks(raw: pd.DataFrame, parsed: pd.DataFrame) -> list[dict]:
    """
    raw: the untouched string frame. parsed: frame after date/numeric parsing and lead-time recovery
    (expects order_date, ship_date, lead_time_days_raw, lead_time_recovered_days/_flag, numeric columns).
    Returns a list of issue dicts sorted by severity.
    """
    issues = []
    n = len(raw)

    # --- missing values ---
    mv = missing_value_summary(raw)
    total_missing = int(mv["missing"].sum() + mv["blank_strings"].sum())
    issues.append(make_issue(
        "missing_values",
        f"{total_missing} missing or blank cells across {len(raw.columns)} columns.",
        total_missing, "info" if total_missing == 0 else "medium",
        {r["column"]: int(r["missing"] + r["blank_strings"]) for _, r in mv.iterrows() if r["missing"] + r["blank_strings"]},
    ))

    # --- date parsing ---
    bad = parsed["order_date"].isna() | parsed["ship_date"].isna()
    if bad.any():
        issues.append(make_issue("invalid_date_format",
                                 f"Order Date or Ship Date could not be parsed as {DATE_FORMAT}.",
                                 bad.sum(), "high"))

    # --- the date anomaly + recovery ---
    ev = date_forensics(parsed[~bad]) if (~bad).any() else {}
    if ev:
        issues.append(make_issue(
            "systemic_lead_time_anomaly",
            f"Ship Date - Order Date is {ev['raw_gap_days']['min']:.0f}-{ev['raw_gap_days']['max']:.0f} days for every "
            f"row and ship mode explains only {100 * (ev['eta2_ship_mode_on_raw_gap'] or 0):.1f}% of its variance. "
            "This raw gap is NOT a delivery lead time and is never used as one.",
            (~bad).sum(), "critical", {k: ev[k] for k in ("order_date_range", "ship_date_range", "raw_gap_days",
                                                          "raw_gap_mean_by_ship_mode", "eta2_ship_mode_on_raw_gap")}))
        issues.append(make_issue(
            "date_fields_disguised",
            "The Order ID year (2021-2024) is the original order year: Order Date years were relabelled "
            "(two original years per new year) and Ship Date is the original ship date shifted by a constant "
            f"{ev['estimated_shift_days']} days. Dates in this file are therefore synthetic/disguised and calendar "
            "values (year, weekday) of Order Date and Ship Date must not be interpreted literally.",
            (~bad).sum(), "critical", {k: ev[k] for k in ("order_id_year_vs_order_date_year",
                                                          "order_id_year_vs_ship_date_year",
                                                          "estimated_shift_days", "corr_ship_date_vs_row_id")}))
        flag = parsed.loc[~bad, "lead_time_recovered_flag"]
        issues.append(make_issue(
            "lead_time_recovered_derived",
            "lead_time_recovered_days = Ship Date - shift - (Order Date with Order ID year). It is a DERIVED value "
            f"under a testable rule (ship mode explains {100 * (ev['eta2_ship_mode_on_recovered_lead'] or 0):.0f}% of "
            "its variance; Same Day rows are ~0 days), not a measured delivery duration. "
            f"{int((flag == 'ok').sum())} rows recovered; {int((flag != 'ok').sum())} set to missing.",
            int((flag != "ok").sum()), "high", {k: ev[k] for k in ("recovered_lead_value_counts",
                                                                    "recovered_lead_mean_by_ship_mode",
                                                                    "recovered_lead_range_by_ship_mode",
                                                                    "eta2_ship_mode_on_recovered_lead",
                                                                    "rebuilt_order_date_failures")}))
        if ev["estimated_shift_days"] is not None and ev["estimated_shift_days"] != EXPECTED_DATE_SHIFT_DAYS:
            issues.append(make_issue("date_shift_changed",
                                     f"Estimated shift {ev['estimated_shift_days']} differs from the expected "
                                     f"{EXPECTED_DATE_SHIFT_DAYS}; review the date forensics before trusting "
                                     "recovered lead times.", (~bad).sum(), "high"))

    # --- numeric fields ---
    num = parsed[NUMERIC_COLUMNS]
    bad_num = num.isna().any(axis=1)
    if bad_num.any():
        issues.append(make_issue("invalid_numeric", "Non-numeric Sales/Units/Gross Profit/Cost.",
                                 bad_num.sum(), "high"))
    nonpos = ((num[["Sales", "Units"]] <= 0).any(axis=1)) | (num["Cost"] < 0)
    if nonpos.any():
        issues.append(make_issue("non_positive_values", "Sales or Units <= 0, or Cost < 0.", nonpos.sum(), "high"))
    resid = (num["Sales"] - num["Cost"] - num["Gross Profit"]).abs()
    inconsistent = resid > 0.01
    issues.append(make_issue(
        "gross_profit_consistency",
        f"Gross Profit = Sales - Cost holds for {int((~inconsistent & ~bad_num).sum())} of {n} rows.",
        inconsistent.sum(), "medium" if inconsistent.any() else "info"))

    # --- duplicates ---
    dup_rowid = raw["Row ID"].duplicated()
    if dup_rowid.any():
        issues.append(make_issue("duplicate_row_id", "Duplicate Row ID values.", dup_rowid.sum(), "high"))
    content_cols = [c for c in raw.columns if c != "Row ID"]
    dup_content = raw.duplicated(subset=content_cols, keep=False)
    if dup_content.any():
        issues.append(make_issue(
            "possible_duplicate_lines",
            "Rows identical in every column except Row ID. They may be genuine repeat lines or duplicates; the "
            "source gives no way to tell, so they are kept and flagged, not removed.",
            raw.duplicated(subset=content_cols).sum(), "low"))
    dup_oid = raw["Order ID"].duplicated(keep=False)
    issues.append(make_issue(
        "order_id_is_order_plus_product",
        f"Order ID embeds Customer ID and Product ID, so it identifies an order line group, not a basket: "
        f"{raw['Order ID'].nunique()} distinct Order IDs for {n} lines ({int(dup_oid.sum())} lines share an ID). "
        "'Orders' counts in this system mean distinct Order IDs.",
        dup_oid.sum(), "low"))

    # --- geography ---
    unknown_geo = ~raw["State/Province"].isin(DESTINATION_CENTROIDS)
    if unknown_geo.any():
        issues.append(make_issue("unknown_destination",
                                 f"No centroid for: {sorted(raw.loc[unknown_geo, 'State/Province'].unique())}.",
                                 unknown_geo.sum(), "high"))
    canada = raw["State/Province"].isin(CANADA_PROVINCE_CENTROIDS)
    if canada.any():
        issues.append(make_issue(
            "canadian_centroid_approximation",
            "Canadian rows use approximate province geographic centres; for large provinces these can be hundreds "
            "of miles from customers' cities, so their distances are less reliable than US state-centroid distances.",
            canada.sum(), "medium"))
    us = raw["Country/Region"] == "United States"
    short_zip = us & (raw["Postal Code"].astype(str).str.len() == 4)
    if short_zip.any():
        issues.append(make_issue("postal_code_leading_zero_lost",
                                 "US postal codes with 4 digits (leading zero lost, e.g. New England). Postal codes "
                                 "are not used for distance, so this does not affect calculations.",
                                 short_zip.sum(), "low"))
    cust_states = raw.groupby("Customer ID")["State/Province"].nunique()
    multi = cust_states[cust_states > 1].index
    if len(multi):
        issues.append(make_issue(
            "customer_multiple_destinations",
            f"{len(multi)} customers ship to more than one state/province. Geography is taken from each order line, "
            "not from the customer record.",
            raw["Customer ID"].isin(multi).sum(), "medium"))
    unknown_region = ~raw["Region"].isin(REGIONS)
    if unknown_region.any():
        issues.append(make_issue("unknown_region", "Region values outside the known set.", unknown_region.sum(), "medium"))
    unknown_mode = ~raw["Ship Mode"].isin(SHIP_MODES)
    if unknown_mode.any():
        issues.append(make_issue("unknown_ship_mode", "Ship Mode values outside the known set.", unknown_mode.sum(), "medium"))

    # --- products vs baseline config ---
    baseline = {p["product_name"]: p for p in PRODUCT_FACTORY_BASELINE}
    unexpected = set(raw["Product Name"]) - set(baseline)
    if unexpected:
        issues.append(make_issue("unmapped_products",
                                 f"Products with no baseline factory: {sorted(unexpected)}. They are excluded from "
                                 "allocation decisions.", raw["Product Name"].isin(unexpected).sum(), "high"))
    missing_products = set(baseline) - set(raw["Product Name"])
    if missing_products:
        issues.append(make_issue("baseline_products_without_orders",
                                 f"Baseline products with no order lines: {sorted(missing_products)}.",
                                 len(missing_products), "medium"))
    mismatch = {}
    for name, g in raw.groupby("Product Name"):
        if name in baseline:
            divs = set(g["Division"])
            if divs != {baseline[name]["division"]}:
                mismatch[name] = {"config": baseline[name]["division"], "data": sorted(divs)}
    if mismatch:
        issues.append(make_issue("division_mismatch_config_vs_data",
                                 f"Product division in config differs from the data: {mismatch}.",
                                 raw["Product Name"].isin(mismatch).sum(), "medium", mismatch))

    # --- demand sparsity ---
    counts = raw["Product Name"].value_counts()
    sparse = counts[counts < MIN_SUPPORT_ROWS]
    if len(sparse):
        issues.append(make_issue(
            "sparse_product_history",
            f"{len(sparse)} products have fewer than {MIN_SUPPORT_ROWS} order lines: "
            + ", ".join(f"{k} ({v})" for k, v in sparse.items())
            + ". Estimates for these products rest on very little data.",
            int(sparse.sum()), "high", {k: int(v) for k, v in sparse.items()}))

    issues.append(make_issue(
        "no_factory_cost_capacity_compatibility_data",
        "The source has no factory-specific production cost, freight rate, factory capacity or product-factory "
        "compatibility data. Unit cost is constant per product. All such inputs are configurable analyst "
        "assumptions.", 0, "info"))

    return sorted(issues, key=lambda i: SEVERITY_ORDER[i["severity"]])


# --------------------------------------------------------------------------------------------
def _f(x):
    try:
        x = float(x)
        return None if np.isnan(x) else round(x, 4)
    except (TypeError, ValueError):
        return None


def _round_dict(s: pd.Series):
    return {str(k): _f(v) for k, v in s.items()}


def _crosstab(a, b):
    ct = pd.crosstab(a, b)
    return {str(int(i)): {str(int(j)): int(ct.loc[i, j]) for j in ct.columns} for i in ct.index}
