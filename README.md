# NexRoute AI — Factory Reallocation & Shipping Optimization Recommendation System for Nassau Candy Distributor

NexRoute AI is a decision-support prototype that answers one question for Nassau Candy Distributor: **which of the
five factories should make each of the 15 products?** It combines historical order analysis, data-quality forensics,
lead-time prediction, geographic distance analysis, scenario simulation and mathematical optimization. Every
recommendation comes with an explanation, a risk rating and the assumptions behind it.

> **Transparency first.**
> - Lead times are **reconstructed** from disguised dates; they are not observed delivery times.
> - Costs, freight rates, capacity and compatibility are **configurable assumptions**.
> - All savings are **simulation estimates**, not realised results.

---

## Official Project Submission Links

The submission form requires four public HTTPS links. Current status (verified 2026-10-22 after publishing, details in
[SUBMISSION_README_VERIFICATION.md](SUBMISSION_README_VERIFICATION.md)):

| # | Submission field | Status | Public HTTPS URL |
|---|---|---|---|
| 1 | GitHub Repository Link | ✅ **Ready** — public, pushed and verified | https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI |
| 2 | Research Paper Link | ✅ **Link ready** — PDF publicly hosted in the repository (not formally published or approved) | https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI/blob/main/reports/research_paper/NexRoute_AI_Research_Paper.pdf |
| 3 | Deployed Project Link | ⏳ **Not yet deployed** — dashboard runs locally only | *Not available yet* |
| 4 | Project Feedback Video Link | ⏳ **Not yet completed** — no video found | *Not available yet* |

### 1. GitHub Repository

- **URL:** https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI
- **Status:** public, with the full development history (branch `main`). The dataset is included with the owner's confirmed
  permission. See [GITHUB_PRE_PUSH_SECURITY_AUDIT.md](GITHUB_PRE_PUSH_SECURITY_AUDIT.md) and [GITHUB_PUBLISHING_VERIFICATION.md](GITHUB_PUBLISHING_VERIFICATION.md).
- **What the repository contains:**
  - the full source code (`src/`, `database/`, `dashboard/`);
  - 109 automated tests;
  - trained model artifacts;
  - the SQLite database;
  - documentation and the research deliverables.

> **Data notice.** The repository includes the Nassau Candy dataset and a database built from it. They are published
> with the repository owner's confirmed permission.

### 2. Research Paper

| Document | Repository path |
|---|---|
| Research paper (PDF, 23 pages) | [reports/research_paper/NexRoute_AI_Research_Paper.pdf](reports/research_paper/NexRoute_AI_Research_Paper.pdf) |
| Research paper (Markdown) | [reports/research_paper/NexRoute_AI_Research_Paper.md](reports/research_paper/NexRoute_AI_Research_Paper.md) |
| EDA methodology and findings | [reports/research_paper/EDA_Methodology_and_Findings.md](reports/research_paper/EDA_Methodology_and_Findings.md) |
| EDA metrics (83 values with sources) | [reports/research_paper/EDA_Metrics_Summary.csv](reports/research_paper/EDA_Metrics_Summary.csv) |
| EDA figures (14 SVG charts) | [reports/research_paper/eda_visualizations/](reports/research_paper/eda_visualizations/) |
| Research paper verification | [reports/research_paper/RESEARCH_PAPER_VERIFICATION.md](reports/research_paper/RESEARCH_PAPER_VERIFICATION.md) |
| Executive summary for government stakeholders (PDF) | [reports/executive_summary/NexRoute_AI_Executive_Summary_Government_Stakeholders.pdf](reports/executive_summary/NexRoute_AI_Executive_Summary_Government_Stakeholders.pdf) |
| Reproducible EDA scripts (used instead of a notebook) | [reports/research_paper/scripts/](reports/research_paper/scripts/) |

- **Publication / approval status:** **not published, not approved, and not peer-reviewed.** No evidence of
  publication or approval exists in the project.
- **Public link:** https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI/blob/main/reports/research_paper/NexRoute_AI_Research_Paper.pdf. Verified: it opens, and the file is byte-identical to the local copy.
- **EDA notebook:** an executed EDA notebook (`notebooks/09_NexRoute_AI_EDA_Research.ipynb` and its `.html`) was
  referred to earlier but **does not exist** in the project. The EDA is reproduced by the scripts linked above instead.

### 3. Deployed Project

