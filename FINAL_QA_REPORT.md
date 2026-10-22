# NexRoute AI — Final QA Report

Date: 2026-10-22 · Scope: independent verification of the completed project, fixes for issues found, and final acceptance.
Rule followed throughout: no destructive operations. Nothing was dropped, rebuilt or deleted, and nothing was pushed or deployed.

## 1. Overall status

**Accepted, with one open item.** All documented functionality was independently verified. Five issues were found and
fixed, and 109/109 tests pass. The production database, raw data, model backups and git history are unchanged or intact.
**Open item:** the visual layout has **not** been inspected in a browser, because no browser control was available.
Section 8 has the manual checklist.

## 2. How verification was done (independent of the project's own tests)

| Check | Method | Result |
|---|---|---|
| Test suite | `python -m pytest -v` | 93/93 at start; **109/109** after fixes |
| Lead-time target | Recomputed from the raw CSV with a separate formula | Identical for all 10,194 rows |
| Cost model | Freight, production cost and revenue recomputed for all 75 product–factory options with an independent Haversine | 0 mismatches; current factory is charged freight (symmetric); profit impact = alternative − current exactly |
| Optimizer (balanced, no capacity) | Brute-force enumeration of every feasible allocation | Same assignment and objective (4.8973) |
| Optimizer (cost, 10% capacity) | Brute-force enumeration with capacity check | Same assignment and objective (+$292.18); capacity respected; current allocation feasible |
| Scenario consistency | Every scenario row compared with the shared candidate table | Max difference 0.0; identical assumptions |
| ML metrics | MAE / RMSE / R² recomputed from saved test predictions | 0.8065 / 0.9859 / 0.6983, identical to stored values |
| ML method | Split dates, feature list, selection rule | Train 2021-01-03→2024-03-09, validation →2024-09-11, test →2024-12-30 (no overlap); no disguised-date features; selected on validation MAE only |
| Database | Read-only `integrity_check`, `foreign_key_check`, duplicates, counts | OK; 0 violations; 0 duplicate source rows; counts match docs |
| Dashboard interactions | Streamlit AppTest driving widgets on a **copy** of the database | All workflows work (section 4) |

## 3. Verified functionality

- **Data:**
  - loading and schema validation (empty input and missing columns rejected)
  - missing-value report
  - date parsing
  - date forensics and lead-time recovery
  - 12-item data-quality report
  - Canadian centroids
- **ML:**
  - baselines plus LR / RF / GB models
  - time-ordered cross-validation
  - parsimony selection rule
  - versioned artifacts and the active-model pointer
  - registry row in the database
  - whole-day prediction ranges, with measured coverage
- **Optimization:**
  - one factory per product
  - ineligible factories excluded under all three eligibility rules
  - profit threshold, reassignment penalty and capacity constraints
  - infeasibility reported (not crashed on)
  - every product has a written explanation
- **Scenarios:** 5 scenarios on one shared table; product-level detail; saved to the database.
- **Risk:** five documented 0–1 components, levels and confidence labels; labelled as heuristics, not probabilities.
- **Persistence:**
  - runs, recommendations, predictions and scenarios
  - status workflow with history and validation
  - versioned data-quality reports (old ones kept)
  - assumptions and settings
  - duplicate saves are a no-op
- **Exports:** 4 download buttons present (cleaned dataset, data-quality report, recommendations, scenarios). Their content comes from the same verified data functions.

## 4. Interactive workflows tested (temporary database copy)

These were tested headlessly; the production database checksum was identical before and after.

- Factory Optimization: all 15 products selected.
- What-If:
  - freight rate change, capacity toggle, eligibility rule, weight preset
  - all 5 scenarios selected in the detail picker
  - save to database (+1 run)
- Recommendations:
  - "Run optimization now & save" (+1 run)
  - switching between saved runs
  - decision filter (row counts match the database) and risk filter
  - status update with note, written to history
- Risk & Impact: view toggle.
- Factory Map: product selector; cluster k = 2, 5, 8.
- Model Analytics: importance model toggle.
- Data Management:
  - save defaults: value saved; an invalid value is rejected with an error message
  - safe refresh: nothing deleted; data-quality report added; caches cleared
  - a saved default appears on What-If without restarting

## 5. Issues found and fixed

| # | Issue | Severity | Fix | Verified by |
|---|---|---|---|---|
| 1 | The "90%" prediction range covered only **59%** of test cases (Same Day 6%). Real-valued edges such as 0.011 days excluded whole-day outcomes | High (misleading claim) | Edges converted to whole days (snapped within 0.1 d, otherwise rounded outward); **measured** coverage computed and shown on Risk & Impact and Model Analytics. Measured test coverage is now **100%**, wider than nominal and reported as such | `tests/test_intervals.py` (5 tests, including Same Day) |
| 2 | Hard-coded statistics on pages: "7 products", "97%", "~70%", "0.002" | Medium | `src/data_stats.py` computes them from the data. Actual values: 7 of 15 sparse; Chocolate 96.6%; ship mode explains 67% of variance (selected model test R² 0.70); distance correlation 0.006 (0.002 US-only); scope 49 US states incl. DC + 10 Canadian provinces | `tests/test_data_stats.py` (4 tests, including a guard against reintroducing the figures) |
| 3 | Three dropdowns (scenario detail, saved run, decision filter) could not be driven by headless tests | Low (testability) | Plain-label mapping; same appearance in the browser | `tests/test_dashboard_interaction.py` |
| 4 | Refresh / save cleared only the data cache, leaving the model and context stale until restart | Medium | `clear_caches()` also clears the resource cache, model loader and pipeline cache | 3 regression tests |
| 5 | `run_id` foreign keys (recommendations, scenario_simulations, shipping_predictions → optimization_runs) are declared in code but **not enforced** by the migrated SQLite database | Medium (documentation was inaccurate) | No table rebuild (as instructed). Added `persistence.integrity_report()`, shown on Data Management → Database. Production: **0 orphan rows**, 0 FK violations. Documented in README §15 | 2 tests (orphans detected; a fresh schema enforces the FK) |

