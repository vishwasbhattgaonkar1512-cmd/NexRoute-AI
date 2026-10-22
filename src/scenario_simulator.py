"""
What-if scenario simulator.

Every scenario is evaluated on the SAME candidate table (same demand, same assumptions, same model), so
scenarios differ only in how the factory for each product is chosen:

  current      Current factory allocation (baseline). All impacts are 0 by definition.
  alternative  Each product forced to its best-scoring COMPATIBLE alternative factory (shows the cost of
               moving; ignores capacity). Products with no compatible alternative stay put.
  distance     Minimise demand-weighted distance (nearest compatible factory), subject to capacity.
  cost         Maximise estimated profit (= minimise production + freight cost), subject to capacity.
  balanced     The recommendation objective: profit, lead time and risk with weights, reassignment penalty
               and minimum-profit threshold (src/optimization_engine.py).

All results are ESTIMATES under analyst assumptions over the historical demand period.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.assumptions import Assumptions, load_assumptions, load_weights
from src.optimization_engine import (
    build_context, evaluate_candidates, score_candidates, solve_allocation, factory_capacities, recommend,
)

SCENARIOS = {
    "current": "Current factory allocation",
    "alternative": "Best alternative factory (forced move)",
    "distance": "Distance-based allocation",
    "cost": "Cost-focused allocation",
    "balanced": "Balanced cost, lead time and risk",
}

DETAIL_COLS = ["product_name", "division", "current_factory", "factory_name", "is_current", "compatibility_basis",
               "units", "lines", "cost_impact", "cost_impact_pct", "profit_impact", "profit_impact_pct_of_revenue",
               "lead_time_impact_days", "processing_impact_days", "distance_impact_miles", "weighted_distance_miles",
               "estimated_lead_days", "risk_level", "overall_risk", "confidence", "score"]


def _rows_for_assignment(ev: pd.DataFrame, assignment: dict) -> pd.DataFrame:
    sel = ev[[assignment.get(p) == f for p, f in zip(ev["product_name"], ev["factory_name"])]]
    return sel.copy()


def _explain_row(r, scenario: str) -> str:
    if r["is_current"]:
        return {"current": "Baseline: current factory.",
                "alternative": "No compatible alternative factory; stays at current factory.",
                }.get(scenario, "Current factory is best under this scenario's objective (or the move is not allowed).")
    return (f"Move to {r['factory_name']}: demand-weighted distance {r['distance_impact_miles']:+,.0f} mi, "
            f"estimated cost {r['cost_impact']:+,.2f} USD, profit {r['profit_impact']:+,.2f} USD, lead time "
            f"{r['lead_time_impact_days']:+.2f} d (transit assumption), risk {r['risk_level']}. "
            f"Compatibility: {r['compatibility_basis']}.")


def simulate_scenarios(a: Assumptions | None = None, weights: dict | None = None, ctx: dict | None = None,
                       scenarios: list | None = None, capacities: dict | None = None) -> dict:
    a = a or load_assumptions()
    weights = weights or load_weights()
    ctx = ctx or build_context()
    scenarios = scenarios or list(SCENARIOS)
    unknown = [s for s in scenarios if s not in SCENARIOS]
    if unknown:
        raise ValueError(f"unknown scenarios: {unknown}")

    ev = evaluate_candidates(a, ctx)
    ev["score"] = score_candidates(ev, weights, a)
    caps = capacities if capacities is not None else factory_capacities(ctx, a)
    current_assign = dict(zip(ev.loc[ev["is_current"], "product_name"], ev.loc[ev["is_current"], "factory_name"]))

    details, summary = [], []
    for s in scenarios:
        status, message, reasons = "optimal", "", {}
        if s == "current":
            assign = current_assign
        elif s == "alternative":
            assign = dict(current_assign)
            alts = ev[~ev["is_current"] & ev["compatible"]].sort_values("score", ascending=False)
            for p, g in alts.groupby("product_name", sort=False):
                assign[p] = g.iloc[0]["factory_name"]
            message = "Capacity not applied (forced-move comparison)."
        elif s in ("distance", "cost"):
            obj = -ev["weighted_distance_miles"].fillna(1e9) if s == "distance" else ev["profit_impact"]
            sol = solve_allocation(ev, obj, ev["compatible"], caps)
            status, message = sol["status"], sol["message"]
            assign = sol["assignment"] or current_assign
        else:  # balanced
            rec = recommend(a, weights, ctx, capacities=caps, ev=ev)
            status, message = rec["run"]["solver_status"], rec["run"]["solver_message"]
            assign = {r["product_name"]: r["recommended_factory"] for r in rec["recommendations"]}
            reasons = {r["product_name"]: r["recommendation_reason"] for r in rec["recommendations"]}

        rows = _rows_for_assignment(ev, assign)[DETAIL_COLS].rename(columns={"factory_name": "proposed_factory"})
        rows.insert(0, "scenario", s)
        rows.insert(1, "scenario_name", SCENARIOS[s])
        if status != "optimal" and s in ("distance", "cost", "balanced"):
            rows["explanation"] = f"INFEASIBLE: {message} Showing current allocation."
        else:
            rows["explanation"] = [reasons.get(p) or _explain_row(r.rename({"proposed_factory": "factory_name"}), s)
                                   for p, (_, r) in zip(rows["product_name"], rows.iterrows())]
        details.append(rows)

        units = rows["units"].sum()
        summary.append({
            "scenario": s, "scenario_name": SCENARIOS[s], "solver_status": status, "note": message,
            "products_moved": int((~rows["is_current"]).sum()),
            "estimated_cost_impact": float(rows["cost_impact"].sum()),
            "estimated_profit_impact": float(rows["profit_impact"].sum()),
            "profit_impact_pct_of_current_estimated_profit":
                100 * float(rows["profit_impact"].sum()) / float(ev.loc[ev["is_current"], "estimated_profit"].sum()),
            "units_weighted_lead_time_impact_days": float((rows["lead_time_impact_days"] * rows["units"]).sum() / units) if units else np.nan,
            "units_weighted_distance_impact_miles": float((rows["distance_impact_miles"] * rows["units"]).sum() / units) if units else np.nan,
            "high_risk_moves": int(((rows["risk_level"] == "High") & ~rows["is_current"]).sum()),
            "mean_risk_of_moved_products": float(rows.loc[~rows["is_current"], "overall_risk"].mean()) if (~rows["is_current"]).any() else 0.0,
        })

    return {"details": pd.concat(details, ignore_index=True), "summary": pd.DataFrame(summary),
            "candidates": ev, "assumptions": a, "weights": weights, "capacities": caps,
            "model_version": ctx["meta"]["model_version"]}


def product_comparison(product_name: str, a: Assumptions | None = None, ctx: dict | None = None,
                       weights: dict | None = None) -> pd.DataFrame:
    """All five factories for one product (used by the Factory Optimization page)."""
    a = a or load_assumptions()
    ev = evaluate_candidates(a, ctx or build_context())
    ev["score"] = score_candidates(ev, weights or load_weights(), a)
    out = ev[ev["product_name"] == product_name]
    if out.empty:
        raise ValueError(f"unknown product or no demand: {product_name!r}")
    return out.reset_index(drop=True)


if __name__ == "__main__":
    res = simulate_scenarios()
    pd.set_option("display.width", 200)
    print(res["summary"][["scenario", "solver_status", "products_moved", "estimated_cost_impact",
                          "estimated_profit_impact", "units_weighted_lead_time_impact_days", "high_risk_moves"]]
          .round(2).to_string(index=False))
