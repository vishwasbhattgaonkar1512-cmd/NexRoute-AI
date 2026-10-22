# Executive Summary — Data Verification

Every number in `NexRoute_AI_Executive_Summary_Government_Stakeholders.md` (and the PDF) is listed here with its source.

**How values were verified.** All values were extracted on 2026-10-22 by a read-only script that:

- loads the raw CSV through the project pipeline (`src/preprocessing.run_pipeline`);
- loads the active model metadata (`models/trained/lt-20261022-215253/meta.json`);
- re-runs the project's scenario simulator and optimizer with the saved default assumptions;
- reads the SQLite database in read-only mode.

**Confirmation that nothing was modified.** The database checksum (md5 `e81b9843…6034ab2`) was identical before and
after extraction. No project source code, data, model or database was modified to produce this summary.

**Value types:**

| Type | Meaning |
|---|---|
| **O** | Observed in the source file |
| **D** | Derived by a stated rule |
| **E** | Estimated under analyst assumptions |

## 1. Dataset at a glance

| Value used | Verified value | Type | Source / method |
|---|---|---|---|
| 10,194 order records | 10,194 rows | O | `data/raw/nassau_candy_distributor.csv`, row count (all rows retained after cleaning) |
| 8,549 distinct order IDs | 8,549 | O | Unique `Order ID` |
| 5,044 customers | 5,044 | O | Unique `Customer ID` |
| 15 products | 15 | O | Unique `Product Name` |
| 3 divisions | Chocolate 9,844 · Other 310 · Sugar 40 | O | `Division` counts |
| 5 factories | 5 | O | `src/config.py` FACTORIES |
| 59 destinations | 59 | O | Unique `State/Province` |
| 49 US states incl. DC | 49 (DC present) | O | `src/data_stats.headline_stats` (destinations not in the Canadian province list) |
| 10 Canadian provinces | 10 (200 lines) | O | As above |
| 4 regions | Pacific 3,253 · Atlantic 2,986 · Interior 2,335 · Gulf 1,620 | O | `Region` counts |
| 4 shipping modes | Standard 6,120 · Second 1,979 · First 1,548 · Same Day 547 | O | `Ship Mode` counts |
| Total sales $141,784 | $141,783.63 | O | Sum of `Sales` |
| Gross profit $93,443 | $93,442.80 | O | Sum of `Gross Profit` (= Sales − Cost; excludes freight) |
| 0 missing values | 0 | O | Missing-cell count on the raw file |

## 2. Key data findings

| Value used | Verified value | Type | Source / method |
|---|---|---|---|
| Chocolate 96.6% | 96.567% | O | 9,844 / 10,194 |
| Other 3.0%, Sugar 0.4% | 3.04%, 0.39% | O | 310 and 40 / 10,194 |
| 7 of 15 products < 30 lines | 7 (Gobstopper 3, Fun Dip 3, Hair Toffee 4, Nerds 4, Fizzy Lifting Drinks 6, Laffy Taffy 10, SweeTARTS 10) | O | Lines per product; threshold `MIN_SUPPORT_ROWS = 30` |
| Two factories handle 96.6% | Lot's O' Nuts 5,692 + Wicked Choccy's 4,152 = 9,844 lines | O | Baseline assignments applied to order lines |
| Factory locations: Arizona / Georgia | (32.88, −111.77) and (32.08, −81.09) | O | Factory coordinates in `src/config.py` |
| Raw date gap 904–1,642 days | 904–1,642 | O | Ship Date − Order Date |
| Original order years 2021–2024 | 2021, 2022, 2023, 2024 | O | Year embedded in `Order ID` |
| Ship dates moved by exactly 2,000 days | 2,000 | D | Estimated by `src/data_validation.estimate_date_shift` (most common gap for Same Day rows) |
| Reconstructed lead time 0–8 days for all but 2 lines | Range 0–11; only 2 lines = 11 days | D | `lead_time_recovered_days` value counts (0:523, 1:369, 2:1,362, 3:1,026, 4:2,837, 5:2,238, 6:1,205, 7:630, 8:2, 11:2) |
| Averages 0 / 2.2 / 3.2 / 5.0 days | Same Day 0.04 · First 2.18 · Second 3.24 · Standard 5.00 | D | Mean reconstructed lead time per ship mode |
| Ship mode explains ~67% | η² = 67.4% | D | Share of variance explained by ship mode |
| Distance correlation 0.006 | 0.0059 (all rows); 0.0021 (US only) | D | Pearson correlation, distance (current factory → destination centroid) vs reconstructed lead time |
| 449 postal codes lost a leading zero | 449 | O | Data-quality report: 4-digit US postal codes |
| 313 possible duplicate lines | 313 | O | Rows identical except Row ID |
| 28 customers / 199 lines with >1 state | 28 / 199 | O | Data-quality report |
| 200 Canadian lines | 200 | O | Rows in Canadian provinces |

