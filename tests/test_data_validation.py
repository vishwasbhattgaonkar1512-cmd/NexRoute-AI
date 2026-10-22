"""Data loading, validation, date forensics, preprocessing, missing values."""
import pandas as pd
import pytest

from src.data_validation import (
    DataValidationError, validate_schema, missing_value_summary, recover_lead_time, estimate_date_shift,
    rebuild_original_order_date, order_id_year, eta_squared, make_issue,
)
from src.preprocessing import run_pipeline, clean, load_raw
from tests.conftest import make_row, LEAD_BY_MODE


def issue_types(issues):
    return {i["issue_type"] for i in issues}


# ---------------- schema / loading
def test_raw_file_loads_with_required_columns():
    raw = load_raw()
    validate_schema(raw)
    assert len(raw) == 10194


def test_empty_dataset_raises():
    with pytest.raises(DataValidationError, match="empty"):
        validate_schema(pd.DataFrame())


def test_missing_columns_raises(synthetic_raw):
    with pytest.raises(DataValidationError, match="Ship Date"):
        run_pipeline(raw_df=synthetic_raw.drop(columns=["Ship Date"]))


def test_missing_value_summary_counts_blanks(synthetic_raw):
    df = synthetic_raw.copy()
    df.loc[0, "City"] = None
    df.loc[1, "City"] = "  "
    mv = missing_value_summary(df).set_index("column")
    assert mv.loc["City", "missing"] == 1 and mv.loc["City", "blank_strings"] == 1


# ---------------- dates
def test_order_id_year_extraction():
    s = pd.Series(["US-2021-103800-CHO-MIL-31000", "CA-2024-1-X", "garbage"])
    out = order_id_year(s)
    assert out.iloc[0] == 2021 and out.iloc[1] == 2024 and pd.isna(out.iloc[2])


def test_rebuild_handles_feb_29_on_non_leap_year():
    od = pd.to_datetime(pd.Series(["29-02-2024"]), format="%d-%m-%Y")
    out = rebuild_original_order_date(od, pd.Series([2021]))
    assert pd.isna(out.iloc[0])


def test_recovered_lead_time_matches_construction(synthetic_raw):
    df, issues = run_pipeline(raw_df=synthetic_raw)
    expected = df["Ship Mode"].map(LEAD_BY_MODE)
    assert (df["lead_time_recovered_days"] == expected).all()
    assert "systemic_lead_time_anomaly" in issue_types(issues)


def test_shift_estimated_from_same_day_rows(synthetic_raw):
    df, _ = run_pipeline(raw_df=synthetic_raw)
    assert estimate_date_shift(df["ship_date"], df["order_date_rebuilt"], df["Ship Mode"]) == 2000


def test_invalid_dates_flagged_and_dropped(synthetic_raw):
    bad = synthetic_raw.copy()
    bad.loc[0, "Order Date"] = "31-02-2024"
    bad.loc[1, "Ship Date"] = "not a date"
    df, issues = run_pipeline(raw_df=bad)
    assert len(df) == len(bad) - 2
    assert {"invalid_date_format", "rows_dropped_unusable"} <= issue_types(issues)


def test_out_of_range_recovered_lead_set_missing(synthetic_raw):
    raw = pd.concat([synthetic_raw, pd.DataFrame([make_row(999, lead=40)])], ignore_index=True)
    df, _ = run_pipeline(raw_df=raw)
    row = df[df["Row ID"] == "999"].iloc[0]
    assert pd.isna(row["lead_time_recovered_days"]) and row["lead_time_recovered_flag"] == "out_of_range"


def test_real_data_recovered_lead_time_is_plausible():
    df, issues = run_pipeline()
    assert df["lead_time_recovered_days"].between(0, 14).all()
    means = df.groupby("Ship Mode")["lead_time_recovered_days"].mean()
    assert means["Same Day"] < means["First Class"] < means["Second Class"] < means["Standard Class"]
    assert {"date_fields_disguised", "lead_time_recovered_derived"} <= issue_types(issues)


def test_raw_dataset_is_not_modified(synthetic_raw):
    before = synthetic_raw.copy()
    run_pipeline(raw_df=synthetic_raw)
    pd.testing.assert_frame_equal(before, synthetic_raw)


def test_pipeline_issue_log_does_not_accumulate():
    _, a = run_pipeline()
    _, b = run_pipeline()
    assert len(a) == len(b)


# ---------------- numeric / other checks
def test_negative_and_non_numeric_values_flagged(synthetic_raw):
    bad = synthetic_raw.copy()
    bad.loc[0, "Units"] = "-3"
    bad.loc[1, "Sales"] = "abc"
    df, issues = run_pipeline(raw_df=bad)
    assert {"non_positive_values", "invalid_numeric"} <= issue_types(issues)
    assert "1" in set(df["Row ID"])      # negative row kept and flagged
    assert "2" not in set(df["Row ID"])  # non-numeric row dropped


def test_unknown_destination_and_product_flagged(synthetic_raw):
    raw = pd.concat([synthetic_raw, pd.DataFrame([make_row(500, state="Atlantis"),
                                                   make_row(501, product="Mystery Bar", pid="X-1")])],
                    ignore_index=True)
    df, issues = run_pipeline(raw_df=raw)
    assert {"unknown_destination", "unmapped_products", "rows_dropped_unmapped_product"} <= issue_types(issues)
    assert df.loc[df["State/Province"] == "Atlantis", "distance_miles"].isna().all()


def test_duplicate_lines_flagged_not_dropped(synthetic_raw):
    dup = synthetic_raw.iloc[[0]].copy()
    dup["Row ID"] = "777"
    df, issues = run_pipeline(raw_df=pd.concat([synthetic_raw, dup], ignore_index=True))
    assert "possible_duplicate_lines" in issue_types(issues)
    assert len(df) == len(synthetic_raw) + 1 and df["is_possible_duplicate"].sum() == 1


def test_eta_squared_bounds():
    v = pd.Series([0, 0, 5, 5.0])
    g = pd.Series(["a", "a", "b", "b"])
    assert eta_squared(v, g) == pytest.approx(1.0)
    assert pd.isna(eta_squared(pd.Series([1.0, 1.0]), pd.Series(["a", "b"])))


def test_make_issue_rejects_unknown_severity():
    with pytest.raises(ValueError):
        make_issue("x", "y", 1, "catastrophic")
