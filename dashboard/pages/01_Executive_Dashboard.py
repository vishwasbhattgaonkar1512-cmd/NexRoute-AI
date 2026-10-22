import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (setup_page, require_database, guard, load_pipeline, current_assumptions, current_weights,  # noqa: E402
                    recommend_cached, scenarios, style, show, usd, FACTORY_COLORS, DECISION_LABELS, ESTIMATE_NOTE, headline)

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

setup_page("Executive Dashboard", "📊", "Current operations, allocation and estimated optimization impact")
require_database()

df, issues = guard(load_pipeline, what="the dataset")
a, w = current_assumptions(), current_weights()
rec = guard(recommend_cached, a, w, what="recommendations")
sim = guard(scenarios, a, w, what="scenarios")

# ---- data-quality banner
S = headline()
crit = [i for i in issues if i["severity"] == "critical"]
high = [i for i in issues if i["severity"] == "high"]
st.error(f"**{len(crit)} critical and {len(high)} high data-quality findings.** The source dates are disguised, "
         f"so lead times are derived rather than measured, and {S['n_sparse_products']} of {S['n_products']} products have "
         f"fewer than {S['min_support_rows']} order lines. "
         "See Risk & Impact and Data Management.", icon="🛑")

# ---- KPIs (observed)
st.subheader("Historical business (observed)")
k = st.columns(5)
k[0].metric("Order lines", f"{len(df):,}")
k[1].metric("Distinct Order IDs", f"{df['Order ID'].nunique():,}",
            help="Order IDs in this file embed the product, so this counts order+product groups, not baskets.")
k[2].metric("Sales", usd(df["Sales"].sum()))
k[3].metric("Gross profit", usd(df["Gross Profit"].sum()), help="Sales − Cost as given in the source (excludes freight).")
k[4].metric("Products · Factories", f"{df['Product Name'].nunique()} · 5")

k = st.columns(4)
k[0].metric("Customers", f"{df['Customer ID'].nunique():,}")
k[1].metric("Destinations", f"{S['n_destinations']}", help=f"{S['n_us_states']} US states (incl. DC) and "
            f"{S['n_canadian_provinces']} Canadian provinces")
k[2].metric("Mean derived lead time", f"{df['lead_time_recovered_days'].mean():.1f} days",
            help="Derived from disguised dates by a stated rule. Not a measured delivery time.")
k[3].metric("Gross margin", f"{100 * df['Gross Profit'].sum() / df['Sales'].sum():.1f}%")

st.divider()

# ---- current allocation
st.subheader("Current allocation")
c1, c2 = st.columns([3, 2])
by_prod = (df.groupby(["Product Name", "current_factory"], as_index=False)
             .agg(units=("Units", "sum"), sales=("Sales", "sum"), lines=("Units", "size"))
             .sort_values("sales"))
with c1:
    fig = px.bar(by_prod, x="sales", y="Product Name", color="current_factory", orientation="h",
                 color_discrete_map=FACTORY_COLORS, labels={"sales": "Sales (USD)", "Product Name": "",
                                                             "current_factory": "Factory"},
                 hover_data={"units": ":,", "lines": ":,"})
    show(style(fig, 460, "Sales by product, coloured by current factory"),
         by_prod.rename(columns={"current_factory": "factory"}))
with c2:
    by_f = df.groupby("current_factory", as_index=False).agg(units=("Units", "sum"), sales=("Sales", "sum"),
                                                              products=("Product Name", "nunique"))
    by_f["share of units %"] = (100 * by_f["units"] / by_f["units"].sum()).round(1)
    fig = px.bar(by_f.sort_values("units"), x="units", y="current_factory", orientation="h",
                 color="current_factory", color_discrete_map=FACTORY_COLORS,
                 labels={"units": "Units shipped", "current_factory": ""})
    show(style(fig, 300, "Units by factory", legend=False), by_f)
    st.caption(f"{S['top_two_factories'][0]} and {S['top_two_factories'][1]} handle "
               f"{S['top_two_factories_share_pct']:.1f}% of order lines; the {S['top_division']} division is "
               f"{S['top_division_share_pct']:.1f}% of all lines.")

st.divider()

# ---- optimization summary
st.subheader("Optimization summary (estimates)")
st.caption(ESTIMATE_NOTE)
recs = pd.DataFrame(rec["recommendations"])
s = sim["summary"].set_index("scenario")
k = st.columns(4)
k[0].metric("Recommended reallocations", int((recs["decision"] == "REALLOCATE").sum()),
            help="Balanced objective: profit, lead time and risk, with reassignment penalty.")
k[1].metric("Est. profit impact — recommendations", usd(s.loc["balanced", "estimated_profit_impact"], True),
            help="Sum over the historical demand period, under current assumptions.")
k[2].metric("Est. profit impact — cost-focused", usd(s.loc["cost", "estimated_profit_impact"], True),
            help="If every product moved to its cheapest compatible factory (ignores risk).")
k[3].metric("Optimizer status", rec["run"]["solver_status"].title())

tbl = recs[["recommendation_rank", "product_name", "current_factory", "decision", "recommended_factory",
            "estimated_profit_impact", "lead_time_impact_days", "risk_level"]].copy()
tbl["decision"] = tbl["decision"].map(DECISION_LABELS)
st.dataframe(tbl, hide_index=True, width="stretch", column_config={
    "recommendation_rank": "Rank", "product_name": "Product", "current_factory": "Current factory",
    "decision": "Decision", "recommended_factory": "Recommended",
    "estimated_profit_impact": st.column_config.NumberColumn("Est. profit impact", format="$%.2f"),
    "lead_time_impact_days": st.column_config.NumberColumn("Est. lead-time change (d)", format="%+.2f"),
    "risk_level": "Risk"})

summary = sim["summary"][["scenario_name", "products_moved", "estimated_profit_impact",
                          "units_weighted_lead_time_impact_days"]]
fig = px.bar(summary, x="scenario_name", y="estimated_profit_impact",
             labels={"scenario_name": "", "estimated_profit_impact": "Est. profit impact (USD)"},
             color_discrete_sequence=["#2a78d6"], hover_data={"products_moved": True})
show(style(fig, 320, "Estimated profit impact by scenario (historical period)", legend=False), summary)
