# NexRoute AI — Intelligent Factory Reallocation & Shipping Optimization

A local, offline decision-support prototype for **Nassau Candy Distributor**. It answers one question:
**which of the five factories should make each of the 15 products?** To answer it, the system combines:

- historical order data
- factory-to-destination geography
- a lead-time model
- transparent cost and profit estimates
- risk scoring
- constrained optimization

It is a prototype for analysis, not a production system, and every estimate is labelled as one.

---

## 1. Problem statement

Nassau Candy ships 15 products from 5 factories to customers across the US and Canada. Each product is currently
made at exactly one factory. Management wants to know whether moving a product to a different factory would:

- reduce shipping cost
- shorten delivery
- improve profit

and at what risk. They also want recommendations they can trust, explain and test under different assumptions.

## 2. Read this first: what the data can and cannot support

| Topic | Finding |
|---|---|
| **Dates** | `Ship Date − Order Date` is 904–1,642 days and **is not a lead time**. The dates are disguised: the Order Date year was relabelled (the Order ID carries the original year, 2021–2024), and Ship Date is shifted by exactly **2,000 days**. |
| **Recovered lead time** | Rule: `Ship Date − 2,000 days − (Order Date with the Order ID year)`. It gives 0–8 days that match ship mode (Same Day ≈ 0, First 1–3, Second 1–5, Standard 3–7; ship mode explains 67% of the variance). This is a **derived** value, never a measured one. Evidence: `reports/PHASE1_AUDIT.md` §2 and the dashboard's Data Management → Date forensics tab. |
| **Geography vs lead time** | Correlation between distance and recovered lead time is **0.002**. The data **cannot** show that a nearer factory delivers faster. Lead-time benefits of a move come from an editable **transit-time assumption**. |
| **Costs, capacity, compatibility** | **Not in the data.** Unit cost is constant per product. Freight rate, alternative-factory cost, capacity and product–factory compatibility are configurable **analyst assumptions**. |
| **Distances** | Straight-line miles to **state/province centroids**. No customer addresses are geocoded. Canadian centroids are coarse. |
| **Sparse products** | 7 products have fewer than 30 order lines (e.g. Fun Dip, Everlasting Gobstopper: 3 each). Their estimates are flagged as weak. |

## 3. Architecture

```
data/raw/*.csv (read-only)
   │
   ▼
src/data_validation.py   schema checks, date forensics, recovered lead time, data-quality report
src/preprocessing.py     cleaning + features (observed vs derived columns), cached pipeline
src/geographic_engine.py Haversine, distance matrix, nearest factory, coverage
   │
   ├─► src/prediction_engine.py   lead-time models: baselines + LR/RF/GB, chronological split, versioned artifacts
   ├─► src/clustering_engine.py   destination demand clusters, route profile clusters
   │
src/assumptions.py   assumptions & weights (session override > database > config), with provenance
src/compatibility.py product–factory eligibility rules
src/profit_engine.py symmetric cost/profit model (same formula for current and alternative factories)
src/confidence_engine.py five documented 0–1 risk components (heuristics, not probabilities)
src/optimization_engine.py  evaluate 15×5 options → balanced score → exact assignment (SciPy MILP)
src/scenario_simulator.py   5 scenarios on one shared candidate table
   │
src/persistence.py   save/read runs, recommendations, predictions, scenarios, registry, DQ reports
database/            SQLAlchemy models, additive migrations (SQLite: data/nassau.db)
dashboard/           Streamlit: home + 8 pages (dashboard/common.py = shared helpers)
tests/               93 pytest tests (unit, edge cases, temporary-DB persistence, every dashboard page)
```

## 4. Technology stack

Python 3.10 · pandas · NumPy · scikit-learn · SciPy (`milp`) · SQLAlchemy 2 + SQLite · Streamlit · Plotly ·
joblib · pytest. Everything runs locally and offline. It uses no paid APIs and no external AI services.

## 5. Directory structure

```
data/raw/            original CSV (never modified)
data/processed/      cleaned_featured.csv, data_quality_logs.json (regenerated)
data/nassau.db       SQLite database (+ nassau_backup_*.db backups)
src/                 business logic (see architecture)
database/            models.py, connection.py, migrations.py
dashboard/           app.py, common.py, pages/01..08
models/trained/<version>/      model.joblib + meta.json; active_model.json points to the active version
models/evaluation/<version>/   model_comparison.json, test_predictions.csv, feature_importance.csv
models/trained/*.joblib, models/evaluation/*.json|csv   legacy models (previous target), kept for reference
models_backup_before_retrain/  older backup, untouched
reports/PHASE1_AUDIT.md        full audit and date forensics
reports/eda/                   profiling and clustering outputs
notebooks/profile_dataset.py   original profiling script
```

## 6. Installation