## 3. Shipping-time prediction

Source: `models/trained/lt-20261022-215253/meta.json`. The split is chronological: train 7,135 rows (2021-01-03 → 2024-03-09), validation 1,529 rows (→ 2024-09-11), test 1,530 rows (→ 2024-12-30).

| Value used | Verified value | Type | Notes |
|---|---|---|---|
| Overall average 1.38 days | Test MAE 1.381 | D | Candidate trained on train set only |
| Per-ship-mode average 0.81 (selected) | Test MAE 0.807; validation MAE 0.828 (lowest) | D | Selected on validation MAE |
| Linear Regression 0.81 | Test MAE 0.812 (validation 0.830) | D | |
| Random Forest 0.82 | Test MAE 0.817 (validation 0.846) | D | |
| Gradient Boosting 0.82 | Test MAE 0.819 (validation 0.844) | D | |
| Final MAE 0.806 days | 0.8065 | D | `final_test` (selected method refit on train + validation) |
| Final RMSE 0.986 days | 0.9859 | D | `final_test` |
| Final R² 0.698 (~70%) | 0.6983 | D | `final_test` |
| Whole-day ranges (e.g. Standard 4–7 days); every test value inside | Same Day 0–1, First 1–3, Second 2–5, Standard 4–7; measured coverage 100% of 1,530 | D | `src/prediction_engine.interval_coverage` on saved test predictions |
| "Location, factory, product type, order size, season added nothing measurable" | Permutation importance ≈ 0 for all features except Ship Mode | D | `models/evaluation/lt-20261022-215253/feature_importance.csv` |

## 4. Scenarios and recommendations

**Assumptions in use** (database defaults):

| Assumption | Value |
|---|---|
| Freight | $0.0005 per unit-mile |
| Alternative-factory cost multiplier | 1.0 |
| Transit | 2 days per 1,000 miles |
| Capacity | Off |
| Minimum profit impact | $0 |
| Reassignment penalty | 2 points |
| Eligibility rule | demonstrated_division |
| Weights (profit / speed / risk) | 0.4 / 0.4 / 0.2 |

**Source:** `src.scenario_simulator.simulate_scenarios()` and `src.optimization_engine.recommend()`. All solver statuses were "optimal".

