"""
Factory allocation optimization.

1. EVALUATE every (product, factory) pair against the product's full historical demand, under one shared
   set of assumptions (src/assumptions.py):
     * revenue, production and freight cost, estimated profit        (src/profit_engine.py)
     * processing lead time = active model's prediction for the product's actual order lines (data-derived)
     * transit time = demand-weighted distance x transit_days_per_1000_miles (ASSUMPTION)
     * estimated lead time = processing + transit
     * risk / confidence components                                   (src/confidence_engine.py)

2. SCORE (balanced objective), relative to the current factory (current = 0):
     score = w_profit x profit gain (% of product revenue)
           + w_speed  x lead-time gain (% of current estimated lead time)
           - w_risk   x risk increase (overall risk x 100, points)
           - reassignment_penalty_points (if the factory changes)

3. SOLVE an assignment problem with scipy.optimize.milp:
     maximise   sum(objective[p,f] * x[p,f])
     subject to sum_f x[p,f] = 1                       every product gets exactly one factory
                x[p,f] = 0 if f is incompatible with p  (compatibility rule; hard constraint)
                x[p,f] = 0 if moving p to f reduces estimated profit below minimum_profit_threshold
                sum_p units[p] x[p,f] <= capacity[f]    only when a capacity assumption is enabled
                x binary
   The current factory is always allowed, so "keep current" is always a valid option. If the problem is
   infeasible (e.g. custom capacities below current volumes) the result says so and why.

Run:  python -m src.optimization_engine
"""
from __future__ import annotations

import datetime as dt
import uuid

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

from src.assumptions import Assumptions, load_assumptions, load_weights
from src.compatibility import compatibility, baseline_map
from src.confidence_engine import assess
from src.config import PRODUCT_FACTORY_BASELINE, FACTORIES, MIN_SUPPORT_ROWS
from src.geographic_engine import distances_for_rows
from src.prediction_engine import load_active_model, predict_lead_time, TARGET
from src.preprocessing import run_pipeline
from src.profit_engine import demand_profile, candidate_costs, compare

FACTORY_NAMES = [f["factory_name"] for f in FACTORIES]
EPS_CURRENT = 1e-6  # tie-break in favour of the current factory


# ------------------------------------------------------------------------------------------------
# Context (historical data + model), built once and reused
# ------------------------------------------------------------------------------------------------
def build_context(df: pd.DataFrame | None = None) -> dict:
    if df is None:
        df, _ = run_pipeline()
    if df.empty:
        raise ValueError("no order lines available")
    model, meta = load_active_model()
    multi = df.groupby("Customer ID")["State/Province"].nunique()
    multi_customers = set(multi[multi > 1].index)
    flag = df["is_canada"].fillna(False) | df.get("is_possible_duplicate", False) | df["Customer ID"].isin(multi_customers)
    sel = meta["selected_model"]
    return {
        "df": df,
        "meta": meta,
        "profile": demand_profile(df),
        "flagged_share": flag.groupby(df["Product Name"]).mean().to_dict(),
        "product_lines": df.groupby("Product Name").size().to_dict(),
        "product_units": df.groupby("Product Name")["Units"].sum().to_dict(),
        "factory_units": df.groupby("current_factory")["Units"].sum().reindex(FACTORY_NAMES, fill_value=0).to_dict(),
        "val_mae": meta["results"][sel]["validation"]["mae"],
        "mean_target": float(df[TARGET].mean()),
    }


def _predict_processing(ctx: dict) -> pd.DataFrame:
    """Mean predicted processing lead time (and mean of per-order whole-day ranges) for each (product, factory)."""
    df = ctx["df"]
    frames = []
    for f in FACTORY_NAMES:
        x = df.copy()
        x["current_factory"] = f
        x["distance_miles"] = distances_for_rows(x["current_factory"], x["State/Province"])
        x["distance_miles"] = x["distance_miles"].fillna(x["distance_miles"].median())
        pred = predict_lead_time(x)
        pred["Product Name"] = df["Product Name"].to_numpy()
        pred["factory_name"] = f
        frames.append(pred)
    allp = pd.concat(frames)
    return (allp.groupby(["Product Name", "factory_name"])
                .agg(processing_lead_days=("predicted_lead_days", "mean"),
                     processing_low=("interval_low", "mean"), processing_high=("interval_high", "mean"))
                .reset_index())