Run all commands from the project folder (`nassau-candy-optimization/`), using the existing virtual environment:

```bash
# Windows (PowerShell)
..\venv\Scripts\Activate.ps1
# Windows (Git Bash) / macOS / Linux
source ../venv/Scripts/activate      # or: source ../venv/bin/activate

pip install -r requirements.txt
```

> Modules are run with `python -m src.<module>` from the project folder. `python src/<module>.py` does not work
> (the imports need the project root on the path).

## 7. Database setup

```bash
python -m src.build_database
```

This is the safe default and can be re-run at any time. It:

- upgrades the schema additively (adds missing tables, columns and indexes);
- inserts any missing rows;
- refreshes only *derived* columns;
- writes a new data-quality report (older reports are kept and marked not current);
- registers the active model.

It **never deletes data**.

A full rebuild is destructive. It makes a timestamped backup first and requires explicit confirmation:

```bash
python -m src.build_database --rebuild --yes-delete-all-data
```

## 8. Model training

```bash
python -m src.prediction_engine        # trains, evaluates, saves models/trained/<version>/, registers in DB
python -m src.clustering_engine        # optional: writes reports/eda/*clusters*.csv
python -m src.preprocessing            # optional: regenerates data/processed/
```

Each training run creates a new versioned folder (it never overwrites one) and moves `active_model.json` to point at it.

## 9. Dashboard

```bash
streamlit run dashboard/app.py
```

| Page | Contents |
|---|---|
| 1 Executive Dashboard | Observed KPIs, current allocation, optimization summary, scenario impact, data-quality banner |
| 2 Factory Optimization | One product × 5 factories: eligibility, distance, cost breakdown, lead time (processing + assumed transit), risk breakdown, recommendation and reason |
| 3 What-If Analysis | Five scenarios, editable assumptions and weights, before/after comparison, product detail, save to DB |
| 4 Recommendations | Ranked recommendations from saved runs, filters, rationale, status workflow (proposed → under review → approved/rejected → implemented) with history |
| 5 Risk & Impact | Data-quality risk, prediction uncertainty, risk components per option, profit-vs-risk of every move, freight sensitivity |
| 6 Factory Map | Factories, destination demand, current routes, distance matrix, coverage, alternative-factory distances, demand clusters |
| 7 Model Analytics | All models: CV / validation / test metrics, permutation importance, residuals by ship mode, intervals, registry, legacy model note |
| 8 Data Management | Dataset and column status, data-quality report, date forensics, CSV validation, DB statistics, safe refresh, assumption editing, exports |

## 10. Testing

```bash
python -m pytest -v
```

The suite has 93 tests and takes about 40 s. Areas covered:

- data loading and preprocessing
- missing values and invalid dates
- recovered lead time
- geography and compatibility
- assumptions validation
- the symmetric cost model
- risk scores
- the prediction pipeline and selection rule
- optimization constraints (compatibility, threshold, capacity, infeasibility)
- all five scenarios
- persistence on a temporary database (idempotency, status workflow, additive migration, rebuild guard)
- every dashboard page rendered headlessly

Edge cases include empty input, missing columns, invalid dates, unknown factories, destinations and products,
infeasible allocations, and invalid or negative values. The test suite never writes to `data/nassau.db`.

## 11. Dataset

There are 10,194 order lines with 18 columns and no missing cells:

- 8,549 distinct Order IDs (each embeds the customer and product)
- 5,044 customers
- 15 products in 3 divisions
- 59 US states and Canadian provinces, in 4 regions (Atlantic, Gulf, Interior, Pacific)
- 4 ship modes

Chocolate is 97% of order lines.

## 12. Methodology

**Cost model.** The same formula applies to every factory, including the current one:

- revenue = historical sales
- production cost = historical cost × (1 at the current factory, or the alternative-factory multiplier elsewhere)
- freight = units × centroid distance × freight rate
- estimated profit = revenue − production − freight
- profit impact = estimated profit (alternative) − estimated profit (current)

