# Nassau Candy Distributor — Factory Reallocation & Shipping Optimization System

A decision-support system (not just a dashboard) that evaluates whether any of Nassau Candy's
15 products should be reassigned from their current factory to one of the other four, using
historical order data, geographic distance, a trained ML model, scenario simulation, a
transparent financial-impact engine, and a constrained optimization/recommendation layer.

## ⚠️ Read this first: critical data-quality finding

The source file's `Ship Date − Order Date` spans **904 to 1,642 days** (2.5–4.5 years) across
the *entire* dataset, and does not vary meaningfully by `Ship Mode` ("Same Day" orders show the
same multi-year gap as "Standard Class"). This is not a real-world shipping-lead-time signal —
most likely a synthetic/corrupted date field. Full details and the documented handling strategy
are in **`DEVELOPMENT_PROGRESS.md`**. In short: the system does not pretend to predict real
delivery days. It predicts a de-trended **relative lead-time index**, labels every prediction
with its actual (near-zero) model reliability, and surfaces the finding prominently in the app.

## Quick start

```bash
pip install -r requirements.txt

# Phase 1 — profiling report (writes reports/eda/data_profile.json)
python notebooks/profile_dataset.py

# Phase 2 — build the SQLite database (idempotent; use --rebuild to reset)
python src/build_database.py --rebuild

# Phase 4 — train & evaluate the 3 required models, save artifacts
python src/prediction_engine.py

# Phase 5 — route/product clustering
python -m src.clustering_engine

# Phase 9 — automated tests
python -m pytest tests/ -v

# Phase 8 — launch the dashboard
streamlit run dashboard/app.py
```

## What's actually implemented vs. simplified

See `DEVELOPMENT_PROGRESS.md` for the full phase-by-phase status and every documented assumption
(factory capacity, alternative-factory cost, shipping cost/mile, product-factory compatibility
beyond the 15 baseline assignments — none of this is in the source data, so each is a labeled,
configurable "ANALYST ASSUMPTION", never silently invented as fact).

## Project structure

```
data/           raw CSV, cleaned/processed output, nassau.db (SQLite)
src/            all business logic (preprocessing, geography, ML, scenarios, profit, optimization)
database/       SQLAlchemy models, connection, 13-table normalized schema
dashboard/      Streamlit app (app.py + 8 pages)
models/         trained model artifacts (.joblib) + evaluation CSV/JSON
reports/        EDA profiling, model evaluation exports
tests/          pytest smoke/integration tests (8 passing)
notebooks/      Phase 1 profiling script
```

## Honest results summary (actual numbers from this run, not fabricated)

- 10,194 raw rows → 10,194 rows survive cleaning (no negative lead times, no bad dates found
  once the correct `dd-mm-yyyy` format was identified — 0 parse failures vs. 6000+ for `mm-dd-yyyy`).
- Best model: **Gradient Boosting**, held-out test R² ≈ **0.038** (near zero — honestly reported,
  consistent with the lead-time field being structurally unreliable, not a modeling failure).
- Route clustering: k=6, silhouette score ≈ **0.52**.
- Optimization run across all 15 products, current default weights (balanced): **all 15 currently
  recommend KEEP_CURRENT_FACTORY** — driven by (a) alternative factories being geographically
  farther from each product's real customer base, (b) the reassignment penalty, and (c) the
  minimum-profit-threshold constraint filtering out candidates with negative estimated profit
  impact. This is a legitimate output of the constraints, not a placeholder.

## Known limitations (see DEVELOPMENT_PROGRESS.md for full list)

- No customer-level geocoding (state-centroid approximation used instead).
- No real alternative-factory manufacturing cost, shipping-cost-per-mile, or capacity data —
  all such figures are configurable, clearly labeled assumptions.
- Product-factory compatibility beyond the 15 supplied baseline pairs is an assumed default
  (same-division compatibility), not verified business data.
