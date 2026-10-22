"""Geography, compatibility, assumptions, profit, confidence/risk."""
import numpy as np
import pandas as pd
import pytest

from src.assumptions import Assumptions, load_assumptions, load_weights
from src.compatibility import compatibility, compatibility_matrix, factory_division_capability
from src.confidence_engine import assess, risk_level, confidence_label
from src.geographic_engine import (
    haversine_miles, distance_factory_to_state, distance_matrix, nearest_factory_by_destination, coverage_analysis,
)
from src.profit_engine import candidate_costs, compare, estimate_scenario_profit

A = load_assumptions(use_database=False)


# ---------------- geography
def test_haversine_zero_and_symmetric():
    assert haversine_miles(40, -90, 40, -90) == pytest.approx(0)
    assert haversine_miles(30, -80, 45, -120) == pytest.approx(haversine_miles(45, -120, 30, -80))


def test_unknown_factory_or_state_gives_nan():
    assert np.isnan(distance_factory_to_state("Nonexistent Factory", "Texas"))
    assert np.isnan(distance_factory_to_state("Sugar Shack", "Atlantis"))


def test_canadian_province_has_distance():
    assert 0 < distance_factory_to_state("Sugar Shack", "Ontario") < 2000


def test_distance_matrix_shape_and_nearest():
    m = distance_matrix(["Texas", "Georgia"])
    assert m.shape == (2, 5)
    near = nearest_factory_by_destination(["Georgia"]).iloc[0]
    assert near["nearest_factory"] == "Wicked Choccy's"  # factory is in Georgia
    assert near["nearest_miles"] <= near["second_miles"]


def test_coverage_is_monotonic_and_nearest_dominates():
    df = pd.DataFrame({"State/Province": ["Texas", "Georgia", "California"], "Units": [1, 2, 3],
                       "current_factory": ["Sugar Shack"] * 3})
    cov = coverage_analysis(df)
    assert cov["pct_units_nearest_factory"].is_monotonic_increasing
    assert (cov["pct_units_nearest_factory"] >= cov["pct_units_current_factory"]).all()


# ---------------- compatibility
def test_current_factory_always_compatible_under_every_rule():
    for rule in ("demonstrated_division", "any_factory", "baseline_only"):
        ok, basis = compatibility("Nerds", "Sugar Shack", rule)
        assert ok and "confirmed" in basis


def test_chocolate_not_allowed_at_sugar_factory():
    ok, basis = compatibility("Wonka Bar - Milk Chocolate", "Sugar Shack", "demonstrated_division")
    assert not ok and "not allowed" in basis


def test_baseline_only_blocks_all_alternatives():
    m = compatibility_matrix("baseline_only")
    assert (m["compatible"] == m["is_current"]).all()


def test_unknown_factory_and_product_incompatible():
    assert compatibility("Nerds", "Ghost Factory", "any_factory")[0] is False
    assert compatibility("Ghost Candy", "Sugar Shack", "any_factory")[0] is False
    with pytest.raises(ValueError):
        compatibility("Nerds", "Sugar Shack", "made_up_rule")


def test_division_capability_derived_from_baseline():
    cap = factory_division_capability()
    assert cap["Lot's O' Nuts"] == {"Chocolate"} and cap["Sugar Shack"] == {"Sugar"}


# ---------------- assumptions
@pytest.mark.parametrize("bad", [
    {"alt_factory_cost_multiplier": 0}, {"freight_cost_per_unit_mile": -1}, {"transit_days_per_1000_miles": -0.1},
    {"factory_capacity_headroom_pct": -5}, {"reassignment_penalty_points": -1}, {"compatibility_rule": "nope"},
    {"freight_cost_per_unit_mile": float("nan")},
])
def test_invalid_assumptions_rejected(bad):
    with pytest.raises(ValueError):
        load_assumptions(bad, use_database=False)


def test_unknown_assumption_rejected():
    with pytest.raises(ValueError, match="unknown"):
        load_assumptions({"magic": 1}, use_database=False)


def test_override_precedence_and_provenance():
    a = load_assumptions({"freight_cost_per_unit_mile": 0.002}, use_database=False)
    assert a.freight_cost_per_unit_mile == 0.002 and a.provenance["freight_cost_per_unit_mile"].startswith("override")
    assert a.provenance["transit_days_per_1000_miles"] == "config default"


