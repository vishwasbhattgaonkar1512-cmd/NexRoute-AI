# Submission README Verification — NexRoute AI

Date: 2026-10-22. Scope: the four mandatory fields of the project submission form, plus checks of the root `README.md`.
Only `README.md` and this file were created or changed. No commits, pushes, deployments or uploads were made.

## 1. Submission readiness

| Official submission field | Status | Verified HTTPS URL | Remaining action |
|---|---|---|---|
| GitHub Repository Link | ❌ **Not available** | None. No git remote is configured. | Create a GitHub repository, add it as `origin`, commit the `reports/` deliverables and push. Make it public (after confirming data-publication rights). |
| Research Paper Link | ⚠️ **Document ready; no public link** | None. The files are not committed, pushed or hosted. Publication or approval is **not verified**. | After pushing, use the GitHub file URL of `reports/research_paper/NexRoute_AI_Research_Paper.pdf`. Do not describe it as published or approved without evidence. |
| Deployed Project Link | ❌ **Not deployed** | None. The app runs only locally (`http://localhost:8501`, not a valid submission link). | Push the repository, then deploy `dashboard/app.py` (e.g. Streamlit Community Cloud), and verify that the `https://` URL loads all pages. |
| Project Feedback Video Link | ❌ **Not completed** | None. No video file or video URL exists. | Record the video (outline in section 6), upload it publicly, and verify that the `https://` link opens without sign-in. |

**Overall status: NOT READY FOR SUBMISSION.** None of the four mandatory fields has a valid public HTTPS URL yet. The
project content itself (code, tests, research paper, executive summary, dashboard) is complete and verified locally.

## 2. Field 1 — GitHub Repository

**What was checked:**

