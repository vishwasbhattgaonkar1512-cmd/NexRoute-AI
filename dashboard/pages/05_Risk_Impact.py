import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (setup_page, require_database, guard, load_pipeline, current_assumptions, current_weights,  # noqa: E402
                    evaluate, recommend_cached, scenarios, style, show, usd, RISK_COLORS, FACTORY_COLORS,
                    lead_time_warning, estimate_note, measured_interval_coverage)

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src.confidence_engine import COMPONENTS, LEVEL_THRESHOLDS  # noqa: E402
from src.prediction_engine import load_active_model  # noqa: E402

setup_page("Risk & Impact", "⚠️", "Operational, data-quality and model risk, and the estimated financial impact")
require_database()
df, issues = guard(load_pipeline, what="the dataset")
a, w = current_assumptions(), current_weights()
ev = guard(evaluate, a, what="risk scores")
rec = guard(recommend_cached, a, w, what="recommendations")
sim = guard(scenarios, a, w, what="scenarios")
_, meta = guard(load_active_model, what="the model")

st.info(f"Risk scores are transparent **heuristics on a 0–1 scale**, not probabilities. Levels: Low < "
        f"{LEVEL_THRESHOLDS[0]} ≤ Medium < {LEVEL_THRESHOLDS[1]} ≤ High. Formulas: src/confidence_engine.py.")

# ---------------------------------------------------------------- data quality
st.subheader("Data-quality risk")
sev_icon = {"critical": "🛑", "high": "🔴", "medium": "🟠", "low": "🟡", "info": "ℹ️"}
for i in issues:
    if i["severity"] in ("critical", "high", "medium"):
        st.markdown(f"{sev_icon[i['severity']]} **[{i['severity'].upper()}] {i['issue_type']}** "
                    f"({i['affected_records']:,} records) — {i['issue_description']}")

# ---------------------------------------------------------------- model uncertainty
st.subheader("Prediction uncertainty")
lead_time_warning()
sel = meta["selected_model"]
k = st.columns(4)
k[0].metric("Selected model", sel.replace("_", " "))
k[1].metric("Validation MAE", f"{meta['results'][sel]['validation']['mae']:.2f} days")
k[2].metric("Test MAE (final)", f"{meta['final_test']['mae']:.2f} days")
cov = measured_interval_coverage()
k[3].metric("Prediction range coverage (test)", "—" if cov is None else f"{100 * cov['overall']:.1f}%",
            help="Share of test-set shipments whose actual (derived) lead time fell inside the predicted whole-day "
                 "range. The range is nominally 90% (5th–95th percentile of validation residuals); because lead "
                 "times take only a few whole-day values, its measured coverage differs from 90%.")
if cov is not None:
    st.caption("Whole-day prediction ranges by ship mode (test coverage): " + "; ".join(
        f"{m} {int(b[0])}–{int(b[1])} d ({100 * cov['by_ship_mode'][m]:.0f}%)" for m, b in cov["bounds_by_ship_mode"].items()))
st.caption("Alternative-factory predictions are extrapolations: each product has only ever been made at one "
           "factory, and the data shows no measurable distance effect on lead time.")

# ---------------------------------------------------------------- risk components
st.subheader("Risk components by option")
recs = pd.DataFrame(rec["recommendations"])
chosen = ev.merge(recs[["product_name", "recommended_factory"]], left_on=["product_name", "factory_name"],
                  right_on=["product_name", "recommended_factory"])
view = st.radio("Show", ["Recommended option per product", "Every eligible alternative"], horizontal=True)
data = chosen if view.startswith("Recommended") else ev[ev["compatible"] & ~ev["is_current"]]
long = data.melt(id_vars=["product_name", "factory_name"], value_vars=COMPONENTS, var_name="component",
                 value_name="score")
long["component"] = long["component"].str.replace("_", " ")
long["option"] = long["product_name"] if view.startswith("Recommended") else long["product_name"] + " → " + long["factory_name"]
fig = px.bar(long, x="score", y="option",
             color="component", facet_col="component", orientation="h",
             color_discrete_sequence=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
             labels={"score": "", "option": ""}, range_x=[0, 1])
fig.for_each_annotation(lambda an: an.update(text=an.text.split("=")[-1]))
show(style(fig, 520 if view.startswith("Recommended") else 900, "Risk components (0 = no concern, 1 = maximum)", legend=False),
     data[["product_name", "factory_name", *COMPONENTS, "overall_risk", "risk_level", "confidence"]])

lvl = data["risk_level"].value_counts().reindex(["Low", "Medium", "High"], fill_value=0).reset_index()
lvl.columns = ["risk_level", "options"]
c1, c2 = st.columns(2)
with c1:
    fig = px.bar(lvl, x="risk_level", y="options", color="risk_level", color_discrete_map=RISK_COLORS,
                 text="options", labels={"risk_level": "", "options": "Options"})
    show(style(fig, 300, "Options by risk level", legend=False))
with c2:
    sparse = df.groupby("Product Name").size().sort_values().head(8).reset_index(name="order lines")
    fig = px.bar(sparse, x="order lines", y="Product Name", orientation="h", color_discrete_sequence=["#2a78d6"],
                 labels={"Product Name": ""})
    fig.add_vline(x=30, line_width=1, line_color="#898781", annotation_text="30-line support minimum")
    show(style(fig, 300, "Products with the least history", legend=False), sparse)

# ---------------------------------------------------------------- financial impact
st.subheader("Financial impact (estimates)")
estimate_note()
moves = ev[ev["compatible"] & ~ev["is_current"]].copy()
fig = px.scatter(moves, x="profit_impact", y="overall_risk", color="factory_name", color_discrete_map=FACTORY_COLORS,
                 hover_data={"product_name": True, "lead_time_impact_days": ":.2f", "profit_impact": ":.2f"},
                 labels={"profit_impact": "Est. profit impact (USD)", "overall_risk": "Overall risk (0–1)",
                         "factory_name": "Move to"})
fig.update_traces(marker=dict(size=11, line=dict(width=2, color="white")))
fig.add_vline(x=0, line_width=1, line_color="#898781")
show(style(fig, 380, "Every eligible move: estimated profit vs risk"),
     moves[["product_name", "factory_name", "profit_impact", "lead_time_impact_days", "overall_risk", "risk_level"]])

s = sim["summary"]
st.markdown("**Sensitivity to the freight-rate assumption** (cost-focused scenario profit impact scales with it):")
rate = a.freight_cost_per_unit_mile
cost_row = s.set_index("scenario").loc["cost"]
if a.alt_factory_cost_multiplier == 1:
    st.write(f"At {rate:.4f} $/unit/mile the cost-focused scenario estimates {usd(cost_row['estimated_profit_impact'], True)} "
             f"over the historical period; at double the rate, about {usd(2 * cost_row['estimated_profit_impact'], True)} "
             "(with equal production cost at every factory, freight savings scale linearly with the rate).")
else:
    st.write(f"Cost-focused scenario: {usd(cost_row['estimated_profit_impact'], True)} at {rate:.4f} $/unit/mile. "
             "Use What-If Analysis to test other rates.")
