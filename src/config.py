"""
Central configuration. No hardcoded absolute paths; everything relative to project root.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "nassau_candy_distributor.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MASTER_DIR = PROJECT_ROOT / "data" / "master"
MODELS_TRAINED_DIR = PROJECT_ROOT / "models" / "trained"
MODELS_EVAL_DIR = PROJECT_ROOT / "models" / "evaluation"
REPORTS_DIR = PROJECT_ROOT / "reports"
DB_PATH = PROJECT_ROOT / "data" / "nassau.db"

DATE_FORMAT = "%d-%m-%Y"  # established empirically in Phase 1 profiling (0 parse failures vs 6000+ for mm-dd-yyyy)

RANDOM_STATE = 42

# Columns the raw file must contain. Validation fails loudly if any are missing.
REQUIRED_COLUMNS = [
    "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID", "Country/Region",
    "City", "State/Province", "Postal Code", "Division", "Region", "Product ID", "Product Name",
    "Sales", "Units", "Gross Profit", "Cost",
]

# Values observed in the source data (used for UI choices and validation).
REGIONS = ["Atlantic", "Gulf", "Interior", "Pacific"]
SHIP_MODES = ["Same Day", "First Class", "Second Class", "Standard Class"]

# Date forensics (see reports/PHASE1_AUDIT.md section 2 and src/data_validation.py).
# Ship Date - (Order Date with its year replaced by the Order ID year) = DATE_SHIFT + lead time.
# The shift is re-estimated from the data on every run; this value is only the expected one and a
# warning is logged if the estimate differs.
EXPECTED_DATE_SHIFT_DAYS = 2000
# Recovered lead times outside this window are treated as implausible and set to missing.
RECOVERED_LEAD_TIME_VALID_RANGE = (0, 14)

# Below this many historical order lines a product's estimates are flagged as weakly supported.
MIN_SUPPORT_ROWS = 30

# Factory master data — EXACT coordinates supplied in the master prompt. Do not alter.
FACTORIES = [
    {"factory_name": "Lot's O' Nuts",     "latitude": 32.881893,  "longitude": -111.768036},
    {"factory_name": "Wicked Choccy's",   "latitude": 32.076176,  "longitude": -81.088371},
    {"factory_name": "Sugar Shack",       "latitude": 48.119140,  "longitude": -96.181150},
    {"factory_name": "Secret Factory",    "latitude": 41.446333,  "longitude": -90.565487},
    {"factory_name": "The Other Factory", "latitude": 35.117500,  "longitude": -89.971107},
]

# Supplied baseline product -> factory mapping. Preserved exactly as the business baseline.
PRODUCT_FACTORY_BASELINE = [
    {"division": "Chocolate", "product_name": "Wonka Bar - Nutty Crunch Surprise", "factory_name": "Lot's O' Nuts"},
    {"division": "Chocolate", "product_name": "Wonka Bar - Fudge Mallows",          "factory_name": "Lot's O' Nuts"},
    {"division": "Chocolate", "product_name": "Wonka Bar -Scrumdiddlyumptious",     "factory_name": "Lot's O' Nuts"},
    {"division": "Chocolate", "product_name": "Wonka Bar - Milk Chocolate",         "factory_name": "Wicked Choccy's"},
    {"division": "Chocolate", "product_name": "Wonka Bar - Triple Dazzle Caramel",  "factory_name": "Wicked Choccy's"},
    {"division": "Sugar",     "product_name": "Laffy Taffy",                       "factory_name": "Sugar Shack"},
    {"division": "Sugar",     "product_name": "SweeTARTS",                         "factory_name": "Sugar Shack"},
    {"division": "Sugar",     "product_name": "Nerds",                             "factory_name": "Sugar Shack"},
    {"division": "Sugar",     "product_name": "Fun Dip",                           "factory_name": "Sugar Shack"},
    # Division corrected from "Other" to "Sugar" (2026-10-22): all 6 source rows say "Sugar".
    # The factory assignment itself is unchanged.
    {"division": "Sugar",     "product_name": "Fizzy Lifting Drinks",              "factory_name": "Sugar Shack"},
    {"division": "Sugar",     "product_name": "Everlasting Gobstopper",            "factory_name": "Secret Factory"},
    {"division": "Sugar",     "product_name": "Hair Toffee",                       "factory_name": "The Other Factory"},
    {"division": "Other",     "product_name": "Lickable Wallpaper",                "factory_name": "Secret Factory"},
    {"division": "Other",     "product_name": "Wonka Gum",                         "factory_name": "Secret Factory"},
    {"division": "Other",     "product_name": "Kazookles",                        "factory_name": "The Other Factory"},
]

# ANALYST ASSUMPTIONS — not present in source data. Clearly labeled and configurable.
# Source: "ANALYST ASSUMPTION" everywhere these are used; change here to update system-wide.
FINANCIAL_ASSUMPTIONS = {
    "alt_factory_cost_multiplier": {
        "value": 1.00,
        "unit": "multiplier on current product Cost",
        "source": "ANALYST ASSUMPTION: no alternative-factory manufacturing cost data supplied. "
                   "Default assumes equal manufacturing cost at any compatible factory; override per scenario.",
        "is_configurable": True,
    },
    "freight_cost_per_unit_mile": {
        # Replaces the legacy 'shipping_cost_per_mile_per_unit' (0.015). 0.015 gives ~$15 freight per unit
        # over 1,000 miles, about 4x the ~$3.50 selling price of a Wonka Bar, so every route was loss-making.
        # New name so the old database row is left untouched. Still illustrative only.
        "value": 0.0005,
        "unit": "USD per unit per straight-line mile",
        "source": "ANALYST ASSUMPTION: no logistics/freight cost data supplied. Illustrative placeholder "
                   "(about $0.50 per unit per 1,000 straight-line miles); must be replaced with real freight "
                   "contracts before any financial decision is made on this number.",
        "is_configurable": True,
    },
    "transit_days_per_1000_miles": {
        "value": 2.0,
        "unit": "estimated transit days per 1,000 straight-line miles",
        "source": "ANALYST ASSUMPTION: rule of thumb of roughly 500 truck miles per day. The source data "
                   "shows NO measurable link between distance and recovered lead time (correlation near zero; see the "
                   "dashboard's Data Management -> Date forensics tab for the computed value), "
                   "so any lead-time benefit of moving production comes from this assumption, not from data.",
        "is_configurable": True,
    },
    "factory_capacity_headroom_pct": {
        "value": -1.0,
        "unit": "% extra units a factory may take on above its current historical volume (-1 = no limit)",
        "source": "ANALYST ASSUMPTION: no factory capacity data supplied. Disabled by default (-1). "
                   "When set to 0 or more, each factory's capacity = its current units x (1 + headroom/100).",
        "is_configurable": True,
    },
    "minimum_profit_threshold": {
        "value": 0.0,
        "unit": "USD estimated profit impact over the historical period, per product",
        "source": "ANALYST ASSUMPTION: optimization will not recommend a reallocation whose estimated profit "
                   "impact falls below this threshold. Default = no reallocation may reduce profit.",
        "is_configurable": True,
    },
    "reassignment_penalty_points": {
        # Replaces legacy 'reassignment_penalty' (0.25 on the old tanh-scaled score, no longer meaningful).
        "value": 2.0,
        "unit": "score points (same % scale as the objective) subtracted for any change of factory",
        "source": "ANALYST ASSUMPTION: stands in for unknown one-off switching costs and discourages "
                   "reallocations with marginal benefit; tunable.",
        "is_configurable": True,
    },
}

# Database rows with these names come from an earlier version and are kept but no longer used.
LEGACY_ASSUMPTIONS = {
    "shipping_cost_per_mile_per_unit": "replaced by freight_cost_per_unit_mile",
    "reassignment_penalty": "replaced by reassignment_penalty_points",
}

# Objective weights. Score = w_profit * profit gain % + w_speed * lead-time gain % - w_risk * risk increase (points)
#                           - reassignment penalty (if the factory changes)
WEIGHT_PRESETS = {
    "balanced": {"profit_weight": 0.4, "speed_weight": 0.4, "risk_weight": 0.2},
    "cost_focused": {"profit_weight": 1.0, "speed_weight": 0.0, "risk_weight": 0.0},
    "speed_focused": {"profit_weight": 0.2, "speed_weight": 0.7, "risk_weight": 0.1},
}
DEFAULT_WEIGHT_PRESET = "balanced"

# Public, static state-centroid coordinates (lat/long of US state geographic centroids).
# Used ONLY because customer-level lat/long is not in the source data and no geocoding
# API is available in this offline environment. This is an approximation, not customer address geocoding.
STATE_CENTROIDS = {
    "Alabama": (32.806671, -86.791130), "Alaska": (61.370716, -152.404419), "Arizona": (33.729759, -111.431221),
    "Arkansas": (34.969704, -92.373123), "California": (36.116203, -119.681564), "Colorado": (39.059811, -105.311104),
    "Connecticut": (41.597782, -72.755371), "Delaware": (39.318523, -75.507141), "Florida": (27.766279, -81.686783),
    "Georgia": (33.040619, -83.643074), "Hawaii": (21.094318, -157.498337), "Idaho": (44.240459, -114.478828),
    "Illinois": (40.349457, -88.986137), "Indiana": (39.849426, -86.258278), "Iowa": (42.011539, -93.210526),
    "Kansas": (38.526600, -96.726486), "Kentucky": (37.668140, -84.670067), "Louisiana": (31.169546, -91.867805),
    "Maine": (44.693947, -69.381927), "Maryland": (39.063946, -76.802101), "Massachusetts": (42.230171, -71.530106),
    "Michigan": (43.326618, -84.536095), "Minnesota": (45.694454, -93.900192), "Mississippi": (32.741646, -89.678696),
    "Missouri": (38.456085, -92.288368), "Montana": (46.921925, -110.454353), "Nebraska": (41.125370, -98.268082),
    "Nevada": (38.313515, -117.055374), "New Hampshire": (43.452492, -71.563896), "New Jersey": (40.298904, -74.521011),
    "New Mexico": (34.840515, -106.248482), "New York": (42.165726, -74.948051), "North Carolina": (35.630066, -79.806419),
    "North Dakota": (47.528912, -99.784012), "Ohio": (40.388783, -82.764915), "Oklahoma": (35.565342, -96.928917),
    "Oregon": (44.572021, -122.070938), "Pennsylvania": (40.590752, -77.209755), "Rhode Island": (41.680893, -71.511780),
    "South Carolina": (33.856892, -80.945007), "South Dakota": (44.299782, -99.438828), "Tennessee": (35.747845, -86.692345),
    "Texas": (31.054487, -97.563461), "Utah": (40.150032, -111.862434), "Vermont": (44.045876, -72.710686),
    "Virginia": (37.769337, -78.169968), "Washington": (47.400902, -121.490494), "West Virginia": (38.491226, -80.954453),
    "Wisconsin": (44.268543, -89.616508), "Wyoming": (42.755966, -107.302490), "District of Columbia": (38.907192, -77.036873),
}

# Approximate geographic centres of the 10 Canadian provinces in the data (200 rows).
# These are coarse approximations: for large provinces (e.g. Ontario, Quebec) the geographic centre
# can be hundreds of miles from where customers actually are (Toronto, Montreal), so Canadian
# distances are less reliable than US state-centroid distances. Flagged in the data-quality report.
CANADA_PROVINCE_CENTROIDS = {
    "Alberta": (55.0, -115.0), "British Columbia": (53.7, -127.6), "Manitoba": (56.4, -98.7),
    "New Brunswick": (46.5, -66.2), "Newfoundland and Labrador": (53.1, -57.7), "Nova Scotia": (45.0, -63.0),
    "Ontario": (50.0, -85.0), "Prince Edward Island": (46.25, -63.0), "Quebec": (52.9, -73.5),
    "Saskatchewan": (52.9, -106.5),
}

# All destination centroids (US states + Canadian provinces).
DESTINATION_CENTROIDS = {**STATE_CENTROIDS, **CANADA_PROVINCE_CENTROIDS}

# Product-factory compatibility rules. None of these come from source data; the default is derived
# from the 15 baseline assignments (a factory "has demonstrated" a division if it currently makes at
# least one product of that division).
COMPATIBILITY_RULES = {
    "demonstrated_division": "A factory may make a product if it already makes another product of the same "
                             "division (derived from the baseline assignments; unverified with the business).",
    "any_factory": "Any factory may make any product (most permissive; no evidence supports this).",
    "baseline_only": "Only the current factory is allowed (no reallocation possible).",
}
DEFAULT_COMPATIBILITY_RULE = "demonstrated_division"