| Value used | Verified value | Type |
|---|---|---|
| Current: 0 moved, $0, 0 days | 0 · $0.00 · 0.000 d | E |
| Best alternative: 15, +$760 (+1.1%), −0.08 d | 15 · +$760.00 · +1.095% · −0.079 d | E |
| Distance-based: 11, +$1,690 (+2.4%), −0.17 d | 11 · +$1,690.30 · +2.436% · −0.175 d (−0.1749) | E |
| Cost-focused: 11, +$1,690 (+2.4%), −0.17 d | Identical to distance-based | E |
| Balanced: 2, +$8, about 0 days | 2 · +$8.09 · +0.012% · −0.001 d | E |
| Percentages relative to $69,390 | Estimated current profit after assumed freight: $69,390.06 | E |
| Three Wonka Bar moves, $506–$633 each | Nutty Crunch +$529.78 · Fudge Mallows +$506.41 · Scrumdiddlyumptious +$633.00 (Lot's O' Nuts → Wicked Choccy's) | E |
| "Almost all of $1,690" | These three = $1,669.19 (98.8%) | E |
| ~150 miles closer to Georgia (about 1,150 vs 1,310 miles) | Volume-weighted distance: 1,309 → 1,152 · 1,312 → 1,165 · 1,319 → 1,156 miles (reductions 157, 147, 164) | D |
| Fun Dip → Secret Factory, +$1.67, 3 orders | +$1.674 · 3 lines · risk Medium | E |
| Laffy Taffy → The Other Factory, +$6.41, 10 orders | +$6.411 · 10 lines · risk Medium | E |
| Other 13 products: keep current factory | 13 × KEEP_CURRENT_FACTORY | E |

## 5. System facts

| Value used | Verified value | Source |
|---|---|---|
| Dashboard with eight pages | 8 page files in `dashboard/pages/` (plus a home page) | Project files |
| Results stored in a database | 15 SQLite tables; 2 saved runs | `data/nassau.db` (read-only) |
| Review statuses (proposed / under review / approved / rejected / implemented) | `RECOMMENDATION_STATUSES` | `database/models.py` |
| Free, open-source tools that run offline | Python, pandas, scikit-learn, SciPy, SQLite, Streamlit, Plotly | `requirements.txt` |

## 6. Corrections made while drafting

Two draft statements were removed because the data did not support them:

1. "the three **highest-volume** chocolate products". This is wrong: Milk Chocolate (2,137 lines) and Triple Dazzle
   Caramel (2,015) have more lines than Fudge Mallows (1,818) and Nutty Crunch (1,810). It was replaced with "three of
   the five Wonka Bar products".
2. "many of their customers are **in the East**". This is not supported: Pacific is the largest region for Lot's O' Nuts
   products (31.8% of units, Atlantic 29.0%). It was replaced with the verified volume-weighted distance comparison.

## 7. Information not available in the current project evidence

- **Author, institution and submission details:** not present in any project document, so they are omitted.
- **Real-world savings, actual delivery times, factory costs, freight rates, capacity, and compatibility:** not in the
  data. The summary labels them as assumptions or estimates throughout.
- **Government deployment or partnership:** none exists. The summary states that NexRoute AI is a prototype built on a
  private distributor's data.
- **Environmental (emissions) effects:** not measured. They are mentioned only as a possible application area ("could
  be reduced"), with no figure.

## 8. Conflict with `reports/research_paper/` (not used as a source)

A research paper (`reports/research_paper/NexRoute_AI_Research_Paper.md` and `.pdf`) is present in the project. It
was **not** used as a source for this executive summary, because it reports **superseded results** that contradict the
current, verified project state:

| Research paper states | Current verified value (used in this summary) | Reason for the difference |
|---|---|---|
| Best model Gradient Boosting, test R² 0.038, predicting a "relative lead-time index" | Per-ship-mode average, test R² 0.698, predicting reconstructed lead time | The paper reflects the model before the date forensics replaced the target |
| 0 reallocations (all 15 keep) | 2 recommended moves (Fun Dip, Laffy Taffy) | The paper reflects the earlier cost model, which charged freight only to alternatives |
| Division counts Other 316 / Sugar 34 | Other 310 / Sugar 40 | Earlier configuration listed Fizzy Lifting Drinks (6 lines) as "Other"; the data says "Sugar" |
| Region counts, e.g. Pacific 3,260 | Pacific 3,253 | The paper uses the customer's first state; the current project uses each order's destination |
| Distance correlation r = 0.015 (with the raw date gap) | 0.006 (with reconstructed lead time) | Different variables |
| 200 missing distances (Canadian) | 0 missing (approximate province centroids added) | Canadian centroids added later |

**Recommendation:** update the research paper from the current project state before submitting both documents
together. Otherwise the two deliverables will disagree.
