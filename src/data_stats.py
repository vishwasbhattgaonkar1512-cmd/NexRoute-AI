"""Headline dataset statistics computed from the data (used by the dashboard instead of hard-coded figures)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import MIN_SUPPORT_ROWS, CANADA_PROVINCE_CENTROIDS
from src.data_validation import eta_squared


def headline_stats(df: pd.DataFrame) -> dict:
    """df: output of preprocessing.run_pipeline()."""
    if df.empty:
        raise ValueError("no rows")
    lines = df.groupby("Product Name").size()
    sparse = lines[lines < MIN_SUPPORT_ROWS].sort_values()
    div = df["Division"].value_counts(normalize=True)
    lead, dist = df["lead_time_recovered_days"], df["distance_miles"]
    us = ~df["State/Province"].isin(CANADA_PROVINCE_CENTROIDS)
    corr = lambda m: float(dist[m].corr(lead[m])) if m.sum() > 2 else float("nan")
    by_factory = df.groupby("current_factory").size().sort_values(ascending=False)
    return {
        "n_lines": int(len(df)),
        "n_products": int(df["Product Name"].nunique()),
        "sparse_products": {k: int(v) for k, v in sparse.items()},
        "n_sparse_products": int(len(sparse)),
        "min_support_rows": MIN_SUPPORT_ROWS,
        "top_division": str(div.index[0]),
        "top_division_share_pct": float(100 * div.iloc[0]),
        "n_us_states": int(df.loc[us, "State/Province"].nunique()),
        "n_canadian_provinces": int(df.loc[~us, "State/Province"].nunique()),
        "n_destinations": int(df["State/Province"].nunique()),
        "ship_mode_eta2_pct": float(100 * eta_squared(lead, df["Ship Mode"])),
        "corr_distance_lead_all": corr(pd.Series(True, index=df.index)),
        "corr_distance_lead_us": corr(us),
        "top_two_factories": list(by_factory.index[:2]),
        "top_two_factories_share_pct": float(100 * by_factory.iloc[:2].sum() / by_factory.sum()),
    }


def scope_text(s: dict) -> str:
    return (f"{s['n_destinations']} destinations ({s['n_us_states']} US states/DC and "
            f"{s['n_canadian_provinces']} Canadian provinces)")
