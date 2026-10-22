import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import setup_page, require_database, guard, load_pipeline, style, show, FACTORY_COLORS, SERIES  # noqa: E402

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import FACTORIES, DESTINATION_CENTROIDS, PRODUCT_FACTORY_BASELINE  # noqa: E402
from src.geographic_engine import distance_matrix, nearest_factory_by_destination, coverage_analysis  # noqa: E402
from src.clustering_engine import destination_clusters  # noqa: E402

setup_page("Factory Map", "🗺️", "Factories, destination demand, distances, coverage and demand clusters")
require_database()
st.warning("Destinations are **state/province centroids**, not customer addresses (no customer coordinates exist "
           "in the data). Distances are **straight-line** miles, shorter than road distance. Canadian province "
           "centres are coarse approximations.", icon="📍")

df, _ = guard(load_pipeline, what="the dataset")
dest = (df.groupby(["State/Province", "Country/Region"], as_index=False)
          .agg(units=("Units", "sum"), sales=("Sales", "sum"), lines=("Units", "size")))
dest["lat"] = dest["State/Province"].map(lambda s: DESTINATION_CENTROIDS.get(s, (None, None))[0])
dest["lon"] = dest["State/Province"].map(lambda s: DESTINATION_CENTROIDS.get(s, (None, None))[1])

c1, c2 = st.columns([1, 3])
with c1:
    product = st.selectbox("Product", ["All products"] + [p["product_name"] for p in PRODUCT_FACTORY_BASELINE])
    show_routes = st.checkbox("Draw current factory → destination lines", value=product != "All products")
    k_choice = st.select_slider("Demand clusters (k)", options=["auto", 2, 3, 4, 5, 6, 7, 8], value="auto",
                                help="'auto' picks k by silhouette score.")
sub = df if product == "All products" else df[df["Product Name"] == product]
pdest = (sub.groupby(["State/Province", "current_factory"], as_index=False).agg(units=("Units", "sum")))
pdest["lat"] = pdest["State/Province"].map(lambda s: DESTINATION_CENTROIDS[s][0])
pdest["lon"] = pdest["State/Province"].map(lambda s: DESTINATION_CENTROIDS[s][1])

fig = go.Figure()
if show_routes:
    for f in FACTORIES:
        rows = pdest[pdest["current_factory"] == f["factory_name"]]
        lats, lons = [], []
        for _, r in rows.iterrows():
            lats += [f["latitude"], r["lat"], None]
            lons += [f["longitude"], r["lon"], None]
        if lats:
            fig.add_trace(go.Scattergeo(lat=lats, lon=lons, mode="lines", hoverinfo="skip", showlegend=False,
                                        line=dict(width=1, color=FACTORY_COLORS[f["factory_name"]]), opacity=0.35))
size = (pdest.groupby("State/Province")["units"].sum())
pts = pdest.drop_duplicates("State/Province").set_index("State/Province").assign(units=size).reset_index()
fig.add_trace(go.Scattergeo(
    lat=pts["lat"], lon=pts["lon"], mode="markers", name="Destination demand (centroid)",
    marker=dict(size=(pts["units"] / pts["units"].max()) ** 0.5 * 30 + 4, color="#898781", opacity=0.55,
                line=dict(width=1, color="white")),
    text=pts["State/Province"] + "<br>" + pts["units"].map("{:,} units".format), hoverinfo="text"))
for f in FACTORIES:
    fig.add_trace(go.Scattergeo(lat=[f["latitude"]], lon=[f["longitude"]], mode="markers+text", name=f["factory_name"],
                                text=[f["factory_name"]], textposition="top center",
                                marker=dict(size=14, symbol="square", color=FACTORY_COLORS[f["factory_name"]],
                                            line=dict(width=2, color="white"))))
