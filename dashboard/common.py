"""Shared helpers for all dashboard pages: setup, caching, warnings, chart styling, formatting."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import FACTORIES, DB_PATH

APP_NAME = "NexRoute AI"

# Fixed categorical order (validated reference palette); colour follows the factory everywhere.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
FACTORY_COLORS = {f["factory_name"]: SERIES[i] for i, f in enumerate(FACTORIES)}
# Status colours are reserved for risk and always shown with a text label.
RISK_COLORS = {"Low": "#0ca30c", "Medium": "#fab219", "High": "#d03b3b", "Unknown": "#898781"}
MUTED, GRID = "#898781", "rgba(137,135,129,0.25)"

LEAD_TIME_NOTE = ("Lead times are **derived**, not measured: the source dates are disguised, and lead time was "
                  "recovered with a stated rule (see Data Management → Date forensics). Transit time for a "
                  "different factory is an **assumption** — the data shows no measurable distance effect.")
ESTIMATE_NOTE = ("Costs, profit impacts and savings are **estimates** under editable analyst assumptions "
                 "(freight rate, factory cost, transit time). They are not realised savings.")


def setup_page(title: str, icon: str, subtitle: str | None = None):
    st.set_page_config(page_title=f"{title} · {APP_NAME}", page_icon=icon, layout="wide")
    st.markdown("""
        <style>
          .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px;}
          div[data-testid="stMetric"] {border: 1px solid rgba(137,135,129,0.25); border-radius: 8px;
                                       padding: 0.75rem 1rem;}
          div[data-testid="stMetricLabel"] p {font-size: 0.85rem;}
          h1 {font-size: 1.9rem !important;}
        </style>""", unsafe_allow_html=True)
    st.title(f"{icon} {title}")
    if subtitle:
        st.caption(subtitle)
    with st.sidebar:
        st.markdown(f"**{APP_NAME}** · decision-support prototype")
        st.caption("All lead times are derived; all financial figures are estimates.")


def require_database():
    if not DB_PATH.exists():
        st.error("Database not found. Run `python -m src.build_database` from the project folder.")
        st.stop()


def guard(fn, *args, what="this view", **kwargs):
    """Run fn; on failure show an actionable error instead of a stack trace."""
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as exc:
        st.error(f"Could not load {what}: {exc}")
    except Exception as exc:  # noqa: BLE001 - dashboard must not crash
        st.error(f"Could not compute {what}: {type(exc).__name__}: {exc}")
    st.stop()


def lead_time_warning():
    st.warning(LEAD_TIME_NOTE, icon="⚠️")


def estimate_note():
    st.info(ESTIMATE_NOTE, icon="ℹ️")


# ----------------------------------------------------------------------------------------- data
@st.cache_data(show_spinner=False)
def load_pipeline():
    from src.preprocessing import run_pipeline
    return run_pipeline()


@st.cache_resource(show_spinner="Loading model and historical demand…")
def load_context():
    from src.optimization_engine import build_context
    df, _ = load_pipeline()
    return build_context(df)


def assumptions_key(a) -> str:
    return json.dumps(a.to_dict(), sort_keys=True)


@st.cache_data(show_spinner="Evaluating every product–factory option…")
def _evaluate(key: str):
    from src.assumptions import load_assumptions
    from src.optimization_engine import evaluate_candidates
    return evaluate_candidates(load_assumptions(json.loads(key), use_database=False), load_context())


def evaluate(a):
    return _evaluate(assumptions_key(a))


@st.cache_data(show_spinner="Running scenarios…")
def _scenarios(key: str, weights_key: str):
    from src.assumptions import load_assumptions
    from src.scenario_simulator import simulate_scenarios
    a = load_assumptions(json.loads(key), use_database=False)
    sim = simulate_scenarios(a, json.loads(weights_key), load_context())
    sim["assumptions_dict"] = a.to_dict()
    return sim


def scenarios(a, weights):
    return _scenarios(assumptions_key(a), json.dumps(weights, sort_keys=True))


@st.cache_data(show_spinner="Optimizing allocation…")
def _recommend(key: str, weights_key: str):
    from src.assumptions import load_assumptions
    from src.optimization_engine import recommend
    return recommend(load_assumptions(json.loads(key), use_database=False), json.loads(weights_key), load_context())


def recommend_cached(a, weights):
    return _recommend(assumptions_key(a), json.dumps(weights, sort_keys=True))


def current_assumptions():
    from src.assumptions import load_assumptions
    return load_assumptions()


def current_weights():
    from src.assumptions import load_weights
    return load_weights()


def clear_caches():
    st.cache_data.clear()


# ----------------------------------------------------------------------------------------- charts
def style(fig: go.Figure, height: int = 380, title: str | None = None, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, title=dict(text=title, x=0, xanchor="left", font=dict(size=15)) if title else None,
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', size=12),
        bargap=0.35, showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title=None),
        hoverlabel=dict(font_size=12),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, zeroline=True, zerolinecolor=GRID, zerolinewidth=1)
    fig.update_traces(selector=dict(type="bar"), marker_line_width=0)
    return fig


def show(fig, table: pd.DataFrame | None = None, table_label="Table view"):
    st.plotly_chart(fig, width="stretch", theme="streamlit")
    if table is not None:
        with st.expander(table_label):
            st.dataframe(table, width="stretch", hide_index=True)


# ----------------------------------------------------------------------------------------- format
def usd(v, signed=False) -> str:
    if v is None or pd.isna(v):
        return "—"
    s = f"${abs(v):,.0f}" if abs(v) >= 100 else f"${abs(v):,.2f}"
    if signed:
        return ("+" if v >= 0 else "−") + s
    return ("−" if v < 0 else "") + s


def risk_badge(level: str) -> str:
    icon = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(level, "⚪")
    return f"{icon} {level}"


DECISION_LABELS = {"REALLOCATE": "Reallocate", "KEEP_CURRENT_FACTORY": "Keep current",
                   "INFEASIBLE": "Infeasible", "NO_DATA": "No data"}


@st.cache_data(show_spinner=False)
def measured_interval_coverage():
    """Measured coverage of the whole-day prediction range on the active model's saved test set."""
    from src.config import PROJECT_ROOT
    from src.prediction_engine import ACTIVE_POINTER, load_active_model, interval_coverage
    ptr = json.loads(ACTIVE_POINTER.read_text())
    _, meta = load_active_model()
    path = PROJECT_ROOT / ptr["eval_dir"] / "test_predictions.csv"
    if not path.exists():
        return None
    return interval_coverage(pd.read_csv(path), meta)
