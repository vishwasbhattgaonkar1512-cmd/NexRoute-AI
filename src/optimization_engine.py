"""
Phase 7: Optimization & recommendation engine (master prompt section 12).

Uses a weighted scoring objective (documented, scaled consistently) evaluated per product
across its historical order mix, then ranks candidate reassignments. This is a real
constrained scoring/assignment procedure, not a plain sort: it applies compatibility,
minimum-profit-threshold, and reassignment-penalty constraints before ranking, and supports
KEEP CURRENT FACTORY as a first-class outcome.
"""
import numpy as np
import pandas as pd
from src.config import PRODUCT_FACTORY_BASELINE, FINANCIAL_ASSUMPTIONS
from src.scenario_simulator import simulate_product_scenario
from database.connection import get_session
from database.models import OrderItem, Product, Order, Customer

MIN_PROFIT_THRESHOLD = FINANCIAL_ASSUMPTIONS["minimum_profit_threshold"]["value"]
REASSIGNMENT_PENALTY = FINANCIAL_ASSUMPTIONS["reassignment_penalty"]["value"]


def _product_representative_destination(product_name):
    """Pull the most common (state, region, ship_mode) + mean sales/units/cost for a product
    from the database, to run one representative scenario per product (rather than per row)."""
    session = get_session()
    q = (session.query(Order.ship_mode, Customer.state_province, Customer.region,
                        OrderItem.sales, OrderItem.units, OrderItem.cost)
         .join(OrderItem, OrderItem.order_id == Order.order_id)
         .join(Product, Product.product_id == OrderItem.product_id)
         .join(Customer, Customer.customer_id == Order.customer_id)
         .filter(Product.product_name == product_name))
    rows = q.all()
    session.close()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ship_mode", "state", "region", "sales", "units", "cost"])
    mode_row = df["state"].mode()
    most_common_state = mode_row.iloc[0] if not mode_row.empty else df["state"].iloc[0]
    most_common_region = df["region"].mode().iloc[0]
    most_common_ship_mode = df["ship_mode"].mode().iloc[0]
    return {
        "state": most_common_state, "region": most_common_region, "ship_mode": most_common_ship_mode,
        "sales": float(df["sales"].mean()), "units": int(round(df["units"].mean())),
        "cost": float(df["cost"].mean()), "n_orders": len(df),
    }


def score_scenario(scenario_row, weights):
    """
    Weighted objective (documented scaling):
      score = w_speed * normalized_lead_time_improvement
            + w_profit * normalized_profit_impact
            - w_risk * risk_penalty
            - reassignment_penalty (if not current factory)
    All components are scaled to roughly comparable ranges before combining.
    """
    lead_time_component = np.tanh(scenario_row["lead_time_reduction_pct"] / 100.0)  # bounded [-1,1]

    profit_impact = scenario_row["profit"]["profit_impact"]
    if profit_impact is None:
        profit_component = -1.0  # insufficient data -> penalize
    else:
        baseline = scenario_row["profit"]["baseline_profit_historical"] or 1.0
        profit_component = np.tanh(profit_impact / max(abs(baseline), 1.0))

    risk_penalty = {
        "standard_risk": 0.0,
        "moderate_risk_low_confidence": 0.3,
        "high_risk_negative_profit": 0.7,
        "high_risk_unsupported": 1.0,
    }.get(scenario_row["risk_status"], 0.5)

    score = (weights["speed_weight"] * lead_time_component
             + weights["profit_weight"] * profit_component
             - weights["risk_weight"] * risk_penalty)

    if not scenario_row["is_current"]:
        score -= REASSIGNMENT_PENALTY

    return float(score)


def recommend_for_product(product_name, weights=None):
    weights = weights or {"speed_weight": 0.4, "profit_weight": 0.4, "risk_weight": 0.2}
    rep = _product_representative_destination(product_name)
    if rep is None:
        return None

    sim = simulate_product_scenario(
        product_name, rep["state"], rep["region"], rep["ship_mode"],
        units=rep["units"], sales=rep["sales"], cost=rep["cost"],
    )

    for s in sim["scenarios"]:
        s["score"] = score_scenario(s, weights)

    current = next(s for s in sim["scenarios"] if s["is_current"])
    candidates = [s for s in sim["scenarios"] if not s["is_current"]]

    # Apply hard constraints
    feasible = [
        c for c in candidates
        if c["risk_status"] != "high_risk_unsupported"
        and (c["profit"]["profit_impact"] is None or c["profit"]["profit_impact"] >= MIN_PROFIT_THRESHOLD)
    ]

    best_alt = max(feasible, key=lambda c: c["score"]) if feasible else None

    if best_alt is None or best_alt["score"] <= current["score"]:
        decision = "KEEP_CURRENT_FACTORY"
        recommended_factory = sim["current_factory"]
        reason = (f"No alternative factory scored higher than the current assignment "
                  f"({sim['current_factory']}) once compatibility, profit threshold, and the "
                  f"reassignment penalty are applied.")
        lead_time_improvement = 0.0
        profit_impact = 0.0
        risk_level = current["risk_status"]
        confidence = current["confidence"]["label"]
    else:
        decision = "REALLOCATE"
        recommended_factory = best_alt["factory_name"]
        reason = (f"{best_alt['factory_name']} scores higher ({best_alt['score']:.2f} vs "
                  f"{current['score']:.2f}): predicted lead-time index improves by "
                  f"{best_alt['lead_time_improvement']} ({best_alt['lead_time_reduction_pct']}%), "
                  f"estimated profit impact {best_alt['profit']['profit_impact']}. "
                  f"NOTE: {best_alt['confidence']['reason']}")
        lead_time_improvement = best_alt["lead_time_improvement"]
        profit_impact = best_alt["profit"]["profit_impact"]
        risk_level = best_alt["risk_status"]
        confidence = best_alt["confidence"]["label"]

    return {
        "product_name": product_name,
        "division": sim["division"],
        "current_factory": sim["current_factory"],
        "decision": decision,
        "recommended_factory": recommended_factory,
        "predicted_lead_time_improvement": lead_time_improvement,
        "estimated_profit_impact": profit_impact,
        "risk_level": risk_level,
        "confidence": confidence,
        "recommendation_reason": reason,
        "n_historical_orders": rep["n_orders"],
        "all_scenarios": sim["scenarios"],
    }


def run_optimization_for_all_products(weights=None):
    results = []
    for p in PRODUCT_FACTORY_BASELINE:
        r = recommend_for_product(p["product_name"], weights=weights)
        if r:
            results.append(r)
    # rank reallocation candidates by absolute improvement magnitude, KEEP_CURRENT at the bottom
    results.sort(key=lambda r: (r["decision"] == "KEEP_CURRENT_FACTORY", -abs(r["predicted_lead_time_improvement"])))
    for i, r in enumerate(results, start=1):
        r["recommendation_rank"] = i
    return results


if __name__ == "__main__":
    import json
    recs = run_optimization_for_all_products()
    summary = [{k: v for k, v in r.items() if k != "all_scenarios"} for r in recs]
    print(json.dumps(summary, indent=2))
