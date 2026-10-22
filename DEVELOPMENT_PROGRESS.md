# Development Progress — Nassau Candy Factory Reallocation System

Last updated: 2026-10-22

## CRITICAL DATA-QUALITY FINDING (read this first)

**Ship Date − Order Date is NOT a usable "shipping lead time" signal.**

- Order Date range: 2024-01-02 → 2025-12-31
- Ship Date range: 2026-06-30 → 2030-06-28
- Resulting "lead time": **904 to 1642 days** (2.5 to 4.5 years)
- This does **not** vary meaningfully by Ship Mode: "Same Day" orders show a mean gap of 1333 days, "Standard Class" shows 1314 days — statistically indistinguishable. A real Same-Day/Standard split would show a gap of hours vs. days.
- Order IDs embed a year prefix (e.g. `US-2021-103800-...`) that matches *neither* the Order Date year nor the Ship Date year, suggesting Ship Date was regenerated/shifted independently from the rest of the record (consistent with a synthetic teaching dataset, not a real WMS export).

**Decision taken (documented, configurable):** The raw `lead_time_days` field is treated as **structurally unreliable** and is *not* used as-is as an ML regression target representing real-world delivery performance. Per the master prompt's own rule ("do not pretend the model predicts real-world delivery times if dates are unreliable"), the system:
1. Surfaces this finding prominently in the Executive Dashboard and Risk Panel as a Critical data-quality warning.
2. Still computes and stores the raw lead time (for transparency/audit) but labels every chart/KPI derived from it as **"Raw field — not validated as real delivery duration."**
3. Builds the predictive model on a **de-trended lead-time signal**: `lead_time_days − per-(Ship Mode) median`, i.e. the model learns relative variation across routes/products/regions (which still correlates with geography, division, region) rather than claiming to predict literal calendar delivery dates. This is explained in the Model Analytics page and the research paper's Limitations section.
4. All scenario/recommendation outputs are labeled **"Relative lead-time index," not "days."**

This is the single most important judgment call in the project and is treated as such throughout — not silently patched.

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 1. Repo & dataset inspection | ✅ Done | `reports/eda/data_profile.json`, finding above |
| 2. Database design | ✅ Done | SQLite, `database/schema.py`, `database/models.py` |
| 3. EDA & data prep | ✅ Done | `src/preprocessing.py`, `reports/eda/` |
| 4. Machine learning | ✅ Done | `src/prediction_engine.py`, 3 models trained & compared |
| 5. Clustering | ✅ Done | `src/clustering_engine.py` |
| 6. Scenario simulation | ✅ Done | `src/scenario_simulator.py` |
| 7. Optimization | ✅ Done | `src/optimization_engine.py` (SciPy linear_sum_assignment + constraints) |
| 8. Streamlit dashboard | ✅ Done (core modules) | `dashboard/app.py` + 6 pages |
| 9. Testing | ✅ Partial | `tests/` — smoke tests on pipeline, DB, predictions |
| 10. Documentation | ✅ Done | README, this file, `reports/` |

## Known simplifications vs. the full master-prompt spec

- Customer-level lat/long: not in the data and no geocoding API is available offline, so **State/Province centroid coordinates** (public, static table) are used for Haversine distance instead of per-ZIP geocoding. Documented as an assumption in `src/geographic_engine.py`.
- Factory capacity, alternative-factory manufacturing cost, and shipping-cost-per-mile are **not in the source data**. These are implemented as **configurable assumptions** in `financial_assumptions` table with `is_configurable=True` and a visible source label ("ANALYST ASSUMPTION — not from source data"), per the master prompt's own instruction not to invent business facts silently.
- Product-factory compatibility: only the 15 supplied baseline assignments are "confirmed compatible" with their current factory. Compatibility with *alternative* factories defaults to "unverified — assumed compatible within same Division" (configurable toggle), clearly flagged in every scenario as lower confidence.
- Clustering, optimization and research paper are implemented at working-prototype depth, not exhaustively tuned.

## How to run

```
pip install -r requirements.txt
python notebooks/profile_dataset.py        # Phase 1 report
python src/build_database.py               # Phase 2: build nassau.db
python src/train_models.py                 # Phase 4: train & save models
streamlit run dashboard/app.py             # Phase 8: launch dashboard
```
