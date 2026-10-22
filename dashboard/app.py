import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import setup_page, require_database, lead_time_warning, estimate_note  # noqa: E402

import streamlit as st  # noqa: E402

setup_page("NexRoute AI", "🏭",
           "Intelligent factory reallocation & shipping optimization — Nassau Candy Distributor")
require_database()

st.markdown("""
NexRoute AI helps decide **which of the five factories should make each of the 15 products**, using
historical orders, factory-to-destination geography, a lead-time model, transparent cost estimates,
risk scoring and constrained optimization.
""")

c1, c2 = st.columns(2)
with c1:
    lead_time_warning()
with c2:
    estimate_note()

st.subheader("What the data can and cannot tell us")
st.markdown("""
| | Status |
|---|---|
| Orders, products, sales, units, cost, destinations | **Observed** in the source file |
| Ship Date − Order Date (904–1,642 days) | **Unusable** — dates are disguised; never shown as a lead time |
| Lead time 0–8 days by ship mode | **Derived** with a stated, tested rule (Data Management → Date forensics) |
| Effect of distance / factory on lead time | **Not measurable** in the data (correlation ≈ 0.002) |
| Freight rates, factory costs, capacity, compatibility | **Not in the data** — editable analyst assumptions |
| Distances | **Approximate**: straight line to state/province centroids |
""")

st.subheader("Pages")
st.markdown("""
1. **Executive Dashboard** — KPIs, current allocation, optimization summary, data-quality warnings
2. **Factory Optimization** — one product across all five factories: eligibility, distance, cost, recommendation
3. **What-If Analysis** — five scenarios with adjustable assumptions, before/after comparison
4. **Recommendations** — ranked, explained recommendations with a review status workflow
5. **Risk & Impact** — operational, data-quality and model risk; financial impact
6. **Factory Map** — factories, destinations, distance matrix, coverage, demand clusters
7. **Model Analytics** — model comparison, validation vs test, importance, residuals, registry
8. **Data Management** — dataset, database, data-quality report, validation, assumptions
""")
st.caption("First-time setup: `python -m src.prediction_engine` then `python -m src.build_database`. "
           "See README.md.")
