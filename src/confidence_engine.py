"""
Confidence and risk scoring.

All scores are transparent HEURISTICS on a 0-1 scale (0 = no concern, 1 = maximum concern).
They are NOT statistically calibrated probabilities. Each component, its formula and its inputs are
returned with the score so the dashboard can explain it.

Components
  model_uncertainty      validation MAE / mean recovered lead time of the active model, plus 0.30 when the
                         candidate factory never made the product (counterfactual; data cannot test it).
  data_quality_risk      0.30 because the lead-time target is derived (not measured), plus 0.70 x share of
                         the product's order lines carrying a data-quality flag (Canadian centroid, possible
                         duplicate, customer with several destinations), plus 0.30 if the product has fewer
                         than MIN_SUPPORT_ROWS lines. Capped at 1.
  missing_info_risk      share of the six decision inputs (revenue, production cost, freight cost, processing
                         lead time, transit time, capacity) that rest on an assumption rather than data.
  compatibility_risk     0 current factory; 0.5 assumed via demonstrated division; 0.9 assumed via
                         'any_factory'; 1.0 not compatible.
  operational_risk       0 current factory; otherwise 0.30 (process change) + 0.50 x moved units / (receiving
                         factory's current units + moved units) + 0.20 if capacity is not modelled. Capped at 1.

overall_risk = mean of the five components. Level: Low < 0.35 <= Medium < 0.60 <= High.
confidence   = the inverse label (High / Medium / Low) of overall_risk.
"""
from __future__ import annotations

import numpy as np

from src.config import MIN_SUPPORT_ROWS

LEVEL_THRESHOLDS = (0.35, 0.60)
COMPONENTS = ["model_uncertainty", "data_quality_risk", "missing_info_risk", "compatibility_risk", "operational_risk"]


def risk_level(score: float) -> str:
    if score is None or np.isnan(score):
        return "Unknown"
    lo, hi = LEVEL_THRESHOLDS
    return "Low" if score < lo else "Medium" if score < hi else "High"


def confidence_label(score: float) -> str:
    return {"Low": "High", "Medium": "Medium", "High": "Low"}.get(risk_level(score), "Unknown")


def model_uncertainty(val_mae: float, mean_target: float, is_current: bool) -> tuple[float, str]:
    if not mean_target or mean_target <= 0 or val_mae is None:
        return 1.0, "No usable model metrics; treated as maximum uncertainty."
    base = min(val_mae / mean_target, 1.0)
    extra = 0.0 if is_current else 0.30
    txt = f"validation MAE {val_mae:.2f} d / mean lead {mean_target:.2f} d = {base:.2f}"
    if extra:
        txt += " + 0.30 (product never made at this factory: prediction is an extrapolation)"
    return min(base + extra, 1.0), txt


def data_quality_risk(flagged_share: float, product_lines: int) -> tuple[float, str]:
    sparse = 0.30 if product_lines < MIN_SUPPORT_ROWS else 0.0
    score = min(0.30 + 0.70 * flagged_share + sparse, 1.0)
    txt = f"0.30 (derived lead-time target) + 0.70 x {flagged_share:.0%} flagged lines"
    if sparse:
        txt += f" + 0.30 (only {product_lines} order lines; < {MIN_SUPPORT_ROWS})"
    return score, txt


def missing_info_risk(is_current: bool, capacity_enabled: bool) -> tuple[float, str]:
    # inputs: revenue, production cost, freight, processing lead, transit, capacity
    if is_current:
        assumed = ["freight cost", "transit time"]          # capacity: current volume is observed to be feasible
    else:
        assumed = ["production cost", "freight cost", "transit time", "capacity"]
    return len(assumed) / 6, f"{len(assumed)} of 6 inputs are assumptions: {', '.join(assumed)}"


def compatibility_risk(is_current: bool, compatible: bool, basis: str) -> tuple[float, str]:
    if is_current:
        return 0.0, "current factory (confirmed)"
    if not compatible:
        return 1.0, basis
    if "any_factory" in basis:
        return 0.9, basis
    return 0.5, basis


def operational_risk(is_current: bool, moved_units: float, receiving_current_units: float,
                     capacity_enabled: bool) -> tuple[float, str]:
    if is_current:
        return 0.0, "no change"
    denom = receiving_current_units + moved_units
    share = moved_units / denom if denom > 0 else 1.0
    cap = 0.0 if capacity_enabled else 0.20
    score = min(0.30 + 0.50 * share + cap, 1.0)
    txt = f"0.30 (process change) + 0.50 x {share:.0%} (moved units / receiving factory's new volume)"
    if cap:
        txt += " + 0.20 (factory capacity not modelled)"
    return score, txt


def assess(*, is_current: bool, compatible: bool, compatibility_basis: str, val_mae: float, mean_target: float,
           flagged_share: float, product_lines: int, moved_units: float, receiving_current_units: float,
           capacity_enabled: bool) -> dict:
    parts = {
        "model_uncertainty": model_uncertainty(val_mae, mean_target, is_current),
        "data_quality_risk": data_quality_risk(flagged_share, product_lines),
        "missing_info_risk": missing_info_risk(is_current, capacity_enabled),
        "compatibility_risk": compatibility_risk(is_current, compatible, compatibility_basis),
        "operational_risk": operational_risk(is_current, moved_units, receiving_current_units, capacity_enabled),
    }
    overall = float(np.mean([v[0] for v in parts.values()]))
    out = {k: round(float(v[0]), 3) for k, v in parts.items()}
    out.update({f"{k}_explanation": v[1] for k, v in parts.items()})
    out.update({"overall_risk": round(overall, 3), "risk_level": risk_level(overall),
                "confidence": confidence_label(overall),
                "score_note": "Heuristic 0-1 scores, not probabilities. See src/confidence_engine.py."})
    return out
