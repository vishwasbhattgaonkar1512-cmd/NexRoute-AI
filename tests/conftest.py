"""Shared fixtures. Synthetic data mimics the real file's structure (including the date disguise)."""
import datetime as dt

import pandas as pd
import pytest

from src.config import REQUIRED_COLUMNS

LEAD_BY_MODE = {"Same Day": 0, "First Class": 2, "Second Class": 3, "Standard Class": 5}


def make_row(row_id, product="Wonka Bar - Milk Chocolate", pid="CHO-MIL-31000", division="Chocolate",
             mode="Standard Class", state="Texas", region="Gulf", country="United States", orig_year=2021,
             month=3, day=10, lead=None, units=2, price=3.25, unit_cost=1.0, customer=100001):
    lead = LEAD_BY_MODE[mode] if lead is None else lead
    orig = dt.date(orig_year, month, day)
    shown_year = 2024 if orig_year in (2021, 2022) else 2025
    order_shown = dt.date(shown_year, month, day)
    ship = orig + dt.timedelta(days=2000 + lead)
    sales, cost = round(units * price, 2), round(units * unit_cost, 2)
    return {
        "Row ID": str(row_id), "Order ID": f"US-{orig_year}-{customer}-{pid}",
        "Order Date": order_shown.strftime("%d-%m-%Y"), "Ship Date": ship.strftime("%d-%m-%Y"),
        "Ship Mode": mode, "Customer ID": str(customer), "Country/Region": country, "City": "X",
        "State/Province": state, "Postal Code": "77095", "Division": division, "Region": region,
        "Product ID": pid, "Product Name": product, "Sales": str(sales), "Units": str(units),
        "Gross Profit": str(round(sales - cost, 2)), "Cost": str(cost),
    }


@pytest.fixture
def synthetic_raw():
    modes = list(LEAD_BY_MODE)
    rows = []
    for i in range(1, 121):
        rows.append(make_row(i, mode=modes[i % 4], orig_year=2021 + (i * 4) // 121, month=1 + (i % 12),
                             day=1 + (i % 27), customer=100000 + i % 30,
                             state=["Texas", "New York", "California", "Ontario"][i % 4],
                             region=["Gulf", "Atlantic", "Pacific", "Interior"][i % 4],
                             country="Canada" if i % 4 == 3 else "United States"))
    df = pd.DataFrame(rows)
    assert list(df.columns) == REQUIRED_COLUMNS
    return df


@pytest.fixture
def temp_engine(tmp_path):
    from database.connection import get_engine
    return get_engine(tmp_path / "test.db")
