import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (setup_page, require_database, guard, current_assumptions, current_weights, scenarios,  # noqa: E402
                    style, show, usd, risk_badge, FACTORY_COLORS, lead_time_warning, estimate_note)

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src.assumptions import load_assumptions, load_weights  # noqa: E402
from src.config import COMPATIBILITY_RULES, WEIGHT_PRESETS, FINANCIAL_ASSUMPTIONS  # noqa: E402
from src.scenario_simulator import SCENARIOS  # noqa: E402

setup_page("What-If Analysis", "🧪", "Compare five allocation scenarios under one shared, editable set of assumptions")
require_database()
base_a, base_w = current_assumptions(), current_weights()

with st.sidebar:
    st.subheader("Assumptions (this session)")
    st.caption("Changes here apply to this page only. Save defaults on the Data Management page.")
    o = {}
    o["freight_cost_per_unit_mile"] = st.number_input(
        "Freight $ per unit per mile", 0.0, 0.05, float(base_a.freight_cost_per_unit_mile), 0.0001, format="%.4f",
        help=FINANCIAL_ASSUMPTIONS["freight_cost_per_unit_mile"]["source"])
    o["alt_factory_cost_multiplier"] = st.slider(
        "Alternative-factory production cost ×", 0.80, 1.50, float(base_a.alt_factory_cost_multiplier), 0.01,
        help=FINANCIAL_ASSUMPTIONS["alt_factory_cost_multiplier"]["source"])
    o["transit_days_per_1000_miles"] = st.slider(
        "Transit days per 1,000 miles", 0.0, 5.0, float(base_a.transit_days_per_1000_miles), 0.1,
        help=FINANCIAL_ASSUMPTIONS["transit_days_per_1000_miles"]["source"])
    cap_on = st.checkbox("Limit factory capacity", value=base_a.capacity_enabled,
                         help=FINANCIAL_ASSUMPTIONS["factory_capacity_headroom_pct"]["source"])
    o["factory_capacity_headroom_pct"] = (st.slider("Capacity headroom above current volume (%)", 0, 200,
                                                    int(max(base_a.factory_capacity_headroom_pct, 20)), 5)
                                          if cap_on else -1.0)
    o["minimum_profit_threshold"] = st.number_input("Minimum profit impact to reallocate ($)", -1000.0, 10000.0,
                                                    float(base_a.minimum_profit_threshold), 10.0)
    o["reassignment_penalty_points"] = st.slider("Reassignment penalty (score points)", 0.0, 10.0,
                                                 float(base_a.reassignment_penalty_points), 0.5)
    o["compatibility_rule"] = st.selectbox("Eligibility rule", list(COMPATIBILITY_RULES),
                                           index=list(COMPATIBILITY_RULES).index(base_a.compatibility_rule),
                                           help="\n".join(f"{k}: {v}" for k, v in COMPATIBILITY_RULES.items()))
    st.subheader("Balanced objective weights")
    preset = st.selectbox("Preset", ["(current settings)"] + list(WEIGHT_PRESETS))
    wbase = base_w if preset == "(current settings)" else WEIGHT_PRESETS[preset]
    weights = {"profit_weight": st.slider("Profit", 0.0, 1.0, float(wbase["profit_weight"]), 0.05),
               "speed_weight": st.slider("Lead time", 0.0, 1.0, float(wbase["speed_weight"]), 0.05),
               "risk_weight": st.slider("Risk", 0.0, 1.0, float(wbase["risk_weight"]), 0.05)}

try:
    a = load_assumptions(o, use_database=False)
    weights = load_weights(overrides=weights, use_database=False)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

sim = guard(scenarios, a, weights, what="scenarios")
summary, details = sim["summary"], sim["details"]

lead_time_warning()
estimate_note()

st.subheader("Scenario comparison (before → after)")
infeasible = summary[summary["solver_status"] != "optimal"]
for _, r in infeasible.iterrows():
    st.error(f"**{r['scenario_name']}** is infeasible: {r['note']}")

st.dataframe(summary[["scenario_name", "products_moved", "estimated_cost_impact", "estimated_profit_impact",
                      "profit_impact_pct_of_current_estimated_profit", "units_weighted_lead_time_impact_days",
                      "units_weighted_distance_impact_miles", "mean_risk_of_moved_products", "solver_status"]],
             hide_index=True, width="stretch", column_config={
                 "scenario_name": "Scenario", "products_moved": "Products moved",
                 "estimated_cost_impact": st.column_config.NumberColumn("Est. cost Δ", format="$%+.2f"),
                 "estimated_profit_impact": st.column_config.NumberColumn("Est. profit Δ", format="$%+.2f"),
                 "profit_impact_pct_of_current_estimated_profit": st.column_config.NumberColumn("Profit Δ %", format="%+.2f%%"),
                 "units_weighted_lead_time_impact_days": st.column_config.NumberColumn("Lead time Δ (d, unit-weighted)", format="%+.2f"),
                 "units_weighted_distance_impact_miles": st.column_config.NumberColumn("Distance Δ (mi)", format="%+.0f"),
                 "mean_risk_of_moved_products": st.column_config.NumberColumn("Mean risk of moves", format="%.2f",
                                                                              help="Heuristic 0–1, not a probability."),
                 "solver_status": "Solver"})

c1, c2 = st.columns(2)
with c1:
    fig = px.bar(summary, x="scenario_name", y="estimated_profit_impact", color_discrete_sequence=["#2a78d6"],
                 labels={"scenario_name": "", "estimated_profit_impact": "USD"})
    show(style(fig, 320, "Estimated profit impact vs current", legend=False))
with c2:
    fig = px.bar(summary, x="scenario_name", y="units_weighted_lead_time_impact_days",
                 color_discrete_sequence=["#eb6834"], labels={"scenario_name": "", "units_weighted_lead_time_impact_days": "Days"})
    show(style(fig, 320, "Estimated lead-time change vs current (negative = faster)", legend=False))

st.subheader("Product-level detail")
pick = st.selectbox("Scenario", list(SCENARIOS), format_func=SCENARIOS.get, index=list(SCENARIOS).index("cost"))
d = details[details["scenario"] == pick].copy()
d["risk_level"] = d["risk_level"].map(risk_badge)
st.dataframe(d[["product_name", "current_factory", "proposed_factory", "cost_impact", "profit_impact",
                "lead_time_impact_days", "risk_level", "confidence", "explanation"]],
             hide_index=True, width="stretch", column_config={
                 "product_name": "Product", "current_factory": "Current", "proposed_factory": "Proposed",
                 "cost_impact": st.column_config.NumberColumn("Est. cost Δ", format="$%+.2f"),
                 "profit_impact": st.column_config.NumberColumn("Est. profit Δ", format="$%+.2f"),
                 "lead_time_impact_days": st.column_config.NumberColumn("Lead time Δ (d)", format="%+.2f"),
                 "risk_level": "Risk", "confidence": "Confidence",
                 "explanation": st.column_config.TextColumn("Explanation", width="large")})

with st.expander("Assumptions used for every scenario on this page"):
    st.dataframe(pd.DataFrame(a.describe()).astype({"value": str}), hide_index=True, width="stretch")
    st.json(weights)

if st.button("Save this scenario comparison to the database", type="primary"):
    from src.persistence import save_scenario_run
    run_id = guard(save_scenario_run, sim, what="saving the scenario run")
    st.success(f"Saved as run **{run_id}** (scenario_simulations + optimization_runs).")
