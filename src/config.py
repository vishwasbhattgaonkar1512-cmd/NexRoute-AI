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
    {"division": "Other",     "product_name": "Fizzy Lifting Drinks",              "factory_name": "Sugar Shack"},
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
    "shipping_cost_per_mile_per_unit": {
        "value": 0.015,
        "unit": "USD per mile per unit shipped",
        "source": "ANALYST ASSUMPTION: no logistics/freight cost data supplied. Illustrative placeholder "
                   "derived from typical US LTL per-mile rates; must be replaced with real freight contracts "
                   "before any financial decision is made on this number.",
        "is_configurable": True,
    },
    "minimum_profit_threshold": {
        "value": 0.0,
        "unit": "USD estimated profit impact",
        "source": "ANALYST ASSUMPTION: optimization will not recommend a reallocation whose estimated profit "
                   "impact falls below this threshold. Default = no reallocation may reduce profit.",
        "is_configurable": True,
    },
    "reassignment_penalty": {
        "value": 0.25,
        "unit": "index points subtracted from score for any change from current factory",
        "source": "ANALYST ASSUMPTION: discourages unnecessary churn; tunable.",
        "is_configurable": True,
    },
}

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