# ------------------------------------------------------------------------------------------------
# 1. Evaluate
# ------------------------------------------------------------------------------------------------
def evaluate_candidates(a: Assumptions | None = None, ctx: dict | None = None) -> pd.DataFrame:
    a = a or load_assumptions()
    ctx = ctx or build_context()
    proc = _predict_processing(ctx).set_index(["Product Name", "factory_name"])
    bm = baseline_map()
    rows = []
    for p in PRODUCT_FACTORY_BASELINE:
        name, cur_f = p["product_name"], p["factory_name"]
        prof = ctx["profile"][ctx["profile"]["Product Name"] == name]
        if prof.empty:
            continue  # no demand: reported as infeasible/no-data by recommend()
        cur_cost = candidate_costs(prof, cur_f, True, a)
        for f in FACTORY_NAMES:
            is_cur = f == cur_f
            ok, basis = compatibility(name, f, a.compatibility_rule)
            costs = candidate_costs(prof, f, is_cur, a)
            imp = compare(cur_cost, costs)
            pr = proc.loc[(name, f)]
            transit = costs["weighted_distance_miles"] * a.transit_days_per_1000_miles / 1000
            risk = assess(is_current=is_cur, compatible=ok, compatibility_basis=basis,
                          val_mae=ctx["val_mae"], mean_target=ctx["mean_target"],
                          flagged_share=ctx["flagged_share"].get(name, 0.0),
                          product_lines=ctx["product_lines"].get(name, 0),
                          moved_units=0 if is_cur else ctx["product_units"][name],
                          receiving_current_units=ctx["factory_units"].get(f, 0),
                          capacity_enabled=a.capacity_enabled)
            rows.append({
                "product_name": name, "division": bm[name]["division"], "current_factory": cur_f,
                "factory_name": f, "is_current": is_cur, "compatible": ok, "compatibility_basis": basis,
                **{k: costs[k] for k in ("revenue", "production_cost", "freight_cost", "total_cost",
                                         "estimated_profit", "historical_gross_profit", "units", "lines",
                                         "weighted_distance_miles", "units_without_distance")},
                **imp,
                "processing_lead_days": float(pr["processing_lead_days"]),
                "processing_low": float(pr["processing_low"]), "processing_high": float(pr["processing_high"]),
                "transit_days_assumed": transit,
                "estimated_lead_days": float(pr["processing_lead_days"]) + transit,
                **risk,
            })
    ev = pd.DataFrame(rows)
    cur = ev[ev["is_current"]].set_index("product_name")
    ev["lead_time_impact_days"] = ev["estimated_lead_days"] - ev["product_name"].map(cur["estimated_lead_days"])
    ev["lead_time_gain_pct"] = -100 * ev["lead_time_impact_days"] / ev["product_name"].map(cur["estimated_lead_days"])
    ev["processing_impact_days"] = ev["processing_lead_days"] - ev["product_name"].map(cur["processing_lead_days"])
    ev["distance_impact_miles"] = ev["weighted_distance_miles"] - ev["product_name"].map(cur["weighted_distance_miles"])
    ev["risk_increase_points"] = 100 * (ev["overall_risk"] - ev["product_name"].map(cur["overall_risk"]))
    return ev


# ------------------------------------------------------------------------------------------------
# 2. Score
# ------------------------------------------------------------------------------------------------
def score_candidates(ev: pd.DataFrame, weights: dict, a: Assumptions) -> pd.Series:
    moved = (~ev["is_current"]).astype(float)
    return (weights["profit_weight"] * ev["profit_impact_pct_of_revenue"].fillna(0)
            + weights["speed_weight"] * ev["lead_time_gain_pct"].fillna(0)
            - weights["risk_weight"] * ev["risk_increase_points"].fillna(0)
            - a.reassignment_penalty_points * moved)


# ------------------------------------------------------------------------------------------------
# 3. Solve
# ------------------------------------------------------------------------------------------------
def factory_capacities(ctx: dict, a: Assumptions) -> dict | None:
    if not a.capacity_enabled:
        return None
    return {f: u * (1 + a.factory_capacity_headroom_pct / 100) for f, u in ctx["factory_units"].items()}


