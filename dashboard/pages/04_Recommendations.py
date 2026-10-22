import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from src.optimization_engine import run_optimization_for_all_products
from src.config import PRODUCT_FACTORY_BASELINE

st.set_page_config(page_title="Recommendation Dashboard", layout="wide")
st.title("🎯 Recommendation Dashboard")

with st.sidebar:
    st.subheader("Optimization priority")
    mode = st.radio("Mode", ["Balanced", "Speed priority", "Profit priority"])
    weights = {
        "Balanced": {"speed_weight": 0.4, "profit_weight": 0.4, "risk_weight": 0.2},
        "Speed priority": {"speed_weight": 0.7, "profit_weight": 0.2, "risk_weight": 0.1},
        "Profit priority": {"speed_weight": 0.2, "profit_weight": 0.7, "risk_weight": 0.1},
    }[mode]

if "recs" not in st.session_state or st.session_state.get("_weights") != weights:
    with st.spinner("Running optimization across all 15 products..."):
        st.session_state.recs = run_optimization_for_all_products(weights=weights)
        st.session_state._weights = weights

recs = st.session_state.recs
df = pd.DataFrame([{k: v for k, v in r.items() if k != "all_scenarios"} for r in recs])

c1, c2, c3 = st.columns(3)
divisions = ["All"] + sorted(df["division"].unique().tolist())
div_filter = c1.selectbox("Division", divisions)
decision_filter = c2.selectbox("Decision", ["All", "REALLOCATE", "KEEP_CURRENT_FACTORY"])
risk_filter = c3.selectbox("Risk level", ["All"] + sorted(df["risk_level"].unique().tolist()))

filtered = df.copy()
if div_filter != "All":
    filtered = filtered[filtered["division"] == div_filter]
if decision_filter != "All":
    filtered = filtered[filtered["decision"] == decision_filter]
if risk_filter != "All":
    filtered = filtered[filtered["risk_level"] == risk_filter]

n_reallocate = (df["decision"] == "REALLOCATE").sum()
n_keep = (df["decision"] == "KEEP_CURRENT_FACTORY").sum()
c1, c2, c3 = st.columns(3)
c1.metric("Products evaluated", len(df))
c2.metric("Reallocation recommendations", n_reallocate)
c3.metric("Keep current", n_keep)

st.dataframe(
    filtered[["recommendation_rank", "product_name", "division", "current_factory", "decision",
              "recommended_factory", "predicted_lead_time_improvement", "estimated_profit_impact",
              "risk_level", "confidence"]],
    use_container_width=True, hide_index=True,
)

st.markdown("---")
st.subheader("Business rationale")
for _, row in filtered.iterrows():
    with st.expander(f"{row['product_name']} — {row['decision']}"):
        st.write(row["recommendation_reason"])
