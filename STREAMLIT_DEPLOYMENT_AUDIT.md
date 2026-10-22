# Streamlit Deployment Audit — NexRoute AI

Date: 2026-10-22 · Repository: https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI (head `5e4c095`) ·
Entry point: `dashboard/app.py`

**Not deployed.** Nothing was deployed, and nothing was pushed or changed on GitHub. One configuration change
(`requirements.txt`, section 4) is prepared **locally for your review**: it is not committed and not pushed.

## 1. Verdict

**Ready to deploy on Streamlit Community Cloud, with Python 3.10 and the pinned `requirements.txt`.** The app needs no
secrets, no external services and no absolute paths. All of its files are in the repository.

**How this was verified:**

- A **fresh clone of the public GitHub repository** was installed into **clean** Python environments, which is what
  Streamlit Cloud does.
- The full test suite was run from that clone.
- Every page was rendered.
- The real server was started.

| Test (fresh clone, clean environment) | Python 3.10 + current `requirements.txt` | Python 3.10 + **pinned** `requirements.txt` (proposed) | Python 3.14 + current `requirements.txt` (newest libraries) |
|---|---|---|---|
| Install | ✅ 118 s | ✅ 98 s | ✅ 131 s |
| Resolved versions | pandas 2.3.3, numpy 2.2.6, scikit-learn 1.7.2, SciPy 1.15.3, SQLAlchemy 2.0.55, Streamlit 1.65.0 | Same (exact pins) | pandas **3.1.0**, numpy 2.5.4, scikit-learn **1.9.1**, SciPy 1.18.1, SQLAlchemy **2.1.6**, Streamlit 1.66.1 |
| Test suite | ✅ 109 / 109 | ✅ 109 / 109 | ❌ **1 failed**, 108 passed; about 25,700 warnings |
| Model loading | ✅ Clean | ✅ Clean | ⚠️ `InconsistentVersionWarning`: model saved with scikit-learn 1.7.2, loaded with 1.9.1 |

## 2. Application structure and page check

| Page | File | Cold render | Exceptions |
|---|---|---:|---:|
| Home | `dashboard/app.py` | 2.0 s | 0 |
| Executive Dashboard | `pages/01_Executive_Dashboard.py` | 3.3 s (builds model and data context) | 0 |
| Factory Optimization | `pages/02_Factory_Optimization.py` | 0.9 s | 0 |
| What-If Analysis | `pages/03_What_If_Analysis.py` | 0.4 s | 0 |
| Recommendations | `pages/04_Recommendations.py` | 0.4 s | 0 |
| Risk & Impact | `pages/05_Risk_Impact.py` | 0.6 s | 0 |
| Factory Map | `pages/06_Factory_Map.py` | 1.0 s | 0 |
| Model Analytics | `pages/07_Model_Analytics.py` | 0.6 s | 0 |
| Data Management | `pages/08_Data_Management.py` | 0.8 s | 0 |

The pages were rendered with Streamlit's headless `AppTest` from the fresh clone (Python 3.10). The interactive
workflows (buttons, forms, filters) are covered by `tests/test_dashboard_interaction.py`, which passed in the same
environment. A real `streamlit run` server from the clone reported healthy **about 2 s** after launch, and all 9 page
routes returned HTTP 200.

## 3. Files the app needs at run time (all committed)

| File | Used for | Read / write |
|---|---|---|
| `data/raw/nassau_candy_distributor.csv` (1.9 MB) | Pipeline, statistics, data-quality report | Read |
| `data/nassau.db` (5.1 MB) | Assumptions, settings, saved runs, recommendations, model registry, data-quality logs | **Read and write** |
| `models/trained/active_model.json` | Pointer to the active model (relative POSIX paths) | Read |
| `models/trained/lt-20261022-215253/model.joblib`, `meta.json` | Active lead-time model and metadata | Read |
| `models/evaluation/lt-20261022-215253/feature_importance.csv`, `test_predictions.csv` | Model Analytics, coverage | Read |
| `models/evaluation/model_comparison.json` | Legacy-model note on Model Analytics (optional) | Read |
| `data/processed/*` | Rewritten only by "Refresh database" (Data Management) | Write |

**Other run-time requirements:**

- No images, fonts or external URLs are loaded at run time.
- The map uses Plotly's built-in geography, which is fetched by the visitor's browser.
- Uploads (Data Management → Validation) are processed in memory and never saved.

**Paths:**

- All paths derive from `src/config.PROJECT_ROOT` (`Path(__file__)…`).
- No Windows drive letters or user folders appear anywhere in the code (checked with `git grep`).
- All 8 run-time file paths match the tracked file names **case-exactly**. This matters on Linux, which treats `Data/`
  and `data/` as different folders.
- Each page adds the project root to `sys.path`, so imports work when Streamlit runs `dashboard/app.py` from the
  repository root.

## 4. Dependencies and Python version

**Issue found.** `requirements.txt` used minimum versions only (`pandas>=2.0`, …). On a newer Python, pip installs the
newest major versions. In testing, those **fail one data-validation test**: pandas 3's new default text type stops
blank-text cells from being counted in the missing-value report. They also **warn when loading the saved model**,
because it was pickled with scikit-learn 1.7.2. The file also listed `statsmodels` and `openpyxl`, which no code imports.