def solve_allocation(ev: pd.DataFrame, objective: pd.Series, allowed: pd.Series,
                     capacities: dict | None = None) -> dict:
    """
    Exact assignment via mixed-integer programming. `allowed` is a boolean mask over ev rows.
    Returns {status, message, assignment {product: factory}, objective_value}.
    """
    ev = ev.reset_index(drop=True)
    obj = objective.reset_index(drop=True).to_numpy(dtype=float) + EPS_CURRENT * ev["is_current"].to_numpy()
    allowed = allowed.reset_index(drop=True).to_numpy(dtype=bool)
    products = list(dict.fromkeys(ev["product_name"]))
    no_option = [p for p in products if not allowed[(ev["product_name"] == p).to_numpy()].any()]
    if no_option:
        return {"status": "infeasible", "assignment": {}, "objective_value": None,
                "message": f"No allowed factory for: {', '.join(no_option)}."}
    n = len(ev)
    A_eq = np.zeros((len(products), n))
    for i, p in enumerate(products):
        A_eq[i, (ev["product_name"] == p).to_numpy()] = 1
    cons = [LinearConstraint(A_eq, 1, 1)]
    if capacities is not None:
        A_cap = np.zeros((len(FACTORY_NAMES), n))
        ub = np.zeros(len(FACTORY_NAMES))
        for j, f in enumerate(FACTORY_NAMES):
            m = (ev["factory_name"] == f).to_numpy()
            A_cap[j, m] = ev.loc[m, "units"].to_numpy()
            ub[j] = capacities.get(f, 0)
        cons.append(LinearConstraint(A_cap, -np.inf, ub + 1e-6))
    res = milp(c=-obj, constraints=cons, integrality=np.ones(n),
               bounds=Bounds(np.zeros(n), allowed.astype(float)))
    if res.status != 0 or res.x is None:
        return {"status": "infeasible", "assignment": {}, "objective_value": None,
                "message": f"Solver could not find a feasible allocation ({res.message}). "
                           "Check capacity assumptions: a capacity below a factory's current volume makes "
                           "the current allocation infeasible."}
    x = np.round(res.x).astype(bool)
    assign = dict(zip(ev.loc[x, "product_name"], ev.loc[x, "factory_name"]))
    return {"status": "optimal", "assignment": assign, "objective_value": float(-res.fun),
            "message": "Optimal allocation found."}


# ------------------------------------------------------------------------------------------------
# Recommendations (balanced objective)
# ------------------------------------------------------------------------------------------------
def _explain(row_cur, row_best_alt, decision, chosen, a: Assumptions) -> str:
    def fx(v):
        return f"{'+' if v >= 0 else '-'}${abs(v):,.2f}"
    if decision == "NO_DATA":
        return "No historical demand for this product, so no allocation can be evaluated."
    if decision == "REALLOCATE":
        r = chosen
        return (f"Move from {r['current_factory']} to {r['factory_name']}. Estimated profit impact {fx(r['profit_impact'])} "
                f"({r['profit_impact_pct_of_revenue']:+.2f}% of revenue) from freight on "
                f"{r['distance_impact_miles']:+,.0f} demand-weighted miles; estimated lead time "
                f"{r['lead_time_impact_days']:+.2f} days (transit assumption; processing time "
                f"{r['processing_impact_days']:+.2f} d per the model). Risk {r['risk_level']} "
                f"({r['risk_increase_points']:+.0f} points vs current). Score {r['score']:+.2f} vs 0 for staying. "
                + (f"CAUTION: based on only {int(r['lines'])} historical order lines. " if r["lines"] < MIN_SUPPORT_ROWS else "")
                + "All figures are ESTIMATES over the historical period under the listed assumptions.")
    if row_best_alt is None:
        return (f"Keep at {row_cur['factory_name']}: no compatible alternative under the "
                f"'{a.compatibility_rule}' rule.")
    r = row_best_alt
    reasons = []
    if not r["meets_profit_threshold"]:
        reasons.append(f"its estimated profit impact {fx(r['profit_impact'])} is below the minimum threshold "
                       f"(${a.minimum_profit_threshold:,.2f})")
    if r["score"] <= 0:
        reasons.append(f"its score {r['score']:+.2f} does not beat staying (0)")
    if not reasons:
        reasons.append("the capacity constraint prevents the move")
    return (f"Keep at {row_cur['factory_name']}. Best compatible alternative is {r['factory_name']} "
            f"(profit {fx(r['profit_impact'])}, lead time {r['lead_time_impact_days']:+.2f} d, "
            f"risk {r['risk_level']}), but " + " and ".join(reasons) + ".")


