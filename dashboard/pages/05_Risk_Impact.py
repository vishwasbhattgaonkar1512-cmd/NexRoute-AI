import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from database.connection import get_session
from database.models import DataQualityLog
from src.optimization_engine import run_optimization_for_all_products

st.set_page_config(page_title="Risk & Impact Panel", layout="wide")
st.title("⚠️ Risk & Impact Panel")

session = get_session()
logs = session.query(DataQualityLog).all()
session.close()

st.subheader("Data-quality warnings")
for log in sorted(logs, key=lambda l: {"critical": 0, "high": 1, "medium": 2, "low": 3}[l.severity]):
    icon = {"critical": "🛑", "high": "🔴", "medium": "🟠", "low": "🟡"}[log.severity]
    st.markdown(f"{icon} **[{log.severity.upper()}] {log.issue_type}** ({log.affected_records} records)")
    st.caption(log.issue_description)

st.markdown("---")
st.subheader("Recommendation-level risk summary")
recs = run_optimization_for_all_products()
df = pd.DataFrame([{k: v for k, v in r.items() if k != "all_scenarios"} for r in recs])

risk_counts = df["risk_level"].value_counts()
st.bar_chart(risk_counts)

low_conf = df[df["confidence"].isin(["low", "unsupported"])]
st.warning(f"{len(low_conf)} of {len(df)} product recommendations rely on low-confidence or unsupported "
           f"model predictions (near-zero held-out R², see Model Analytics page).")
st.dataframe(low_conf[["product_name", "decision", "risk_level", "confidence"]], use_container_width=True, hide_index=True)

negative_profit = df[df["estimated_profit_impact"] < 0]
if len(negative_profit):
    st.error(f"{len(negative_profit)} scenarios show negative estimated profit impact.")
    st.dataframe(negative_profit[["product_name", "recommended_factory", "estimated_profit_impact"]],
                 use_container_width=True, hide_index=True)
else:
    st.success("No active recommendations show negative profit impact (all REALLOCATE candidates below threshold were filtered).")
