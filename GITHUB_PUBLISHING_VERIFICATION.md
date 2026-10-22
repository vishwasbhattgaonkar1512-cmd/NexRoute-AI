# GitHub Publishing Verification — NexRoute AI

Date: 2026-10-22

| Item | Value |
|---|---|
| Repository URL | https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI (public) |
| Branch | `main` (local `main` tracks `origin/main`) |
| Published commit (initial push) | `07d2aba496f69f5dc6700a9f3f4e09e4e93028b1` |
| Commit count at initial push | 14: the 12 original commits, unchanged, plus 2 documentation commits added before pushing |
| Push method | `git push -u origin main`. The remote was empty and the push created a new branch. **No force, no history rewriting, no merge or rebase.** |
| Follow-up | One further documentation commit (this file, plus README and submission-status updates) is pushed on top as a normal fast-forward. |

## Verification performed after the push

| Check | Result |
|---|---|
| Remote head equals local head (`git ls-remote origin refs/heads/main`) | ✅ `07d2aba…` on both |
| Commit count on GitHub (commits API) | ✅ 14 |
| Files on GitHub vs locally tracked files (GitHub tree API, recursive, not truncated) | ✅ Identical sets (152 files) |
| Excluded file types present on GitHub (`__pycache__`, `.pyc`, `.pytest_cache`, DB backups, `venv`, `.env`, `secrets.toml`) | ✅ None |
| README relative links resolving to files on GitHub | ✅ 15 of 15 |
| Repository page and README page | ✅ HTTP 200 |
| Research paper PDF at `…/blob/main/reports/research_paper/NexRoute_AI_Research_Paper.pdf` | ✅ HTTP 200. The raw download is **byte-identical** to the local file (md5 `fd411eec…098a8`). |

## Test results (before publishing)

- `python -m pytest -v`: **109 passed** (0 failed).
- Research paper PDF: valid (`%PDF-1.4` / `%%EOF`, 23 pages).
- Executive summary PDF: valid (10 pages).
- Paper vs executive summary: 49/49 metric checks consistent.

## Security audit status

See `GITHUB_PRE_PUSH_SECURITY_AUDIT.md`.

| Area | Status |
|---|---|
| Credentials | ✅ None in any commit |
| Dataset | ✅ The original dataset and the derived database or CSVs are included, with the **owner's confirmed permission** to redistribute (Option A, recorded in audit section 10) |
| Personal information | ⚠️ The commit author email (`vishwasbhattgaonkar1512@gmail.com`) is visible in commit metadata, as accepted with Option A. The dataset contains customer IDs, cities and postal codes, but no names or contact details. |
| Large files | ✅ Largest is 7.6 MB (legacy random-forest model); total about 8 MiB. No Git LFS needed. |

## Files published (152 tracked files)

| Area | Files |
|---|---:|
| `src/` (application logic) | 17 |
| `dashboard/` (Streamlit app and 8 pages) | 10 |
| `database/` | 4 |
| `tests/` | 11 |
| `data/` (raw CSV, processed CSV, data-quality JSON, SQLite DB) | 4 |
| `models/` (active model, legacy models, evaluations) | 13 |
| `models_backup_before_retrain/` | 7 |
| `reports/` (audit, EDA, research paper v2 with figures, data and scripts, archived v1, executive summary) | 76 |
| Root documents and configuration (README, QA report, summary, progress, audits, `requirements.txt`, `pytest.ini`, `.gitignore`) | 9 |
| `notebooks/profile_dataset.py` | 1 |

## Files excluded (present locally, intentionally not published)

- **`data/nassau_backup_2026-10-22_pre_phase7.db`:** a database backup, excluded by `.gitignore` (`data/*_backup_*.db`).
- **`__pycache__/` folders:** in `src/`, `dashboard/`, `database/`, `tests/` and `reports/research_paper/scripts/`.
- **`.pytest_cache/`.**
- **Virtual environment `..\venv`:** lives outside the repository folder.

## README status

The README is rendered on GitHub and all relative links resolve. The four submission fields show:

| # | Field | Status | URL |
|---|---|---|---|
| 1 | GitHub Repository Link | ✅ Ready | https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI |
| 2 | Research Paper Link | ✅ Link ready (PDF hosted in the repository; **not formally published or approved**) | https://github.com/vishwasbhattgaonkar1512-cmd/NexRoute-AI/blob/main/reports/research_paper/NexRoute_AI_Research_Paper.pdf |
| 3 | Deployed Project Link | ⏳ Not deployed | — |
| 4 | Project Feedback Video Link | ⏳ Not completed | — |

## Remaining submission requirements

1. **Deployed project.** Deploy `dashboard/app.py` from this repository (for example, Streamlit Community Cloud:
   repository `vishwasbhattgaonkar1512-cmd/NexRoute-AI`, branch `main`, main file `dashboard/app.py`, Python 3.10).
   Then open every page at the resulting `https://` URL and add it to the README.
2. **Feedback video.** Record it (outline in `SUBMISSION_README_VERIFICATION.md` section 6), upload with public
   sharing, check that it opens without signing in, and add the URL to the README.

**Overall submission readiness: PARTIALLY READY — ACTION REQUIRED (2 of 4 fields have verified HTTPS URLs).**
