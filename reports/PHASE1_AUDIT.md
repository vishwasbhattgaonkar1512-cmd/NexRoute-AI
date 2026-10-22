# NexRoute AI — Phase 1 Audit

Date: 2026-10-22. Every number below was re-measured from the files in this folder during the audit.
Scratch analysis scripts were run from a temporary folder; nothing in the project was modified except this report.

---

## 1. Verified current state

| Item | Verified value |
|---|---|
| Raw rows | 10,194 (18 columns, **0 missing values**) |
| SQLite tables | 13 |
| `orders` / `order_items` / `customers` / `products` / `factories` | 8,549 / 10,194 / 5,044 / 15 / 5 |
| `model_registry`, `shipping_predictions`, `scenario_simulations`, `recommendations` | **all empty (0 rows)** |
| `data_quality_logs` | 1 row (and its `source_file` is a Linux path, `/home/claude/...`, from another machine) |
| Tests | 8 / 8 pass (≈20 s) — all are smoke tests on live data |
| Python env | `D:\nassau-candy-optimization\venv` (Python 3.10.1; pandas 2.3.3, sklearn 1.7.2, streamlit 1.65, SQLAlchemy 2.0.55, plotly 7.1) |
| Model results | Match the brief (GB test R² 0.038, RF 0.013, LR −0.014) |
| Version control | The project folder is **not its own git repo**; git sees `D:\` as the root and refuses to run ("dubious ownership"). There is currently no way to roll back edits. |

No separate problem-statement or dataset-dictionary document exists in the folder; the problem is described only in README / DEVELOPMENT_PROGRESS and `src/config.py`.

---

## 2. The date problem — solved forensically

### 2.1 What the existing docs say (confirmed)
- Order Date 2024-01-02 → 2025-12-31; Ship Date 2026-06-30 → 2030-06-28; raw gap 904–1,642 days.
- Ship mode explains **0.1 %** of the variance of the raw gap (η² = 0.001). The raw gap is meaningless as a lead time.

### 2.2 New evidence (not previously found)

1. **The Order ID year is the original order year.** Order IDs carry 2021–2024. Order IDs from 2021 *and* 2022 both have Order Date in 2024; 2023 and 2024 both have Order Date in 2025. So the Order Date year was **relabelled** (two original years folded onto one), while day and month were kept.
2. **Ship Date is the original ship date shifted by exactly 2,000 days.** Rebuild the original order date as *(Order ID year, Order Date month and day)*. Then for **every one of the 10,194 rows**:

   `Ship Date − rebuilt order date = 2,000 + k days`, where k is 0–8 (only 2 rows show 11)

3. **That remainder k behaves exactly like a real lead time:**

   | Ship Mode | k range (≈99 % of rows) | mean k | n |
   |---|---|---|---|
   | Same Day | 0 (523 rows), 1 (24 rows) | 0.04 | 547 |
   | First Class | 1–3 | 2.18 | 1,548 |
   | Second Class | 1–5 | 3.24 | 1,979 |
   | Standard Class | 3–7 | 5.00 | 6,120 |

   Ship mode explains **67 %** of the variance of k (η² = 0.674), against 0.1 % of the raw gap. A coincidence can't produce Same-Day = 0 for 96 % of Same-Day rows.
4. **Other evidence that agrees:** Ship Date correlates 0.994 with Row ID (rows are in original order sequence). Order ID year never decreases as Row ID increases. Order IDs embed Customer ID and Product ID, which match those columns 100 %. The record layout matches the widely used "Superstore" teaching dataset, with dates disguised.

### 2.3 What this means
- The dataset is **synthetic or disguised**. The Order Date year is altered, and Ship Date is offset by a constant.
- A **recovered lead time** (k) can be derived **from observed fields only**, with a single, testable rule and no invented values. It is still an *inference*, so it must be labelled "derived". It must never be presented as a measured delivery duration.
- **Recovered lead time has no relationship to geography:** corr(distance, k) = 0.002, and within each ship mode it is 0.005. The mean k barely differs by region (3.91–4.05) or factory (±0.13 days). **In this data, lead time depends on ship mode only. Factory location has no measurable effect.** This is the most important business finding. Historical data cannot show that moving a product to a nearer factory shortens delivery. Any lead-time benefit from reallocation can only come from an explicit, configurable **transit-time assumption** (e.g. extra days per 1,000 miles).

### 2.4 The current "lead_time_index" target is invalid
`lead_time_days_raw − median per ship mode` still correlates **0.63 with order date**, because the raw gap grows with time as an artifact of the date relabelling. As a result:
- The top features of the "best" model are `order_year_2025` (52 %), `order_year_2024` (31 %) and `order_dow` (12 %). **The model learned the date-disguise artifact**, not shipping behaviour.
- The chronological split makes things worse: the test set covers later dates where the artifact is larger.
- The near-zero R² does not show that "geography carries little signal". It shows that the target is mostly noise from the disguise.

---

## 3. Other data-quality findings

| # | Finding | Evidence | Severity |
|---|---|---|---|
| D1 | Canadian provinces have no coordinates | 200 rows (10 provinces) → `distance_miles = NaN`. These rows are silently dropped from training and can't be costed | High |
| D2 | **Config error:** `Fizzy Lifting Drinks` is listed as division "Other" in `config.py`; the data says "Sugar" | config vs. all 6 rows | Medium |
| D3 | Postal codes lost leading zeros | 449 US codes have 4 digits (e.g. New England 0xxxx) | Low |
| D4 | Order ID is *order + product*, not an order | 8,549 unique IDs for 10,194 lines; 1,373 IDs repeat (3,018 lines). The original baskets (prefix-year-customer + date) number ≈5,111 | Medium (affects "Total Orders" KPI semantics) |
| D5 | 313 rows are identical in every column except Row ID | possible duplicates *or* legitimate repeat lines — cannot be determined; must be flagged, not dropped | Low |
| D6 | 28 customers ship to >1 state (199 rows) | `customers` table stores one state per customer, but dashboards join geography via the customer → **misattributes 199 rows' geography**. Geography belongs on the order | Medium |
| D7 | Extreme demand imbalance | Chocolate 9,844 rows; Other 310; **Sugar 40**. Five products have ≤ 6 rows (Gobstopper 3, Fun Dip 3, Hair Toffee 4, Nerds 4, Fizzy 6) | High for confidence |
| D8 | Unit price and unit cost are constant per product | 1 unique price & 1 unique cost per product; Gross Profit = Sales − Cost exactly | Info — no factory-specific cost data exists |
| D9 | No capacity, freight-rate, factory-cost or compatibility data in the source | — | Must stay configurable assumptions |

---

## 4. Module-by-module audit

### preprocessing.py
- ✅ Correct date format (dd-mm-yyyy), raw data never modified, critical issue logged.
- ❌ Target `lead_time_index` is invalid (see 2.4).
- ❌ `DATA_QUALITY_LOG` is a module-level list: it keeps growing on every `run_pipeline()` call in the same process (dashboard / tests duplicate entries).
- ❌ No validation of required columns or empty input. No checks for Canadian rows, postal codes, duplicates, or config/data division mismatches.
- ❌ `df.apply` row-wise distance (slow); no caching. The pipeline re-reads the CSV in every module (clustering, training, DB build).

### prediction_engine.py
- ❌ **Model selected on test R²** (line 87) — the test set is used for selection, which leaks.
- ❌ `order_year` / `order_dow` / `order_month` features encode the date artifact.
- ❌ No naive baseline (mean / per-ship-mode mean) for comparison; no train metrics; no time-series CV.
- ❌ Line 117 bug: uses leftover loop variable `name` (works only by coincidence).
- ❌ Feature importance uses impurity importance on one-hot columns (biased); no permutation importance.
- ❌ No versioning or timestamps; `model_registry` never written. Overwrites artifacts in place.
- ⚠️ Structural limitation: factory is fully determined by product (each product has one factory). The model has **never seen** a product made at another factory, so counterfactual "what if factory X" predictions are extrapolation by construction.
- ❌ Cannot run as documented (`python src/prediction_engine.py` → `ModuleNotFoundError: No module named 'src'`). Must use `python -m src.prediction_engine`.

### scenario_simulator.py
- ❌ `eligible_factories` docstring says "compatible within same Division", but the code marks **all 5 factories eligible for every product** and never uses division.
- ❌ Predictions hard-code `order_year=2025, month=6, dow=2`.
- ❌ `lead_time_reduction_pct` divides by |baseline index|, which is near 0 → percentages explode.
- ❌ Loads model + meta from disk on every call; `confidence_label` reloads joblib + JSON for every factory (≈75 disk loads per optimization run).
- ❌ Only one representative (state, units, sales) per product, not the product's real demand mix.

### profit_engine.py
- ❌ **Asymmetric comparison (major bug):** current-factory profit = Sales − Cost (no shipping), alternative = Sales − Cost − shipping. Every alternative is therefore *guaranteed* to look worse. **This is the main reason all 15 products say KEEP_CURRENT.** The README's statement that this is "a legitimate output of the constraints" is incorrect.
- ❌ No cost totals, savings %, or scenario-level aggregation; uses mean order rather than total demand.

### optimization_engine.py
- ❌ DEVELOPMENT_PROGRESS claims "SciPy linear_sum_assignment + constraints"; **the code does not use SciPy at all**. It is a per-product weighted score.
- ❌ Scores use the invalid lead-time index and the biased profit; tanh-normalisation of an exploding percentage.
- ❌ No capacity constraint option; no infeasibility handling; no explicit objective statement; DB settings (`optimization_settings`, `financial_assumptions`) are ignored in favour of `config.py`.
- ❌ Ranking sorts by |lead-time improvement| even for KEEP decisions.

### confidence_engine.py
- ❌ "Support" = training rows per *factory*, not per product-factory pair. An alternative factory gets credit for rows of other products.
- ❌ Only two possible outputs ("unsupported"/"low"); no decomposition into model / data / compatibility / operational risk.

### geographic_engine.py / clustering_engine.py
- ✅ Haversine is correct (tested against Chicago–NYC).
- ❌ No Canadian centroids; no distance matrix; no coverage analysis; no destination clustering.
- ❌ Clustering uses the invalid index; `potential_congestion_indicator` is not supported by the evidence; silhouette over k=2–6 only.

### Database (models.py / connection.py / build_database.py)
- ❌ Four result tables are empty; no code writes to them.
- ❌ No ORM relationships; FK columns lack indexes (except `order_items.product_id`); no unique constraint on `order_items.source_row_id` or on `(product, factory, assignment_type)`; SQLite foreign-key enforcement is not switched on (`PRAGMA foreign_keys`).
- ❌ `ModelRegistry` lacks validation/test split metrics, a target definition and feature list; `Recommendation` lacks a decision, a status-change timestamp and a run ID; `ShippingPrediction` has no destination state or interval.
- ⚠️ **`build_database.py` deletes all orders / customers / order items / DQ logs on every run, even without `--rebuild`.** README tells users to run `--rebuild`. Both are destructive. I have not run either.
- ❌ `python src/build_database.py` fails (`No module named 'database'`); needs `python -m src.build_database`.
- ❌ `datetime.utcnow` is deprecated.

### Dashboard (app + 8 pages)
- ❌ **Pages 2 & 3 offer regions "East/West/Central/South"**, which don't exist in the data (it has Pacific / Atlantic / Interior / Gulf). The model one-hot silently ignores them. The region should be derived from the chosen state anyway.
- ❌ **Page 3 sliders do nothing:** cost multiplier and shipping-rate values are never passed to the simulator. Its "Save this comparison" button is nested inside another button, so it can never fire. Units, sales and cost are hard-coded (3 / $14 / $5) for every product.
- ❌ Pages 4, 5 and 8 each re-run the full optimization on load; nothing is persisted.
- ❌ Page 1 shows "Average RAW lead time (days) ≈ 1,321" as a KPI, which is misleading even with its caption. "Total Orders" counts order+product IDs.
- ❌ Page 6 has no distances, routes, coverage or clusters. Page 8 has exports only, with no DB stats, DQ report or missing-value view.
- ❌ Page 7 has no validation-vs-test view or model metadata, and no explanation that its importance is the artifact.
- ❌ `app.py` uses a cwd-relative `os.path.exists("data/nassau.db")`. No page handles missing artifacts gracefully. Navigation lists 7 modules (Data Management missing).

### Tests
- 8 smoke tests that hit the real CSV + DB + models. No unit tests, no edge cases (empty data, missing columns, invalid dates, unknown factories, infeasible allocations, negative inputs), and no DB persistence tests. They use a non-existent region "South".

### Documentation
- Outdated or wrong commands: `src/train_models.py` doesn't exist; `python src/*.py` invocations fail; "6 pages"; the SciPy claim; `database/schema.py` doesn't exist; "Honest results" contains the incorrect KEEP explanation.

### Security / reliability
- No secrets or credentials; ORM queries (no SQL-injection surface). Main reliability risks: the destructive DB build, no version control, and the global mutable DQ log.

---

## 5. Proposed architecture & plan

```
raw CSV (read-only)
  └─ src/data_validation.py   NEW  schema checks, date forensics, DQ report (pure functions, testable)
  └─ src/preprocessing.py           cleaning + features; targets:
        lead_time_days_raw            (observed, flagged unusable)
        lead_time_recovered_days      (derived via rule in 2.2, labelled "derived")
  └─ src/geographic_engine.py       + Canadian province centroids, distance matrix, coverage
  └─ src/prediction_engine.py       val-based selection, naive baselines, TimeSeries CV,
                                    permutation importance, versioned artifacts + registry
  └─ src/assumptions.py        NEW  one place to load/edit assumptions (DB first, config fallback)
  └─ src/profit_engine.py           symmetric cost model: production + freight(current) vs (alternative)
  └─ src/confidence_engine.py       decomposed, documented scores (not probabilities)
  └─ src/optimization_engine.py     explicit objective; compatibility hard constraint;
                                    optional capacity via SciPy linprog; infeasibility reports
  └─ src/scenario_simulator.py      5 named scenarios under one shared assumption set
  └─ src/persistence.py        NEW  save/load predictions, scenarios, recommendations, registry, DQ
database/                           additive schema changes only (new columns/tables, indexes)
dashboard/                          8 pages, shared helpers (dashboard/common.py), cached loaders
tests/                              unit + edge-case + integration suites
```

Sequence: Phases 3 → 10 as in the brief. Each phase ends with a summary, files changed and test results.

**Decisions needed before Phase 3 (see summary in chat).**
