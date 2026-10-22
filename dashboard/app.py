import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

st.set_page_config(page_title="Nassau Candy — Factory Reallocation System", layout="wide", page_icon="🏭")

st.title("🏭 Nassau Candy Distributor — Factory Reallocation & Shipping Optimization")
st.caption("Decision-support system — see sidebar for modules.")

st.warning(
    "⚠️ **Critical data-quality finding**: the source file's Ship Date − Order Date field spans "
    "900–1,640+ days and does not vary meaningfully by Ship Mode (e.g. 'Same Day' shows the same "
    "multi-year gap as 'Standard Class'). This is not a valid real-world delivery-time signal. "
    "All lead-time predictions in this app are a **de-trended relative index**, not calendar days, "
    "and every recommendation is labeled with its actual model confidence. "
    "Full explanation: `DEVELOPMENT_PROGRESS.md` in the project root.",
    icon="⚠️",
)

st.markdown("""
### Modules (left sidebar)
1. **Executive Dashboard** — current operations at a glance
2. **Factory Optimization Simulator** — pick a product + destination, compare all 5 factories
3. **What-If Analysis** — custom scenario comparison with adjustable assumptions
4. **Recommendations** — ranked reallocation recommendations across all 15 products
5. **Risk & Impact Panel** — data-quality and reliability warnings
6. **Factory Map** — geographic view of factories and routes
7. **Model Analytics** — ML model comparison, residuals, feature importance, clustering

Run `python src/build_database.py --rebuild` then `python src/prediction_engine.py` before first use
if `data/nassau.db` or `models/trained/` don't exist yet.
""")

from database.connection import get_session
from database.models import Order, OrderItem, Product, Factory, Customer
import os

if os.path.exists("data/nassau.db"):
    session = get_session()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders", session.query(Order).count())
    c2.metric("Order lines", session.query(OrderItem).count())
    c3.metric("Products", session.query(Product).count())
    c4.metric("Factories", session.query(Factory).count())
    session.close()
else:
    st.error("Database not found. Run `python src/build_database.py --rebuild` first.")