| Check | Result |
|---|---|
| `git remote -v` in the project folder | **No remotes** |
| Branch | `main` |
| Latest commit | `6f9f8af` "Final QA: reports, docs updated with verified results, LF line endings" (12 commits in total) |
| Parent repository at `D:\` (checked read-only) | No commits, no remotes, not related |
| GitHub URLs in project files (excluding `venv` and `.git`) | None found |
| `gh` (GitHub CLI) | Not installed |

**Not committed (working tree):**

- `README.md` (modified)
- `SUBMISSION_README_VERIFICATION.md` (new)
- `reports/executive_summary/` (new)
- `reports/research_paper/` (new)

**Nothing has been pushed anywhere.**

**Conclusion:** no genuine GitHub URL exists. None was invented.

**Before publishing:**

- **Data rights.** The repository contains the raw distributor dataset, `data/nassau.db` and model files. Confirm you
  have the right to publish this data.
- **Repository size.** The repository includes database backup files, `models_backup_before_retrain/` and archived
  report versions. `.gitignore` already excludes `data/*_backup_*.db`.

## 3. Field 2 — Research Paper

| Check | Result |
|---|---|
| `reports/research_paper/NexRoute_AI_Research_Paper.pdf` | Exists. Valid (`%PDF-1.4` header, `%%EOF` trailer), 23 pages, 521,737 bytes |
| `NexRoute_AI_Research_Paper.md`, `EDA_Methodology_and_Findings.md`, `EDA_Metrics_Summary.csv`, `RESEARCH_PAPER_VERIFICATION.md` | All exist |
| `eda_visualizations/` | 14 SVG figures |
| Consistency with the current implementation and the executive summary | `scripts/verify_paper.py`: **49/49 metric checks passed; 11/11 superseded values absent** |
| Executive summary PDF | Valid, 10 pages |
| `notebooks/09_NexRoute_AI_EDA_Research.ipynb` | **Missing — does not exist** |
| `notebooks/09_NexRoute_AI_EDA_Research.html` | **Missing — does not exist** |
| Publication / approval / peer review evidence | **None found** |

**The notebook claim could not be confirmed.** The earlier report of "30 executed cells, 0 errors, 18 embedded
charts, 13 sections" refers to a notebook that is **not in the project**. The `notebooks/` folder contains only
`profile_dataset.py`. The EDA is instead reproducible through `reports/research_paper/scripts/`. The README says this
openly and does not link to the missing notebook.

**Conclusion:**

- The paper itself is ready and consistent.
- **No public URL exists.** A local file or a repository-relative path is not a valid submission URL.
- After the files are committed and pushed to a public repository, a valid link takes the form
  `https://github.com/<owner>/<repo>/blob/main/reports/research_paper/NexRoute_AI_Research_Paper.pdf`.
  Verify that it opens before submitting.
- The paper must be described as **unpublished / not formally approved** unless evidence is obtained.

## 4. Field 3 — Deployed Project

| Check | Result |
|---|---|
| Entry point | `dashboard/app.py` (home page) |
| Pages | 8 files in `dashboard/pages/`: Executive Dashboard, Factory Optimization, What-If Analysis, Recommendations, Risk & Impact, Factory Map, Model Analytics, Data Management. Titles confirmed from each file's `setup_page(...)` call. |
| Launch command | `streamlit run dashboard/app.py`. A local instance from this session answered `/_stcore/health` with `ok`. All 9 pages rendered without exceptions in the automated tests. |
| `requirements.txt` | pandas, numpy, scikit-learn, scipy, sqlalchemy, streamlit, plotly, joblib, openpyxl, statsmodels, pytest |
| Deployment configuration (`.streamlit/`, `Procfile`, `runtime.txt`, etc.) | None present |
| `*.streamlit.app` or other deployment URLs in project files | None found |
| Tests | `python -m pytest -v`: 109 passed |

**Conclusion:** NOT YET DEPLOYED. No public URL exists. `localhost` addresses are not valid submission links.

**What a deployment needs** (not performed; it requires your authorization):

- a public GitHub repository (Field 1);
- a hosting service pointed at `dashboard/app.py` with Python 3.10 and `requirements.txt`;
- the committed `data/nassau.db`, `data/raw/` and `models/trained/` files, which the app loads at start-up;
- a check that every page loads at the resulting `https://` URL.

The note on publishing the dataset applies here too.

## 5. Field 4 — Project Feedback Video

| Check | Result |
|---|---|
| Video files (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.wmv`) in the project | None |
| YouTube, Google Drive, Loom or Vimeo URLs in project files | None |

**Conclusion:** NOT YET COMPLETED. No URL was invented.

## 6. Recommended video outline (about 5–8 minutes)

1. **Introduction and project overview:** NexRoute AI and what it decides.
2. **Problem statement and objective:** 15 products, 5 factories; keep or move each product.
3. **Dataset and EDA findings:**
   - 10,194 order lines;
   - the disguised dates and the reconstructed lead time;
   - ship mode, not distance, drives lead time.
4. **Machine learning and factory optimization:**
   - why the per-ship-mode average was selected (test MAE 0.806 days, R² 0.698);
   - the scenario results (+$1,690 cost-focused vs +$8 balanced, all estimates).
5. **Streamlit dashboard demonstration:** Executive Dashboard → Factory Optimization → What-If → Recommendations → Model Analytics.
6. **Key learnings and project experience:** data-quality forensics, and honest evaluation over impressive numbers.
7. **Conclusion:** limitations and next steps (validate costs, capacity and delivery data).

## 7. README checks

| Check | Result |
|---|---|
| Structure | Follows the requested 13-part structure. The four submission fields appear in a table and as sections 1–4. |
| Relative links | 14 file/folder links and 1 internal anchor were checked: all resolve. The only exception was this file, which is now created. |
| HTTPS URLs presented as real submission links | **None.** The only `https://` strings are clearly marked templates (`https://github.com/<owner>/<repo>…`). The only other address is `http://localhost:8501`, labelled as local and not a submission link. |
| Figures | Dataset, ML and scenario figures match the verified project: 10,194 lines; 5,044 customers; 59 destinations; test MAE 0.806 / RMSE 0.986 / R² 0.698; scenarios 0 / 15 / 11 / 11 / 2 moves and $0 / +$760 / +$1,690 / +$1,690 / +$8. |
| Claims | No claims of publication, approval, deployment or a video. Lead times are labelled as reconstructed, and savings as simulation estimates. |
| Project data | Database md5 `e81b9843…6034ab2` unchanged. No source, data, model, paper, summary or notebook files were modified. |

## 8. Steps to reach "ready" (in order)

1. **Confirm data rights,** then create a GitHub repository. Add it as the remote, commit `README.md`,
   `SUBMISSION_README_VERIFICATION.md`, `reports/research_paper/` and `reports/executive_summary/`, and push.
   → Field 1 URL.
2. **Verify the research paper link** by opening `https://github.com/<owner>/<repo>/blob/main/reports/research_paper/NexRoute_AI_Research_Paper.pdf`
   while logged out. → Field 2 URL.
3. **Deploy `dashboard/app.py`** from the repository and open every page at the public URL. → Field 3 URL.
4. **Record and upload the feedback video** with public link sharing. → Field 4 URL.
5. **Replace "pending"** in the README table with the four verified URLs, and re-check that each opens without sign-in.
