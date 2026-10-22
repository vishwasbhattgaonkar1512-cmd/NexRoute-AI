# GitHub Pre-Push Security Audit — NexRoute AI

Date: 2026-10-22 · Repository: `D:\nassau-candy-optimization\nassau-candy-optimization` · Destination:
https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI (verified to exist, **public**, **empty**).

## Verdict: DO NOT PUSH (yet)

**The original Nassau Candy dataset, and full copies derived from it, are present in every one of the 12 commits,
starting from the first commit (`d2a7d54`).** Dataset redistribution permission is **unconfirmed**. Because the
destination repository is public, pushing `main` would publish that data immediately and permanently, since forks and
clones cannot be recalled.

Adding the files to `.gitignore` would **not** fix this: they are already tracked and present in history.

No push was made. No history was changed. No files were removed.

## 1. Repository facts (verified)

| Item | Value |
|---|---|
| Branch | `main` (only branch) |
| Commits | 12 (`d2a7d54` … `6f9f8af`) |
| Remote | `origin` → `https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI.git`. Added during this audit; previously there was none. |
| Remote state | `git ls-remote`: no refs (empty). GitHub API: `visibility: public`, `size: 0`, default branch `main`. |
| Push compatibility | The remote is empty, so `git push -u origin main` would succeed without force or merging. The **only** blocker is data permission. |
| Tracked files | 80 (about 8.3 MiB of objects in history) |
| Not yet committed | `README.md` (modified); `SUBMISSION_README_VERIFICATION.md`, `GITHUB_PRE_PUSH_SECURITY_AUDIT.md`, `reports/executive_summary/`, `reports/research_paper/` (untracked) |
| `.gitignore` | `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.streamlit/secrets.toml`, `data/*_backup_*.db` |
| Untracked and ignored (correctly not in git) | `data/nassau_backup_2026-10-22_pre_phase7.db`; the virtual environment lives outside the project folder (`..\venv`), so it cannot be committed |

## 2. Credentials and secrets

**Scan:** every text blob in the entire history was searched for API keys, passwords, tokens, private keys, AWS, GitHub
and OpenAI key formats, and `.env` or credential files.

**Result: none found.** No `.env`, key or credential files were ever committed. The app uses no external services, so
it needs no secrets.

## 3. Personal information

| Finding | Where | Risk |
|---|---|---|
| **Your email address** `vishwasbhattgaonkar1512@gmail.com` is the author and committer of all 12 commits | Commit metadata (every commit) | GitHub shows commit emails publicly once pushed. Changing it on existing commits requires rewriting history (not done). Option B in section 7 avoids it. |
| Customer-level records: Customer ID, City, State/Province, Postal Code (5,044 customers) — no names, emails or phone numbers | `data/raw/…csv`, `data/processed/cleaned_featured.csv`, `data/nassau.db` (`customers`, `orders`) | Quasi-identifiers plus the distributor's commercial data (sales, cost, profit). Covered by the redistribution question. |
| `/home/claude/...` path mentioned in text | `reports/PHASE1_AUDIT.md` | None (describes an old log entry). |

## 4. Dataset and derived-data exposure (in git history)

| Path | Size | In commits | Content | Status |
|---|---:|---|---|---|
| `data/raw/nassau_candy_distributor.csv` | 1.9 MB | all 12 | **Original dataset**, 10,194 rows | 🔴 Restricted until permission is confirmed |
| `data/processed/cleaned_featured.csv` | 3.2 MB (3 versions) | all 12 | **Full row-level copy** plus derived columns | 🔴 Restricted |
| `data/nassau.db` | 5.1 MB (2 versions) | all 12 | **Full row-level copy** (customers, orders, order_items), plus results | 🔴 Restricted |
| `data/processed/data_quality_logs.json` | small | all | Aggregate data-quality findings | 🟢 Low |
| `models/evaluation/lt-…/test_predictions.csv` | 92 KB | 21c90aa→ | 1,530 rows: Row ID, ship mode, reconstructed lead time | 🟠 Row-level derived (no customer fields) |
| `models/evaluation/test_predictions.csv`, `models_backup_before_retrain/evaluation/test_predictions.csv` | 65 KB each | all | 1,500 rows of derived values | 🟠 Row-level derived (no identifiers) |
| `reports/eda/route_clusters.csv`, `destination_clusters.csv`, `data_profile.json` | small | various | Aggregates per route or destination | 🟢 Low (aggregate) |

