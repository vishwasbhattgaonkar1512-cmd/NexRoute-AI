"""Database persistence on a TEMPORARY database (the project database is never touched)."""
import sqlite3

import pytest
from sqlalchemy import text

from database.migrations import upgrade_schema
from src import persistence as P
from src.build_database import build
from src.optimization_engine import build_context, recommend
from src.preprocessing import run_pipeline
from src.scenario_simulator import simulate_scenarios


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    from database.connection import get_engine
    eng = get_engine(tmp_path_factory.mktemp("db") / "nexroute_test.db")
    df, issues = run_pipeline()
    report = build(engine=eng, df=df, issues=issues, verbose=False)
    ctx = build_context(df)
    return eng, report, ctx


def test_build_populates_all_core_tables(built):
    eng, report, _ = built
    rows = report["table_rows"]
    assert rows["orders"] == 8549 and rows["order_items"] == 10194 and rows["products"] == 15
    assert rows["factories"] == 5 and rows["customers"] == 5044 and rows["model_registry"] == 1


def test_build_is_idempotent_and_keeps_old_dq_reports(built):
    eng, _, _ = built
    df, issues = run_pipeline()
    r2 = build(engine=eng, df=df, issues=issues, verbose=False)
    assert r2["inserted"] == {"customers": 0, "orders": 0, "order_items": 0}
    dq_all, dq_cur = P.get_data_quality(False, engine=eng), P.get_data_quality(True, engine=eng)
    assert len(dq_all) == 2 * len(issues) and len(dq_cur) == len(issues)
    assert P.get_model_registry(engine=eng)["is_active"].sum() == 1


def test_recommendation_run_saved_once(built):
    eng, _, ctx = built
    res = recommend(ctx=ctx)
    P.save_recommendation_run(res, engine=eng)
    P.save_recommendation_run(res, engine=eng)  # duplicate -> no-op
    recs = P.get_recommendations(engine=eng)
    assert len(recs) == 15 and set(recs["recommendation_status"]) == {"proposed"}
    with eng.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM shipping_predictions WHERE run_id=:r"),
                      {"r": res["run"]["run_id"]}).scalar()
    assert n == 75


def test_status_workflow_and_validation(built):
    eng, _, _ = built
    rid = int(P.get_recommendations(engine=eng).iloc[0]["recommendation_id"])
    P.update_recommendation_status(rid, "approved", "ok by ops", engine=eng)
    hist = P.get_status_history(rid, engine=eng)
    assert list(hist["new_status"]) == ["approved"] and hist["old_status"].iloc[0] == "proposed"
    with pytest.raises(ValueError):
        P.update_recommendation_status(rid, "maybe", engine=eng)
    with pytest.raises(P.PersistenceError):
        P.update_recommendation_status(999999, "approved", engine=eng)


def test_scenario_run_saved_and_read_back(built):
    eng, _, ctx = built
    sim = simulate_scenarios(ctx=ctx)
    rid = P.save_scenario_run(sim, engine=eng)
    P.save_scenario_run(sim, engine=eng, run_id=rid)  # same id -> no-op
    sc = P.get_scenarios(rid, engine=eng)
    assert len(sc) == 75 and sc["explanation"].notna().all()


def test_assumption_and_settings_saved_with_validation(built):
    eng, _, _ = built
    P.save_assumption("transit_days_per_1000_miles", 1.5, engine=eng)
    with pytest.raises(ValueError):
        P.save_assumption("transit_days_per_1000_miles", -1, engine=eng)
    with pytest.raises(ValueError):
        P.save_assumption("not_an_assumption", 1, engine=eng)
    with pytest.raises(ValueError):
        P.save_settings({"profit_weight": -1, "speed_weight": 0, "risk_weight": 0}, "any_factory", engine=eng)


def test_migration_is_additive_on_old_schema(tmp_path):
    """An old-style table with data gains new columns and keeps every row."""
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE model_registry (model_id INTEGER PRIMARY KEY, model_name VARCHAR, model_version VARCHAR, "
                "algorithm VARCHAR, mae FLOAT, rmse FLOAT, r2_score FLOAT, training_timestamp DATETIME, "
                "model_path VARCHAR, is_active BOOLEAN)")
    con.execute("INSERT INTO model_registry (model_name, model_version, mae) VALUES ('old', 'v0', 1.0)")
    con.commit()
    con.close()
    from database.connection import get_engine
    eng = get_engine(path)
    actions = upgrade_schema(eng)
    assert any("model_registry.val_mae" in a for a in actions)
    assert upgrade_schema(eng) == []  # second run changes nothing
    with eng.connect() as c:
        assert c.execute(text("SELECT model_name, mae FROM model_registry")).fetchall() == [("old", 1.0)]


def test_rebuild_requires_confirmation_flag():
    import subprocess, sys
    out = subprocess.run([sys.executable, "-m", "src.build_database", "--rebuild"], capture_output=True, text=True)
    assert out.returncode != 0 and "Refusing to rebuild" in (out.stderr + out.stdout)
