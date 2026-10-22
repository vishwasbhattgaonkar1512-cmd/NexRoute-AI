"""Dashboard headline statistics are computed from the data, not hard-coded."""
import re
from pathlib import Path

import pandas as pd
import pytest

from src.data_stats import headline_stats, scope_text
from src.preprocessing import run_pipeline
from tests.conftest import make_row

ROOT = Path(__file__).resolve().parent.parent


def test_headline_stats_match_direct_computation():
    df, _ = run_pipeline()
    s = headline_stats(df)
    counts = df["Product Name"].value_counts()
    assert s["n_sparse_products"] == int((counts < 30).sum())
    assert s["top_division_share_pct"] == pytest.approx(100 * df["Division"].value_counts(normalize=True).iloc[0])
    assert s["n_us_states"] + s["n_canadian_provinces"] == s["n_destinations"] == df["State/Province"].nunique()
    assert s["corr_distance_lead_all"] == pytest.approx(df["distance_miles"].corr(df["lead_time_recovered_days"]))
    assert 0 <= s["ship_mode_eta2_pct"] <= 100
    assert "Canadian provinces" in scope_text(s)


def test_headline_stats_follow_the_data(synthetic_raw):
    """With different data the statistics change (proves nothing is hard-coded)."""
    df, _ = run_pipeline(raw_df=synthetic_raw)
    s = headline_stats(df)
    assert s["n_products"] == 1 and s["n_sparse_products"] == 0 and s["top_division_share_pct"] == 100
    assert s["n_canadian_provinces"] == 1


def test_empty_frame_rejected(synthetic_raw):
    df, _ = run_pipeline(raw_df=synthetic_raw)
    with pytest.raises(ValueError):
        headline_stats(df.iloc[0:0])


def test_no_hard_coded_headline_figures_in_dashboard():
    pattern = re.compile(r"97%|\b7 products|~70%|0\.002")
    for f in [ROOT / "dashboard" / "app.py", *(ROOT / "dashboard" / "pages").glob("*.py")]:
        assert not pattern.search(f.read_text(encoding="utf-8")), f.name
