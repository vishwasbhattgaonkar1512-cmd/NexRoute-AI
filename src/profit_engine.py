"""
Cost and profit estimation. Every figure is either HISTORICAL (from the source file) or ESTIMATED
(uses analyst assumptions). Estimated figures are never realised savings.

Cost model, applied identically to the current and to every alternative factory:

    revenue            = sum(Sales)                                   HISTORICAL (customers & prices unchanged)
    production cost    = sum(Cost) x m      m = 1 at the current factory, alt_factory_cost_multiplier elsewhere
                                                                      HISTORICAL x ASSUMPTION
    freight cost       = sum(Units x distance(factory, destination) x freight_cost_per_unit_mile)
                                                                      ESTIMATED (assumed rate, centroid distance)
    estimated profit   = revenue - production cost - freight cost
    profit impact      = estimated profit(alternative) - estimated profit(current)

Note: the source file's Gross Profit (= Sales - Cost) excludes freight, so "estimated profit" here is
lower than the historical Gross Profit for every factory, including the current one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.assumptions import Assumptions
from src.geographic_engine import distance_factory_to_state


def demand_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Historical demand per (product, destination): lines, units, revenue, production cost."""
    need = ["Product Name", "State/Province", "Units", "Sales", "Cost"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"demand_profile: missing columns {missing}")
    return (df.groupby(["Product Name", "State/Province"], as_index=False)
              .agg(lines=("Units", "size"), units=("Units", "sum"), revenue=("Sales", "sum"), cost=("Cost", "sum")))


def candidate_costs(profile: pd.DataFrame, factory: str, is_current: bool, a: Assumptions) -> dict:
    """
    Cost breakdown for serving one product's historical demand (`profile` rows of one product) from `factory`.
    Destinations without coordinates are excluded from freight and reported in `units_without_distance`.
    """
    if profile.empty:
        raise ValueError("empty demand profile")
    if (profile[["units", "revenue", "cost"]] < 0).any().any():
        raise ValueError("demand profile contains negative units, revenue or cost")
    dist = profile["State/Province"].map(lambda s: distance_factory_to_state(factory, s))
    known = dist.notna()
    multiplier = 1.0 if is_current else a.alt_factory_cost_multiplier
    revenue = float(profile["revenue"].sum())
    production = float(profile["cost"].sum() * multiplier)
    freight = float((profile.loc[known, "units"] * dist[known]).sum() * a.freight_cost_per_unit_mile)
    units_known = float(profile.loc[known, "units"].sum())
    wdist = float((profile.loc[known, "units"] * dist[known]).sum() / units_known) if units_known else np.nan
    return {
        "revenue": revenue,
        "production_cost": production,
        "freight_cost": freight,
        "total_cost": production + freight,
        "estimated_profit": revenue - production - freight,
        "historical_gross_profit": float(profile["revenue"].sum() - profile["cost"].sum()),
        "units": float(profile["units"].sum()),
        "lines": int(profile["lines"].sum()),
        "weighted_distance_miles": wdist,
        "units_without_distance": float(profile.loc[~known, "units"].sum()),
        "production_cost_multiplier": multiplier,
        "freight_rate": a.freight_cost_per_unit_mile,
    }


def compare(current: dict, alternative: dict) -> dict:
    """Impact of moving from `current` to `alternative` (both outputs of candidate_costs)."""
    cost_impact = alternative["total_cost"] - current["total_cost"]
    profit_impact = alternative["estimated_profit"] - current["estimated_profit"]
    return {
        "cost_impact": cost_impact,  # + means more expensive
        "cost_impact_pct": 100 * cost_impact / current["total_cost"] if current["total_cost"] else np.nan,
        "profit_impact": profit_impact,  # + means better
        "profit_impact_pct_of_revenue": 100 * profit_impact / current["revenue"] if current["revenue"] else np.nan,
        "classification": ("positive" if profit_impact > 0.005 else "negative" if profit_impact < -0.005 else "neutral"),
    }


def estimate_scenario_profit(sales, current_cost, units, current_factory, proposed_factory, state_province,
                             a: Assumptions | None = None) -> dict:
    """Single-order version of the same symmetric model (kept for API compatibility)."""
    from src.assumptions import load_assumptions
    a = a or load_assumptions(use_database=False)
    if min(sales, current_cost, units) < 0:
        raise ValueError("sales, cost and units must be >= 0")
    prof = pd.DataFrame([{"State/Province": state_province, "lines": 1, "units": units,
                          "revenue": sales, "cost": current_cost}])
    cur = candidate_costs(prof, current_factory, True, a)
    alt = candidate_costs(prof, proposed_factory, proposed_factory == current_factory, a)
    if np.isnan(cur["weighted_distance_miles"]) or np.isnan(alt["weighted_distance_miles"]):
        return {"profit_impact": None, "classification": "insufficient_financial_data",
                "note": "No coordinates for this destination or factory; cannot estimate freight."}
    out = compare(cur, alt)
    out.update({"current": cur, "proposed": alt,
                "note": "ESTIMATE using analyst assumptions; not realised savings."})
    return out
