"""
Product-factory compatibility.

The source data contains NO compatibility information. The only facts are the 15 baseline
assignments (each product is made at exactly one factory). Rules (configurable, see config.COMPATIBILITY_RULES):

  demonstrated_division (default)  factory f may make product p if f already makes another product of p's
                                   division. Derived from the baseline; NOT verified with the business.
  any_factory                      every factory may make every product.
  baseline_only                    only the current factory (reallocation impossible).

The current factory is always compatible ("confirmed: baseline assignment").
"""
from __future__ import annotations

import pandas as pd

from src.config import PRODUCT_FACTORY_BASELINE, FACTORIES, COMPATIBILITY_RULES

CONFIRMED = "confirmed (current baseline assignment)"


def baseline_map() -> dict:
    return {p["product_name"]: p for p in PRODUCT_FACTORY_BASELINE}


def factory_division_capability() -> dict:
    """{factory: set of divisions it currently makes} from the baseline assignments."""
    cap = {f["factory_name"]: set() for f in FACTORIES}
    for p in PRODUCT_FACTORY_BASELINE:
        cap.setdefault(p["factory_name"], set()).add(p["division"])
    return cap


def compatibility(product_name: str, factory_name: str, rule: str) -> tuple[bool, str]:
    """(is_compatible, basis). Unknown product or factory -> (False, reason)."""
    if rule not in COMPATIBILITY_RULES:
        raise ValueError(f"unknown compatibility rule {rule!r}")
    bm = baseline_map()
    if product_name not in bm:
        return False, "unknown product (no baseline assignment)"
    if factory_name not in {f["factory_name"] for f in FACTORIES}:
        return False, "unknown factory"
    p = bm[product_name]
    if factory_name == p["factory_name"]:
        return True, CONFIRMED
    if rule == "baseline_only":
        return False, "not allowed: rule 'baseline_only'"
    if rule == "any_factory":
        return True, "ASSUMED (rule 'any_factory'; no supporting data)"
    makes = factory_division_capability().get(factory_name, set())
    if p["division"] in makes:
        return True, (f"ASSUMED: {factory_name} already makes {p['division']} products "
                      "(unverified with the business)")
    return False, (f"not allowed: {factory_name} makes no {p['division']} products "
                   f"(it makes: {', '.join(sorted(makes)) or 'nothing'})")


def compatibility_matrix(rule: str) -> pd.DataFrame:
    rows = []
    for p in PRODUCT_FACTORY_BASELINE:
        for f in FACTORIES:
            ok, basis = compatibility(p["product_name"], f["factory_name"], rule)
            rows.append({"product_name": p["product_name"], "division": p["division"],
                         "factory_name": f["factory_name"], "is_current": f["factory_name"] == p["factory_name"],
                         "compatible": ok, "basis": basis})
    return pd.DataFrame(rows)