fig.update_layout(geo=dict(scope="north america", projection_type="conic conformal", showland=True,
                           landcolor="rgba(137,135,129,0.08)", lakecolor="rgba(0,0,0,0)", showcountries=True,
                           countrycolor="rgba(137,135,129,0.4)", showsubunits=True,
                           subunitcolor="rgba(137,135,129,0.25)", lataxis_range=[22, 58], lonaxis_range=[-130, -55]),
                  height=620, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.02))
with c2:
    st.plotly_chart(fig, width="stretch")

st.subheader("Distance matrix (straight-line miles, factory → destination centroid)")
dm = distance_matrix(sorted(dest["State/Province"])).round(0)
near = nearest_factory_by_destination(dm.index).set_index("destination")
dm["nearest factory"] = near["nearest_factory"]
dm.insert(0, "units", dest.set_index("State/Province")["units"])
st.dataframe(dm.sort_values("units", ascending=False), width="stretch")

st.subheader("Coverage")
cov = coverage_analysis(df)
cov_long = cov.melt(id_vars="within_miles", var_name="basis", value_name="pct")
cov_long["basis"] = cov_long["basis"].map({"pct_units_current_factory": "From current factory",
                                           "pct_units_nearest_factory": "From nearest factory"})
cov_long["within"] = "≤ " + cov_long["within_miles"].map("{:,}".format) + " mi"
fig = px.bar(cov_long, x="within", y="pct", color="basis", barmode="group",
             color_discrete_sequence=[SERIES[0], SERIES[1]], labels={"within": "", "pct": "% of units"})
show(style(fig, 320, "Share of historical units within each distance of a factory"), cov)
st.caption("The gap between the two bars is the distance that could in principle be saved by serving each "
           "destination from its nearest factory — subject to product compatibility, which this chart ignores.")

st.subheader("Alternative-factory distance comparison by product")
rows = []
for p in PRODUCT_FACTORY_BASELINE:
    s = df[df["Product Name"] == p["product_name"]]
    if s.empty:
        continue
    dmp = distance_matrix(sorted(s["State/Province"].unique()))
    u = s.groupby("State/Province")["Units"].sum()
    for f in dmp.columns:
        rows.append({"product": p["product_name"], "factory": f, "is_current": f == p["factory_name"],
                     "weighted_miles": (dmp.loc[u.index, f] * u).sum() / u.sum()})
cmp_df = pd.DataFrame(rows)
fig = px.scatter(cmp_df, x="weighted_miles", y="product", color="factory", symbol="is_current",
                 symbol_map={True: "diamond", False: "circle"}, color_discrete_map=FACTORY_COLORS,
                 labels={"weighted_miles": "Demand-weighted miles", "product": "", "is_current": "Current"})
fig.update_traces(marker=dict(size=11, line=dict(width=2, color="white")))
show(style(fig, 520, "Demand-weighted distance from each factory (diamond = current; ignores compatibility)"),
     cmp_df.pivot(index="product", columns="factory", values="weighted_miles").round(0).reset_index())

st.subheader("Geographic demand clusters")
dcl, summ, k, sil = guard(destination_clusters, df, None if k_choice == "auto" else int(k_choice),
                          what="demand clusters")
dcl["cluster"] = dcl["cluster"].astype(str)
fig = px.scatter_geo(dcl, lat="lat", lon="lon", color="cluster", size="units", hover_name="State/Province",
                     color_discrete_sequence=SERIES, size_max=30)
fig.update_layout(geo=dict(scope="north america", lataxis_range=[22, 58], lonaxis_range=[-130, -55],
                           showsubunits=True, subunitcolor="rgba(137,135,129,0.25)"),
                  height=480, margin=dict(l=0, r=0, t=30, b=0),
                  title=dict(text=f"k = {k}, silhouette = {sil:.2f} (units-weighted K-Means on centroids)", x=0))
st.plotly_chart(fig, width="stretch")
st.dataframe(summ.round(1), hide_index=True, width="stretch")
st.caption("Clusters describe where demand concentrates; they do not imply any cause. Colours here identify "
           "clusters, not factories.")
