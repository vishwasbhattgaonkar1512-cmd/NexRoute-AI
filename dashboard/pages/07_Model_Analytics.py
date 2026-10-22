import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import json
import plotly.express as px
from src.config import MODELS_EVAL_DIR, REPORTS_DIR

st.set_page_config(page_title="Model Performance & Analytics", layout="wide")
st.title("📈 Model Performance & Analytics")

with open(MODELS_EVAL_DIR / "model_comparison.json") as f:
    comparison = json.load(f)

st.subheader("Model comparison (held-out, chronological split)")
comp_df = pd.DataFrame(comparison["results"]).T.reset_index().rename(columns={"index": "model"})
st.dataframe(comp_df, use_container_width=True, hide_index=True)
st.info(f"Best model selected: **{comparison['best_model']}** (highest held-out test R²). "
        f"Residual std used for confidence intervals: **{comparison['residual_std']:.1f}**")

st.warning(
    "Held-out R² is near zero (0.01–0.04) across all three models. This is an honest result, not a bug: "
    "it reflects that the underlying lead-time field is a corrupted/synthetic signal (see "
    "DEVELOPMENT_PROGRESS.md). Distance, division, region and ship mode carry very little genuine "
    "predictive signal for it. All downstream predictions are labeled 'low confidence' accordingly."
)

fig = px.bar(comp_df, x="model", y=["test_mae", "test_rmse"], barmode="group", title="Test MAE / RMSE by model")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Actual vs. Predicted (best model, test set)")
diag = pd.read_csv(MODELS_EVAL_DIR / "test_predictions.csv")
st.plotly_chart(px.scatter(diag, x="actual", y="predicted", title="Actual vs. Predicted lead-time index",
                            trendline="ols"), use_container_width=True)

st.subheader("Residual distribution")
st.plotly_chart(px.histogram(diag, x="residual", nbins=50, title="Residuals (actual - predicted)"),
                use_container_width=True)

fi_path = MODELS_EVAL_DIR / "feature_importance.csv"
if fi_path.exists():
    st.markdown("---")
    st.subheader("Feature importance (best tree-based model)")
    fi = pd.read_csv(fi_path)
    st.plotly_chart(px.bar(fi.head(15), x="importance", y="feature", orientation="h"), use_container_width=True)

st.markdown("---")
st.subheader("Route clustering (performance-similarity groups, not proof of congestion)")
cluster_path = REPORTS_DIR / "eda" / "route_clusters.csv"
if cluster_path.exists():
    clusters = pd.read_csv(cluster_path)
    summary = clusters.groupby("cluster").agg(
        n_routes=("cluster", "count"),
        mean_lead_time_index=("mean_lead_time_index", "mean"),
        mean_distance=("mean_distance", "mean"),
        potential_congestion_indicator=("potential_congestion_indicator", "any"),
    ).reset_index()
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.plotly_chart(px.scatter(clusters, x="mean_distance", y="mean_lead_time_index", color="cluster_label",
                                hover_data=["Product Name", "Region", "current_factory"],
                                title="Route clusters: distance vs. lead-time index"),
                    use_container_width=True)
else:
    st.info("Run `python -m src.clustering_engine` to generate route clustering results.")
