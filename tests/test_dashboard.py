"""Every dashboard page renders without an exception (Streamlit's headless AppTest)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = [ROOT / "dashboard" / "app.py"] + sorted((ROOT / "dashboard" / "pages").glob("*.py"))


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_renders(page):
    at = AppTest.from_file(str(page), default_timeout=240).run()
    assert not at.exception, [e.value for e in at.exception]