**Prepared change (local, not committed or pushed):**

```
pandas==2.3.3
numpy==2.2.6
scikit-learn==1.7.2
scipy==1.15.3
sqlalchemy==2.0.55
streamlit==1.65.0
plotly==7.1.0
joblib==1.6.0
pytest==9.1.1
```

| Item | Before | After |
|---|---|---|
| Version pins | Minimum versions only | Exact versions, verified: fresh Python 3.10 environment, 109/109 tests |
| Removed packages | — | `statsmodels`, `openpyxl` (unused) |
| Kept packages | — | `pytest`, so the documented test command still works |
| Functionality | — | No functionality removed |

Review it with `git diff requirements.txt`.

**Python version: select 3.10.** That is the version all tests and the saved model were verified with. Python 3.11–3.13
should work with these pins, since all of them publish wheels for those versions, but this was **not tested**.
Python 3.14 is **not compatible** with the pinned SciPy 1.15.3.

**Optional follow-up (not done, needs your approval).** Make `missing_value_summary` in `src/data_validation.py`
pandas-3-safe, by treating string dtypes the same as `object`. That would allow unpinning later. It is not required
while versions are pinned.

## 5. Database behaviour on Streamlit Community Cloud

| Aspect | Behaviour |
|---|---|
| Initialisation | None needed. The committed `data/nassau.db` already has the full schema and data. Nothing runs migrations at start-up. |
| Writes | Saving scenarios or recommendation runs, status updates, saving default assumptions, and "Refresh database" all write to `data/nassau.db` inside the container. |
| Persistence | ⚠️ **Not persistent.** The container's file system is temporary: writes survive while the app runs but are **lost when the app restarts, redeploys, wakes from sleep or is rebuilt**. The app then returns to the committed database. |
| Shared state | ⚠️ All visitors share one database file. On a **public** app, **anyone** can change recommendation statuses and saved default assumptions until the next restart. |
| Concurrency | SQLite is suitable for light use, a few simultaneous users. Heavy concurrent writing is not supported. |

**Options**, for your decision. No code was changed.

1. **Accept as a demonstration** (recommended for an academic submission). State in the README that changes made on
   the public app are temporary.
2. Add a "read-only demo" switch (for example an environment variable or secret) that hides the write buttons on the
   public app. This is a small dashboard change that needs your approval.
3. Use an external database for permanent storage. This is out of scope and would add a paid or hosted dependency.

## 6. Secrets and credentials

| Check | Result |
|---|---|
| `st.secrets`, `os.environ` or `getenv` used in code | None |
| Secrets required for deployment | **None.** Leave the Secrets box empty. |
| `.streamlit/secrets.toml` | Not present, and excluded by `.gitignore` |
| Credentials in git history | None (see `GITHUB_PRE_PUSH_SECURITY_AUDIT.md`) |

## 7. Memory and start-up

| Measure | Result (Windows, Python 3.10, from the fresh clone) |
|---|---|
| Process memory, all 9 pages rendered | **Peak ~262 MB** (60 MB at start, 230 MB after the first data page) |
| First visit (cold) | ~3–5 s for the Executive Dashboard: loads the CSV, the model, and evaluates 75 product–factory options |
| Later visits | ~0.4–1 s (results cached and shared between sessions) |
| Server start | ~2 s |
| First deployment build on Cloud | Dominated by installing packages: about 1.5–2 minutes locally |

Linux memory use is expected to be similar. Cached results are shared between visitors, so memory grows little with
more users. This is comfortably inside Community Cloud's per-app limits.

## 8. Streamlit Community Cloud limitations

Check the current Streamlit documentation for exact figures.

- **Temporary file system.** See section 5.
- **Limited CPU and memory per app.** The app's ~260 MB peak leaves ample headroom.
- **Sleep.** Apps sleep after a period without traffic. The first visitor afterwards waits for the app to wake: about a
  minute, including start-up.
- **Public apps** are reachable by anyone with the link. The full dataset can be downloaded from Data Management →
  Exports; publishing it is covered by the permission you confirmed.
- **Python version** is chosen when deploying (Advanced settings). Changing it later generally means deleting and
  redeploying the app.
- **Windows-only issue.** Cloning this repository into a very deep Windows folder can fail with "Filename too long",
  because of the archived report images. Use a short folder or `git clone -c core.longpaths=true`. This does not
  affect Streamlit Cloud, which runs on Linux.

## 9. What was changed locally

| File | Change | Committed / pushed? |
|---|---|---|
| `requirements.txt` | Exact pins; unused `statsmodels` and `openpyxl` removed | ❌ No, awaiting your review |
| `STREAMLIT_DEPLOYMENT_AUDIT.md`, `STREAMLIT_DEPLOYMENT_GUIDE.md` | New documents | ❌ No |

**Unchanged:** application code, ML models, optimization logic, data, database and dashboard functionality. The
database checksum is unchanged.
