# Development Progress — NexRoute AI

Last updated: 2026-10-22. Git history (project-level repo, created 2026-10-22) has one commit per phase.

## Status

| Phase | Status | Main files |
|---|---|---|
| 1. Audit | ✅ Done | `reports/PHASE1_AUDIT.md` |
| 2. Architecture | ✅ Done | audit §5, README §3 |
| 3. Data engineering | ✅ Done | `src/data_validation.py` (new), `src/preprocessing.py`, `src/geographic_engine.py`, `src/config.py` |
| 4. Machine learning | ✅ Done | `src/prediction_engine.py`, `src/model_components.py` (new), `models/trained/<version>/` |
| 5. Optimization, geography, cost | ✅ Done | `src/optimization_engine.py`, `src/profit_engine.py`, `src/compatibility.py` (new), `src/assumptions.py` (new), `src/clustering_engine.py` |
| 6. Scenarios, risk, recommendations | ✅ Done | `src/scenario_simulator.py`, `src/confidence_engine.py` |
| 7. Database | ✅ Done | `database/models.py`, `database/migrations.py` (new), `database/connection.py`, `src/persistence.py` (new), `src/build_database.py` |
| 8. Dashboard | ✅ Done | `dashboard/app.py`, `dashboard/common.py` (new), `dashboard/pages/01–08` |
| 9. Testing | ✅ Done | `tests/` — 93 tests passing |
| 10. Documentation | ✅ Done | `README.md`, this file |

## Key decisions

1. **Lead-time target: recovered lead time.** The Phase 1 forensics showed two things. The Order Date year was
   relabelled (the Order ID year is the original year), and Ship Date is shifted by exactly 2,000 days. Removing
   both gives a 0–8 day value that matches ship-mode semantics. It is used as the ML target, labelled "derived"
   everywhere. The raw gap is kept for audit only. The previous target, `lead_time_index`, is kept in the database
   but no longer used, because it mostly encoded the date disguise.
2. **Model selection on validation only**, with a parsimony rule (a simpler model wins within 1%). The
   per-ship-mode average was selected, because no ML model beat it.
3. **Symmetric cost model.** The old profit engine charged freight only to alternative factories, so every
   alternative lost by construction. This is fixed.
4. **Exact optimization.** The SciPy `milp` assignment handles compatibility, the profit threshold and an
   optional capacity limit. Infeasibility is reported.
5. **Additive database changes only.** The user approved this approach. Backup:
   `data/nassau_backup_2026-10-22_pre_phase7.db`. Every original row was preserved. The four previously empty
   tables (model_registry, shipping_predictions, scenario_simulations, recommendations) are now written to by
   real workflows.
6. **New assumption names where the meaning or scale changed.** `freight_cost_per_unit_mile` and
   `reassignment_penalty_points` were added, so the legacy database rows were not overwritten.
7. **Config fix:** Fizzy Lifting Drinks division "Other" → "Sugar" (as in all 6 source rows).

## Bugs fixed (from the audit)

- Model selected on test R²; leftover-loop-variable bug in the diagnostics export; disguised-date features in the model.
- Asymmetric profit comparison; percentage blow-up dividing by a near-zero index.
- Eligibility docstring said "same division" while the code allowed every factory.
- The What-If sliders were never passed to the simulator; the nested "Save" button could never fire; the region
  list contained regions that are not in the data.
- Pages 4, 5 and 8 re-ran the optimization on every load (results are now cached and persisted).
- The global data-quality log grew on every pipeline call; the data-quality log path pointed to another machine.
- The documented commands (`python src/...`, `src/train_models.py`) did not run.
- `build_database.py` deleted order data on every run; `--rebuild` had no safeguard.
- No Canadian coordinates (200 rows had no distance).
- Customer geography was misattributed for 28 multi-state customers (geography now comes from the order).

## Verified commands

```
python -m src.prediction_engine
python -m src.build_database
python -m src.clustering_engine
python -m pytest -v
streamlit run dashboard/app.py
```

## Remaining limitations

See README §15. The main ones:

- The lead time is derived, not measured.
- Alternative-factory effects are counterfactual.
- Every cost, capacity and compatibility input is an assumption.
- Seven products have very little history.
