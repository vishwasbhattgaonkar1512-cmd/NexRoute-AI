"""Prediction pipeline, optimization constraints, scenarios, recommendations."""
import numpy as np
import pandas as pd
import pytest

from src.assumptions import load_assumptions
from src.compatibility import compatibility
from src.model_components import GroupMeanRegressor
from src.optimization_engine import build_context, evaluate_candidates, recommend, solve_allocation, score_candidates
from src.prediction_engine import (
    chronological_split, select_model, prepare_training_frame, predict_lead_time, load_active_model, FEATURES,
    train_and_evaluate,
)
from src.preprocessing import run_pipeline
from src.scenario_simulator import simulate_scenarios, SCENARIOS


@pytest.fixture(scope="module")
def ctx():
    return build_context()


@pytest.fixture(scope="module")
def a():
    return load_assumptions(use_database=False)


# ---------------- prediction
def test_group_mean_regressor_and_fallback():
    X = pd.DataFrame({"Ship Mode": ["a", "a", "b"]})
    m = GroupMeanRegressor().fit(X, [1, 3, 10])
    assert list(m.predict(pd.DataFrame({"Ship Mode": ["a", "b", "zzz"]}))) == [2, 10, pytest.approx(14 / 3)]


def test_select_model_uses_parsimony():
    val = {"baseline_ship_mode_mean": {"mae": 0.828}, "linear_regression": {"mae": 0.825},
           "gradient_boosting": {"mae": 0.70}}
    assert select_model(val) == "gradient_boosting"
    val["gradient_boosting"]["mae"] = 0.83
    assert select_model(val) == "baseline_ship_mode_mean"  # within 1% -> simpler model


def test_chronological_split_has_no_time_overlap():
    df, _ = run_pipeline()
    tr, va, te = chronological_split(prepare_training_frame(df))
    assert tr["order_seq"].max() <= va["order_seq"].min() and va["order_seq"].max() <= te["order_seq"].min()
    assert len(tr) + len(va) + len(te) == len(prepare_training_frame(df))


def test_training_rejects_too_few_rows_or_missing_columns():
    df, _ = run_pipeline()
    with pytest.raises(ValueError, match="at least 50"):
        prepare_training_frame(df.head(10))
    with pytest.raises(ValueError, match="missing"):
        prepare_training_frame(df.drop(columns=["Ship Mode"]))


def test_disguised_date_features_not_used():
    assert "order_year" not in FEATURES and "order_dow" not in FEATURES


def test_training_is_honest_and_selection_ignores_test():
    df, _ = run_pipeline()
    out = train_and_evaluate(df, save=False, cv_splits=3, verbose=False)
    meta = out["meta"]
    val = {k: v["validation"] for k, v in meta["results"].items()}
    assert meta["selected_model"] == select_model(val)
    # the ship-mode baseline must clearly beat the global mean
    assert meta["results"]["baseline_ship_mode_mean"]["validation"]["mae"] < meta["results"]["baseline_mean"]["validation"]["mae"]
    assert 0 <= meta["final_test"]["mae"] < 2


def test_active_model_predicts_with_intervals():
    _, meta = load_active_model()
    rows = pd.DataFrame([{"Ship Mode": m, "Region": "Gulf", "Division": "Sugar", "current_factory": "Sugar Shack",
                          "distance_miles": 900, "Units": 3, "Sales": 10, "order_month": 6, "order_dow_rebuilt": 2}
                         for m in ["Same Day", "Standard Class"]])
    p = predict_lead_time(rows)
    assert (p["interval_low"] <= p["predicted_lead_days"]).all() and (p["predicted_lead_days"] <= p["interval_high"]).all()
    assert p["predicted_lead_days"].iloc[0] < p["predicted_lead_days"].iloc[1]
    with pytest.raises(ValueError):
        predict_lead_time(rows.drop(columns=["Ship Mode"]))


# ---------------- optimization
def test_candidates_cover_all_pairs(ctx, a):
    ev = evaluate_candidates(a, ctx)
    assert len(ev) == 75 and ev.groupby("product_name")["is_current"].sum().eq(1).all()
    assert (ev.loc[ev["is_current"], "profit_impact"] == 0).all()


