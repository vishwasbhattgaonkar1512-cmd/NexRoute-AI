import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from src.config import PRODUCT_FACTORY_BASELINE, STATE_CENTROIDS, FINANCIAL_ASSUMPTIONS
from src.scenario_simulator import simulate_product_scenario

st.set_page_config(page_title="What-If Scenario Analysis", layout="wide")
st.title("🧪 What-If Scenario Analysis")
st.caption("Compare multiple products/destinations side by side, with adjustable financial assumptions.")

product_names = [p["product_name"] for p in PRODUCT_FACTORY_BASELINE]
states = sorted(STATE_CENTROIDS.keys())

with st.sidebar:
    st.subheader("Configurable financial assumptions")
    cost_mult = st.slider("Alt-factory cost multiplier", 0.8, 1.5,
                           FINANCIAL_ASSUMPTIONS["alt_factory_cost_multiplier"]["value"], 0.05)
    ship_rate = st.slider("Shipping $ per mile per unit", 0.0, 0.05,
                           FINANCIAL_ASSUMPTIONS["shipping_cost_per_mile_per_unit"]["value"], 0.001)
    st.caption("These override the default ANALYST ASSUMPTION values for this session only.")

products_selected = st.multiselect("Products to compare", product_names, default=product_names[:3])
state = st.selectbox("Destination State", states, index=states.index("Texas") if "Texas" in states else 0)
region = st.selectbox("Destination Region", ["Interior", "East", "West", "Central", "South"])
ship_mode = st.selectbox("Ship Mode", ["Standard Class", "Second Class", "First Class", "Same Day"])

if "saved_scenarios" not in st.session_state:
    st.session_state.saved_scenarios = []

if st.button("Compare", type="primary") and products_selected:
    all_rows = []
    for product in products_selected:
        result = simulate_product_scenario(product, state, region, ship_mode, units=3, sales=14.0, cost=5.0)
        for s in result["scenarios"]:
            all_rows.append({
                "Product": product,
                "Factory": s["factory_name"],
                "Is Current": s["is_current"],
                "Predicted Lead-Time Index": s["predicted_lead_time_index"],
                "Profit Impact ($)": s["profit"]["profit_impact"],
                "Risk Status": s["risk_status"],
                "Confidence": s["confidence"]["label"],
            })
    df = pd.DataFrame(all_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    fig = px.scatter(df, x="Predicted Lead-Time Index", y="Profit Impact ($)", color="Product",
                      symbol="Is Current", size_max=15,
                      title="Lead-time index vs. profit impact, by product/factory scenario")
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Save this comparison"):
        st.session_state.saved_scenarios.append(df)
        st.success("Saved to this session's scenario list below.")

if st.session_state.saved_scenarios:
    st.markdown("---")
    st.subheader("Saved scenarios (this session)")
    for i, saved in enumerate(st.session_state.saved_scenarios):
        st.markdown(f"**Scenario {i+1}**")
        st.dataframe(saved, use_container_width=True, hide_index=True)