def recommend(a: Assumptions | None = None, weights: dict | None = None, ctx: dict | None = None,
              capacities: dict | None = None, ev: pd.DataFrame | None = None) -> dict:
    """Balanced-objective recommendations. Pass `ev` (from evaluate_candidates with the same `a`) to reuse it."""
    a = a or load_assumptions()
    weights = weights or load_weights()
    ctx = ctx or build_context()
    ev = evaluate_candidates(a, ctx) if ev is None else ev.copy()
    ev["score"] = score_candidates(ev, weights, a)
    ev["meets_profit_threshold"] = ev["is_current"] | (ev["profit_impact"] >= a.minimum_profit_threshold)
    allowed = ev["compatible"] & ev["meets_profit_threshold"]
    caps = capacities if capacities is not None else factory_capacities(ctx, a)
    sol = solve_allocation(ev, ev["score"], allowed, caps)

    recs = []
    evaluated = set(ev["product_name"])
    for p in PRODUCT_FACTORY_BASELINE:
        name = p["product_name"]
        if name not in evaluated:
            recs.append({"product_name": name, "division": p["division"], "current_factory": p["factory_name"],
                         "decision": "NO_DATA", "recommended_factory": p["factory_name"],
                         "recommendation_reason": _explain(None, None, "NO_DATA", None, a)})
            continue
        g = ev[ev["product_name"] == name]
        cur = g[g["is_current"]].iloc[0]
        alts = g[~g["is_current"] & g["compatible"]].sort_values("score", ascending=False)
        best_alt = alts.iloc[0] if len(alts) else None
        if sol["status"] != "optimal":
            decision, chosen = "INFEASIBLE", cur
            reason = f"Optimization infeasible: {sol['message']} Current allocation shown for reference."
        else:
            chosen_f = sol["assignment"][name]
            chosen = g[g["factory_name"] == chosen_f].iloc[0]
            decision = "KEEP_CURRENT_FACTORY" if chosen_f == p["factory_name"] else "REALLOCATE"
            reason = _explain(cur, best_alt, decision, chosen, a)
        recs.append({
            "product_name": name, "division": p["division"], "current_factory": p["factory_name"],
            "decision": decision, "recommended_factory": chosen["factory_name"],
            "best_alternative": best_alt["factory_name"] if best_alt is not None else None,
            "best_alternative_score": float(best_alt["score"]) if best_alt is not None else None,
            "score": float(chosen["score"]),
            "estimated_profit_impact": float(chosen["profit_impact"]),
            "estimated_cost_impact": float(chosen["cost_impact"]),
            "lead_time_impact_days": float(chosen["lead_time_impact_days"]),
            "predicted_lead_time_improvement": float(-chosen["lead_time_impact_days"]),
            "risk_level": chosen["risk_level"], "overall_risk": float(chosen["overall_risk"]),
            "confidence": chosen["confidence"],
            "n_historical_lines": int(cur["lines"]), "units": float(cur["units"]),
            "recommendation_reason": reason,
        })
    order = {"REALLOCATE": 0, "KEEP_CURRENT_FACTORY": 1, "INFEASIBLE": 2, "NO_DATA": 3}
    recs.sort(key=lambda r: (order[r["decision"]],
                             -(r.get("score") or 0) if r["decision"] == "REALLOCATE"
                             else -(r.get("best_alternative_score") if r.get("best_alternative_score") is not None else -1e9)))
    for i, r in enumerate(recs, 1):
        r["recommendation_rank"] = i

    run = {
        "run_id": "opt-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6],
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "objective": "maximise sum of balanced score (see src/optimization_engine.py)",
        "weights": weights, "assumptions": a.to_dict(), "assumption_provenance": a.provenance,
        "capacities": caps, "solver_status": sol["status"], "solver_message": sol["message"],
        "objective_value": sol["objective_value"], "model_version": ctx["meta"]["model_version"],
        "n_products": len(recs),
    }
    return {"run": run, "recommendations": recs, "candidates": ev}


def run_optimization_for_all_products(weights=None, assumptions=None):
    """Backward-compatible helper: list of recommendation dicts."""
    return recommend(a=assumptions, weights=weights)["recommendations"]


if __name__ == "__main__":
    out = recommend()
    print(f"Run {out['run']['run_id']}: solver {out['run']['solver_status']}")
    for r in out["recommendations"]:
        print(f"{r['recommendation_rank']:2}. {r['product_name']:35} {r['decision']:21} -> {r['recommended_factory']:18} "
              f"profit {r.get('estimated_profit_impact', 0):+9.2f}  risk {r.get('risk_level', '-')}")
        print("    " + r["recommendation_reason"])
