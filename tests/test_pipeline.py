"""
End-to-end smoke/integration tests on the real dataset. Run: python -m pytest -v
(The original 8 tests, updated to the current API.)
"""
import pytest

from src.preprocessing import run_pipeline
from src.geographic_engine import haversine_miles, distance_factory_to_state
from src.compatibility import compatibility_matrix
from src.optimization_engine import run_optimization_for_all_products
from src.scenario_simulator import product_comparison
from src.config import PRODUCT_FACTORY_BASELINE


def test_preprocessing_runs_and_keeps_rows():
    df, logs = run_pipeline()
    assert len(df) > 9000  # should not silently drop most of the 10194 raw rows
    assert "lead_time_recovered_days" in df.columns
    assert any(l["severity"] == "critical" for l in logs)  # the date anomaly must be logged


def test_preprocessing_no_negative_raw_lead_time():
    df, _ = run_pipeline()
    assert (df["lead_time_days_raw"] >= 0).all()


def test_haversine_known_distance():
    # Chicago to NYC, approx 712 miles great-circle
    d = haversine_miles(41.8781, -87.6298, 40.7128, -74.0060)
    assert 700 < d < 730


def test_distance_factory_to_state_returns_number():
    d = distance_factory_to_state("Sugar Shack", "Minnesota")
    assert d > 0


def test_compatibility_always_includes_current():
    m = compatibility_matrix("demonstrated_division")
    g = m[m["product_name"] == "Laffy Taffy"]
    assert len(g) == 5
    cur = g[g["is_current"]]
    assert cur["factory_name"].item() == "Sugar Shack" and cur["compatible"].item()


def test_product_comparison_has_five_factories_with_risk():
    result = product_comparison("Wonka Gum")
    assert len(result) == 5
    assert set(result["risk_level"]) <= {"Low", "Medium", "High"}
    assert result["profit_impact"].notna().all()


def test_optimization_covers_all_15_products():
    recs = run_optimization_for_all_products()
    assert len(recs) == 15
    assert {p["product_name"] for p in PRODUCT_FACTORY_BASELINE} == {r["product_name"] for r in recs}


def test_optimization_decision_is_valid_enum():
    for r in run_optimization_for_all_products():
        assert r["decision"] in ("KEEP_CURRENT_FACTORY", "REALLOCATE")
        if r["decision"] == "KEEP_CURRENT_FACTORY":
            assert r["recommended_factory"] == r["current_factory"]