def test_weights_validation():
    with pytest.raises(ValueError):
        load_weights(overrides={"risk_weight": -1}, use_database=False)
    with pytest.raises(ValueError):
        load_weights(overrides={"profit_weight": 0, "speed_weight": 0, "risk_weight": 0}, use_database=False)
    with pytest.raises(ValueError):
        load_weights(preset="nonexistent")


# ---------------- profit
def profile(state="Texas", units=10, revenue=40.0, cost=10.0):
    return pd.DataFrame([{"State/Province": state, "lines": 2, "units": units, "revenue": revenue, "cost": cost}])


def test_current_vs_itself_is_zero_impact():
    p = profile()
    c = candidate_costs(p, "Sugar Shack", True, A)
    assert compare(c, c)["profit_impact"] == 0


def test_cost_model_is_symmetric_freight_charged_to_current_too():
    p = profile()
    cur = candidate_costs(p, "Sugar Shack", True, A)
    assert cur["freight_cost"] > 0
    expected = 10 * distance_factory_to_state("Sugar Shack", "Texas") * A.freight_cost_per_unit_mile
    assert cur["freight_cost"] == pytest.approx(expected)


def test_closer_factory_with_equal_cost_has_positive_impact():
    p = profile(state="Georgia")
    cur = candidate_costs(p, "Lot's O' Nuts", True, A)          # Arizona
    alt = candidate_costs(p, "Wicked Choccy's", False, A)       # Georgia
    assert compare(cur, alt)["profit_impact"] > 0


def test_cost_multiplier_applies_only_to_alternatives():
    a = load_assumptions({"alt_factory_cost_multiplier": 1.5, "freight_cost_per_unit_mile": 0}, use_database=False)
    p = profile()
    cur, alt = candidate_costs(p, "Sugar Shack", True, a), candidate_costs(p, "Secret Factory", False, a)
    assert alt["production_cost"] == pytest.approx(15) and cur["production_cost"] == pytest.approx(10)
    assert compare(cur, alt)["profit_impact"] == pytest.approx(-5)


def test_unknown_destination_freight_excluded_and_reported():
    c = candidate_costs(profile(state="Atlantis"), "Sugar Shack", True, A)
    assert c["freight_cost"] == 0 and c["units_without_distance"] == 10 and np.isnan(c["weighted_distance_miles"])
    out = estimate_scenario_profit(10, 3, 2, "Sugar Shack", "Secret Factory", "Atlantis", A)
    assert out["classification"] == "insufficient_financial_data"


def test_negative_inputs_rejected():
    with pytest.raises(ValueError):
        candidate_costs(profile(units=-1), "Sugar Shack", True, A)
    with pytest.raises(ValueError):
        estimate_scenario_profit(-1, 3, 2, "Sugar Shack", "Secret Factory", "Texas", A)
    with pytest.raises(ValueError):
        candidate_costs(profile().iloc[0:0], "Sugar Shack", True, A)


# ---------------- confidence / risk
def _assess(**kw):
    base = dict(is_current=False, compatible=True, compatibility_basis="ASSUMED: x", val_mae=0.8, mean_target=4.0,
                flagged_share=0.1, product_lines=1000, moved_units=100, receiving_current_units=1000,
                capacity_enabled=False)
    base.update(kw)
    return assess(**base)


def test_risk_scores_bounded_and_labelled():
    r = _assess()
    for k in ("model_uncertainty", "data_quality_risk", "missing_info_risk", "compatibility_risk",
              "operational_risk", "overall_risk"):
        assert 0 <= r[k] <= 1
    assert r["risk_level"] in ("Low", "Medium", "High") and "not probabilities" in r["score_note"]


def test_current_factory_less_risky_than_alternative():
    assert _assess(is_current=True)["overall_risk"] < _assess()["overall_risk"]


def test_sparse_history_increases_data_risk():
    assert _assess(product_lines=5)["data_quality_risk"] > _assess()["data_quality_risk"]


def test_missing_model_metrics_mean_max_uncertainty():
    assert _assess(mean_target=0)["model_uncertainty"] == 1.0


def test_risk_level_thresholds():
    assert risk_level(0.1) == "Low" and risk_level(0.5) == "Medium" and risk_level(0.9) == "High"
    assert risk_level(float("nan")) == "Unknown" and confidence_label(0.1) == "High"