def test_recommended_factories_are_always_compatible(ctx):
    for rule in ("demonstrated_division", "any_factory", "baseline_only"):
        a = load_assumptions({"compatibility_rule": rule}, use_database=False)
        for r in recommend(a, ctx=ctx)["recommendations"]:
            assert compatibility(r["product_name"], r["recommended_factory"], rule)[0]
        if rule == "baseline_only":
            assert all(r["decision"] == "KEEP_CURRENT_FACTORY" for r in recommend(a, ctx=ctx)["recommendations"])


def test_all_15_products_get_a_valid_decision(ctx, a):
    out = recommend(a, ctx=ctx)
    assert out["run"]["solver_status"] == "optimal" and len(out["recommendations"]) == 15
    for r in out["recommendations"]:
        assert r["decision"] in ("KEEP_CURRENT_FACTORY", "REALLOCATE") and r["recommendation_reason"]


def test_huge_penalty_keeps_everything(ctx):
    a = load_assumptions({"reassignment_penalty_points": 1e6}, use_database=False)
    assert all(r["decision"] == "KEEP_CURRENT_FACTORY" for r in recommend(a, ctx=ctx)["recommendations"])


def test_profit_threshold_blocks_low_value_moves(ctx):
    a = load_assumptions({"minimum_profit_threshold": 1e9}, use_database=False)
    assert all(r["decision"] == "KEEP_CURRENT_FACTORY" for r in recommend(a, ctx=ctx)["recommendations"])


def test_capacity_constraint_respected(ctx):
    a = load_assumptions({"factory_capacity_headroom_pct": 0}, use_database=False)
    sim = simulate_scenarios(a, ctx=ctx, scenarios=["cost"])
    d = sim["details"]
    load = d.groupby("proposed_factory")["units"].sum()
    for f, cap in sim["capacities"].items():
        assert load.get(f, 0) <= cap + 1e-6


def test_infeasible_capacity_reported_not_crashing(ctx, a):
    ev = evaluate_candidates(a, ctx)
    sol = solve_allocation(ev, score_candidates(ev, {"profit_weight": 1, "speed_weight": 0, "risk_weight": 0}, a),
                           ev["compatible"], capacities={f: 0 for f in ev["factory_name"].unique()})
    assert sol["status"] == "infeasible" and "capacity" in sol["message"].lower()
    rec = recommend(a, ctx=ctx, capacities={f: 0 for f in ev["factory_name"].unique()})
    assert all(r["decision"] == "INFEASIBLE" for r in rec["recommendations"])


def test_no_allowed_factory_is_infeasible(ctx, a):
    ev = evaluate_candidates(a, ctx)
    sol = solve_allocation(ev, pd.Series(np.zeros(len(ev))), pd.Series(False, index=ev.index))
    assert sol["status"] == "infeasible"


# ---------------- scenarios
def test_five_scenarios_with_required_fields(ctx, a):
    sim = simulate_scenarios(a, ctx=ctx)
    assert set(sim["summary"]["scenario"]) == set(SCENARIOS) and len(SCENARIOS) >= 5
    d = sim["details"]
    for col in ("scenario_name", "product_name", "current_factory", "proposed_factory", "cost_impact",
                "lead_time_impact_days", "risk_level", "confidence", "explanation"):
        assert col in d.columns and d[col].notna().all()
    cur = d[d["scenario"] == "current"]
    assert (cur["profit_impact"] == 0).all() and cur["is_current"].all()


def test_distance_scenario_picks_nearest_compatible(ctx, a):
    sim = simulate_scenarios(a, ctx=ctx, scenarios=["distance"])
    ev = sim["candidates"]
    for _, r in sim["details"].iterrows():
        opts = ev[(ev["product_name"] == r["product_name"]) & ev["compatible"]]
        assert r["weighted_distance_miles"] == pytest.approx(opts["weighted_distance_miles"].min())


def test_cost_scenario_never_loses_money_vs_current(ctx, a):
    s = simulate_scenarios(a, ctx=ctx, scenarios=["cost"])["summary"].iloc[0]
    assert s["estimated_profit_impact"] >= 0


def test_unknown_scenario_rejected(ctx, a):
    with pytest.raises(ValueError):
        simulate_scenarios(a, ctx=ctx, scenarios=["fantasy"])
