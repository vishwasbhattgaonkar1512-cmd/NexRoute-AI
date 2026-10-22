import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from src.config import PRODUCT_FACTORY_BASELINE, STATE_CENTROIDS
from src.scenario_simulator import simulate_product_scenario

st.set_page_config(page_title="Factory Optimization Simulator", layout="wide")
st.title("🔧 Factory Optimization Simulator")

product_names = [p["product_name"] for p in PRODUCT_FACTORY_BASELINE]
states = sorted(STATE_CENTROIDS.keys())

c1, c2, c3, c4 = st.columns(4)
product = c1.selectbox("Product", product_names)
state = c2.selectbox("Destination State", states, index=states.index("California") if "California" in states else 0)
region = c3.selectbox("Destination Region", ["Interior", "East", "West", "Central", "South"])
ship_mode = c4.selectbox("Ship Mode", ["Standard Class", "Second Class", "First Class", "Same Day"])

c5, c6, c7 = st.columns(3)
units = c5.number_input("Units", min_value=1, max_value=20, value=3)
sales = c6.number_input("Sales ($)", min_value=1.0, max_value=500.0, value=12.0)
cost = c7.number_input("Cost ($)", min_value=0.5, max_value=300.0, value=4.5)

if st.button("Run Simulation", type="primary"):
    result = simulate_product_scenario(product, state, region, ship_mode, units=units, sales=sales, cost=cost)

    st.subheader(f"Current factory: **{result['current_factory']}**")

    rows = []
    for s in result["scenarios"]:
        rows.append({
            "Factory": s["factory_name"] + (" (current)" if s["is_current"] else ""),
            "Compatibility": s["compatibility"],
            "Distance (mi, straight-line)": s["distance_miles"],
            "Predicted Lead-Time Index": s["predicted_lead_time_index"],
            "95% Interval": f"{s['prediction_interval_95'][0]} to {s['prediction_interval_95'][1]}",
            "Lead-Time Improvement": s["lead_time_improvement"],
            "Improvement %": s["lead_time_reduction_pct"],
            "Profit Impact ($)": s["profit"]["profit_impact"],
            "Confidence": s["confidence"]["label"],
            "Risk Status": s["risk_status"],
        })
    table = pd.DataFrame(rows)
    st.dataframe(table, use_container_width=True, hide_index=True)

    fig = px.bar(table, x="Factory", y="Predicted Lead-Time Index", color="Risk Status",
                 title="Predicted lead-time index by factory (lower = faster, relative index not days)")
    st.plotly_chart(fig, use_container_width=True)

    for s in result["scenarios"]:
        if not s["is_current"]:
            with st.expander(f"Why this confidence/risk level — {s['factory_name']}"):
                st.write(s["confidence"]["reason"])
                st.write(s["profit"]["note"])
                for a in s["profit"].get("assumptions_used", []):
                    st.caption(f"**{a['name']}** = {a['value']} — {a['source']}")
