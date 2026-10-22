# NexRoute AI — Final Project Summary

**Intelligent Factory Reallocation & Shipping Optimization Platform** for Nassau Candy Distributor.
A local, offline decision-support prototype. Status: complete and verified (109/109 tests). See FINAL_QA_REPORT.md.

## Problem and objectives
Nassau Candy makes 15 products at 5 factories and ships them to customers across the US and Canada. Each product is
made at exactly one factory today. The objective is to decide, product by product, whether to **keep or reallocate**
production, and to do so with:

- transparent cost and profit estimates;
- the lead-time effect;
- a risk and confidence assessment;
- what-if scenarios;
- an explanation management can act on.

## How to read the numbers
| Label | Meaning | Examples |
|---|---|---|
| **Observed** | Taken from the source file unchanged | Sales, units, cost, destinations, ship mode |
| **Derived** | Computed from observed data by a stated rule | Recovered lead time (0–8 days); centroid distances |
| **Estimated** | Depends on analyst assumptions; never realised savings | Freight cost, profit impact, transit time, scenario savings |

## Architecture
Raw CSV (read-only) → **data validation and date forensics** → **preprocessing** →

- **lead-time model**
- **geography**
- **symmetric cost model**
- **risk engine**

→ **MILP optimizer** and **5-scenario simulator** → **SQLite persistence** → **Streamlit dashboard** (home + 8 pages).

Stack: Python 3.10, pandas, NumPy, scikit-learn, SciPy, SQLAlchemy/SQLite, Streamlit, Plotly, pytest.

## Dataset
- 10,194 order lines, 18 columns, no missing cells
- 15 products, 5 factories, 5,044 customers
- 59 destinations: 49 US states including DC, and 10 Canadian provinces
- Chocolate is 96.6% of lines
- 7 products have fewer than 30 lines

## Key data finding
The dates are disguised:

- The Order Date year was relabelled. The Order ID carries the real year (2021–2024).
- Ship Date was shifted by exactly 2,000 days.

Undoing this recovers a 0–8 day lead time that matches ship mode (Same Day ≈ 0 … Standard ≈ 5). Ship mode explains
67% of its variance. Distance has **no measurable effect** on lead time (correlation 0.006).

## Machine learning
- Target: the recovered lead time.
- Method: chronological 70/15/15 split, time-ordered cross-validation, model selected on validation MAE, test set used once.
- Result: the **per-ship-mode average is as good as any ML model** (validation MAE 0.828 vs 0.830 for the best ML
  model), so it is the active model.
- Final test: MAE 0.806 days, RMSE 0.986, R² 0.698.
- Whole-day prediction ranges are nominally 90%; their measured test coverage is 100%.

## Optimization and scenarios
**Balanced score** (current factory = 0):

- \+ profit gain, weighted
- \+ lead-time gain, weighted
- − risk increase, weighted
- − reassignment penalty

**Solver:** exact assignment with SciPy `milp`. Constraints:

- one factory per product
- eligibility rule (default: the factory already makes that division)
- minimum profit
- optional capacity

The solution was independently confirmed by brute force.

Estimated results over the historical demand period, under default assumptions:

| Scenario | Moves | Est. profit impact |
|---|---|---|
| Current | 0 | $0 |
| Forced best alternative | 15 | +$760 |
| Distance-based | 11 | +$1,690 (+2.4%) |
| Cost-focused | 11 | +$1,690 (+2.4%) |
| **Balanced (recommendation)** | **2** | **+$8** |

**Interpretation:**

- The biggest possible saving is moving three Wonka Bars from Lot's O' Nuts (Arizona) to Wicked Choccy's (Georgia), at about +$500–630 each.
- The balanced objective judges that roughly 2% estimated gain too small for the risk involved: an unverified production move, an extrapolated lead time, and assumed costs.
- It therefore recommends moving only Fun Dip and Laffy Taffy. Those estimates are weak (3 and 10 order lines).
- All of this can be explored on the What-If page.

## Financial assumptions (editable; none come from the data)
| Assumption | Default |
|---|---|
| Freight | $0.0005 per unit-mile |
| Alternative-factory cost multiplier | 1.0 |
| Transit | 2 days per 1,000 miles |
| Capacity | Off |
| Minimum profit impact | $0 |
| Reassignment penalty | 2 points |
| Eligibility | Demonstrated division |

## Risk methodology
Five 0–1 components:

- model uncertainty
- data quality
- missing information
- compatibility
- operational

The overall score is their mean (Low < 0.35 ≤ Medium < 0.60 ≤ High). These are documented heuristics, **not probabilities**.

## Database
SQLite, 15 tables:

- master and order data
- optimization runs
- recommendations, with status history
- shipping predictions and scenario simulations
- model registry
- assumptions and settings
- versioned data-quality logs

Schema changes are additive only. A backup was taken before the change, and every original row was preserved. An
integrity check reports orphan records (currently 0). Three `run_id` foreign keys are enforced in code rather than by
the migrated database.

## Dashboard modules
1. Executive Dashboard
2. Factory Optimization
3. What-If Analysis
4. Recommendations (with review workflow)
5. Risk & Impact
6. Factory Map
7. Model Analytics
8. Data Management

## Testing
109 automated tests, all passing:

- unit and edge-case tests
- persistence on temporary databases
- every page rendered
- interactive workflows on a database copy
- regression tests for every QA fix

## Limitations
- The lead time is derived, not measured.
- Alternative-factory effects are counterfactual.
- Costs, capacity and compatibility are assumptions.
- Distances are approximate centroid distances.
- Product history is sparse for 7 products.
- The prediction ranges are wide.
- Visual browser review is still to be done manually.

## Future scope
- Real freight, cost, capacity and compatibility data from the business.
- Measured shipment timestamps.
- Postal-code geocoding and road distances.
- Demand forecasting and multi-period planning.
- Authentication and audit for approvals.
- A server database.

## Run it
```
cd nassau-candy-optimization
..\venv\Scripts\Activate.ps1          (or: source ../venv/Scripts/activate)
python -m pytest -v                   # 109 tests
streamlit run dashboard/app.py        # http://localhost:8501
```
Optional rebuild of derived artifacts: `python -m src.prediction_engine`, then `python -m src.build_database` (safe; never deletes).
