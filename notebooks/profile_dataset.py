"""
Phase 1: Dataset profiling for Nassau Candy Distributor.
Run: python notebooks/profile_dataset.py
Outputs a JSON + text report to reports/eda/
"""
import pandas as pd
import numpy as np
import json
import os

RAW_PATH = "data/raw/nassau_candy_distributor.csv"
OUT_DIR = "reports/eda"
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(RAW_PATH, dtype=str)  # read as str first, don't assume types
report = {}

report["n_rows"] = len(df)
report["n_cols"] = len(df.columns)
report["columns"] = list(df.columns)

# missing values
report["missing_values"] = df.isna().sum().to_dict()
report["missing_values"] = {k: int(v) for k, v in report["missing_values"].items()}

# duplicates
report["duplicate_rows_full"] = int(df.duplicated().sum())
report["duplicate_row_id"] = int(df["Row ID"].duplicated().sum())

# unique counts
for col in ["Order ID", "Customer ID", "Product ID", "Product Name", "Division",
            "Region", "Country/Region", "State/Province", "City", "Ship Mode", "Postal Code"]:
    report.setdefault("unique_counts", {})[col] = int(df[col].nunique())

# how many rows per order id (multi-line orders)
rows_per_order = df.groupby("Order ID").size()
report["orders_total"] = int(rows_per_order.shape[0])
report["rows_per_order_distribution"] = rows_per_order.value_counts().to_dict()
report["rows_per_order_distribution"] = {int(k): int(v) for k, v in report["rows_per_order_distribution"].items()}

# Date parsing - try dd-mm-yyyy format based on sample seen (03-01-2024 ... 30-06-2026)
def try_parse_dates(series, fmt):
    parsed = pd.to_datetime(series, format=fmt, errors="coerce")
    n_failed = parsed.isna().sum() - series.isna().sum()
    return parsed, n_failed

order_dt_dmy, fail_order_dmy = try_parse_dates(df["Order Date"], "%d-%m-%Y")
ship_dt_dmy, fail_ship_dmy = try_parse_dates(df["Ship Date"], "%d-%m-%Y")

order_dt_mdy, fail_order_mdy = try_parse_dates(df["Order Date"], "%m-%d-%Y")
ship_dt_mdy, fail_ship_mdy = try_parse_dates(df["Ship Date"], "%m-%d-%Y")

report["date_format_test"] = {
    "dd-mm-yyyy_order_fail": int(fail_order_dmy),
    "dd-mm-yyyy_ship_fail": int(fail_ship_dmy),
    "mm-dd-yyyy_order_fail": int(fail_order_mdy),
    "mm-dd-yyyy_ship_fail": int(fail_ship_mdy),
}

# Use whichever format parses with fewer failures; report both sets of stats
chosen_fmt = "%d-%m-%Y" if (fail_order_dmy + fail_ship_dmy) <= (fail_order_mdy + fail_ship_mdy) else "%m-%d-%Y"
report["chosen_date_format"] = chosen_fmt

order_dt = pd.to_datetime(df["Order Date"], format=chosen_fmt, errors="coerce")
ship_dt = pd.to_datetime(df["Ship Date"], format=chosen_fmt, errors="coerce")

report["order_date_range"] = [str(order_dt.min()), str(order_dt.max())]
report["ship_date_range"] = [str(ship_dt.min()), str(ship_dt.max())]
report["order_date_parse_failures"] = int(order_dt.isna().sum())
report["ship_date_parse_failures"] = int(ship_dt.isna().sum())

lead_time = (ship_dt - order_dt).dt.days
report["lead_time_stats"] = {
    "min": float(np.nanmin(lead_time)) if lead_time.notna().any() else None,
    "max": float(np.nanmax(lead_time)) if lead_time.notna().any() else None,
    "mean": float(np.nanmean(lead_time)) if lead_time.notna().any() else None,
    "median": float(np.nanmedian(lead_time)) if lead_time.notna().any() else None,
    "std": float(np.nanstd(lead_time)) if lead_time.notna().any() else None,
    "negative_count": int((lead_time < 0).sum()),
    "zero_count": int((lead_time == 0).sum()),
    "over_365_count": int((lead_time > 365).sum()),
    "over_30_count": int((lead_time > 30).sum()),
    "null_count": int(lead_time.isna().sum()),
}

# percentile distribution of lead time to understand shape
report["lead_time_percentiles"] = {
    str(p): float(np.nanpercentile(lead_time.dropna(), p)) for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]
}

# Year breakdown - are order year and ship year wildly different (systemic issue)?
order_year = order_dt.dt.year
ship_year = ship_dt.dt.year
report["order_year_counts"] = order_year.value_counts().sort_index().to_dict()
report["order_year_counts"] = {int(k): int(v) for k, v in report["order_year_counts"].items()}
report["ship_year_counts"] = ship_year.value_counts().sort_index().to_dict()
report["ship_year_counts"] = {int(k): int(v) for k, v in report["ship_year_counts"].items()}

year_gap = ship_year - order_year
report["year_gap_distribution"] = year_gap.value_counts().sort_index().to_dict()
report["year_gap_distribution"] = {str(k): int(v) for k, v in report["year_gap_distribution"].items()}

# numeric fields
for col in ["Sales", "Units", "Gross Profit", "Cost"]:
    series = pd.to_numeric(df[col], errors="coerce")
    report.setdefault("numeric_stats", {})[col] = {
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "null_count": int(series.isna().sum()),
        "negative_count": int((series < 0).sum()),
    }

# Division / Region / Ship Mode / Product Name distributions
report["division_counts"] = df["Division"].value_counts().to_dict()
report["region_counts"] = df["Region"].value_counts().to_dict()
report["ship_mode_counts"] = df["Ship Mode"].value_counts().to_dict()
report["product_name_counts"] = df["Product Name"].value_counts().to_dict()
report["country_counts"] = df["Country/Region"].value_counts().to_dict()
report["state_counts"] = df["State/Province"].value_counts().head(20).to_dict()

# product name consistency check against the 15 expected products
expected_products = [
    "Wonka Bar - Nutty Crunch Surprise", "Wonka Bar - Fudge Mallows", "Wonka Bar -Scrumdiddlyumptious",
    "Wonka Bar - Milk Chocolate", "Wonka Bar - Triple Dazzle Caramel", "Laffy Taffy", "SweeTARTS",
    "Nerds", "Fun Dip", "Fizzy Lifting Drinks", "Everlasting Gobstopper", "Hair Toffee",
    "Lickable Wallpaper", "Wonka Gum", "Kazookles"
]
actual_products = set(df["Product Name"].unique())
report["expected_products_not_found"] = [p for p in expected_products if p not in actual_products]
report["actual_products_not_expected"] = [p for p in actual_products if p not in expected_products]

with open(f"{OUT_DIR}/data_profile.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print(json.dumps(report, indent=2, default=str)[:3000])
print("\n... (full report written to reports/eda/data_profile.json)")
