# EDA Methodology and Findings — Detailed Record

This document records exactly how each number in `NexRoute_AI_Research_Paper.md` was produced,
for verification. It accompanies, rather than repeats, the paper.

## Data source and method

All figures were computed by `notebooks/research_eda.py`, which:
1. Reads from the project's **already-built SQLite database** (`data/nassau.db`) — the same
   cleaned data used by the dashboard and ML models, not a separate re-extraction.
2. Reuses the existing model evaluation file (`models/evaluation/model_comparison.json`) and the
   existing optimization engine (`src/optimization_engine.py`) rather than recomputing them with
   different logic.
3. Writes every number to `EDA_Metrics_Summary.csv` and every chart to `eda_visualizations/`.
4. **Does not modify** any source file, the database, the raw CSV, or any trained model.

## Verification table

| Paper claim | Source computation | Verification file |
|---|---|---|
| 10,194 order lines, 8,549 orders, 5,044 customers, 15 products | `df.nunique()` on the DB join query | `EDA_Metrics_Summary.csv` |
| Top product: Wonka Bar - Triple Dazzle Caramel, $28,485 | `df.groupby('product_name')['sales'].sum()` | `EDA_Metrics_Summary.csv`, Figure 1 |
| Top 5 products = 92.9% of sales | computed from the same groupby, ratio of top-5 sum to total | `EDA_Metrics_Summary.csv` |
| Division split: Chocolate 9,844 / Other 316 / Sugar 34 | `df['division'].value_counts()` | `EDA_Metrics_Summary.csv`, Figure 2 |
| Avg orders/customer 1.69, max 15, top-10 share 1.1% | `df.groupby('customer_id')['order_id'].nunique()` | `EDA_Metrics_Summary.csv`, Figure 3 |
| Region counts: Pacific 3260, Atlantic 2988, Interior 2326, Gulf 1620 | `df['region'].value_counts()` | `EDA_Metrics_Summary.csv`, Figure 5 |
| Raw lead time 904–1,642 days, mean 1,320.8, std 262.4 | `df['lead_time_days_raw'].describe()` | `EDA_Metrics_Summary.csv`, Figure 8 |
| Same Day mean 1,333.4 vs Standard Class 1,314.3 (gap −19.1 in wrong direction) | `df.groupby('ship_mode')['lead_time_days_raw'].mean()` | `lead_time_by_ship_mode.csv`, Figure 7 |
| Year-gap distribution: 2/3/4/5-year gaps, counts 711/3075/4280/2128 | `(ship_year - order_year).value_counts()` | `EDA_Metrics_Summary.csv`, Figure 9 |
| Factory order-line counts | `df['current_factory'].value_counts()` using the supplied baseline mapping | `EDA_Metrics_Summary.csv`, Figure 10 |
| Distance vs. lead-time correlation r=0.015 | `df[['distance_miles','lead_time_days_raw']].corr()` | `correlation_matrix.csv`, Figures 11–12 |
| 200 missing distances, all Canadian | `df.isna().sum()` then cross-checked against raw CSV `Country/Region` for those rows | investigated live during this analysis; see paper Section 5.8 |
| 313 duplicate order lines, present in raw CSV | `raw_df.duplicated().sum()` on the untouched source CSV, re-verified by inspecting one duplicate order's raw rows | investigated live during this analysis |
| Model comparison table (MAE/RMSE/R² for 3 models) | reused verbatim from `models/evaluation/model_comparison.json`, produced earlier by `src/prediction_engine.py` | `model_comparison_export.csv`, Figures 13–14 |
| Best model = Gradient Boosting, test R² = 0.038 | same file as above | `model_comparison_export.csv` |
| 15 products evaluated, 0 reallocation, 15 keep-current | `src/optimization_engine.run_optimization_for_all_products()`, called live by the EDA script, balanced weights (0.4 speed / 0.4 profit / 0.2 risk) | `recommendation_summary_export.csv`, Figure 15 |

## Notes on the duplicate-row and missing-distance investigations

These two items required a short ad-hoc check beyond the main EDA script, run against the raw
CSV and documented here for transparency:

**Duplicates:** Order `CA-2021-123625-CHO-MIL-31000` (Row IDs 2018, 2020, 2021, 2023) contains two
rows (2020 and 2021) with identical Product Name, Sales, Units, Gross Profit, and Cost. This
pattern repeats across 313 pairs/groups in the raw file. No row was removed from the analysis
because of this — it is reported as a finding for business review, not treated as confirmed
error.

**Missing distances:** All 200 records with a null `distance_miles` have `Country/Region ==
"Canada"`, with State/Province values (Ontario, Quebec, Alberta, British Columbia, Manitoba,
Prince Edward Island, New Brunswick, Nova Scotia, Newfoundland and Labrador, Saskatchewan) that
fall outside the project's US-state-centroid reference table (`src/config.py:STATE_CENTROIDS`).
This is a scope limitation of the tool, not a flaw in the source data.

## What could not be completed

- A true "per-shipment" geocoded distance (street-address-level) could not be computed — no
  geocoding API is available in this environment, and the source data has no customer
  coordinates. State-centroid approximation was used instead, as already documented in the main
  project.
- Canadian-order financial/distance scenarios could not be scored, for the reason above.
- A capacity-constrained version of the optimization engine could not be run, since no factory
  capacity data exists anywhere in the project or the source file.