Also fixed: some edited files had been rewritten with Windows (CRLF) line endings; they were normalised back to LF so diffs show only the real changes.

## 6. Test results

```
python -m pytest -v      →  109 passed in 44.3 s
  test_data_validation 18 · test_engines 31 · test_model_and_optimization 19 · test_persistence 8
  test_pipeline 8 · test_dashboard 9 · test_dashboard_interaction 7 · test_intervals 5 · test_data_stats 4
```

Integrity checks run around the final test run:

| Item | Checksum / result | Status |
|---|---|---|
| `data/nassau.db` | md5 `e81b9843…6034ab2` | Unchanged before and after |
| `data/raw/nassau_candy_distributor.csv` | md5 `caf7903f…065a1` | Unchanged; identical to the baseline commit |
| `data/nassau_backup_2026-10-22_pre_phase7.db` | — | Unchanged |
| `models/trained/**` and `models_backup_before_retrain/**` (14 files) | — | Unchanged; legacy and backup models identical to the baseline commit |
| Git history | 11 commits before this report's commit | `git fsck` clean |
| `streamlit run dashboard/app.py` | Health endpoint `ok`; home + 8 page routes return HTTP 200 | Starts successfully |

## 7. Remaining limitations (unchanged by QA)

- **Lead time:** it is derived from disguised dates by a stated, tested rule. It is not a measured delivery time.
- **Alternative factories:** each product was only ever made at one factory, so alternative-factory effects are counterfactual estimates.
- **Assumptions:** freight rate, production cost at other factories, transit time, capacity and compatibility are all analyst assumptions. Financial figures are estimates, not realised savings.
- **Prediction ranges:** with only a few whole-day values per ship mode, the "nominal 90%" range has 100% measured coverage. It is honest but wide.
- **Foreign keys:** see issue 5 (enforced in code, not by the existing database).
- **Not verified in a browser:** visual layout, chart readability, label overlap, responsive behaviour, and the actual file downloads (only the presence of the buttons was tested).

## 8. Manual browser checklist (to be done by a person)

Start: `streamlit run dashboard/app.py`, then open http://localhost:8501. Check each item and note any problem.

**All pages**
- [ ] Sidebar navigation lists Home + 8 pages in order
- [ ] No text clipped or overlapping
- [ ] Charts have readable axes
- [ ] Tables scroll instead of overflowing the page
- [ ] Light and dark themes both readable (Settings → Theme)

**Page by page**
1. [ ] Executive Dashboard: red data-quality banner; KPI tiles align; the sales-by-product bar labels are readable.
2. [ ] Factory Optimization: switch products; hatched (ineligible) bars are visible; the expander shows the risk breakdown.
3. [ ] What-If: move the sliders and the tables update; the capacity checkbox reveals its slider; "Save" shows a success message.
4. [ ] Recommendations: "Run optimization now & save"; change a status, click Update, and the history table appears.
5. [ ] Risk & Impact: the faceted risk chart is readable in both views; the coverage tile reads 100.0%.
6. [ ] Factory Map: the map renders factories as coloured squares and demand circles; route lines toggle; k slider; the distance matrix scrolls.
7. [ ] Model Analytics: model table, validation-vs-test chart, importance toggle, residual charts, coverage table.
8. [ ] Data Management:
   - every tab opens
   - the date-forensics chart shows days 0–8
   - uploading `data/raw/nassau_candy_distributor.csv` in Validation reports "Schema OK"
   - each export button downloads a non-empty file
   - the Integrity check shows 0 orphans

## 9. Files modified in this QA round

| Type | Files |
|---|---|
| New | `src/data_stats.py`; `tests/test_intervals.py`, `tests/test_data_stats.py`, `tests/test_dashboard_interaction.py`; `FINAL_QA_REPORT.md`, `FINAL_PROJECT_SUMMARY.md` |
| Changed | `src/prediction_engine.py` (whole-day ranges, coverage), `src/persistence.py` (integrity report), `src/config.py` (assumption description text), `src/optimization_engine.py` (docstring) |
| Changed | `dashboard/common.py`, `dashboard/app.py`, `dashboard/pages/01, 03, 04, 05, 07, 08` |
| Changed | `README.md`, `DEVELOPMENT_PROGRESS.md` |

No changes were made to: raw data, the database schema or records (production), model artifacts, or backups.
