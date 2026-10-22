"""
Geographic distance calculations. Haversine straight-line distance only.
Never described as road distance anywhere downstream.
"""
import numpy as np
from src.config import STATE_CENTROIDS, FACTORIES

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1, lon1, lat2, lon2):
    """Straight-line (great-circle) distance in miles. NOT road distance."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.minimum(1, np.sqrt(a)))
    return EARTH_RADIUS_MILES * c


def state_coords(state_name):
    """Returns (lat, lon) centroid for a US state, or (None, None) if unknown."""
    return STATE_CENTROIDS.get(state_name, (None, None))


def factory_coords(factory_name):
    for f in FACTORIES:
        if f["factory_name"] == factory_name:
            return f["latitude"], f["longitude"]
    return None, None


def distance_factory_to_state(factory_name, state_name):
    flat, flon = factory_coords(factory_name)
    slat, slon = state_coords(state_name)
    if None in (flat, flon, slat, slon):
        return np.nan
    return float(haversine_miles(flat, flon, slat, slon))
