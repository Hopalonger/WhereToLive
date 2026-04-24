import math
from typing import Dict, List, Tuple

import numpy as np
import streamlit as st

from where_to_live.constants import PLACE_TYPE_TO_OVERPASS
from where_to_live.map_view import build_map
from where_to_live.scoring import color_for_minutes, compute_score_for_home, generate_grid, point_in_geojson
from where_to_live.services import fetch_isochrone_geojson, fetch_pois, fetch_pois_nominatim
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
    isochrone_minutes = st.slider("Road Reachability Limit (minutes)", 10, 120, 45, step=5)

anchors = render_anchor_editor()
address_coords, address_errors = resolve_addresses(anchors)
ors_api_key = ors_api_key.strip()

if "heatmap_results" not in st.session_state:
    st.session_state["heatmap_results"] = None

if address_coords:
    center = (
        float(np.mean([c[0] for c in address_coords.values()])),
        float(np.mean([c[1] for c in address_coords.values()])),
    )
else:
    center = (39.5, -98.35)

st.subheader("Map")
st.write("Map loads immediately for exploration. Pins mark any exact-address anchors.")
build_map(center, address_coords, map_key="base_map")

if address_errors:
    for msg in address_errors:
        st.warning(msg)

if st.button("Generate Commute Heatmap", type="primary"):
    if not address_coords:
        st.error("Please add at least one valid exact address anchor before generating the heatmap.")
        st.stop()

    pois_by_type: Dict[str, List[Tuple[float, float]]] = {}
    st.session_state["ors_request_succeeded"] = False
    st.session_state["ors_request_count"] = 0
    st.session_state["ors_unroutable_count"] = 0
    st.session_state.pop("ors_last_error", None)
    for anchor in anchors:
        if anchor.location_type == "Type of Place":
            filter_exprs = PLACE_TYPE_TO_OVERPASS.get(anchor.place_type)
            if not filter_exprs:
                st.warning(f"Unsupported place type for '{anchor.name}'.")
                continue
            if anchor.place_type not in pois_by_type:
                points = fetch_pois(center[0], center[1], poi_radius_m, filter_exprs)
                if not points:
                    points = fetch_pois_nominatim(center[0], center[1], poi_radius_m, anchor.place_type)
                pois_by_type[anchor.place_type] = points
                st.write(f"{anchor.place_type}: found {len(pois_by_type[anchor.place_type])} matches")

    if ors_api_key:
        st.caption("OpenRouteService API key provided: live routing requests enabled.")
    else:
        st.caption("No OpenRouteService API key provided: using distance/speed fallback estimates.")

    cells = generate_grid(center, search_radius_km, grid_side)
    if ors_api_key:
        primary_mode = "driving-car"
        origin_for_iso = next(iter(address_coords.values()))
        isochrone = fetch_isochrone_geojson(
            origin_for_iso[0],
            origin_for_iso[1],
            primary_mode,
            isochrone_minutes,
            ors_api_key or None,
        )
        if isochrone and isochrone.get("features"):
            polygon_geometry = isochrone["features"][0].get("geometry", {})
            cells = [pt for pt in cells if point_in_geojson(pt[0], pt[1], polygon_geometry)]
            st.caption(
                f"Road-aware isochrone filter kept {len(cells)} candidate cells within about {isochrone_minutes} minutes."
            )
        else:
            st.warning("Could not load isochrone filter from OpenRouteService. Continuing without road-area clipping.")

    total_trips = max(sum(a.trips_per_week for a in anchors if a.trips_per_week > 0), 1)

    score_rows: List[Dict[str, float]] = []
    for lat, lon in cells:
        weekly = compute_score_for_home((lat, lon), anchors, address_coords, pois_by_type, ors_api_key or None)
        if math.isinf(weekly):
            continue
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
    if not score_rows:
        st.error(
            "No routable candidate cells were found. Increase search radius/time, add more roads-accessible anchors, "
            "or verify your OpenRouteService key."
        )
    st.session_state["heatmap_results"] = {
        "score_rows": score_rows,
        "ors_key_was_provided": bool(ors_api_key),
    }

heatmap_results = st.session_state.get("heatmap_results")
if heatmap_results and heatmap_results.get("score_rows"):
    score_rows = heatmap_results["score_rows"]
    best = score_rows[0]

    c1, c2 = st.columns(2)
    c1.metric("Best Weekly Minutes", f"{best['weekly_minutes']:.1f}")
    c2.metric("Best Avg Minutes per Trip", f"{best['avg_minutes_per_trip']:.1f}")

    st.subheader("Heatmap + Pins")
    build_map(center, address_coords, score_rows, map_key="heatmap_map")

    if heatmap_results.get("ors_key_was_provided"):
        if st.session_state.get("ors_request_succeeded"):
            st.success(
                "OpenRouteService requests succeeded for this heatmap run. "
                f"Successful requests: {st.session_state.get('ors_request_count', 0)}"
            )
        elif st.session_state.get("ors_last_error"):
            st.warning(
                "OpenRouteService key was provided, but requests failed. "
                f"Latest error: {st.session_state['ors_last_error']}"
            )

        unroutable = st.session_state.get("ors_unroutable_count", 0)
        if unroutable:
            st.info(
                f"Excluded {unroutable} unroutable route attempts (for example across water or disconnected roads)."
            )
