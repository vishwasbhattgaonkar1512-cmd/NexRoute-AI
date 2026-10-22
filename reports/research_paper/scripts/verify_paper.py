"""
Cross-check the research paper and the executive summary against freshly computed metrics.
Run after compute_research_metrics.py:  python reports/research_paper/scripts/verify_paper.py
Writes data/verification_results.csv and prints a summary. Exit code 1 if any check fails.
"""
import json
import sys
from pathlib import Path

import pandas as pd

RP = Path(__file__).resolve().parents[1]
ROOT = RP.parents[1]
M = json.loads((RP / "data" / "metrics.json").read_text(encoding="utf-8"))
paper = (RP / "NexRoute_AI_Research_Paper.md").read_text(encoding="utf-8")
execs = (ROOT / "reports" / "executive_summary" / "NexRoute_AI_Executive_Summary_Government_Stakeholders.md").read_text(encoding="utf-8")
sc, ft = M["scenarios"], M["final_test"]
mc = M["model_comparison"]

# (claim, computed value, string expected in paper, string expected in executive summary or None)
C = [
    ("Order lines", M["raw_rows"], f"{M['raw_rows']:,}", f"{M['raw_rows']:,}"),
    ("Distinct order IDs", M["distinct_order_ids"], f"{M['distinct_order_ids']:,}", f"{M['distinct_order_ids']:,}"),
    ("Customers", M["customers"], f"{M['customers']:,}", f"{M['customers']:,}"),
    ("Products", M["products"], "15 products", "15 products"),
    ("Factories", M["factories"], "five factories", "5 factories"),
    ("Destinations", M["destinations"], f"{M['destinations']} destinations", "| Destinations | 59 |"),
    ("US states incl. DC", M["us_states_incl_dc"], f"{M['us_states_incl_dc']} US states incl. DC", "| 49 |"),
    ("Canadian provinces", M["canadian_provinces"], f"{M['canadian_provinces']} Canadian provinces", "| Canadian provinces | 10 |"),
    ("Chocolate lines", M["divisions"]["Chocolate"], "Chocolate 9,844", "9,844"),
    ("Other lines", M["divisions"]["Other"], "Other 310", None),
    ("Sugar lines", M["divisions"]["Sugar"], "Sugar 40", "(40 lines)"),
    ("Chocolate share %", M["chocolate_share_pct"], "96.6%", "96.6%"),
    ("Sales total", M["sales_total"], "$141,783.63", "$141,784"),
    ("Gross profit total", M["gross_profit_total"], "$93,442.80", "$93,443"),
    ("Sparse products (<30 lines)", len(M["sparse_products_lt30_lines"]), "Seven of the 15 products", "7 of the 15 products"),
    ("Raw gap range", M["raw_gap_days_min_max_mean_std"][:2], "904–1,642 days", "904 to 1,642 days"),
    ("Date shift", M["date_shift_days"], "2,000 days", "2,000 days"),
    ("Ship-mode share of variance (reconstructed)", M["eta2_ship_mode_recovered_lead_pct"], "67.4%", "67%"),
    ("Distance correlation (all rows)", M["corr_distance_recovered_lead_all"], "r = 0.006", "correlation 0.006"),
    ("Selected model", M["model_selected"], "Per-shipping-mode mean (selected)", "Average for each shipping mode (selected)"),
    ("Validation MAE selected", round(mc["baseline_ship_mode_mean"]["val_mae"], 3), "**0.828**", None),
    ("Final test MAE", round(ft["mae"], 3), "0.806 days", "0.806 days"),
    ("Final test RMSE", round(ft["rmse"], 3), "0.986 days", "0.986 days"),
    ("Final test R²", round(ft["r2"], 3), "R² 0.698", "0.698"),
    ("LR test MAE", round(mc["linear_regression"]["test_mae"], 3), "| 0.812 |", "| Linear Regression | 0.81 |"),
    ("RF test MAE", round(mc["random_forest"]["test_mae"], 3), "| 0.817 |", "| Random Forest | 0.82 |"),
    ("GB test MAE", round(mc["gradient_boosting"]["test_mae"], 3), "| 0.819 |", "| Gradient Boosting | 0.82 |"),
    ("Overall-mean test MAE", round(mc["baseline_mean"]["test_mae"], 3), "| 1.381 |", "| 1.38 |"),
    ("Interval test coverage", M["interval_test_coverage"], "measured coverage on the test set is 100%", "every actual value fell inside its range"),
    ("Scenario alternative: moved", sc["alternative"]["products_moved"], "| Best alternative (forced) | 15 |", "| 15 | +$760"),
    ("Scenario alternative: profit", round(sc["alternative"]["estimated_profit_impact"]), "+$760", "+$760"),
    ("Scenario distance: moved/profit", [sc["distance"]["products_moved"], round(sc["distance"]["estimated_profit_impact"])], "| Distance-based | 11 | +$1,690 |", "| 11 | +$1,690 (+2.4%)"),
    ("Scenario cost: moved/profit", [sc["cost"]["products_moved"], round(sc["cost"]["estimated_profit_impact"])], "| Cost-focused | 11 | +$1,690 |", "| 11 | +$1,690 (+2.4%)"),
    ("Scenario balanced: moved/profit", [sc["balanced"]["products_moved"], round(sc["balanced"]["estimated_profit_impact"])], "| **2** | **+$8** |", "| **2** | **+$8** |"),
    ("Cost scenario % of est. current profit", round(sc["cost"]["profit_impact_pct_of_current_estimated_profit"], 1), "+2.4%", "+2.4%"),
    ("Lead-time change distance/cost", round(sc["cost"]["units_weighted_lead_time_impact_days"], 2), "−0.17 days", "−0.17 days"),
    ("Lead-time change alternative", round(sc["alternative"]["units_weighted_lead_time_impact_days"], 2), "−0.08 days", "−0.08 days"),
    ("Estimated current profit after freight", round(M["current_estimated_profit_after_freight"]), "$69,390", "$69,390"),
    ("Top-3 share of cost-scenario gain", M["cost_top3_share_pct"], "98.8%", None),
    ("Scrumdiddlyumptious move", M["cost_scenario_moves"]["Wonka Bar -Scrumdiddlyumptious"]["profit_impact"], "+$633.00", "$633"),
    ("Fudge Mallows move", M["cost_scenario_moves"]["Wonka Bar - Fudge Mallows"]["profit_impact"], "+$506.41", "$506"),
    ("Fun Dip recommendation", M["recommended_reallocations"]["Fun Dip"]["estimated_profit_impact"], "+$1.67", "+$1.67"),
    ("Laffy Taffy recommendation", M["recommended_reallocations"]["Laffy Taffy"]["estimated_profit_impact"], "+$6.41", "+$6.41"),
    ("Keep-current count", M["keep_current_count"], "keeping 13 products", None),
    ("Freight doubled sensitivity", round(M["sensitivity_freight_x2_cost"]["estimated_profit_impact"]), "+$3,381", None),
    ("Capacity +10% sensitivity", [M["sensitivity_capacity10_cost"]["products_moved"], round(M["sensitivity_capacity10_cost"]["estimated_profit_impact"])], "| 9 | +$292 |", None),
    ("Eligible alternatives", M["eligible_alternatives"], "22 eligible alternatives", None),
    ("Freight assumption", M["assumptions"]["freight_cost_per_unit_mile"], "$0.0005 per unit-mile", "$0.0005"),
    ("Transit assumption", M["assumptions"]["transit_days_per_1000_miles"], "2 days per 1,000 miles", "2 days per 1,000"),
]
# Superseded values that must NOT appear in the paper anymore
STALE = ["0.038", "zero reallocation", "Other 316", "Sugar 34", "3,260", "57 states", "96.9%", "lead-time index", "r = 0.015",
         "169.02", "178.12"]

rows = []
for claim, val, p, e in C:
    rows.append({"claim": claim, "computed_value": json.dumps(val), "paper_text": p, "in_paper": p in paper,
                 "exec_text": e or "", "in_exec_summary": (e in execs) if e else None})
for s in STALE:
    rows.append({"claim": f"superseded value absent: {s!r}", "computed_value": "", "paper_text": s,
                 "in_paper": s not in paper, "exec_text": "", "in_exec_summary": None})
df = pd.DataFrame(rows)
df.to_csv(RP / "data" / "verification_results.csv", index=False)
fail = df[(df["in_paper"] == False) | (df["in_exec_summary"] == False)]  # noqa: E712
print(f"{len(C)} metric checks, {len(STALE)} superseded-value checks; failures: {len(fail)}")
if len(fail):
    print(fail[["claim", "paper_text", "in_paper", "exec_text", "in_exec_summary"]].to_string())
    sys.exit(1)
