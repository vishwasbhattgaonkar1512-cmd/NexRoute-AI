import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from database.connection import get_session
from database.models import Order, OrderItem, Product, Customer, DataQualityLog

st.set_page_config(page_title="Executive Dashboard", layout="wide")
st.title("📊 Executive Dashboard")

session = get_session()

q = (session.query(Order.order_id, Order.ship_mode, Customer.region, Customer.state_province,
                    Product.division, Product.product_name,
                    OrderItem.sales, OrderItem.units, OrderItem.gross_profit, OrderItem.cost,
                    OrderItem.lead_time_days_raw, OrderItem.lead_time_index)
     .join(OrderItem, OrderItem.order_id == Order.order_id)
     .join(Product, Product.product_id == OrderItem.product_id)
     .join(Customer, Customer.customer_id == Order.customer_id))
df = pd.DataFrame(q.all(), columns=["order_id", "ship_mode", "region", "state", "division", "product_name",
                                     "sales", "units", "gross_profit", "cost", "lead_time_raw", "lead_time_index"])

dq_logs = session.query(DataQualityLog).all()
session.close()

# --- KPI row ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Orders", f"{df['order_id'].nunique():,}")
c2.metric("Total Order Lines", f"{len(df):,}")
c3.metric("Total Sales", f"${df['sales'].sum():,.0f}")
c4.metric("Total Gross Profit", f"${df['gross_profit'].sum():,.0f}")
c5.metric("Products", df["product_name"].nunique())

st.markdown("---")

for log in dq_logs:
    if log.severity == "critical":
        st.error(f"**{log.issue_type}**: {log.issue_description}")

col1, col2 = st.columns(2)
with col1:
    raw_mean = df["lead_time_raw"].mean()
    st.metric("Average RAW lead time (days)", f"{raw_mean:,.0f}",
              help="Raw field — NOT validated as real delivery duration. See data-quality warning above.")
with col2:
    idx_mean = df["lead_time_index"].mean()
    st.metric("Average lead-time INDEX (de-trended)", f"{idx_mean:,.1f}",
              help="Relative index used by the ML model. Not calendar days.")

st.markdown("---")
st.subheader("Historical business performance (actual, from source data)")

c1, c2 = st.columns(2)
with c1:
    sales_by_region = df.groupby("region", as_index=False)["sales"].sum()
    st.plotly_chart(px.bar(sales_by_region, x="region", y="sales", title="Sales by Region"), use_container_width=True)
with c2:
    profit_by_div = df.groupby("division", as_index=False)["gross_profit"].sum()
    st.plotly_chart(px.bar(profit_by_div, x="division", y="gross_profit", title="Gross Profit by Division"), use_container_width=True)

c3, c4 = st.columns(2)
with c3:
    orders_by_mode = df["ship_mode"].value_counts().reset_index()
    orders_by_mode.columns = ["ship_mode", "count"]
    st.plotly_chart(px.pie(orders_by_mode, names="ship_mode", values="count", title="Orders by Ship Mode"), use_container_width=True)
with c4:
    product_perf = df.groupby("product_name", as_index=False)["sales"].sum().sort_values("sales", ascending=True)
    st.plotly_chart(px.bar(product_perf, x="sales", y="product_name", orientation="h", title="Sales by Product"), use_container_width=True)

st.markdown("---")
st.subheader("Raw lead-time distribution (flagged unreliable — shown for transparency only)")
st.plotly_chart(px.histogram(df, x="lead_time_raw", nbins=60,
                              title="Raw Ship Date − Order Date (days) — NOT a validated delivery-time signal"),
                use_container_width=True)
