"""
Phase 5: Route/product clustering (master prompt section 9).
K-Means on [distance_miles, lead_time_index, units, sales] per product-region-factory route,
evaluated with silhouette score. Framed as "performance similarity clusters", not proof of congestion.
"""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from src.config import PROCESSED_DIR, REPORTS_DIR
from src.preprocessing import run_pipeline


def build_route_aggregates(df):
    agg = df.groupby(["current_factory", "Region", "Product Name"]).agg(
        mean_distance=("distance_miles", "mean"),
        mean_lead_time_index=("lead_time_index", "mean"),
        total_units=("Units", "sum"),
        total_sales=("Sales", "sum"),
        n_orders=("Order ID", "count"),
    ).reset_index()
    return agg.dropna()


def run_clustering(k=4):
    df, _ = run_pipeline()
    routes = build_route_aggregates(df)

    features = ["mean_distance", "mean_lead_time_index", "total_units", "total_sales"]
    X = StandardScaler().fit_transform(routes[features])

    best_k, best_score, best_labels = None, -1, None
    for k_try in range(2, 7):
        km = KMeans(n_clusters=k_try, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        score = silhouette_score(X, labels)
        if score > best_score:
            best_k, best_score, best_labels = k_try, score, labels

    routes["cluster"] = best_labels
    routes["cluster_label"] = routes["cluster"].map(
        lambda c: f"performance_similarity_cluster_{c}"  # NOT claimed as proof of congestion
    )

    # Identify "consistently slow" clusters by mean_lead_time_index rank
    cluster_means = routes.groupby("cluster")["mean_lead_time_index"].mean().sort_values(ascending=False)
    slow_cluster = cluster_means.index[0]
    routes["potential_congestion_indicator"] = routes["cluster"] == slow_cluster

    REPORTS_DIR.joinpath("eda").mkdir(parents=True, exist_ok=True)
    routes.to_csv(REPORTS_DIR / "eda" / "route_clusters.csv", index=False)

    print(f"Best k={best_k}, silhouette score={best_score:.3f}")
    print(routes.groupby("cluster").agg(
        n_routes=("cluster", "count"),
        mean_lead_time_index=("mean_lead_time_index", "mean"),
        mean_distance=("mean_distance", "mean"),
    ))
    return routes, best_k, best_score


if __name__ == "__main__":
    run_clustering()
