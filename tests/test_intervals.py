"""Regression tests for whole-day prediction ranges (bug: 'nominal 90%' range covered only 59% on test)."""
import json

import numpy as np
import pandas as pd
import pytest

from src.config import PROJECT_ROOT
from src.prediction_engine import (
    ACTIVE_POINTER, whole_day_bounds, interval_bounds, interval_coverage, load_active_model, predict_lead_time,
)


def test_near_integer_edges_snap_to_whole_days():
    lo, hi = whole_day_bounds([0.011, 4.001, 0.97], [1.011, 7.001, 2.97])
    assert list(lo) == [0, 4, 1] and list(hi) == [1, 7, 3]


def test_other_edges_round_outward_and_never_negative():
    lo, hi = whole_day_bounds([0.4, -0.6], [2.6, 0.2])
    assert list(lo) == [0, 0] and list(hi) == [3, 1]


def test_same_day_zero_lead_time_is_inside_range():
    """The original bug: Same Day range started at 0.011 days, excluding 0-day shipments."""
    rows = pd.DataFrame([{"Ship Mode": "Same Day", "Region": "Gulf", "Division": "Chocolate",
                          "current_factory": "Wicked Choccy's", "distance_miles": 500, "Units": 2, "Sales": 7,
                          "order_month": 5, "order_dow_rebuilt": 1}])
    p = predict_lead_time(rows).iloc[0]
    assert p["interval_low"] == 0 and p["interval_high"] >= 1
    assert float(p["interval_low"]).is_integer() and float(p["interval_high"]).is_integer()


def test_measured_coverage_matches_manual_count():
    _, meta = load_active_model()
    ptr = json.loads(ACTIVE_POINTER.read_text())
    tp = pd.read_csv(PROJECT_ROOT / ptr["eval_dir"] / "test_predictions.csv")
    cov = interval_coverage(tp, meta)
    lo, hi = interval_bounds(tp["predicted"].to_numpy(), tp["ship_mode"], meta)
    manual = np.mean((tp["actual"] >= lo) & (tp["actual"] <= hi))
    assert cov["overall"] == pytest.approx(manual) and cov["n"] == len(tp)
    assert cov["by_ship_mode"]["Same Day"] > 0.9   # was 0.061 before the fix
    assert cov["overall"] > 0.9                     # was 0.593 before the fix


def test_coverage_of_empty_frame_is_nan():
    _, meta = load_active_model()
    out = interval_coverage(pd.DataFrame(columns=["ship_mode", "actual", "predicted"]), meta)
    assert out["n"] == 0 and np.isnan(out["overall"])
