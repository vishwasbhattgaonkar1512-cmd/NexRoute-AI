import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (setup_page, require_database, guard, current_assumptions, current_weights, evaluate,  # noqa: E402
                    recommend_cached, style, show, usd, risk_badge, FACTORY_COLORS, lead_time_warning, estimate_note,
                    DECISION_LABELS)

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import PRODUCT_FACTORY_BASELINE, COMPATIBILITY_RULES  # noqa: E402
from src.optimization_engine import score_candidates  # noqa: E402

setup_page("Factory Optimization", "🔧", "One product, all five factories — eligibility, distance, cost, lead time, risk")
require_database()

a, w = current_assumptions(), current_weights()
products = [p["product_name"] for p in PRODUCT_FACTORY_BASELINE]
product = st.selectbox("Product", products, help="Each product is evaluated against its full historical demand.")

ev = guard(evaluate, a, what="factory options")
ev = ev.copy()
ev["score"] = score_candidates(ev, w, a)
g = ev[ev["product_name"] == product].copy()
rec = next(r for r in guard(recommend_cached, a, w, what="recommendation")["recommendations"]
           if r["product_name"] == product)
cur = g[g["is_current"]].iloc[0]

k = st.columns(4)
k[0].metric("Current factory", cur["factory_name"])
k[1].metric("Recommendation", DECISION_LABELS[rec["decision"]],
            None if rec["decision"] != "REALLOCATE" else f"→ {rec['recommended_factory']}", delta_color="off")
k[2].metric("Historical order lines", f"{int(cur['lines']):,}",
            help="Fewer than 30 lines = weakly supported estimates.")
k[3].metric("Demand-weighted distance now", f"{cur['weighted_distance_miles']:,.0f} mi",
            help="Straight-line miles to state/province centroids, weighted by units.")

st.markdown(f"**Why:** {rec['recommendation_reason']}")
if cur["lines"] < 30:
    st.warning(f"Only {int(cur['lines'])} historical order lines for this product — treat all estimates as weak.")

st.subheader("All five factories")
table = g[["factory_name", "is_current", "compatible", "compatibility_basis", "weighted_distance_miles",
           "distance_impact_miles", "freight_cost", "total_cost", "profit_impact", "estimated_lead_days",
           "lead_time_impact_days", "risk_level", "confidence", "score"]].copy()
table["risk_level"] = table["risk_level"].map(risk_badge)
st.dataframe(table, hide_index=True, width="stretch", column_config={
    "factory_name": "Factory", "is_current": "Current", "compatible": "Eligible",
    "compatibility_basis": st.column_config.TextColumn("Eligibility basis", width="large"),
    "weighted_distance_miles": st.column_config.NumberColumn("Distance (mi)", format="%.0f"),
    "distance_impact_miles": st.column_config.NumberColumn("Δ distance (mi)", format="%+.0f"),
    "freight_cost": st.column_config.NumberColumn("Est. freight", format="$%.2f"),
    "total_cost": st.column_config.NumberColumn("Est. total cost", format="$%.2f"),
    "profit_impact": st.column_config.NumberColumn("Est. profit impact", format="$%+.2f"),
    "estimated_lead_days": st.column_config.NumberColumn("Est. lead time (d)", format="%.2f"),
    "lead_time_impact_days": st.column_config.NumberColumn("Δ lead time (d)", format="%+.2f"),
    "risk_level": "Risk", "confidence": "Confidence",
    "score": st.column_config.NumberColumn("Score", format="%+.2f", help="Balanced objective; current = 0."),
})
st.caption(f"Eligibility rule: **{a.compatibility_rule}** — {COMPATIBILITY_RULES[a.compatibility_rule]} "
           "Ineligible factories are never recommended.")

c1, c2 = st.columns(2)
with c1:
    fig = px.bar(g, x="factory_name", y="weighted_distance_miles", color="factory_name",
                 color_discrete_map=FACTORY_COLORS, pattern_shape="compatible",
                 pattern_shape_map={True: "", False: "/"},
                 labels={"factory_name": "", "weighted_distance_miles": "Demand-weighted miles"},
                 hover_data={"compatible": True, "compatibility_basis": True})
    show(style(fig, 340, "Distance to this product's customers (hatched = not eligible)", legend=False))
with c2:
    fig = px.bar(g, x="factory_name", y=["production_cost", "freight_cost"], barmode="stack",
                 labels={"factory_name": "", "value": "Estimated cost (USD)", "variable": ""},
                 color_discrete_sequence=["#2a78d6", "#eb6834"])
    show(style(fig, 340, "Estimated cost breakdown by factory"))

st.subheader("Lead time")
lead_time_warning()
lt = g[["factory_name", "processing_lead_days", "processing_low", "processing_high", "transit_days_assumed",
        "estimated_lead_days"]]
fig = px.bar(lt, x="factory_name", y=["processing_lead_days", "transit_days_assumed"], barmode="stack",
             labels={"factory_name": "", "value": "Days", "variable": ""},
             color_discrete_sequence=["#2a78d6", "#eb6834"])
fig.for_each_trace(lambda t: t.update(name={"processing_lead_days": "Processing (model, derived target)",
                                             "transit_days_assumed": "Transit (assumption)"}[t.name]))
show(style(fig, 320, "Estimated lead time = processing + assumed transit"), lt)

with st.expander("Risk breakdown per factory"):
    for _, r in g.iterrows():
        st.markdown(f"**{r['factory_name']}** — overall {r['overall_risk']:.2f} ({r['risk_level']}), "
                    f"confidence {r['confidence']}")
        for comp in ["model_uncertainty", "data_quality_risk", "missing_info_risk", "compatibility_risk",
                     "operational_risk"]:
            st.caption(f"{comp.replace('_', ' ')}: **{r[comp]:.2f}** — {r[comp + '_explanation']}")
    st.caption(g["score_note"].iloc[0])

estimate_note()
