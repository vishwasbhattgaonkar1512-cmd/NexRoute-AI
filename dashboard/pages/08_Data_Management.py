import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (setup_page, require_database, guard, load_pipeline, current_assumptions, current_weights,  # noqa: E402
                    clear_caches, style, show, headline)

import json  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import RAW_DATA_PATH, FINANCIAL_ASSUMPTIONS, COMPATIBILITY_RULES, LEGACY_ASSUMPTIONS  # noqa: E402
from src.data_validation import missing_value_summary, validate_schema, DataValidationError  # noqa: E402
from src.preprocessing import load_raw, run_pipeline  # noqa: E402
from src import persistence as P  # noqa: E402

setup_page("Data Management", "📦", "Dataset, database, data quality, validation and assumptions")
require_database()
raw = guard(load_raw, what="the raw dataset")
df, issues = guard(load_pipeline, what="the processed dataset")

tabs = st.tabs(["Dataset", "Data-quality report", "Date forensics", "Validation", "Database", "Assumptions", "Exports"])

with tabs[0]:
    k = st.columns(4)
    k[0].metric("Raw rows", f"{len(raw):,}")
    k[1].metric("Columns", len(raw.columns))
    k[2].metric("Rows after cleaning", f"{len(df):,}")
    k[3].metric("Missing / blank cells", int(missing_value_summary(raw)[["missing", "blank_strings"]].sum().sum()))
    st.caption(f"Source file: `{RAW_DATA_PATH.relative_to(RAW_DATA_PATH.parents[2]).as_posix()}` — read-only; never modified.")
    st.markdown("**Column status**")
    st.dataframe(pd.DataFrame([
        ("Order Date", "Observed, but year relabelled — do not read calendar year/weekday literally"),
        ("Ship Date", "Observed, but shifted by a constant number of days"),
        ("Order ID", "Observed; embeds original order year, Customer ID and Product ID"),
        ("lead_time_days_raw", "Derived — raw gap, NOT a lead time"),
        ("lead_time_recovered_days", "Derived — 0–8 day lead time (date-forensics rule); ML target"),
        ("distance_miles", "Derived — straight line to state/province centroid (approximate)"),
        ("Sales, Units, Cost, Gross Profit", "Observed (Gross Profit = Sales − Cost exactly)"),
    ], columns=["column", "status"]), hide_index=True, width="stretch")
    st.markdown("**Missing values by column**")
    st.dataframe(missing_value_summary(raw), hide_index=True, width="stretch")
    st.markdown("**Sample rows (raw)**")
    st.dataframe(raw.head(50), width="stretch")

with tabs[1]:
    dq = P.get_data_quality()
    st.caption(f"Current report: {dq['report_id'].iloc[0] if not dq.empty else '—'} "
               "(older reports are kept in the database, marked not current).")
    icons = {"critical": "🛑", "high": "🔴", "medium": "🟠", "low": "🟡", "info": "ℹ️"}
    for i in issues:
        with st.expander(f"{icons[i['severity']]} [{i['severity'].upper()}] {i['issue_type']} — {i['affected_records']:,} records"):
            st.write(i["issue_description"])
            if i.get("evidence"):
                st.json(i["evidence"], expanded=False)

with tabs[2]:
    ev = next(i for i in issues if i["issue_type"] == "lead_time_recovered_derived")["evidence"]
    ev2 = next(i for i in issues if i["issue_type"] == "date_fields_disguised")["evidence"]
    ev3 = next(i for i in issues if i["issue_type"] == "systemic_lead_time_anomaly")["evidence"]
    st.markdown(f"""
**What was found**
1. Ship Date − Order Date is {ev3['raw_gap_days']['min']:.0f}–{ev3['raw_gap_days']['max']:.0f} days for every row; ship mode
   explains {100 * ev3['eta2_ship_mode_on_raw_gap']:.1f}% of its variance. It is not a lead time.
2. The Order ID year is the original order year. Order Date years were relabelled (table below).
3. Ship Date − (Order Date with the Order ID year) = **{ev2['estimated_shift_days']:,} days + k**, with k = 0–8 days.
4. k behaves like a real lead time: ship mode explains **{100 * ev['eta2_ship_mode_on_recovered_lead']:.0f}%** of its variance and
   Same Day orders are ~0 days. k is published as `lead_time_recovered_days` — **derived, not measured**.
5. Correlation between distance (current factory → destination centroid) and recovered lead time:
   **{headline()['corr_distance_lead_all']:.4f}** for all rows, **{headline()['corr_distance_lead_us']:.4f}** for US rows only.
""")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("Order ID year × Order Date year (rows)")
        st.dataframe(pd.DataFrame(ev2["order_id_year_vs_order_date_year"]).T, width="stretch")
    with c2:
        st.markdown("Recovered lead time: mean by ship mode (days)")
        st.dataframe(pd.Series(ev["recovered_lead_mean_by_ship_mode"], name="mean days"), width="stretch")
    ct = pd.crosstab(df["Ship Mode"], df["lead_time_recovered_days"])
    long = ct.reset_index().melt(id_vars="Ship Mode", var_name="days", value_name="rows")
    fig = px.bar(long, x="days", y="rows", color="Ship Mode", barmode="group",
                 category_orders={"Ship Mode": ["Same Day", "First Class", "Second Class", "Standard Class"]},
                 color_discrete_sequence=["#2a78d6", "#eb6834", "#1baf7a", "#6250d6"],
                 labels={"days": "Recovered lead time (days)", "rows": "Order lines"})
    show(style(fig, 360, "Recovered lead time by ship mode"), ct.rename(columns=lambda c: f"{c:g} d").reset_index())

