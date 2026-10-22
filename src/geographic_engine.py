"""
Geographic distance calculations.

All distances are straight-line (great-circle / Haversine) miles between a factory and the
*centroid* of the destination state or province. They are approximations:
  - customer addresses are not geocoded (no customer coordinates exist in the source data);
  - straight-line distance is shorter than road distance.
Never present these numbers as actual shipping distances.
"""
import numpy as np
import pandas as pd

from src.config import DESTINATION_CENTROIDS, FACTORIES, CANADA_PROVINCE_CENTROIDS

EARTH_RADIUS_MILES = 3958.8
DISTANCE_LABEL = "straight-line miles to state/province centroid (approximate)"


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles. Works on scalars or NumPy arrays. NOT road distance."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.minimum(1, np.sqrt(a)))
    return EARTH_RADIUS_MILES * c


def factory_names():
    return [f["factory_name"] for f in FACTORIES]


def state_coords(state_name):
    """(lat, lon) centroid for a US state or Canadian province, or (None, None) if unknown."""
    return DESTINATION_CENTROIDS.get(state_name, (None, None))


def is_canadian(state_name):
    return state_name in CANADA_PROVINCE_CENTROIDS


def factory_coords(factory_name):
    for f in FACTORIES:
        if f["factory_name"] == factory_name:
            return f["latitude"], f["longitude"]
    return None, None


def distance_factory_to_state(factory_name, state_name):
    """Distance in miles, or NaN if the factory or destination is unknown."""
    flat, flon = factory_coords(factory_name)
    slat, slon = state_coords(state_name)
    if None in (flat, flon, slat, slon):
        return np.nan
    return float(haversine_miles(flat, flon, slat, slon))


def distance_matrix(destinations=None) -> pd.DataFrame:
    """Factory x destination distance matrix (rows = destinations, columns = factories)."""
    destinations = sorted(DESTINATION_CENTROIDS) if destinations is None else list(destinations)
    out = {}
    for f in FACTORIES:
        out[f["factory_name"]] = [distance_factory_to_state(f["factory_name"], d) for d in destinations]
    return pd.DataFrame(out, index=pd.Index(destinations, name="destination"))


def distances_for_rows(factories: pd.Series, states: pd.Series) -> np.ndarray:
    """Vectorised distance for paired (factory, state) series. Unknown pairs -> NaN."""
    matrix = distance_matrix(sorted(set(states.dropna())))
    lookup = matrix.stack().to_dict()  # {(destination, factory): miles}
    return np.array([lookup.get((s, f), np.nan) for f, s in zip(factories, states)], dtype=float)


def nearest_factory_by_destination(destinations=None) -> pd.DataFrame:
    """For each destination: the nearest factory, its distance, and the runner-up."""
    m = distance_matrix(destinations)
    rows = []
    for dest, r in m.iterrows():
        r = r.dropna().sort_values()
        if r.empty:
            continue
        rows.append({
            "destination": dest,
            "nearest_factory": r.index[0], "nearest_miles": r.iloc[0],
            "second_factory": r.index[1] if len(r) > 1 else None,
            "second_miles": r.iloc[1] if len(r) > 1 else np.nan,
        })
    return pd.DataFrame(rows)


def coverage_analysis(order_lines: pd.DataFrame, state_col="State/Province", units_col="Units",
                      bands=(500, 1000, 1500)) -> pd.DataFrame:
    """
    Share of historical units whose destination lies within each distance band of
    (a) the factory currently serving it and (b) the nearest of all five factories.
    Requires columns: state_col, units_col, and 'current_factory'.
    """
    df = order_lines[[state_col, units_col, "current_factory"]].copy()
    df["current_miles"] = distances_for_rows(df["current_factory"], df[state_col])
    nearest = nearest_factory_by_destination(sorted(set(df[state_col].dropna()))).set_index("destination")
    df["nearest_miles"] = df[state_col].map(nearest["nearest_miles"])
    total = df[units_col].sum()
    rows = []
    for b in bands:
        rows.append({
            "within_miles": b,
            "pct_units_current_factory": 100 * df.loc[df["current_miles"] <= b, units_col].sum() / total if total else np.nan,
            "pct_units_nearest_factory": 100 * df.loc[df["nearest_miles"] <= b, units_col].sum() / total if total else np.nan,
        })
    return pd.DataFrame(rows)