- **Deployment status:** **NOT YET DEPLOYED.** No public URL exists, and no deployment configuration is present.
- **Runs locally:** `streamlit run dashboard/app.py` → http://localhost:8501. This is local only and is *not* a submission link.
- **Required before a link can be submitted:**
  - deploy `dashboard/app.py` (for example on Streamlit Community Cloud, with Python 3.10 and `requirements.txt`);
  - confirm the resulting `https://…` URL opens all pages.

  The app needs the committed `data/nassau.db` and `models/trained/` files.
- **Dashboard:** a home page plus eight pages. See [Streamlit Dashboard](#9-streamlit-dashboard).

### 4. Project Feedback Video

- **Status:** **NOT YET COMPLETED.** No video file or video URL exists in the project.
- **Required action:** record the video, upload it to a public platform (for example YouTube or Google Drive with
  link sharing), and enter its `https://` URL here.
- A suggested outline is in [SUBMISSION_README_VERIFICATION.md](SUBMISSION_README_VERIFICATION.md).

---

## 3. Project Overview

| | |
|---|---|
| **Business problem** | Each of 15 products is made at one of 5 factories. Products made far from their customers may cost more to ship and take longer to arrive. Management needs evidence before moving production. |
| **Objective** | Evaluate every product–factory option and recommend whether to keep or reallocate each product, with cost, delivery-time and risk trade-offs made explicit. |
| **Approach** | Data validation and date forensics → lead-time prediction → symmetric cost model → heuristic risk scoring → exact optimization (SciPy MILP) → five-scenario simulation → explained recommendations in a dashboard backed by a database. |

## 4. Key Features

- **Data-quality engine:** 12 automated checks, plus forensic reconstruction of the disguised shipping dates.
- **Honest ML evaluation:** chronological train/validation/test split, selection on validation data only, baselines included, and measured prediction-range coverage.
- **Symmetric cost model:** the same formula for the current and every alternative factory.
- **Exact optimizer:** compatibility, minimum-profit and optional capacity constraints; reports infeasibility instead of failing.
- **Five scenarios** under one shared, editable assumption set.
- **Explained recommendations:** a written reason for every product, a risk breakdown, and a review workflow (proposed → approved → implemented).
- **SQLite persistence** with additive migrations, run history and an integrity check.
- **Eight-page Streamlit dashboard** and **109 automated tests**.

## 5. Dataset Overview

Source: `data/raw/nassau_candy_distributor.csv` (read-only). All values below are observed, verified against the current pipeline.

| Metric | Value |
|---|---:|
| Order lines | 10,194 (18 columns, 0 missing values) |
| Distinct order IDs | 8,549 |
| Customers | 5,044 |
| Products · divisions | 15 · 3 (Chocolate 9,844 · Other 310 · Sugar 40 lines) |
| Factories | 5 |
| Destinations | 59 (49 US states incl. DC · 10 Canadian provinces) |
| Regions | 4 (Pacific · Atlantic · Interior · Gulf) |
| Shipping modes | 4 (Standard · Second · First Class · Same Day) |
| Sales · gross profit | $141,783.63 · $93,442.80 |

## 6. EDA and Research Findings

1. **The recorded dates are disguised.** Ship Date − Order Date is 904–1,642 days for every order. The Order ID
   carries the original year (2021–2024), the Order Date year was relabelled, and the Ship Date was shifted by exactly
   2,000 days. Reversing this gives a **reconstructed lead time** of 0–8 days (all but 2 lines).
2. **Ship mode, not distance, drives lead time.** Ship mode explains 67.4% of the variance. Distance shows no measurable
   relationship (r = 0.006).
3. **Demand is concentrated.** Chocolate is 96.6% of order lines, and two factories handle 96.6% of lines. Seven
   products have fewer than 30 order lines, so estimates for them are weak.

## 7. Machine Learning Results

All metrics refer to the **reconstructed** lead time, not observed delivery times.

| Model | Validation MAE | Test MAE | Test R² |
|---|---:|---:|---:|
| Overall mean (baseline) | 1.361 | 1.381 | −0.003 |
| **Per-ship-mode mean (selected)** | **0.828** | 0.807 | 0.698 |
| Linear Regression | 0.830 | 0.812 | 0.699 |
| Random Forest | 0.846 | 0.817 | 0.697 |
| Gradient Boosting | 0.844 | 0.819 | 0.696 |

The selected model was refit on train + validation and evaluated once on the test set: **MAE 0.806 days, RMSE 0.986
days, R² 0.698**.

The ML models do not beat the simple per-ship-mode average, so the simpler model is used. The whole-day prediction
ranges (for example, Standard Class 4–7 days) have a measured test coverage of 100%.

## 8. Factory Optimization Results

These are simulation estimates over the historical period under default assumptions ($0.0005 per unit-mile freight;
equal factory costs). They are **not guaranteed savings**.

| Scenario | Products moved | Estimated profit impact |
|---|---:|---:|
| Current allocation | 0 | $0 |
| Best alternative (forced) | 15 | +$760 |
| Distance-based | 11 | +$1,690 |
| Cost-focused | 11 | +$1,690 |
| **Balanced (recommended)** | **2** | **+$8** |

- **Most of the potential gain is in three products.** Moving three Wonka Bar products from Lot's O' Nuts to Wicked
  Choccy's accounts for 98.8% of the cost-focused gain.
- **The balanced objective is cautious.** It weighs that gain against unverified risk and recommends moving only
  Fun Dip and Laffy Taffy, two very small products.

## 9. Streamlit Dashboard

Entry point: `dashboard/app.py` (home page) plus eight pages in `dashboard/pages/`:

| # | Page | Purpose |
|---|---|---|
| 1 | Executive Dashboard | KPIs, current allocation, optimization summary, data-quality banner |
| 2 | Factory Optimization | One product across all five factories: eligibility, distance, cost, lead time, risk, recommendation |
| 3 | What-If Analysis | Five scenarios with editable assumptions and weights; save runs |
| 4 | Recommendations | Ranked recommendations, filters, rationale, review status with history |
| 5 | Risk & Impact | Risk components, prediction uncertainty, profit vs risk, sensitivity |
| 6 | Factory Map | Factories, demand, routes, distance matrix, coverage, demand clusters |
| 7 | Model Analytics | Model comparison, validation vs test, importance, residuals, coverage, registry |
| 8 | Data Management | Data-quality report, date forensics, CSV validation, integrity check, assumptions, exports |

## 10. Technology Stack

Python 3.10 · pandas · NumPy · scikit-learn · SciPy (`milp` / HiGHS) · SQLAlchemy + SQLite · Streamlit · Plotly · joblib · pytest.

Everything runs locally and offline; no paid services or external APIs are used.

## 11. Project Structure

```
data/raw/                 original dataset (read-only)
data/nassau.db            SQLite database (15 tables)
src/                      validation, preprocessing, geography, prediction, profit, risk, optimization, scenarios, persistence
database/                 SQLAlchemy models, connection, additive migrations
dashboard/                Streamlit app (app.py, common.py, pages/01–08)
models/trained/           versioned model artifacts (active: lt-20261022-215253)
reports/research_paper/   research paper, EDA record, figures, scripts, verification
reports/executive_summary/ executive summary for government stakeholders
tests/                    109 automated tests
```

**Further documentation:**

| Document | Contents |
|---|---|
| [FINAL_PROJECT_SUMMARY.md](FINAL_PROJECT_SUMMARY.md) | One-page project summary |
| [FINAL_QA_REPORT.md](FINAL_QA_REPORT.md) | Final QA verification and fixes |
| [DEVELOPMENT_PROGRESS.md](DEVELOPMENT_PROGRESS.md) | Development history and decisions |
| [reports/PHASE1_AUDIT.md](reports/PHASE1_AUDIT.md) | Original audit and date forensics |

## 12. Limitations and Transparency

- **Lead time:** reconstructed from disguised dates by a tested rule, not measured.
- **Alternative factories:** each product was only ever made at one factory, so alternative-factory effects are counterfactual estimates.
- **Assumptions:** factory costs, freight rates, transit times, capacity and compatibility are configurable assumptions, not data.
- **Risk scores:** heuristic rules of thumb, not calibrated probabilities.
- **Distances:** straight lines to state/province centroids; Canadian centroids are coarse.
- **Sparse history:** seven products have very little order history.
- **Database constraints:** three `run_id` foreign keys are enforced in code rather than by the existing database (monitored by an integrity check; currently 0 orphan records).

## 13. Installation and Local Execution

From the project folder, using the existing virtual environment one level up:

```bash
# Windows PowerShell:  ..\venv\Scripts\Activate.ps1      Git Bash:  source ../venv/Scripts/activate
pip install -r requirements.txt

python -m pytest -v                  # 109 tests
streamlit run dashboard/app.py       # opens http://localhost:8501
```

Optional: rebuild the derived artifacts. Both commands are safe and never delete data.

```bash
python -m src.prediction_engine      # train a new versioned model
python -m src.build_database         # additive schema upgrade + refresh derived columns
```
