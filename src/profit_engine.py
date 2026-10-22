"""
Phase 11: financial evaluation. Distinguishes historical actuals from simulated/assumed values.
Every assumption used is labeled with its source (see src/config.py FINANCIAL_ASSUMPTIONS).
"""
from src.config import FINANCIAL_ASSUMPTIONS
from src.geographic_engine import distance_factory_to_state


def estimate_scenario_profit(sales, current_cost, units, current_factory, proposed_factory, state_province,
                              cost_multiplier=None, shipping_rate=None):
    """
    Returns a dict with historical vs. estimated/simulated figures, each clearly labeled.
    """
    cost_multiplier = cost_multiplier if cost_multiplier is not None else FINANCIAL_ASSUMPTIONS["alt_factory_cost_multiplier"]["value"]
    shipping_rate = shipping_rate if shipping_rate is not None else FINANCIAL_ASSUMPTIONS["shipping_cost_per_mile_per_unit"]["value"]

    baseline_profit = sales - current_cost  # HISTORICAL actual (Gross Profit field already = sales-cost in source)

    if proposed_factory == current_factory:
        return {
            "baseline_profit_historical": baseline_profit,
            "estimated_scenario_profit": baseline_profit,
            "profit_impact": 0.0,
            "classification": "neutral_financial_impact",
            "assumptions_used": [],
            "note": "No reallocation — historical profit applies unchanged.",
        }

    distance = distance_factory_to_state(proposed_factory, state_province)
    if distance != distance:  # NaN
        return {
            "baseline_profit_historical": baseline_profit,
            "estimated_scenario_profit": None,
            "profit_impact": None,
            "classification": "insufficient_financial_data",
            "assumptions_used": [],
            "note": "No state-centroid coordinate available for this destination; cannot estimate shipping cost.",
        }

    estimated_alt_cost = current_cost * cost_multiplier  # SIMULATED
    estimated_shipping_cost = distance * shipping_rate * units  # SIMULATED
    estimated_scenario_profit = sales - estimated_alt_cost - estimated_shipping_cost
    profit_impact = estimated_scenario_profit - baseline_profit

    if profit_impact > 0.01:
        classification = "positive_financial_impact"
    elif profit_impact < -0.01:
        classification = "negative_financial_impact"
    else:
        classification = "neutral_financial_impact"

    return {
        "baseline_profit_historical": round(baseline_profit, 2),
        "estimated_scenario_profit": round(estimated_scenario_profit, 2),
        "profit_impact": round(profit_impact, 2),
        "classification": classification,
        "distance_miles": round(distance, 1),
        "assumptions_used": [
            {"name": "alt_factory_cost_multiplier", "value": cost_multiplier,
             "source": FINANCIAL_ASSUMPTIONS["alt_factory_cost_multiplier"]["source"]},
            {"name": "shipping_cost_per_mile_per_unit", "value": shipping_rate,
             "source": FINANCIAL_ASSUMPTIONS["shipping_cost_per_mile_per_unit"]["source"]},
        ],
        "note": "estimated_scenario_profit and profit_impact are SIMULATED using analyst assumptions above, "
                "not actual financial data for the alternative factory.",
    }