**Untracked deliverables** (`reports/research_paper/data/*.csv`, executive summary, paper) contain **aggregates only**:
per product, per destination, per scenario. They contain no row-level records.

## 5. Model files

| File | Content | Assessment |
|---|---|---|
| `models/trained/lt-20261022-215253/model.joblib` (active) | Four per-ship-mode means | 🟢 No data records |
| `models/trained/{random_forest,gradient_boosting,linear_regression}.joblib`, `model_meta.joblib` (legacy) | Fitted pipelines: category lists (division, factory, region, state names), tree split thresholds and leaf averages | 🟢 No raw records, but derived from the dataset. Unused by the app. |
| `models_backup_before_retrain/**` | Duplicates of the legacy models | 🟡 Redundant |

The `.joblib` files are pickles: loading them executes code. That is normal for scikit-learn, but users should only load
model files from trusted sources.

## 6. Large and unnecessary files

| File | Size | Comment |
|---|---:|---|
| `models/trained/random_forest.joblib` | 7.6 MB | Legacy model, unused by the app |
| `models_backup_before_retrain/trained/random_forest.joblib` | 7.6 MB | Duplicate backup |
| `data/nassau.db` | 5.1 MB | Needed by the app (contains restricted data) |
| `data/processed/cleaned_featured.csv` | 3.2 MB | Regenerable with `python -m src.preprocessing` |

No file exceeds GitHub's 50 MB warning or 100 MB limit. The total history is about 8.3 MiB, so Git LFS is not needed.

## 7. Remediation options (your decision required)

| Option | What happens | Preserves the 12 local commits? | Public history contains the dataset? | Dashboard deployable? |
|---|---|---|---|---|
| **A. Confirm permission, then push `main` as is** | Commit the deliverables, then `git push -u origin main` (no force) | ✅ Yes, all pushed | ⚠️ Yes (allowed once confirmed) | ✅ Yes (data included) |
| **B. Publish a data-free snapshot as a new, separate history** | Create a new local branch with **no parent** containing the current code, docs and reports, excluding restricted files (Recommended `.gitignore`). Push it to GitHub `main` with `git push -u origin public-release:main`. Local `main` is untouched. | ✅ Yes, locally (they are simply not published) | ❌ No | ❌ Not as is: the app needs `data/nassau.db`. Deployment would need a permitted or sample dataset. |
| **C. Rewrite history** (`git filter-repo`) to strip data from all 12 commits | Changes every commit hash | ❌ No | ❌ No | ❌ Same as B |
| **D. Make the GitHub repository private** (only you can change visibility) and push `main` | Full history stays private | ✅ Yes | Private only | Limited; a private repository does not satisfy a public submission link |

**Recommendation:**

- If the dataset came from your course or program and you can confirm that sharing it is allowed (for example, it is
  publicly provided to all participants), use **Option A**. It is the simplest, keeps the full history, and allows
  deployment.
- Otherwise, use **Option B**. It publishes everything except the data, without touching your local history. Option B
  can also author the new commit with GitHub's no-reply email, so your Gmail address is not published.

**Option C is not recommended:** B achieves the same public result without rewriting anything.

## 8. Recommended `.gitignore` additions

**Safe to add now** (no effect on tracked files):

```
venv/
.venv/
*.log
.ipynb_checkpoints/
.DS_Store
Thumbs.db
```

**Only for Option B.** These exclusions apply to the new release branch; on `main` they are already tracked, so
ignoring them alone does nothing:

```
data/raw/
data/processed/
data/nassau.db
data/*.db
models_backup_before_retrain/
models/evaluation/**/test_predictions.csv
models/trained/random_forest.joblib
models/trained/gradient_boosting.joblib
models/trained/linear_regression.joblib
models/trained/model_meta.joblib
reports/research_paper/archive_superseded_v1_2026-10-22/
```

## 9. What was done in this audit

- Read-only inspection of the working tree, the full history, file contents and the remote repository.
- Added the `origin` remote (local configuration; reversible with `git remote remove origin`).
- Added the safe `.gitignore` entries from section 8, and updated `README.md` with the verified repository URL
  (marked as not yet pushed). `GITHUB_PUBLISHING_VERIFICATION.md` will be created only after a successful push.
- **Not done:** no push, no history change, no file removal, no change to data, models, code or the dashboard.
