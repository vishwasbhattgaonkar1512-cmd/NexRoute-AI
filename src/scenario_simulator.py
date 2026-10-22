"""
Phase 6: Factory reallocation scenario simulator (master prompt section 10).
"""
import joblib
import pandas as pd
from src.config import FACTORIES, PRODUCT_FACTORY_BASELINE, MODELS_TRAINED_DIR
from src.geographic_engine import distance_factory_to_state
from src.confidence_engine import confidence_label
from src.profit_engine import estimate_scenario_profit

FACTORY_NAMES = [f["factory_name"] for f in FACTORIES]


def _load_best_model():
    meta = joblib.load(MODELS_TRAINED_DIR / "model_meta.joblib")
    best_name = meta["best_model_name"]
    model = joblib.load(MODELS_TRAINED_DIR / f"{best_name}.joblib")
    return model, meta


def eligible_factories(product_name: str):
    """
    Compatibility rule (documented assumption, see DEVELOPMENT_PROGRESS.md):
    - the baseline factory is always 'confirmed compatible'.
    - any other factory is 'unverified - assumed compatible within same Division' (lower confidence),
      since no compatibility data beyond the 15 baseline assignments was supplied.
    """
    baseline = next(p for p in PRODUCT_FACTORY_BASELINE if p["product_name"] == product_name)
    current_factory = baseline["factory_name"]
    division = baseline["division"]

    result = []
    for fname in FACTORY_NAMES:
        if fname == current_factory:
            result.append({"factory_name": fname, "is_current": True, "compatibility": "confirmed (baseline assignment)"})
        else:
            result.append({"factory_name": fname, "is_current": False,
                            "compatibility": "unverified - assumed compatible within same Division (ANALYST ASSUMPTION)"})
    return result, current_factory, division


def predict_lead_time_index(model, meta, division, factory, region, state, ship_mode,
                             distance_miles, units, sales, order_month=6, order_dow=2, order_year=2025):
    row = pd.DataFrame([{
        "Division": division, "current_factory": factory, "Region": region,
        "State/Province": state, "Ship Mode": ship_mode, "order_year": order_year,
        "distance_miles": distance_miles, "Units": units, "Sales": sales,
        "order_month": order_month, "order_dow": order_dow,
    }])
    pred = model.predict(row)[0]
    residual_std = meta["residual_std"]
    return float(pred), float(residual_std)


def simulate_product_scenario(product_name: str, destination_state: str, destination_region: str,
                               ship_mode: str, units: int = 3, sales: float = 14.0, cost: float = 5.0):
    model, meta = _load_best_model()
    factories, current_factory, division = eligible_factories(product_name)

    scenarios = []
    for f in factories:
        fname = f["factory_name"]
        distance = distance_factory_to_state(fname, destination_state)
        pred_index, residual_std = predict_lead_time_index(
            model, meta, division, fname, destination_region, destination_state, ship_mode,
            distance, units, sales,
        )
        conf = confidence_label(fname)
        profit = estimate_scenario_profit(
            sales=sales, current_cost=cost, units=units,
            current_factory=current_factory, proposed_factory=fname,
            state_province=destination_state,
        )

        scenarios.append({
            "factory_name": fname,
            "is_current": f["is_current"],
            "compatibility": f["compatibility"],
            "distance_miles": round(distance, 1) if distance == distance else None,
            "predicted_lead_time_index": round(pred_index, 1),
            "prediction_interval_95": [round(pred_index - 1.96 * residual_std, 1),
                                        round(pred_index + 1.96 * residual_std, 1)],
            "confidence": conf,
            "profit": profit,
        })

    baseline_scenario = next(s for s in scenarios if s["is_current"])
    for s in scenarios:
        s["lead_time_improvement"] = round(baseline_scenario["predicted_lead_time_index"] - s["predicted_lead_time_index"], 1)
        denom = abs(baseline_scenario["predicted_lead_time_index"]) or 1e-6
        s["lead_time_reduction_pct"] = round(100 * s["lead_time_improvement"] / denom, 1)

        # risk classification combines confidence + profit classification
        if s["confidence"]["label"] == "unsupported":
            s["risk_status"] = "high_risk_unsupported"
        elif s["profit"]["classification"] == "negative_financial_impact":
            s["risk_status"] = "high_risk_negative_profit"
        elif s["confidence"]["label"] == "low":
            s["risk_status"] = "moderate_risk_low_confidence"
        else:
            s["risk_status"] = "standard_risk"

    return {
        "product_name": product_name,
        "division": division,
        "current_factory": current_factory,
        "destination_state": destination_state,
        "destination_region": destination_region,
        "ship_mode": ship_mode,
        "scenarios": scenarios,
    }