**Lead time.** Estimated lead time = processing (model prediction on the product's actual order lines) +
transit (distance × transit-days assumption).

**Objective (balanced).** The current factory scores 0. Every other option scores:

```
score = w_profit × profit gain (% of revenue)
      + w_speed  × lead-time gain (%)
      − w_risk   × risk increase (points)
      − reassignment penalty
```

**Constraints.** The model is solved as an exact assignment with `scipy.optimize.milp`, under these constraints:

- one factory per product;
- incompatible factories are excluded (default rule: a factory may take a product only if it already makes that
  product's division);
- moves below the minimum-profit threshold are excluded;
- optional capacity: the factory's current units × (1 + headroom).

Keeping the current factory is always feasible. Infeasible settings are reported, not crashed on.

**Scenarios** (all use the same candidate table and assumptions):

- *current*
- *alternative* (forced best compatible move)
- *distance* (nearest compatible factory)
- *cost* (maximum estimated profit)
- *balanced* (the recommendation objective)

**Risk.** Five components, each on a 0–1 scale:

- model uncertainty
- data quality
- missing information
- compatibility
- operational

The overall score is their mean (Low < 0.35 ≤ Medium < 0.60 ≤ High). These are documented heuristics, **not probabilities**.

## 13. Results (current data and default assumptions)

**Lead-time model** (target: recovered lead time; chronological 70/15/15 split; selected on validation MAE):

| Model | CV MAE (train) | Validation MAE | Test MAE | Test R² |
|---|---:|---:|---:|---:|
| Global mean (baseline) | 1.331 | 1.361 | 1.381 | −0.003 |
| **Per-ship-mode mean (baseline) — selected** | 0.811 | 0.828 | 0.807 | 0.698 |
| Linear regression | 0.823 | 0.830 | 0.812 | 0.699 |
| Random forest | 0.833 | 0.846 | 0.817 | 0.697 |
| Gradient boosting | 0.839 | 0.844 | 0.819 | 0.696 |

Final model (refit on train+validation), evaluated once on the test set: MAE 0.806 days, RMSE 0.986, R² 0.698.
The ML models do not beat the per-ship-mode average, and permutation importance gives distance, factory, region
and the other features ≈ 0. The earlier models (test R² 0.01–0.04) predicted a target that mostly encoded the
date disguise, and selected the best model using the test set.

**Scenarios.** These are estimated over the historical demand period, at $0.0005 per unit-mile freight and equal
production cost at every factory:

| Scenario | Products moved | Est. profit impact | Est. lead-time change |
|---|---:|---:|---:|
| Current | 0 | $0 | 0 d |
| Best alternative (forced) | 15 | +$760 (+1.1%) | −0.08 d |
| Distance-based | 11 | +$1,690 (+2.4%) | −0.17 d |
| Cost-focused | 11 | +$1,690 (+2.4%) | −0.17 d |
| Balanced (recommendation) | 2 | +$8 | ≈ 0 d |

What the scenarios show:

- **Distance and cost give the same result** while production cost is equal everywhere, because freight then
  depends only on distance.
- **Most of the potential saving comes from moving the three Lot's O' Nuts Wonka Bars to Wicked Choccy's** (about
  +$500–630 each), because much of their demand is in the East.
- **The balanced objective does not recommend those three moves.** The added risk (an unverified production move,
  an extrapolated lead time and assumed costs) outweighs a roughly 2% estimated gain. Instead it recommends moving
  Fun Dip and Laffy Taffy, two very small products whose estimates rest on 3 and 10 order lines.

Changing the weights, penalty or assumptions on the What-If page shows how sensitive these conclusions are.

Clustering: destination demand k=2 (silhouette 0.51, East/West), route profiles k=6 (silhouette 0.48). Both are descriptive only.

## 14. Assumptions (all editable on Data Management / What-If)

| Assumption | Default | Notes |
|---|---|---|
| freight_cost_per_unit_mile | $0.0005 | Illustrative. The legacy value 0.015 (about $15/unit per 1,000 mi, 4× the selling price) is kept in the DB but unused |
| alt_factory_cost_multiplier | 1.00 | No factory cost data |
| transit_days_per_1000_miles | 2.0 | Rule of thumb (~500 truck miles/day); not supported by the data |
| factory_capacity_headroom_pct | −1 (off) | No capacity data |
| minimum_profit_threshold | $0 | A move must not reduce estimated profit |
| reassignment_penalty_points | 2.0 | Stands in for unknown switching costs |
| compatibility_rule | demonstrated_division | Derived from baseline assignments; unverified |
| weights (profit/speed/risk) | 0.4 / 0.4 / 0.2 | Presets: balanced, cost_focused, speed_focused |

## 15. Limitations

- The lead time is reconstructed from disguised dates. The rule is strongly supported but remains an inference.
- Each product has only ever been made at one factory, so all alternative-factory effects are counterfactual estimates.
- Distances are centroid straight lines; Canadian ones are coarse.
- All financial figures are estimates under assumptions, not realised savings.
- Seven products have very little history.
- "Orders" counts Order IDs (order+product), not customer baskets.
- Risk scores are heuristics, not calibrated probabilities.

## 16. Future improvements

- Real data: freight contracts or rate cards, factory production costs, capacities, and verified compatibility.
- Measured ship/delivery timestamps from the WMS/TMS, to replace the derived lead time.
- Customer-level geocoding (postal-code centroids) and road distances.
- Multi-period demand forecasting, plus capacity planning with switching costs.
- User authentication and audit for the recommendation workflow; migration to a server database.

---
Development history: `DEVELOPMENT_PROGRESS.md`. Full audit: `reports/PHASE1_AUDIT.md`.
