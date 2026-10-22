"""
Interactive dashboard workflows driven headlessly (Streamlit AppTest) against a TEMPORARY COPY of the
database. The project database is never written to.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from src.config import DB_PATH

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "dashboard" / "pages"
sys.path.insert(0, str(ROOT / "dashboard"))


@pytest.fixture
def app_db(tmp_path, monkeypatch):
    import database.connection as dc
    copy = tmp_path / "app_copy.db"
    shutil.copy(DB_PATH, copy)
    monkeypatch.setattr(dc, "DB_PATH", copy)
    monkeypatch.setattr(dc, "_engine", None)
    monkeypatch.setattr(dc, "_SessionLocal", None)
    st.cache_data.clear()
    st.cache_resource.clear()
    yield copy
    if dc._engine is not None:
        dc._engine.dispose()
    st.cache_data.clear()


def q(db, sql):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def run(page):
    at = AppTest.from_file(str(PAGES / page), default_timeout=300).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def no_exc(at):
    assert not at.exception, [e.value for e in at.exception]


def test_what_if_scenario_selection_and_save(app_db):
    at = run("03_What_If_Analysis.py")
    sb = at.selectbox(key="scenario_detail")
    seen = []
    for label in sb.options:
        sb.select(label).run()
        no_exc(at)
        sb = at.selectbox(key="scenario_detail")
        assert sb.value == label
        seen.append(label)
    assert len(seen) == 5
    before = q(app_db, "select count(*) from optimization_runs where run_type='scenario'")[0][0]
    [b for b in at.button if "Save this scenario" in b.label][0].click().run()
    no_exc(at)
    assert q(app_db, "select count(*) from optimization_runs where run_type='scenario'")[0][0] == before + 1


def test_recommendations_saved_run_selection_filters_and_status(app_db):
    at = run("04_Recommendations.py")
    [b for b in at.button if "Run optimization" in b.label][0].click().run()
    no_exc(at)
    runs = q(app_db, "select run_id from optimization_runs where run_type='recommendation'")
    assert len(runs) == 2

    sel = at.selectbox(key="saved_run")
    assert len(sel.options) == 2
    for label in sel.options:
        sel.select(label).run()
        no_exc(at)
        sel = at.selectbox(key="saved_run")
        assert at.selectbox(key="saved_run").value == label

    n_realloc = q(app_db, "select count(*) from recommendations r join optimization_runs o on o.run_id=r.run_id "
                          "where r.decision='REALLOCATE' and r.run_id=(select run_id from optimization_runs "
                          "where run_type='recommendation' order by created_at desc limit 1)")[0][0]
    at.selectbox(key="saved_run").select_index(0).run()
    at.multiselect(key="decision_filter").select("Reallocate").run()
    no_exc(at)
    assert len(at.dataframe[0].value) == n_realloc
    at.multiselect(key="decision_filter").unselect("Reallocate").select("Keep current").run()
    no_exc(at)
    assert len(at.dataframe[0].value) == 15 - n_realloc

    at.multiselect(key="decision_filter").unselect("Keep current").run()
    [s for s in at.selectbox if s.label == "Status"][0].select("under_review")
    at.text_input[0].input("QA check")
    [b for b in at.button if b.label == "Update"][0].click().run()
    no_exc(at)
    assert q(app_db, "select old_status, new_status, note from recommendation_status_history") == \
        [("proposed", "under_review", "QA check")]


def test_clear_caches_drops_model_and_context():
    import common
    from src.prediction_engine import load_active_model
    ctx1 = common.load_context()
    load_active_model()
    assert load_active_model.cache_info().currsize == 1
    common.clear_caches()
    assert load_active_model.cache_info().currsize == 0
    assert common.load_context() is not ctx1


def test_refresh_button_clears_cached_context(app_db):
    import common
    ctx_before = common.load_context()
    at = run("08_Data_Management.py")
    [b for b in at.button if "Refresh database" in b.label][0].click().run()
    no_exc(at)
    assert any("Done." in s.value for s in at.success)
    assert common.load_context() is not ctx_before
    assert q(app_db, "select count(*) from order_items")[0][0] == 10194   # nothing deleted


def test_saved_default_shows_up_without_restart(app_db):
    at = run("08_Data_Management.py")
    [n for n in at.number_input if n.label == "transit_days_per_1000_miles"][0].set_value(1.5)
    [b for b in at.button if b.label == "Save defaults"][0].click().run()
    no_exc(at)
    at2 = run("03_What_If_Analysis.py")
    assert [s for s in at2.sidebar.slider if s.label == "Transit days per 1,000 miles"][0].value == 1.5


def test_integrity_report_on_project_copy(app_db):
    from database.connection import get_engine
    from src.persistence import integrity_report
    rep = integrity_report(get_engine(app_db))
    assert rep["ok"] and sum(rep["orphan_run_rows"].values()) == 0
    assert set(rep["unenforced_foreign_keys"]) == {"recommendations.run_id -> optimization_runs",
                                                   "scenario_simulations.run_id -> optimization_runs",
                                                   "shipping_predictions.run_id -> optimization_runs"}


def test_integrity_report_detects_orphans_and_fresh_schema_enforces_fk(tmp_path):
    from database.connection import get_engine, init_db
    from src.persistence import integrity_report
    eng = get_engine(tmp_path / "fresh.db")
    init_db(engine=eng)
    rep = integrity_report(eng)
    assert rep["unenforced_foreign_keys"] == [] and rep["ok"]
    with pytest.raises(Exception):  # fresh schema: FK enforced
        with eng.begin() as c:
            c.execute(text("INSERT INTO recommendations (run_id, decision) VALUES ('no-such-run', 'X')"))
    con = sqlite3.connect(tmp_path / "fresh.db")      # simulate a legacy/migrated orphan (FK checks off)
    con.execute("PRAGMA foreign_keys=OFF")
    con.execute("INSERT INTO recommendations (run_id, decision) VALUES ('no-such-run', 'X')")
    con.commit()
    con.close()
    rep = integrity_report(eng)
    assert rep["orphan_run_rows"]["recommendations"] == 1 and not rep["ok"]
    eng.dispose()
