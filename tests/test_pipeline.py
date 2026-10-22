"""
Phase 9: smoke/integration tests. Run: python -m pytest tests/ -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.preprocessing import run_pipeline
from src.geographic_engine import haversine_miles, distance_factory_to_state
from src.scenario_simulator import simulate_product_scenario, eligible_factories
from src.optimization_engine import recommend_for_product, run_optimization_for_all_products
from src.config import PRODUCT_FACTORY_BASELINE


def test_preprocessing_runs_and_keeps_rows():
    df, logs = run_pipeline()
    assert len(df) > 9000  # should not silently drop most of the 10194 raw rows
    assert "lead_time_index" in df.columns
    assert any(l["severity"] == "critical" for l in logs)  # the lead-time anomaly must be logged


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


def test_eligible_factories_always_includes_current():
    factories, current, division = eligible_factories("Laffy Taffy")
    assert current == "Sugar Shack"
    assert any(f["is_current"] for f in factories)
    assert len(factories) == 5


def test_scenario_simulator_produces_five_scenarios_with_confidence():
    result = simulate_product_scenario("Wonka Gum", "Tennessee", "South", "Standard Class")
    assert len(result["scenarios"]) == 5
    for s in result["scenarios"]:
        assert s["confidence"]["label"] in ("unsupported", "low", "moderate", "high")
        assert "profit_impact" in s["profit"] or s["profit"]["classification"] == "insufficient_financial_data"


def test_optimization_covers_all_15_products():
    recs = run_optimization_for_all_products()
    assert len(recs) == 15
    product_names = {p["product_name"] for p in PRODUCT_FACTORY_BASELINE}
    rec_names = {r["product_name"] for r in recs}
    assert product_names == rec_names


def test_optimization_decision_is_valid_enum():
    recs = run_optimization_for_all_products()
    for r in recs:
        assert r["decision"] in ("KEEP_CURRENT_FACTORY", "REALLOCATE")
        if r["decision"] == "KEEP_CURRENT_FACTORY":
            assert r["recommended_factory"] == r["current_factory"]


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python3", "-m", "pytest", __file__, "-v"])
