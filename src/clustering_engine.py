"""
Clustering (descriptive only — clusters describe similarity, they do not prove causes such as congestion).

1. Destination demand clusters: K-Means on destination state/province centroids (lat/lon), weighted by
   historical units. Shows where demand concentrates and which factory is nearest to each cluster.
   Locations are centroids, not customer addresses.
2. Route profile clusters: K-Means on per (factory, region, product) route aggregates
   [mean distance, mean recovered lead time, total units, total sales], standardised.

k is chosen by silhouette score over k = 2..8.
Run:  python -m src.clustering_engine
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.config import REPORTS_DIR, RANDOM_STATE, DESTINATION_CENTROIDS
from src.geographic_engine import nearest_factory_by_destination
from src.preprocessing import run_pipeline

K_RANGE = range(2, 9)


def _best_kmeans(X: np.ndarray, sample_weight=None, k_fixed: int | None = None):
    best = (None, -1.0, None, None)
    for k in ([k_fixed] if k_fixed else K_RANGE):
        if k >= len(X):
            break
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit(X, sample_weight=sample_weight)
        s = silhouette_score(X, km.labels_)
        if s > best[1]:
            best = (k, float(s), km.labels_, km)
    return best


def destination_clusters(df: pd.DataFrame, k: int | None = None):
    """k=None picks k by silhouette; an explicit k is used as given."""
    dest = (df.groupby("State/Province", as_index=False)
              .agg(units=("Units", "sum"), sales=("Sales", "sum"), lines=("Units", "size")))
    dest = dest[dest["State/Province"].isin(DESTINATION_CENTROIDS)].copy()
    if len(dest) < 3:
        raise ValueError("need at least 3 destinations with coordinates to cluster")
    dest["lat"] = dest["State/Province"].map(lambda s: DESTINATION_CENTROIDS[s][0])
    dest["lon"] = dest["State/Province"].map(lambda s: DESTINATION_CENTROIDS[s][1])
    k, score, labels, km = _best_kmeans(dest[["lat", "lon"]].to_numpy(), sample_weight=dest["units"].to_numpy(), k_fixed=k)
    dest["cluster"] = labels
    near = nearest_factory_by_destination(dest["State/Province"]).set_index("destination")
    dest["nearest_factory"] = dest["State/Province"].map(near["nearest_factory"])
    dest["nearest_miles"] = dest["State/Province"].map(near["nearest_miles"])
    summary = (dest.groupby("cluster")
                   .apply(lambda g: pd.Series({
                       "n_destinations": len(g),
                       "units": g["units"].sum(),
                       "pct_units": 0.0,
                       "center_lat": np.average(g["lat"], weights=g["units"]),
                       "center_lon": np.average(g["lon"], weights=g["units"]),
                       "most_common_nearest_factory": g.groupby("nearest_factory")["units"].sum().idxmax(),
                       "destinations": ", ".join(g.sort_values("units", ascending=False)["State/Province"].head(6)),
                   }), include_groups=False)
                   .reset_index())
    summary["pct_units"] = 100 * summary["units"] / summary["units"].sum()
    return dest, summary, k, score


def build_route_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby(["current_factory", "Region", "Product Name"]).agg(
        mean_distance=("distance_miles", "mean"),
        mean_recovered_lead_days=("lead_time_recovered_days", "mean"),
        total_units=("Units", "sum"),
        total_sales=("Sales", "sum"),
        n_lines=("Units", "size"),
    ).reset_index()
    return agg.dropna()


def route_clusters(df: pd.DataFrame):
    routes = build_route_aggregates(df)
    feats = ["mean_distance", "mean_recovered_lead_days", "total_units", "total_sales"]
    if len(routes) < 3:
        raise ValueError("need at least 3 routes to cluster")
    X = StandardScaler().fit_transform(routes[feats])
    k, score, labels, _ = _best_kmeans(X)
    routes["cluster"] = labels
    routes["cluster_label"] = routes["cluster"].map(lambda c: f"route_profile_{c}")
    return routes, k, score


def run_clustering(df: pd.DataFrame | None = None, save: bool = True):
    if df is None:
        df, _ = run_pipeline()
    dest, dest_summary, dk, ds = destination_clusters(df)
    routes, rk, rs = route_clusters(df)
    if save:
        out = REPORTS_DIR / "eda"
        out.mkdir(parents=True, exist_ok=True)
        routes.to_csv(out / "route_clusters.csv", index=False)
        dest.to_csv(out / "destination_clusters.csv", index=False)
        dest_summary.to_csv(out / "destination_cluster_summary.csv", index=False)
        pd.DataFrame([{"clustering": "destination_demand", "k": dk, "silhouette": ds},
                      {"clustering": "route_profile", "k": rk, "silhouette": rs}]).to_csv(out / "clustering_scores.csv", index=False)
    print(f"Destination demand clusters: k={dk}, silhouette={ds:.3f}")
    print(f"Route profile clusters:      k={rk}, silhouette={rs:.3f}")
    return routes, rk, rs


if __name__ == "__main__":
    run_clustering()