with tabs[3]:
    st.markdown("Upload a CSV with the same layout to validate it. Nothing is written anywhere.")
    up = st.file_uploader("CSV file", type="csv")
    if up is not None:
        try:
            cand = pd.read_csv(up, dtype=str, keep_default_na=False, na_values=[""])
            validate_schema(cand)
            _, cand_issues = run_pipeline(raw_df=cand)
            st.success(f"Schema OK: {len(cand):,} rows.")
            st.dataframe(pd.DataFrame(cand_issues)[["severity", "issue_type", "affected_records", "issue_description"]],
                         hide_index=True, width="stretch")
        except DataValidationError as exc:
            st.error(f"Validation failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not process the file: {type(exc).__name__}: {exc}")

with tabs[4]:
    stats = P.database_statistics()
    st.dataframe(stats, hide_index=True, width="stretch")
    runs = P.list_runs()
    st.markdown(f"**Saved runs:** {len(runs)}")
    if not runs.empty:
        st.dataframe(runs[["run_id", "run_type", "created_at", "solver_status", "model_version"]], hide_index=True,
                     width="stretch")
    st.markdown("**Integrity check** (read-only)")
    integ = P.integrity_report()
    orphans = sum(integ["orphan_run_rows"].values())
    (st.success if integ["ok"] else st.error)(
        f"Orphan run records: {orphans} · SQLite foreign-key violations: {integ['sqlite_foreign_key_violations']}")
    st.dataframe(pd.DataFrame({"table": list(integ["orphan_run_rows"]),
                               "orphan rows (run_id without a run)": list(integ["orphan_run_rows"].values()),
                               "rows without run_id (legacy)": list(integ["legacy_rows_without_run"].values())}),
                 hide_index=True, width="stretch")
    if integ["unenforced_foreign_keys"]:
        st.caption("Declared in code but **not enforced by the database** (SQLite cannot add a foreign key to a column "
                   "added later; rebuilding the tables was deliberately avoided). Enforced in code instead — runs are "
                   "always saved before their rows — and monitored by this check: "
                   + ", ".join(f"`{x}`" for x in integ["unenforced_foreign_keys"]))
    st.markdown("**Safe operations**")
    st.caption("Refresh derived columns and add a new data-quality report from the raw file. Inserts missing rows "
               "only; never deletes. (A full rebuild is only available from the command line, with explicit "
               "confirmation and an automatic backup.)")
    if st.button("Refresh database from raw file (safe)"):
        from src.build_database import build
        rep = guard(build, verbose=False, what="the database refresh")
        clear_caches()
        st.success(f"Done. Inserted {rep['inserted']}, refreshed {rep['refreshed']}, report {rep['data_quality_report_id']}.")

with tabs[5]:
    a, w = current_assumptions(), current_weights()
    st.markdown("Saved defaults used by every page (What-If can override them per session). "
                "**None of these values come from the source data.**")
    st.dataframe(pd.DataFrame(a.describe()).astype({"value": str}), hide_index=True, width="stretch")
    st.caption("Legacy database rows kept but unused: " + "; ".join(f"{k} ({v})" for k, v in LEGACY_ASSUMPTIONS.items()))
    with st.form("assumptions"):
        vals = {}
        cols = st.columns(3)
        for i, name in enumerate(FINANCIAL_ASSUMPTIONS):
            vals[name] = cols[i % 3].number_input(name, value=float(getattr(a, name)), format="%.4f",
                                                  help=FINANCIAL_ASSUMPTIONS[name]["unit"])
        rule = st.selectbox("Eligibility rule", list(COMPATIBILITY_RULES), index=list(COMPATIBILITY_RULES).index(a.compatibility_rule))
        wc = st.columns(3)
        wts = {"profit_weight": wc[0].number_input("Profit weight", 0.0, 1.0, float(w["profit_weight"]), 0.05),
               "speed_weight": wc[1].number_input("Lead-time weight", 0.0, 1.0, float(w["speed_weight"]), 0.05),
               "risk_weight": wc[2].number_input("Risk weight", 0.0, 1.0, float(w["risk_weight"]), 0.05)}
        if st.form_submit_button("Save defaults", type="primary"):
            try:
                for name, v in vals.items():
                    if v != getattr(a, name):
                        P.save_assumption(name, v)
                if rule != a.compatibility_rule or wts != {k_: w[k_] for k_ in wts}:
                    P.save_settings(wts, rule)
                clear_caches()
                st.success("Saved. Other pages now use these defaults.")
            except ValueError as exc:
                st.error(str(exc))

with tabs[6]:
    st.download_button("Cleaned dataset (CSV)", df.to_csv(index=False), "nexroute_cleaned_dataset.csv", "text/csv")
    st.download_button("Data-quality report (JSON)", json.dumps(issues, indent=2, default=str),
                       "nexroute_data_quality.json", "application/json")
    recs = P.get_recommendations()
    if not recs.empty:
        st.download_button("Latest recommendations (CSV)", recs.to_csv(index=False), "nexroute_recommendations.csv",
                           "text/csv")
    sc = P.get_scenarios()
    if not sc.empty:
        st.download_button("Latest scenario run (CSV)", sc.to_csv(index=False), "nexroute_scenarios.csv", "text/csv")
