# Streamlit Community Cloud Deployment Guide — NexRoute AI

Follow these steps in order. The background for each setting is in `STREAMLIT_DEPLOYMENT_AUDIT.md`.

## Step 1 — Approve and publish the pinned requirements (one-time)

The pinned `requirements.txt` is prepared locally but **not yet pushed**. Review it, then commit and push it from the
project folder:

```bash
git diff requirements.txt
git add requirements.txt STREAMLIT_DEPLOYMENT_AUDIT.md STREAMLIT_DEPLOYMENT_GUIDE.md
git commit -m "Pin verified dependency versions for Streamlit Cloud; add deployment audit and guide"
git push origin main
```

This is a normal push with no force needed. Deploying without this step is possible, but it risks the newest-version
problems described in audit section 4.

## Step 2 — Create the app

1. Go to **https://share.streamlit.io** and sign in with the GitHub account that owns the repository.
2. Choose **Create app**, then deploy a public app from GitHub.
3. Enter **exactly** these settings:

   | Setting | Value |
   |---|---|
   | Repository | `vishwasbhattgaonkar1512-cmd/NexRoute-AI` |
   | Branch | `main` |
   | Main file path | `dashboard/app.py` |
   | App URL (optional) | Choose a subdomain, e.g. `nexroute-ai`. Availability is not guaranteed. |
   | Advanced settings → Python version | **3.10** |
   | Advanced settings → Secrets | *Leave empty.* No secrets are needed. |

4. Click **Deploy**. The first build installs the packages, which takes a few minutes. Streamlit Cloud uses the
   repository-root `requirements.txt`, because there is none inside `dashboard/`.

## Step 3 — Test the public URL (required before claiming deployment)

Open the `https://…streamlit.app` URL in a **private or incognito** window, so that you are not signed in, and check:

| # | Check | Expected |
|---|---|---|
| 1 | Home page | Loads with the two warning boxes |
| 2 | Executive Dashboard | KPIs show 10,194 order lines and 5,044 customers; red data-quality banner |
| 3 | Factory Optimization | Switching product updates the five-factory table |
| 4 | What-If Analysis | Moving a sidebar slider changes the scenario table |
| 5 | Recommendations | A saved run is listed; 15 products; 2 "Reallocate" |
| 6 | Risk & Impact | "Prediction range coverage (test)" shows 100.0% |
| 7 | Factory Map | Map shows five coloured factory squares |
| 8 | Model Analytics | Selected model is "baseline ship mode mean"; final test MAE 0.806 |
| 9 | Data Management | Integrity check reports 0 orphan run records |

If a page shows an error, open **Manage app → Logs** in Streamlit Cloud. The most likely causes are a wrong Python
version, or the pinned requirements not having been pushed.

## Step 4 — Record the URL

Once all 9 checks pass, send me the URL. I'll re-verify it, add it to the README's "Deployed Project Link" field, and
update `SUBMISSION_README_VERIFICATION.md`.

## Things to know about the public app

- **Changes are temporary.** Saving runs, changing recommendation statuses, saving defaults and "Refresh database" all
  write to the app's own copy of the database. These changes are **lost when the app restarts or sleeps**. Anyone with
  the link can make them.
- **Sleep.** After a period without visitors the app sleeps. The next visitor waits about a minute for it to wake.
  Open it shortly before a demonstration.
- **Data downloads.** The dataset can be downloaded from the public app (Data Management → Exports). This is covered by
  the redistribution permission you confirmed.

## Running locally (unchanged)

```bash
cd D:\nassau-candy-optimization\nassau-candy-optimization
..\venv\Scripts\Activate.ps1
streamlit run dashboard/app.py          # http://localhost:8501
python -m pytest -v                     # 109 tests
```
