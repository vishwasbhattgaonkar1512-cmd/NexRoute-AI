"""
Persistence layer: save and read model metadata, predictions, scenarios, recommendations and
data-quality reports. Every function takes an optional `engine` so tests can use a temporary database.

Rules
  * Nothing is ever deleted. Older data-quality reports are marked is_current = False.
  * Saving the same run twice is a no-op (run_id is the key; unique indexes prevent duplicates).
  * Recommendation status changes are validated and recorded in recommendation_status_history.
"""
from __future__ import annotations

import json
import uuid
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from database.connection import get_engine, get_session, init_db
from database.models import (
    Factory, Product, ModelRegistry, OptimizationRun, Recommendation, RecommendationStatusHistory,
    ShippingPrediction, ScenarioSimulation, DataQualityLog, FinancialAssumption, OptimizationSetting,
    RECOMMENDATION_STATUSES, utc_now,
)
from src.config import PROJECT_ROOT, RAW_DATA_PATH, FINANCIAL_ASSUMPTIONS


class PersistenceError(RuntimeError):
    pass


def _session(engine=None):
    return get_session(engine) if engine is not None else get_session()


def _json(obj) -> str:
    def default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (dt.datetime, dt.date)):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, default=default)


def _f(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(v) else v


def _ids(s):
    products = {p.product_name: p.product_id for p in s.query(Product).all()}
    factories = {f.factory_name: f.factory_id for f in s.query(Factory).all()}
    return products, factories


def _require(mapping, key, kind):
    if key not in mapping:
        raise PersistenceError(f"unknown {kind} {key!r}: not in the database")
    return mapping[key]


# ----------------------------------------------------------------------------------------------
# Model registry
# ----------------------------------------------------------------------------------------------
def register_model_version(meta: dict, model_path: Path | str, engine=None, activate: bool = True) -> int:
    """Insert (or return existing) registry row for meta['model_version']; mark it active."""
    init_db(engine=engine) if engine is not None else init_db()
    sel = meta["selected_model"]
    r = meta["results"][sel]
    path = Path(model_path)
    try:
        path = path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        pass
    with _session(engine) as s:
        row = s.query(ModelRegistry).filter_by(model_version=meta["model_version"], model_name=sel).first()
        if row is None:
            row = ModelRegistry(
                model_name=sel, model_version=meta["model_version"], algorithm=sel,
                mae=meta["final_test"]["mae"], rmse=meta["final_test"]["rmse"], r2_score=meta["final_test"]["r2"],
                training_timestamp=dt.datetime.fromisoformat(meta["trained_at"]), model_path=path.as_posix(),
                target=meta["target"], val_mae=r["validation"]["mae"], val_rmse=r["validation"]["rmse"],
                val_r2=r["validation"]["r2"], cv_mae_mean=r["cv_mae_mean"], cv_mae_std=r["cv_mae_std"],
                train_rows=meta["split"]["train_rows"], validation_rows=meta["split"]["validation_rows"],
                test_rows=meta["split"]["test_rows"],
                features_json=_json({"categorical": meta["categorical"], "numeric": meta["numeric"]}),
                metrics_json=_json(meta["results"]), data_sha256=meta.get("data_file_sha256"),
                notes=meta["selection_rule"] + ". " + " ".join(meta.get("limitations", [])),
            )
            s.add(row)
            s.flush()
        if activate:
            s.query(ModelRegistry).filter(ModelRegistry.model_id != row.model_id).update({"is_active": False})
            row.is_active = True
        s.commit()
        return row.model_id


def get_model_registry(engine=None) -> pd.DataFrame:
    with _session(engine) as s:
        rows = s.query(ModelRegistry).order_by(ModelRegistry.training_timestamp.desc()).all()
        return pd.DataFrame([{c.name: getattr(r, c.name) for c in ModelRegistry.__table__.columns} for r in rows])


# ----------------------------------------------------------------------------------------------
# Optimization runs, recommendations, predictions
# ----------------------------------------------------------------------------------------------
def _save_run_row(s, run: dict, run_type: str) -> bool:
    if s.get(OptimizationRun, run["run_id"]) is not None:
        return False
    s.add(OptimizationRun(
        run_id=run["run_id"], run_type=run_type, objective=run.get("objective"),
        weights_json=_json(run.get("weights")), assumptions_json=_json(run.get("assumptions")),
        capacities_json=_json(run.get("capacities")), solver_status=run.get("solver_status"),
        solver_message=run.get("solver_message"), objective_value=_f(run.get("objective_value")),
        model_version=run.get("model_version"), n_products=run.get("n_products"), notes=run.get("notes"),
    ))
    return True


def save_recommendation_run(result: dict, engine=None) -> str:
    """Persist output of optimization_engine.recommend(): run + recommendations + per-pair predictions."""
    run = result["run"]
    with _session(engine) as s:
        if not _save_run_row(s, run, "recommendation"):
            return run["run_id"]  # already saved
        products, factories = _ids(s)
        for r in result["recommendations"]:
            s.add(Recommendation(
                run_id=run["run_id"], product_id=_require(products, r["product_name"], "product"),
                current_factory_id=_require(factories, r["current_factory"], "factory"),
                recommended_factory_id=factories.get(r.get("recommended_factory")),
                decision=r["decision"], predicted_lead_time_improvement=_f(r.get("predicted_lead_time_improvement")),
                estimated_profit_impact=_f(r.get("estimated_profit_impact")),
                estimated_cost_impact=_f(r.get("estimated_cost_impact")),
                risk_level=r.get("risk_level"), confidence_label=r.get("confidence"),
                confidence_score=_f(1 - r["overall_risk"]) if r.get("overall_risk") is not None else None,
                score=_f(r.get("score")), recommendation_rank=r["recommendation_rank"],
                recommendation_reason=r["recommendation_reason"], recommendation_status="proposed",
                status_updated_at=utc_now(), model_version=run.get("model_version"),
            ))
        for _, c in result["candidates"].iterrows():
            s.add(ShippingPrediction(
                run_id=run["run_id"], product_id=products[c["product_name"]], factory_id=factories[c["factory_name"]],
                destination_region="ALL", ship_mode="MIX", predicted_lead_time=_f(c["estimated_lead_days"]),
                processing_lead_days=_f(c["processing_lead_days"]), transit_days_assumed=_f(c["transit_days_assumed"]),
                interval_low=_f(c["processing_low"] + c["transit_days_assumed"]),
                interval_high=_f(c["processing_high"] + c["transit_days_assumed"]),
                weighted_distance_miles=_f(c["weighted_distance_miles"]),
                prediction_unit="days (processing: model on derived target; transit: assumption)",
                model_version=run.get("model_version"),
                confidence_information=_json({"risk_level": c["risk_level"], "overall_risk": c["overall_risk"],
                                              "confidence": c["confidence"], "note": c["score_note"]}),
            ))
        s.commit()
    return run["run_id"]


def save_scenario_run(sim: dict, engine=None, run_id: str | None = None, notes: str | None = None) -> str:
    """Persist output of scenario_simulator.simulate_scenarios()."""
    run_id = run_id or "scn-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    summary = sim["summary"]
    run = {"run_id": run_id, "objective": "scenario comparison: " + ", ".join(summary["scenario"]),
           "weights": sim["weights"], "assumptions": sim["assumptions"].to_dict(), "capacities": sim["capacities"],
           "solver_status": ";".join(f"{a}:{b}" for a, b in zip(summary["scenario"], summary["solver_status"])),
           "model_version": sim["model_version"], "n_products": int(sim["details"]["product_name"].nunique()),
           "notes": notes or _json(summary.to_dict(orient="records"))}
    with _session(engine) as s:
        if not _save_run_row(s, run, "scenario"):
            return run_id
        products, factories = _ids(s)
        cand = sim["candidates"].set_index(["product_name", "factory_name"])
        for _, d in sim["details"].iterrows():
            base_lead = cand.loc[(d["product_name"], d["current_factory"]), "estimated_lead_days"]
            alt_lead = cand.loc[(d["product_name"], d["proposed_factory"]), "estimated_lead_days"]
            s.add(ScenarioSimulation(
                run_id=run_id, scenario_key=d["scenario"], scenario_name=d["scenario_name"],
                product_id=_require(products, d["product_name"], "product"),
                baseline_factory_id=factories[d["current_factory"]], proposed_factory_id=factories[d["proposed_factory"]],
                destination_region="ALL", ship_mode="MIX",
                baseline_predicted_lead_time=_f(base_lead), alternative_predicted_lead_time=_f(alt_lead),
                lead_time_reduction_percentage=_f(100 * (base_lead - alt_lead) / base_lead) if base_lead else None,
                lead_time_impact_days=_f(d["lead_time_impact_days"]), estimated_profit_impact=_f(d["profit_impact"]),
                estimated_cost_impact=_f(d["cost_impact"]), distance_impact_miles=_f(d["distance_impact_miles"]),
                risk_level=d["risk_level"], overall_risk=_f(d["overall_risk"]), confidence_label=d["confidence"],
                scenario_status="current" if d["is_current"] else "proposed", explanation=d["explanation"],
            ))
        s.commit()
    return run_id


def list_runs(run_type: str | None = None, engine=None) -> pd.DataFrame:
    with _session(engine) as s:
        q = s.query(OptimizationRun)
        if run_type:
            q = q.filter(OptimizationRun.run_type == run_type)
        rows = q.order_by(OptimizationRun.created_at.desc()).all()
        return pd.DataFrame([{c.name: getattr(r, c.name) for c in OptimizationRun.__table__.columns} for r in rows])


def latest_run_id(run_type: str, engine=None) -> str | None:
    runs = list_runs(run_type, engine)
    return None if runs.empty else runs.iloc[0]["run_id"]


def get_recommendations(run_id: str | None = None, engine=None) -> pd.DataFrame:
    run_id = run_id or latest_run_id("recommendation", engine)
    if run_id is None:
        return pd.DataFrame()
    with _session(engine) as s:
        products = {v: k for k, v in _ids(s)[0].items()}
        factories = {v: k for k, v in _ids(s)[1].items()}
        rows = (s.query(Recommendation).filter_by(run_id=run_id)
                 .order_by(Recommendation.recommendation_rank).all())
        out = []
        for r in rows:
            d = {c.name: getattr(r, c.name) for c in Recommendation.__table__.columns}
            d["product_name"] = products.get(r.product_id)
            d["current_factory"] = factories.get(r.current_factory_id)
            d["recommended_factory"] = factories.get(r.recommended_factory_id)
            out.append(d)
        return pd.DataFrame(out)


def get_scenarios(run_id: str | None = None, engine=None) -> pd.DataFrame:
    run_id = run_id or latest_run_id("scenario", engine)
    if run_id is None:
        return pd.DataFrame()
    with _session(engine) as s:
        products = {v: k for k, v in _ids(s)[0].items()}
        factories = {v: k for k, v in _ids(s)[1].items()}
        rows = s.query(ScenarioSimulation).filter_by(run_id=run_id).all()
        out = []
        for r in rows:
            d = {c.name: getattr(r, c.name) for c in ScenarioSimulation.__table__.columns}
            d.update(product_name=products.get(r.product_id), current_factory=factories.get(r.baseline_factory_id),
                     proposed_factory=factories.get(r.proposed_factory_id))
            out.append(d)
        return pd.DataFrame(out)


def update_recommendation_status(recommendation_id: int, new_status: str, note: str | None = None,
                                 engine=None) -> None:
    if new_status not in RECOMMENDATION_STATUSES:
        raise ValueError(f"status must be one of {RECOMMENDATION_STATUSES}")
    with _session(engine) as s:
        rec = s.get(Recommendation, int(recommendation_id))
        if rec is None:
            raise PersistenceError(f"recommendation {recommendation_id} not found")
        if rec.recommendation_status == new_status and not note:
            return
        s.add(RecommendationStatusHistory(recommendation_id=rec.recommendation_id,
                                          old_status=rec.recommendation_status, new_status=new_status, note=note))
        rec.recommendation_status = new_status
        rec.status_updated_at = utc_now()
        rec.status_note = note
        s.commit()


def get_status_history(recommendation_id: int, engine=None) -> pd.DataFrame:
    with _session(engine) as s:
        rows = (s.query(RecommendationStatusHistory).filter_by(recommendation_id=int(recommendation_id))
                 .order_by(RecommendationStatusHistory.changed_at).all())
        return pd.DataFrame([{c.name: getattr(r, c.name) for c in RecommendationStatusHistory.__table__.columns}
                             for r in rows])


# ----------------------------------------------------------------------------------------------
# Data quality
# ----------------------------------------------------------------------------------------------
def save_data_quality_report(issues: list[dict], engine=None, source_file: Path | str = RAW_DATA_PATH) -> str:
    """Insert a new report (all rows share a report_id) and mark older rows not current. Nothing is deleted."""
    report_id = "dq-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    try:
        src = Path(source_file).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        src = str(source_file)
    with _session(engine) as s:
        s.query(DataQualityLog).filter((DataQualityLog.is_current.is_(None)) | (DataQualityLog.is_current.is_(True))) \
            .update({"is_current": False}, synchronize_session=False)
        for i in issues:
            s.add(DataQualityLog(source_file=src, issue_type=i["issue_type"], issue_description=i["issue_description"],
                                 affected_records=int(i["affected_records"]), severity=i["severity"],
                                 report_id=report_id, is_current=True, evidence_json=_json(i.get("evidence", {}))))
        s.commit()
    return report_id


def get_data_quality(current_only: bool = True, engine=None) -> pd.DataFrame:
    with _session(engine) as s:
        q = s.query(DataQualityLog)
        if current_only:
            q = q.filter(DataQualityLog.is_current.is_(True))
        rows = q.order_by(DataQualityLog.log_id).all()
        return pd.DataFrame([{c.name: getattr(r, c.name) for c in DataQualityLog.__table__.columns} for r in rows])


# ----------------------------------------------------------------------------------------------
# Assumptions & settings (editable from the dashboard)
# ----------------------------------------------------------------------------------------------
def save_assumption(name: str, value: float, engine=None) -> None:
    if name not in FINANCIAL_ASSUMPTIONS:
        raise ValueError(f"unknown assumption {name!r}")
    from src.assumptions import load_assumptions
    load_assumptions({name: value}, use_database=False)  # validates the value
    cfg = FINANCIAL_ASSUMPTIONS[name]
    with _session(engine) as s:
        row = s.query(FinancialAssumption).filter_by(assumption_name=name).first()
        if row is None:
            s.add(FinancialAssumption(assumption_name=name, assumption_value=float(value), assumption_unit=cfg["unit"],
                                      assumption_source=cfg["source"], is_configurable=cfg["is_configurable"]))
        else:
            row.assumption_value = float(value)
        s.commit()


def save_settings(weights: dict, compatibility_rule: str, mode: str = "custom", engine=None) -> None:
    from src.assumptions import load_weights, load_assumptions
    load_weights(overrides=weights, use_database=False)
    load_assumptions({"compatibility_rule": compatibility_rule}, use_database=False)
    with _session(engine) as s:
        s.add(OptimizationSetting(speed_weight=weights["speed_weight"], profit_weight=weights["profit_weight"],
                                  risk_weight=weights["risk_weight"], optimization_mode=mode,
                                  compatibility_rule=compatibility_rule))
        s.commit()


def database_statistics(engine=None) -> pd.DataFrame:
    from sqlalchemy import inspect, text
    eng = engine or get_engine()
    names = inspect(eng).get_table_names()
    with eng.connect() as c:
        return pd.DataFrame([{"table": n, "rows": c.execute(text(f'SELECT COUNT(*) FROM "{n}"')).scalar()} for n in names])
