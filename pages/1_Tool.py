from typing import Dict, List, Tuple

import numpy as np
import streamlit as st

from where_to_live.constants import PLACE_TYPE_TO_OVERPASS
from where_to_live.map_view import build_map
from where_to_live.scoring import color_for_minutes, compute_score_for_home, generate_grid
from where_to_live.services import fetch_pois
from where_to_live.ui import render_anchor_editor, resolve_addresses

st.set_page_config(page_title="Where To Live Tool", page_icon="🗺️", layout="wide")

st.title("🗺️ Optimizer Tool")
st.caption("Configure anchors, generate a commute heatmap, and explore candidate living areas.")

with st.sidebar:
    st.header("Settings")
    ors_api_key = st.text_input("OpenRouteService API Key (optional)", type="password")
    st.info("If no key is provided, travel time is estimated by distance + average speed.")
    search_radius_km = st.slider("Search Radius (km)", 2, 35, 10)
    grid_side = st.slider("Map Resolution", 6, 30, 12)
    poi_radius_m = st.slider("POI Search Radius (meters)", 1000, 30000, 12000, step=500)

anchors = render_anchor_editor()
address_coords, address_errors = resolve_addresses(anchors)

if address_coords:
    center = (
        float(np.mean([c[0] for c in address_coords.values()])),
        float(np.mean([c[1] for c in address_coords.values()])),
    )
else:
    center = (39.5, -98.35)

st.subheader("Map")
st.write("Map loads immediately for exploration. Pins mark any exact-address anchors.")
build_map(center, address_coords)

if address_errors:
    for msg in address_errors:
        st.warning(msg)

if st.button("Generate Commute Heatmap", type="primary"):
    if not address_coords:
        st.error("Please add at least one valid exact address anchor before generating the heatmap.")
        st.stop()

    pois_by_type: Dict[str, List[Tuple[float, float]]] = {}
    for anchor in anchors:
        if anchor.location_type == "Type of Place":
            filter_expr = PLACE_TYPE_TO_OVERPASS.get(anchor.place_type)
            if not filter_expr:
                st.warning(f"Unsupported place type for '{anchor.name}'.")
                continue
            if anchor.place_type not in pois_by_type:
                pois_by_type[anchor.place_type] = fetch_pois(center[0], center[1], poi_radius_m, filter_expr)
                st.write(f"{anchor.place_type}: found {len(pois_by_type[anchor.place_type])} matches")

    cells = generate_grid(center, search_radius_km, grid_side)
    total_trips = max(sum(a.trips_per_week for a in anchors if a.trips_per_week > 0), 1)

    score_rows: List[Dict[str, float]] = []
    for lat, lon in cells:
        weekly = compute_score_for_home((lat, lon), anchors, address_coords, pois_by_type, ors_api_key or None)
        per_trip = weekly / total_trips
        score_rows.append(
            {
                "lat": lat,
                "lon": lon,
                "weekly_minutes": weekly,
                "avg_minutes_per_trip": per_trip,
                "color": color_for_minutes(per_trip),
            }
        )

    score_rows = sorted(score_rows, key=lambda x: x["weekly_minutes"])
    best = score_rows[0]

    c1, c2 = st.columns(2)
    c1.metric("Best Weekly Minutes", f"{best['weekly_minutes']:.1f}")
    c2.metric("Best Avg Minutes per Trip", f"{best['avg_minutes_per_trip']:.1f}")

    st.subheader("Heatmap + Pins")
    build_map(center, address_coords, score_rows)
