import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.config import FACTORIES, STATE_CENTROIDS, PRODUCT_FACTORY_BASELINE

st.set_page_config(page_title="Factory & Shipping Map", layout="wide")
st.title("🗺️ Factory & Shipping Map")
st.caption("Straight-line (Haversine) distances shown — NOT actual road routes or delivery paths.")

fig = go.Figure()

fig.add_trace(go.Scattergeo(
    lon=[f["longitude"] for f in FACTORIES],
    lat=[f["latitude"] for f in FACTORIES],
    text=[f["factory_name"] for f in FACTORIES],
    mode="markers+text",
    marker=dict(size=14, color="red", symbol="square"),
    textposition="top center",
    name="Factories",
))

state_lons = [v[1] for v in STATE_CENTROIDS.values()]
state_lats = [v[0] for v in STATE_CENTROIDS.values()]
state_names = list(STATE_CENTROIDS.keys())
fig.add_trace(go.Scattergeo(
    lon=state_lons, lat=state_lats, text=state_names,
    mode="markers", marker=dict(size=4, color="steelblue", opacity=0.5),
    name="State centroids (customer approximation)",
))

fig.update_layout(
    geo=dict(scope="usa", projection_type="albers usa"),
    height=650,
    title="Five Nassau Candy factories and approximate customer state centroids",
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Current product → factory assignments")
mapping_df = pd.DataFrame(PRODUCT_FACTORY_BASELINE)
st.dataframe(mapping_df, use_container_width=True, hide_index=True)
