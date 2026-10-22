import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (setup_page, require_database, guard, current_assumptions, current_weights, recommend_cached,  # noqa: E402
                    usd, risk_badge, DECISION_LABELS, estimate_note, lead_time_warning)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from database.models import RECOMMENDATION_STATUSES  # noqa: E402
from src import persistence as P  # noqa: E402

setup_page("Recommendations", "🎯", "Ranked, explained factory recommendations with a review workflow")
require_database()

runs = guard(P.list_runs, "recommendation", what="saved runs")
c1, c2 = st.columns([3, 1])
with c2:
    if st.button("Run optimization now & save", type="primary",
                 help="Uses the saved default assumptions and weights (edit them on Data Management)."):
        res = guard(recommend_cached, current_assumptions(), current_weights(), what="the optimization")
        res = dict(res, run=dict(res["run"]))
        import datetime as dt, uuid
        res["run"]["run_id"] = "opt-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        rid = guard(P.save_recommendation_run, res, what="saving the run")
        st.success(f"Saved run {rid}.")
        runs = P.list_runs("recommendation")
if runs.empty:
    st.info("No saved recommendation run yet. Click **Run optimization now & save**.")
    st.stop()
with c1:
    run_id = st.selectbox("Saved run", runs["run_id"],
                          format_func=lambda r: f"{r} · {runs.set_index('run_id').loc[r, 'solver_status']}")
run = runs.set_index("run_id").loc[run_id]
recs = guard(P.get_recommendations, run_id, what="recommendations")

estimate_note()
k = st.columns(4)
k[0].metric("Products", len(recs))
k[1].metric("Reallocate", int((recs["decision"] == "REALLOCATE").sum()))
k[2].metric("Est. profit impact", usd(recs["estimated_profit_impact"].sum(), True))
k[3].metric("Model version", run["model_version"] or "—")

f1, f2, f3 = st.columns(3)
dec = f1.multiselect("Decision", sorted(recs["decision"].unique()), format_func=DECISION_LABELS.get)
risk = f2.multiselect("Risk", ["Low", "Medium", "High"])
stat = f3.multiselect("Status", RECOMMENDATION_STATUSES)
view = recs.copy()
if dec:
    view = view[view["decision"].isin(dec)]
if risk:
    view = view[view["risk_level"].isin(risk)]
if stat:
    view = view[view["recommendation_status"].isin(stat)]

show_cols = view.assign(decision=view["decision"].map(DECISION_LABELS), risk=view["risk_level"].map(risk_badge))
st.dataframe(show_cols[["recommendation_rank", "product_name", "current_factory", "decision", "recommended_factory",
                        "estimated_profit_impact", "predicted_lead_time_improvement", "risk", "confidence_label",
                        "score", "recommendation_status"]],
             hide_index=True, width="stretch", column_config={
                 "recommendation_rank": "Rank", "product_name": "Product", "current_factory": "Current",
                 "decision": "Decision", "recommended_factory": "Recommended",
                 "estimated_profit_impact": st.column_config.NumberColumn("Est. profit Δ", format="$%+.2f"),
                 "predicted_lead_time_improvement": st.column_config.NumberColumn("Est. days faster", format="%+.2f"),
                 "risk": "Risk", "confidence_label": "Confidence",
                 "score": st.column_config.NumberColumn("Score", format="%+.2f"),
                 "recommendation_status": "Status"})
st.caption("Ranking: reallocations first (highest score), then 'keep' decisions ordered by how close the best "
           "alternative came. Confidence is a heuristic label, not a probability.")

st.subheader("Rationale and review")
lead_time_warning()
for _, r in view.iterrows():
    head = f"#{r['recommendation_rank']} {r['product_name']} — {DECISION_LABELS.get(r['decision'], r['decision'])}"
    if r["decision"] == "REALLOCATE":
        head += f" → {r['recommended_factory']}"
    with st.expander(f"{head}   ·   status: {r['recommendation_status']}"):
        st.write(r["recommendation_reason"])
        with st.form(f"status-{r['recommendation_id']}"):
            cols = st.columns([1, 3, 1])
            new = cols[0].selectbox("Status", RECOMMENDATION_STATUSES,
                                    index=RECOMMENDATION_STATUSES.index(r["recommendation_status"] or "proposed"))
            note = cols[1].text_input("Note (optional)", value="")
            if cols[2].form_submit_button("Update"):
                guard(P.update_recommendation_status, int(r["recommendation_id"]), new, note or None,
                      what="the status update")
                st.success("Status updated.")
                st.rerun()
        hist = P.get_status_history(int(r["recommendation_id"]))
        if not hist.empty:
            st.dataframe(hist[["changed_at", "old_status", "new_status", "note"]], hide_index=True,
                         width="stretch")

with st.expander("Run details (objective, weights, assumptions)"):
    st.write(f"**Objective:** {run['objective']}")
    st.write(f"**Solver:** {run['solver_status']} — {run['solver_message']}")
    import json
    st.json({"weights": json.loads(run["weights_json"] or "{}"),
             "assumptions": json.loads(run["assumptions_json"] or "{}")})
