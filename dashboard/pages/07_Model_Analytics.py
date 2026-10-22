import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import setup_page, require_database, guard, style, show, lead_time_warning  # noqa: E402

import json  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import PROJECT_ROOT, MODELS_EVAL_DIR  # noqa: E402
from src.prediction_engine import ACTIVE_POINTER, load_active_model  # noqa: E402
from src import persistence as P  # noqa: E402

setup_page("Model Analytics", "📈", "How well lead time can be predicted — evaluated honestly")
require_database()
lead_time_warning()

_, meta = guard(load_active_model, what="the active model")
ptr = json.loads(ACTIVE_POINTER.read_text())
eval_dir = PROJECT_ROOT / ptr["eval_dir"]
sel = meta["selected_model"]

k = st.columns(4)
k[0].metric("Active model", sel.replace("_", " "))
k[1].metric("Version", meta["model_version"])
k[2].metric("Final test MAE", f"{meta['final_test']['mae']:.3f} d")
k[3].metric("Final test R²", f"{meta['final_test']['r2']:.3f}")

st.success(
    f"**Finding:** a simple average per ship mode predicts the derived lead time as well as any ML model "
    f"(validation MAE {meta['results']['baseline_ship_mode_mean']['validation']['mae']:.3f} d vs "
    f"{meta['results'][meta['best_ml_model']]['validation']['mae']:.3f} d for the best ML model, "
    f"{meta['best_ml_model'].replace('_', ' ')}). Ship mode explains ~70% of the variance; distance, factory, "
    "region, product division, order size and season add nothing measurable. Per the selection rule the "
    "simpler model is used.", icon="✅")

st.subheader("Model comparison")
rows = []
for name, r in meta["results"].items():
    rows.append({"model": name, "cv MAE (train, time-ordered)": r["cv_mae_mean"], "cv MAE std": r["cv_mae_std"],
                 "train MAE": r["train"]["mae"], "validation MAE": r["validation"]["mae"],
                 "validation RMSE": r["validation"]["rmse"], "validation R²": r["validation"]["r2"],
                 "test MAE": r["test"]["mae"], "test RMSE": r["test"]["rmse"], "test R²": r["test"]["r2"],
                 "selected": name == sel})
comp = pd.DataFrame(rows)
st.dataframe(comp.round(3), hide_index=True, width="stretch")
st.caption(f"Selection rule: {meta['selection_rule']} — the test set was not used for selection. Test columns "
           f"for every candidate (trained on train only) are shown for transparency; the active model was then "
           f"refit on train+validation and scored once on test (MAE {meta['final_test']['mae']:.3f}, "
           f"RMSE {meta['final_test']['rmse']:.3f}, R² {meta['final_test']['r2']:.3f}).")

long = comp.melt(id_vars="model", value_vars=["validation MAE", "test MAE"], var_name="set", value_name="MAE")
fig = px.bar(long, x="model", y="MAE", color="set", barmode="group", color_discrete_sequence=["#2a78d6", "#eb6834"],
             labels={"model": "", "MAE": "MAE (days)", "set": ""})
show(style(fig, 340, "Validation vs test MAE (lower is better)"))

sp = meta["split"]
st.caption(f"Chronological split on the rebuilt order date — train {sp['train_rows']:,} rows "
           f"({sp['train_period'][0]} → {sp['train_period'][1]}), validation {sp['validation_rows']:,} "
           f"({sp['validation_period'][0]} → {sp['validation_period'][1]}), test {sp['test_rows']:,} "
           f"({sp['test_period'][0]} → {sp['test_period'][1]}).")

st.subheader("Feature importance (permutation, validation set)")
fi_path = eval_dir / "feature_importance.csv"
if fi_path.exists():
    fi = pd.read_csv(fi_path)
    model_pick = st.radio("Model", list(fi["model"].unique()), horizontal=True)
    f = fi[fi["model"] == model_pick].sort_values("importance_mae_increase")
    fig = px.bar(f, x="importance_mae_increase", y="feature", orientation="h", error_x="importance_std",
                 color_discrete_sequence=["#2a78d6"], labels={"importance_mae_increase": "MAE increase when shuffled (days)",
                                                              "feature": ""})
    show(style(fig, 360, None, legend=False), f)
else:
    st.info("No feature-importance file for this model version.")

st.subheader("Residual analysis (test set)")
tp = eval_dir / "test_predictions.csv"
if tp.exists():
    diag = pd.read_csv(tp)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(diag, x="residual", nbins=30, color_discrete_sequence=["#2a78d6"],
                           labels={"residual": "Actual − predicted (days)"})
        show(style(fig, 320, "Residual distribution", legend=False))
    with c2:
        by = diag.groupby("ship_mode").agg(n=("residual", "size"), mae=("residual", lambda r: r.abs().mean()),
                                           bias=("residual", "mean")).reset_index()
        fig = px.box(diag, x="ship_mode", y="residual", color_discrete_sequence=["#2a78d6"],
                     labels={"ship_mode": "", "residual": "Residual (days)"})
        show(style(fig, 320, "Residuals by ship mode", legend=False), by.round(3))
    st.caption("Residuals reflect the spread of lead time within each ship mode (e.g. Standard Class 3–7 days), "
               "which none of the available features explain.")

st.subheader("Prediction intervals")
iv = pd.DataFrame([{"ship mode": k_, "low": v[0], "high": v[1]} for k_, v in meta["residual_intervals"].items()])
st.dataframe(iv.round(2), hide_index=True)
st.caption("Empirical 5th–95th percentiles of validation residuals added to each prediction (90% range). "
           "They are not calibrated for alternative factories, which are extrapolations.")

st.subheader("Model registry & metadata")
reg = P.get_model_registry()
if not reg.empty:
    st.dataframe(reg[["model_version", "model_name", "is_active", "training_timestamp", "target", "val_mae", "mae",
                      "r2_score", "train_rows", "validation_rows", "test_rows", "data_sha256"]],
                 hide_index=True, width="stretch")
with st.expander("Full metadata (meta.json)"):
    st.json({k_: v for k_, v in meta.items() if k_ != "results"})
legacy = MODELS_EVAL_DIR / "model_comparison.json"
if legacy.exists():
    with st.expander("Legacy model (previous target, kept for reference)"):
        st.warning("The previous models predicted 'lead_time_index' (raw gap minus ship-mode median). That target "
                   "mostly encodes the date disguise — its top features were order_year and order weekday of the "
                   "disguised Order Date — and the best model was chosen on test R², which leaks. Not used.")
        st.json(json.loads(legacy.read_text()))
