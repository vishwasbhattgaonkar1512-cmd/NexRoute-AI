# EDA Methodology and Findings — Detailed Record (version 2)

This document records how every number in `NexRoute_AI_Research_Paper.md` was produced, so that each one can be
re-checked. It replaces version 1 (archived in `archive_superseded_v1_2026-10-22/`), which reported results from an
earlier project state.

## 1. Method

All numbers come from three scripts in `scripts/`. All of them **read** the current project and modify nothing:

| Script | What it does | Outputs |
|---|---|---|
| `compute_research_metrics.py` | Loads the raw CSV through the project pipeline (`src.preprocessing.run_pipeline`, which includes `src.data_validation`), the active model metadata (`models/trained/lt-20261022-215253/meta.json`), the saved test predictions, the scenario simulator and optimizer (with the saved default assumptions), and the database (read-only) | `EDA_Metrics_Summary.csv` (83 metrics, each tagged Observed / Derived / Estimated with its source) and `data/*.csv` supporting tables |
| `make_figures.py` | Draws Figures 1–14 as SVG | `eda_visualizations/`, using `data/metrics.json` and `data/*.csv` |
| `verify_paper.py` | Cross-checks 49 key metrics against the text of the paper and of the executive summary, and checks that 11 superseded values no longer appear | `data/verification_results.csv` |

The PDF is produced with `scripts/md_to_html.py` and headless Microsoft Edge ("print to PDF"). No additional Python
packages were installed.

To reproduce, run from the project root:

```
python reports/research_paper/scripts/compute_research_metrics.py
python reports/research_paper/scripts/make_figures.py
python reports/research_paper/scripts/verify_paper.py
```

The database checksum (md5 `e81b9843…6034ab2`) was identical before and after running these scripts.

## 2. Findings and how each was computed

| Paper section | Finding | Computation | File |
|---|---|---|---|
| 4 | 10,194 lines, 18 columns, 0 missing; 8,549 order IDs; 5,044 customers; 15 products | Row/column counts; `nunique()` | `EDA_Metrics_Summary.csv` |
| 4 | 59 destinations = 49 US states incl. DC + 10 Canadian provinces (200 lines) | Destinations split by membership of the Canadian province list in `src/config.py` | same |
| 4 | Sales $141,783.63; gross profit $93,442.80 (65.9%) | Column sums | same |
| 5.1 | Top product Triple Dazzle Caramel $28,485; top 5 = 92.9% of sales; Fun Dip $12 | `groupby('Product Name')['Sales'].sum()` | `data/products.csv`, Fig. 1 |
| 5.1 | 7 products with fewer than 30 lines | Lines per product < `MIN_SUPPORT_ROWS` (30) | same |
| 5.1 | Divisions: Chocolate 9,844 / Other 310 / Sugar 40 | `Division` counts (data, not config) | Fig. 2 |
| 5.2 | 1.69 order IDs per customer (max 15); 55.7% have one; top 10 = 1.15% | `groupby('Customer ID')['Order ID'].nunique()` | `data/order_ids_per_customer.csv`, Fig. 3 |
| 5.2 | 28 customers ship to more than one state | `groupby('Customer ID')['State/Province'].nunique() > 1` | — |
| 5.3 | Top 5 destinations = 51.1% of lines | State line counts | `data/destinations.csv`, Fig. 4 |
| 5.3 | Regions Pacific 3,253 / Atlantic 2,986 / Interior 2,335 / Gulf 1,620 | `Region` of each **order line** | Fig. 5 |
| 5.3 | Demand clusters k = 2, silhouette 0.513 | `reports/eda/clustering_scores.csv` (`python -m src.clustering_engine`) | — |
| 5.4 | Raw gap 904–1,642 days (mean 1,320.8, SD 262.4); ship mode explains 0.12% | `Ship Date − Order Date`; η² by ship mode | Fig. 7 |
| 5.4 | Order ID year vs recorded year (Table 2) | Crosstab | `EDA_Metrics_Summary.csv` |
| 5.4 | Shift of 2,000 days; reconstructed lead time 0–8 days (2 lines = 11) | `src.data_validation.estimate_date_shift` / `recover_lead_time` | Fig. 8 |
| 5.4 | Mean by mode 0.04 / 2.18 / 3.24 / 5.00 days; η² 67.4% | `groupby('Ship Mode')`; η² | Fig. 9 |
| 5.5 | Factory lines (5,692 / 4,152 / 217 / 100 / 33); top 2 = 96.6% | Baseline assignment applied to lines | `data/factories.csv`, Fig. 10 |
| 5.5 | Lead time by factory 3.69–4.36; by region 3.91–4.05 days | Group means | `EDA_Metrics_Summary.csv` |
| 5.6 | r(distance, reconstructed lead) = 0.006 (US only 0.002) | Pearson correlation | `data/correlation_matrix.csv` |
| 5.7 | Data-quality findings (Table 4) | `src.data_validation.run_quality_checks` | `data/data_quality_report.csv` |
| 8–9 | Model comparison (Table 5), final test MAE 0.806, RMSE 0.986, R² 0.698 | `meta.json` results / `final_test` | `data/model_comparison.csv`, Fig. 11 |
| 9 | Permutation importance: only Ship Mode matters | `feature_importance.csv` of the active model version | `data/feature_importance.csv`, Fig. 12 |
| 9 | Test MAE by mode 0.10 / 0.67 / 1.03 / 0.85 days; range coverage 100% | Saved test predictions; `src.prediction_engine.interval_coverage` | `data/residuals_by_ship_mode.csv` |
| 10.2 | Risk 0.17–0.23 (current) vs 0.53–0.57 (eligible alternatives) | `src.confidence_engine` via `evaluate_candidates` | `EDA_Metrics_Summary.csv` |
| 10.4 | 22 eligible alternatives | `compatibility == True` and not current | same |
| 11.1 | Scenario results (Table 7) | `src.scenario_simulator.simulate_scenarios` (default assumptions) | `data/scenario_summary.csv`, Fig. 13 |
| 11.1 | Cost-scenario moves (Table 8); top 3 = 98.8% | Same, cost scenario | `data/cost_scenario_moves.csv`, Fig. 14 |
| 11.2 | Balanced recommendations (Table 9) | `src.optimization_engine.recommend` | `data/recommendations.csv` |
| 11.3 | Sensitivity: freight × 2 → +$3,381; capacity +10% → 9 moves, +$292 | `simulate_scenarios` with one assumption overridden | `EDA_Metrics_Summary.csv` |

## 3. Notes

- **The ~150-mile distance statement** comes from the demand-weighted distances computed by the optimizer for the
  three Wonka Bar products: 1,309 → 1,152, 1,312 → 1,165 and 1,319 → 1,156 miles from Lot's O' Nuts → Wicked Choccy's.
- **Duplicates and Canadian rows.** Possible duplicate lines (313) are flagged, not removed. Canadian destinations
  (200 lines) now have approximate province centroids, so no distances are missing (version 1 reported 200 missing).
- **Geography.** Uses each order line's destination, not the customer's first state. That is why regional counts
  differ slightly from version 1.
- **Divisions.** Taken from the data. Version 1 used an earlier configuration that listed Fizzy Lifting Drinks
  (6 lines) as "Other".
