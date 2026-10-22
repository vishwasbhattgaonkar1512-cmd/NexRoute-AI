import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import json
from database.connection import get_session
from database.models import Order, OrderItem, Product, Customer
from src.optimization_engine import run_optimization_for_all_products
from src.config import MODELS_EVAL_DIR, PROCESSED_DIR

st.set_page_config(page_title="Data & Report Exports", layout="wide")
st.title("📦 Data & Report Exports")

session = get_session()
q = (session.query(Order.order_id, Order.order_date, Order.ship_date, Order.ship_mode,
                    Customer.region, Customer.state_province, Product.division, Product.product_name,
                    OrderItem.sales, OrderItem.units, OrderItem.gross_profit, OrderItem.cost,
                    OrderItem.lead_time_days_raw, OrderItem.lead_time_index, OrderItem.distance_miles)
     .join(OrderItem, OrderItem.order_id == Order.order_id)
     .join(Product, Product.product_id == OrderItem.product_id)
     .join(Customer, Customer.customer_id == Order.customer_id))
cleaned_df = pd.DataFrame(q.all(), columns=["order_id", "order_date", "ship_date", "ship_mode", "region",
                                             "state", "division", "product_name", "sales", "units",
                                             "gross_profit", "cost", "lead_time_days_raw", "lead_time_index",
                                             "distance_miles"])
session.close()

st.subheader("Cleaned dataset")
st.download_button("Download cleaned dataset (CSV)", cleaned_df.to_csv(index=False),
                    file_name="nassau_cleaned_dataset.csv", mime="text/csv")

st.subheader("Model evaluation results")
with open(MODELS_EVAL_DIR / "model_comparison.json") as f:
    model_eval = f.read()
st.download_button("Download model evaluation (JSON)", model_eval, file_name="model_evaluation.json")

st.subheader("Recommendation report")
recs = run_optimization_for_all_products()
rec_df = pd.DataFrame([{k: v for k, v in r.items() if k != "all_scenarios"} for r in recs])
st.download_button("Download recommendation report (CSV)", rec_df.to_csv(index=False),
                    file_name="recommendation_report.csv", mime="text/csv")

st.subheader("KPI summary")
kpi = {
    "total_orders": int(cleaned_df["order_id"].nunique()),
    "total_sales": float(cleaned_df["sales"].sum()),
    "total_gross_profit": float(cleaned_df["gross_profit"].sum()),
    "avg_raw_lead_time_days": float(cleaned_df["lead_time_days_raw"].mean()),
    "reallocation_count": int((rec_df["decision"] == "REALLOCATE").sum()),
    "high_risk_recommendations": int(rec_df["risk_level"].str.contains("high_risk").sum()),
}
st.json(kpi)
st.download_button("Download KPI summary (JSON)", json.dumps(kpi, indent=2), file_name="kpi_summary.json")
