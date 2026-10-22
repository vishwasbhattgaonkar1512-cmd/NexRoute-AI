"""
Compute every number used in the NexRoute AI research paper from the CURRENT project (read-only).

Run from the project root:
    python reports/research_paper/scripts/compute_research_metrics.py

Outputs (reports/research_paper/):
    EDA_Metrics_Summary.csv     metric, value, type (O observed / D derived / E estimated), source
    data/metrics.json           the same values in structured form (used to draw the figures)
    data/*.csv                  supporting tables (correlations, models, scenarios, recommendations, ...)
Nothing in the project (raw data, database, models, source code) is modified.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.config import CANADA_PROVINCE_CENTROIDS, FACTORIES, PRODUCT_FACTORY_BASELINE, MIN_SUPPORT_ROWS
from src.preprocessing import load_raw, run_pipeline
from src.data_validation import eta_squared
from src.prediction_engine import load_active_model, interval_coverage, ACTIVE_POINTER
from src.assumptions import load_assumptions, load_weights
from src.scenario_simulator import simulate_scenarios
from src.optimization_engine import recommend

OUT = ROOT / "reports" / "research_paper"
DATA = OUT / "data"
DATA.mkdir(parents=True, exist_ok=True)
rows, M = [], {}


def put(key, value, typ, source):
    M[key] = value
    rows.append({"metric": key, "value": json.dumps(value) if isinstance(value, (dict, list)) else value,
                 "type": typ, "source": source})


raw = load_raw()
df, issues = run_pipeline()
SRC = "data/raw/nassau_candy_distributor.csv via src.preprocessing.run_pipeline"

# ---------------- dataset
put("raw_rows", len(raw), "O", "raw CSV row count")
put("raw_columns", raw.shape[1], "O", "raw CSV column count")
put("missing_cells_raw", int(raw.isna().sum().sum()), "O", "raw CSV")
put("rows_after_cleaning", len(df), "O", SRC)
put("distinct_order_ids", int(df["Order ID"].nunique()), "O", SRC)
put("customers", int(df["Customer ID"].nunique()), "O", SRC)
put("products", int(df["Product Name"].nunique()), "O", SRC)
put("factories", len(FACTORIES), "O", "src/config.py FACTORIES")
put("divisions", df["Division"].value_counts().to_dict(), "O", SRC)
put("chocolate_share_pct", round(100 * (df["Division"] == "Chocolate").mean(), 2), "O", SRC)
us = ~df["State/Province"].isin(CANADA_PROVINCE_CENTROIDS)
put("destinations", int(df["State/Province"].nunique()), "O", SRC)
put("us_states_incl_dc", int(df.loc[us, "State/Province"].nunique()), "O", SRC)
put("canadian_provinces", int(df.loc[~us, "State/Province"].nunique()), "O", SRC)
put("canadian_lines", int((~us).sum()), "O", SRC)
put("countries", df["Country/Region"].value_counts().to_dict(), "O", SRC)
put("regions", df["Region"].value_counts().to_dict(), "O", SRC + " (order-line Region column)")
put("ship_modes", df["Ship Mode"].value_counts().to_dict(), "O", SRC)
put("order_date_range_as_recorded", [str(df["order_date"].min().date()), str(df["order_date"].max().date())], "O", SRC)
put("ship_date_range_as_recorded", [str(df["ship_date"].min().date()), str(df["ship_date"].max().date())], "O", SRC)
put("sales_total", round(float(df["Sales"].sum()), 2), "O", SRC)
put("gross_profit_total", round(float(df["Gross Profit"].sum()), 2), "O", SRC)
put("gross_margin_pct", round(100 * df["Gross Profit"].sum() / df["Sales"].sum(), 2), "O", SRC)
put("units_total", int(df["Units"].sum()), "O", SRC)

# ---------------- products
prod = (df.groupby("Product Name").agg(lines=("Units", "size"), units=("Units", "sum"), sales=("Sales", "sum"),
                                       gross_profit=("Gross Profit", "sum"))
          .sort_values("sales", ascending=False))
prod["division"] = prod.index.map({p["product_name"]: p["division"] for p in PRODUCT_FACTORY_BASELINE})
prod["factory"] = prod.index.map({p["product_name"]: p["factory_name"] for p in PRODUCT_FACTORY_BASELINE})
prod["unit_price"] = (prod["sales"] / prod["units"]).round(2)
prod.round(2).to_csv(DATA / "products.csv")
put("top_product_by_sales", [prod.index[0], round(float(prod["sales"].iloc[0]), 2)], "O", SRC)
put("bottom_product_by_sales", [prod.index[-1], round(float(prod["sales"].iloc[-1]), 2)], "O", SRC)
put("top5_sales_share_pct", round(100 * prod["sales"].head(5).sum() / prod["sales"].sum(), 2), "O", SRC)
put("unit_price_constant_per_product", bool(((df["Sales"] / df["Units"]).round(4).groupby(df["Product Name"]).nunique() == 1).all()), "O", SRC)
sparse = prod["lines"][prod["lines"] < MIN_SUPPORT_ROWS].sort_values()
put("sparse_products_lt30_lines", {k: int(v) for k, v in sparse.items()}, "O", SRC)

# ---------------- customers
opc = df.groupby("Customer ID")["Order ID"].nunique()
put("avg_order_ids_per_customer", round(float(opc.mean()), 2), "O", SRC)
put("max_order_ids_single_customer", int(opc.max()), "O", SRC)
put("customers_with_one_order_id_pct", round(100 * (opc == 1).mean(), 1), "O", SRC)
put("top10_customers_order_id_share_pct", round(100 * opc.sort_values(ascending=False).head(10).sum() / opc.sum(), 2), "O", SRC)
opc.value_counts().sort_index().rename("customers").to_csv(DATA / "order_ids_per_customer.csv", index_label="order_ids")
multi = df.groupby("Customer ID")["State/Province"].nunique()
put("customers_multiple_destinations", int((multi > 1).sum()), "O", SRC)

# ---------------- geography
st = df.groupby("State/Province").agg(lines=("Units", "size"), units=("Units", "sum")).sort_values("lines", ascending=False)
st.to_csv(DATA / "destinations.csv")
put("top5_destinations_by_lines", {k: int(v) for k, v in st["lines"].head(5).items()}, "O", SRC)
put("top5_destinations_line_share_pct", round(100 * st["lines"].head(5).sum() / st["lines"].sum(), 1), "O", SRC)

# ---------------- factories
fac = df.groupby("current_factory").agg(lines=("Units", "size"), units=("Units", "sum"), products=("Product Name", "nunique"))
fac = fac.sort_values("lines", ascending=False)
fac.to_csv(DATA / "factories.csv")
put("factory_lines", fac["lines"].astype(int).to_dict(), "O", SRC + " + baseline assignment")
put("factory_products", fac["products"].astype(int).to_dict(), "O", "src/config.py PRODUCT_FACTORY_BASELINE")
put("top2_factory_line_share_pct", round(100 * fac["lines"].head(2).sum() / fac["lines"].sum(), 2), "O", SRC)

# ---------------- dates and lead time
put("raw_gap_days_min_max_mean_std", [int(df["lead_time_days_raw"].min()), int(df["lead_time_days_raw"].max()),
                                      round(float(df["lead_time_days_raw"].mean()), 1), round(float(df["lead_time_days_raw"].std()), 1)], "O", SRC)
put("raw_gap_mean_by_ship_mode", df.groupby("Ship Mode")["lead_time_days_raw"].mean().round(1).to_dict(), "O", SRC)
put("eta2_ship_mode_raw_gap_pct", round(100 * eta_squared(df["lead_time_days_raw"], df["Ship Mode"]), 2), "D", "src.data_validation.eta_squared")
ct = pd.crosstab(df["order_id_year"].astype(int), df["order_date"].dt.year)
put("order_id_year_vs_order_date_year", {str(i): {str(j): int(ct.loc[i, j]) for j in ct.columns} for i in ct.index}, "O", SRC)
dq = {i["issue_type"]: i for i in issues}
put("date_shift_days", dq["date_fields_disguised"]["evidence"]["estimated_shift_days"], "D", "src.data_validation.estimate_date_shift")
lt = df["lead_time_recovered_days"]
put("recovered_lead_value_counts", {str(int(k)): int(v) for k, v in lt.value_counts().sort_index().items()}, "D", SRC)
put("recovered_lead_mean_by_ship_mode", df.groupby("Ship Mode")["lead_time_recovered_days"].mean().round(2).to_dict(), "D", SRC)
put("recovered_lead_range_by_ship_mode_p0_5_p99_5", {m: [float(g.quantile(0.005)), float(g.quantile(0.995))]
                                                     for m, g in lt.groupby(df["Ship Mode"])}, "D", SRC)
put("recovered_lead_mean_std", [round(float(lt.mean()), 2), round(float(lt.std()), 2)], "D", SRC)
put("eta2_ship_mode_recovered_lead_pct", round(100 * eta_squared(lt, df["Ship Mode"]), 2), "D", "src.data_validation.eta_squared")
put("recovered_lead_mean_by_region", df.groupby("Region")["lead_time_recovered_days"].mean().round(2).to_dict(), "D", SRC)
put("recovered_lead_mean_by_factory", df.groupby("current_factory")["lead_time_recovered_days"].mean().round(2).to_dict(), "D", SRC)
put("corr_distance_recovered_lead_all", round(float(df["distance_miles"].corr(lt)), 4), "D", SRC)
put("corr_distance_recovered_lead_us", round(float(df.loc[us, "distance_miles"].corr(lt[us])), 4), "D", SRC)
put("corr_distance_raw_gap_all", round(float(df["distance_miles"].corr(df["lead_time_days_raw"])), 4), "D", SRC)
corr = df[["Sales", "Units", "Cost", "Gross Profit", "distance_miles", "lead_time_recovered_days", "lead_time_days_raw"]].corr().round(3)
corr.to_csv(DATA / "correlation_matrix.csv")
put("corr_sales_units", float(corr.loc["Sales", "Units"]), "O", SRC)

# ---------------- data quality
put("data_quality_issues", {k: [v["severity"], v["affected_records"]] for k, v in dq.items()}, "O/D", "src.data_validation.run_quality_checks")
pd.DataFrame([{k: v for k, v in i.items() if k != "evidence"} for i in issues]).to_csv(DATA / "data_quality_report.csv", index=False)

# ---------------- model
_, meta = load_active_model()
put("model_version", meta["model_version"], "D", "models/trained/active_model.json")
put("model_selected", meta["selected_model"], "D", "meta.json")
put("model_selection_rule", meta["selection_rule"], "D", "meta.json")
put("model_features", meta["categorical"] + meta["numeric"], "D", "meta.json")
put("split", {k: meta["split"][k] for k in ("train_rows", "validation_rows", "test_rows", "train_period",
                                              "validation_period", "test_period")}, "D", "meta.json")
mres = pd.DataFrame([{"model": k, "cv_mae_mean": v["cv_mae_mean"], "cv_mae_std": v["cv_mae_std"],
                      "train_mae": v["train"]["mae"], "val_mae": v["validation"]["mae"], "val_rmse": v["validation"]["rmse"],
                      "val_r2": v["validation"]["r2"], "test_mae": v["test"]["mae"], "test_rmse": v["test"]["rmse"],
                      "test_r2": v["test"]["r2"]} for k, v in meta["results"].items()]).round(6)
mres.to_csv(DATA / "model_comparison.csv", index=False)
put("model_comparison", mres.set_index("model").to_dict(orient="index"), "D", "meta.json results")
put("final_test", {k: round(v, 4) for k, v in meta["final_test"].items()}, "D", "meta.json final_test")
ptr = json.loads(ACTIVE_POINTER.read_text())
fi = pd.read_csv(ROOT / ptr["eval_dir"] / "feature_importance.csv")
fi.round(5).to_csv(DATA / "feature_importance.csv", index=False)
put("permutation_importance", {m: dict(zip(g["feature"], g["importance_mae_increase"].round(5))) for m, g in fi.groupby("model")}, "D", "feature_importance.csv")
tp = pd.read_csv(ROOT / ptr["eval_dir"] / "test_predictions.csv")
cov = interval_coverage(tp, meta)
put("interval_bounds_by_ship_mode", cov["bounds_by_ship_mode"], "D", "src.prediction_engine.interval_coverage")
put("interval_test_coverage", round(cov["overall"], 4), "D", "src.prediction_engine.interval_coverage")
res = tp.assign(abs_err=(tp["actual"] - tp["predicted"]).abs()).groupby("ship_mode").agg(
    n=("abs_err", "size"), mae=("abs_err", "mean"), bias=("residual", "mean")).round(3)
res.to_csv(DATA / "residuals_by_ship_mode.csv")
put("test_mae_by_ship_mode", res["mae"].to_dict(), "D", "test_predictions.csv")

# ---------------- optimization & scenarios
a, w = load_assumptions(), load_weights()
put("assumptions", a.to_dict(), "E", "financial_assumptions / optimization_settings (database) via src.assumptions")
put("weights", w, "E", "optimization_settings via src.assumptions")
sim = simulate_scenarios(a, w)
summ = sim["summary"].round(4)
summ.to_csv(DATA / "scenario_summary.csv", index=False)
put("scenarios", summ.set_index("scenario")[["products_moved", "estimated_profit_impact", "estimated_cost_impact",
                                             "profit_impact_pct_of_current_estimated_profit",
                                             "units_weighted_lead_time_impact_days", "units_weighted_distance_impact_miles",
                                             "solver_status"]].to_dict(orient="index"), "E", "src.scenario_simulator")
cand = sim["candidates"]
put("current_estimated_profit_after_freight", round(float(cand.loc[cand["is_current"], "estimated_profit"].sum()), 2), "E", "src.optimization_engine.evaluate_candidates")
put("current_estimated_freight_cost", round(float(cand.loc[cand["is_current"], "freight_cost"].sum()), 2), "E", "src.optimization_engine.evaluate_candidates")
put("eligible_alternatives", int((cand["compatible"] & ~cand["is_current"]).sum()), "E", "src.compatibility (demonstrated_division)")
det = sim["details"]
cost = det[(det["scenario"] == "cost") & ~det["is_current"]][["product_name", "current_factory", "proposed_factory", "lines",
                                                              "distance_impact_miles", "profit_impact", "lead_time_impact_days", "risk_level"]]
cost.round(2).to_csv(DATA / "cost_scenario_moves.csv", index=False)
put("cost_scenario_moves", cost.round(2).set_index("product_name")[["proposed_factory", "profit_impact", "lines"]].to_dict(orient="index"), "E", "src.scenario_simulator")
top3 = cost.nlargest(3, "profit_impact")
put("cost_top3_share_pct", round(100 * top3["profit_impact"].sum() / cost["profit_impact"].sum(), 1), "E", "src.scenario_simulator")
rec = recommend(a, w)
recs = pd.DataFrame(rec["recommendations"])
recs[["recommendation_rank", "product_name", "division", "current_factory", "decision", "recommended_factory",
      "best_alternative", "score", "best_alternative_score", "estimated_profit_impact", "lead_time_impact_days",
      "risk_level", "confidence", "n_historical_lines", "recommendation_reason"]].round(3).to_csv(DATA / "recommendations.csv", index=False)
put("recommendation_solver_status", rec["run"]["solver_status"], "E", "src.optimization_engine.recommend")
put("recommended_reallocations", recs.loc[recs["decision"] == "REALLOCATE", ["product_name", "recommended_factory", "estimated_profit_impact", "n_historical_lines", "risk_level"]]
    .round(2).set_index("product_name").to_dict(orient="index"), "E", "src.optimization_engine.recommend")
put("keep_current_count", int((recs["decision"] == "KEEP_CURRENT_FACTORY").sum()), "E", "src.optimization_engine.recommend")
risk_cur = cand[cand["is_current"]]["overall_risk"]
risk_alt = cand[cand["compatible"] & ~cand["is_current"]]["overall_risk"]
put("risk_overall_current_range", [round(float(risk_cur.min()), 3), round(float(risk_cur.max()), 3)], "E", "src.confidence_engine")
put("risk_overall_alternative_range", [round(float(risk_alt.min()), 3), round(float(risk_alt.max()), 3)], "E", "src.confidence_engine")

# capacity sensitivity (documented, non-default)
a10 = load_assumptions({"factory_capacity_headroom_pct": 10})
s10 = simulate_scenarios(a10, w, scenarios=["cost", "balanced"])["summary"].set_index("scenario")
put("sensitivity_capacity10_cost", {"products_moved": int(s10.loc["cost", "products_moved"]),
                                    "estimated_profit_impact": round(float(s10.loc["cost", "estimated_profit_impact"]), 2)}, "E", "simulate_scenarios with 10% capacity headroom")
a2 = load_assumptions({"freight_cost_per_unit_mile": 2 * a.freight_cost_per_unit_mile})
s2 = simulate_scenarios(a2, w, scenarios=["cost"])["summary"].set_index("scenario")
put("sensitivity_freight_x2_cost", {"products_moved": int(s2.loc["cost", "products_moved"]),
                                    "estimated_profit_impact": round(float(s2.loc["cost", "estimated_profit_impact"]), 2)}, "E", "simulate_scenarios with doubled freight rate")

# ---------------- clustering (descriptive, from saved reports)
cs = pd.read_csv(ROOT / "reports" / "eda" / "clustering_scores.csv")
put("clustering_scores", cs.round(3).to_dict(orient="records"), "D", "reports/eda/clustering_scores.csv (python -m src.clustering_engine)")

# ---------------- database
con = sqlite3.connect(f"file:{ROOT / 'data' / 'nassau.db'}?mode=ro", uri=True)
put("database_tables", len(con.execute("select name from sqlite_master where type='table'").fetchall()), "O", "data/nassau.db (read-only)")
con.close()

pd.DataFrame(rows).to_csv(OUT / "EDA_Metrics_Summary.csv", index=False)
(DATA / "metrics.json").write_text(json.dumps(M, indent=1, default=str), encoding="utf-8")
print(f"{len(rows)} metrics written")
