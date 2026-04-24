import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Where To Live", page_icon="🏠", layout="wide")


PLACE_TYPE_TO_OVERPASS = {
    "Grocery Store": '(node["shop"="supermarket"];node["shop"="grocery"];)',
    "Gym": '(node["leisure"="fitness_centre"];node["amenity"="gym"];)',
    "Coffee Shop": '(node["amenity"="cafe"];)',
    "Mountain / Trail": '(node["natural"="peak"];node["highway"="path"];node["route"="hiking"];)',
    "Park": '(node["leisure"="park"];)',
}

SPEED_KMPH_FALLBACK = {
    "driving-car": 40,
    "cycling-regular": 18,
    "foot-walking": 5,
    "transit": 25,
}

MODE_OPTIONS = ["driving-car", "cycling-regular", "foot-walking", "transit"]


@dataclass
class Anchor:
    name: str
    kind: str  # address or place_type
    value: str
    mode: str
    frequency: float
    after_anchor: Optional[str]


@st.cache_resource
def geocoder() -> Nominatim:
    return Nominatim(user_agent="where-to-live-app")


@st.cache_data(show_spinner=False)
def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    result = geocoder().geocode(address, timeout=15)
    if not result:
        return None
    return (result.latitude, result.longitude)


@lru_cache(maxsize=8000)
def route_minutes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    mode: str,
    ors_api_key: Optional[str],
) -> float:
    if ors_api_key:
        url = f"https://api.openrouteservice.org/v2/directions/{mode}"
        headers = {"Authorization": ors_api_key, "Content-Type": "application/json"}
        body = {
            "coordinates": [[origin_lon, origin_lat], [dest_lon, dest_lat]],
            "instructions": False,
        }
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            seconds = data["routes"][0]["summary"]["duration"]
            return seconds / 60
        except Exception:
            pass

    # Fallback approximation if ORS fails or key missing.
    km = geodesic((origin_lat, origin_lon), (dest_lat, dest_lon)).km
    speed = SPEED_KMPH_FALLBACK.get(mode, 25)
    return (km / speed) * 60


@st.cache_data(show_spinner=False)
def fetch_pois(
    center_lat: float,
    center_lon: float,
    radius_m: int,
    overpass_filter: str,
) -> List[Tuple[float, float]]:
    query = f"""
    [out:json][timeout:25];
    (
      {overpass_filter}
    )(around:{radius_m},{center_lat},{center_lon});
    out body;
    """
    try:
        resp = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": query},
            timeout=35,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        return [(el["lat"], el["lon"]) for el in elements if "lat" in el and "lon" in el]
    except Exception:
        return []


def generate_grid(center: Tuple[float, float], radius_km: float, points_per_side: int) -> List[Tuple[float, float]]:
    lat, lon = center
    lats = np.linspace(lat - radius_km / 111, lat + radius_km / 111, points_per_side)
    lons = np.linspace(lon - radius_km / (111 * max(math.cos(math.radians(lat)), 0.2)),
                       lon + radius_km / (111 * max(math.cos(math.radians(lat)), 0.2)),
                       points_per_side)
    return [(float(la), float(lo)) for la in lats for lo in lons]


def rgba_for_minutes(minutes_per_trip: float) -> List[int]:
    # Green <=20 min, red >=60 min.
    value = max(0.0, min(1.0, (minutes_per_trip - 20) / 40))
    red = int(255 * value)
    green = int(255 * (1 - value))
    return [red, green, 40, 180]


def resolve_anchor_rows(raw_df: pd.DataFrame) -> Tuple[List[Anchor], Dict[str, Tuple[float, float]], List[str]]:
    errors: List[str] = []
    anchors: List[Anchor] = []
    address_coords: Dict[str, Tuple[float, float]] = {}

    for _, row in raw_df.iterrows():
        name = str(row["name"]).strip()
        kind = str(row["kind"]).strip()
        value = str(row["value"]).strip()
        mode = str(row["mode"]).strip()
        after_anchor_raw = str(row["after_anchor"]).strip()
        after_anchor = after_anchor_raw if after_anchor_raw and after_anchor_raw.lower() != "none" else None

        if not name:
            continue
        if kind not in {"address", "place_type"}:
            errors.append(f"Anchor '{name}' has invalid kind.")
            continue
        if not value:
            errors.append(f"Anchor '{name}' is missing a value.")
            continue

        freq = float(row["frequency_per_week"])
        anchor = Anchor(name=name, kind=kind, value=value, mode=mode, frequency=freq, after_anchor=after_anchor)
        anchors.append(anchor)

        if kind == "address":
            coord = geocode_address(value)
            if not coord:
                errors.append(f"Could not geocode address for '{name}'.")
            else:
                address_coords[name] = coord

    anchor_names = {a.name for a in anchors}
    for a in anchors:
        if a.after_anchor and a.after_anchor not in anchor_names:
            errors.append(f"Anchor '{a.name}' references missing after_anchor '{a.after_anchor}'.")

    return anchors, address_coords, errors


def compute_score_for_home(
    home: Tuple[float, float],
    anchors: List[Anchor],
    address_coords: Dict[str, Tuple[float, float]],
    pois_by_type: Dict[str, List[Tuple[float, float]]],
    ors_api_key: Optional[str],
) -> float:
    total_weekly_minutes = 0.0

    for anchor in anchors:
        if anchor.frequency <= 0:
            continue

        if anchor.after_anchor:
            if anchor.after_anchor not in address_coords:
                continue
            origin = address_coords[anchor.after_anchor]
        else:
            origin = home

        if anchor.kind == "address":
            if anchor.name not in address_coords:
                continue
            dest = address_coords[anchor.name]
            mins = route_minutes(origin[0], origin[1], dest[0], dest[1], anchor.mode, ors_api_key)
        else:
            candidates = pois_by_type.get(anchor.value, [])
            if not candidates:
                continue

            # Pick nearest POI by estimated route minutes.
            sampled = sorted(
                candidates,
                key=lambda p: geodesic(origin, p).km,
            )[:12]
            mins = min(
                route_minutes(origin[0], origin[1], p[0], p[1], anchor.mode, ors_api_key)
                for p in sampled
            )

        total_weekly_minutes += mins * anchor.frequency

    return total_weekly_minutes


def main() -> None:
    st.title("🏠 Where To Live Optimizer")
    st.caption("Find high-fit home zones from your life anchors (work, gym, grocery, trails, etc.).")

    with st.sidebar:
        st.header("Configuration")
        ors_api_key = st.text_input("OpenRouteService API key (optional)", type="password")
        st.markdown(
            "Without an ORS key, travel times use distance-based approximations. "
            "For realistic car/walk/bike/transit times, add a key."
        )
        search_radius_km = st.slider("Search radius around center (km)", 2, 30, 10)
        grid_side = st.slider("Grid resolution (higher = slower)", 6, 30, 12)
        poi_radius_m = st.slider("POI lookup radius (meters)", 1000, 30000, 12000, step=500)

    st.subheader("Anchor locations")
    st.write(
        "Define locations/types that matter and how often you travel there. "
        "Use `after_anchor` when trips usually happen after another fixed anchor (like work → gym)."
    )

    default = pd.DataFrame(
        [
            {
                "name": "Work",
                "kind": "address",
                "value": "1 Market St, San Francisco, CA",
                "mode": "driving-car",
                "frequency_per_week": 5,
                "after_anchor": "",
            },
            {
                "name": "Gym",
                "kind": "place_type",
                "value": "Gym",
                "mode": "driving-car",
                "frequency_per_week": 4,
                "after_anchor": "Work",
            },
            {
                "name": "Grocery",
                "kind": "place_type",
                "value": "Grocery Store",
                "mode": "driving-car",
                "frequency_per_week": 3,
                "after_anchor": "",
            },
        ]
    )

    edited = st.data_editor(
        default,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "kind": st.column_config.SelectboxColumn("kind", options=["address", "place_type"]),
            "mode": st.column_config.SelectboxColumn("mode", options=MODE_OPTIONS),
            "value": st.column_config.SelectboxColumn(
                "value",
                options=list(PLACE_TYPE_TO_OVERPASS.keys()) + [""],
                help="For address kind, type full address. For place_type, pick one option.",
            ),
            "frequency_per_week": st.column_config.NumberColumn(min_value=0, step=1),
        },
    )

    if st.button("Generate heatmap", type="primary"):
        anchors, address_coords, errors = resolve_anchor_rows(edited)
        if not anchors:
            st.error("Please add at least one valid anchor.")
            return

        if errors:
            for err in errors:
                st.warning(err)

        fixed_points = list(address_coords.values())
        if not fixed_points:
            st.error("At least one address anchor is needed to center the search area.")
            return

        center = (
            float(np.mean([p[0] for p in fixed_points])),
            float(np.mean([p[1] for p in fixed_points])),
        )

        st.info("Fetching place-type points of interest...")
        pois_by_type: Dict[str, List[Tuple[float, float]]] = {}
        for anchor in anchors:
            if anchor.kind != "place_type":
                continue
            if anchor.value not in PLACE_TYPE_TO_OVERPASS:
                st.warning(f"Unsupported place type '{anchor.value}' for anchor '{anchor.name}'.")
                continue
            if anchor.value not in pois_by_type:
                pois = fetch_pois(center[0], center[1], poi_radius_m, PLACE_TYPE_TO_OVERPASS[anchor.value])
                pois_by_type[anchor.value] = pois
                st.write(f"{anchor.value}: found {len(pois)} matching points")

        st.info("Scoring candidate home cells...")
        cells = generate_grid(center, search_radius_km, grid_side)

        scored_rows = []
        for lat, lon in cells:
            weekly = compute_score_for_home((lat, lon), anchors, address_coords, pois_by_type, ors_api_key or None)
            per_trip = weekly / max(sum(a.frequency for a in anchors if a.frequency > 0), 1)
            scored_rows.append(
                {
                    "lat": lat,
                    "lon": lon,
                    "weekly_minutes": weekly,
                    "avg_minutes_per_trip": per_trip,
                    "color": rgba_for_minutes(per_trip),
                }
            )

        score_df = pd.DataFrame(scored_rows).sort_values("weekly_minutes")
        st.success("Done. Lower weekly minutes = better fit.")

        best = score_df.iloc[0]
        st.metric("Best candidate weekly minutes", f"{best['weekly_minutes']:.1f}")
        st.metric("Best candidate avg minutes/trip", f"{best['avg_minutes_per_trip']:.1f}")

        anchor_df = pd.DataFrame(
            [
                {"lat": c[0], "lon": c[1], "label": name}
                for name, c in address_coords.items()
            ]
        )

        layer_cells = pdk.Layer(
            "ScatterplotLayer",
            data=score_df,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=220,
            pickable=True,
            opacity=0.65,
        )
        layers = [layer_cells]

        if not anchor_df.empty:
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=anchor_df,
                    get_position="[lon, lat]",
                    get_fill_color="[20,20,20,255]",
                    get_radius=320,
                    pickable=True,
                )
            )

        deck = pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=pdk.ViewState(latitude=center[0], longitude=center[1], zoom=11),
            layers=layers,
            tooltip={
                "html": "<b>Avg minutes/trip:</b> {avg_minutes_per_trip}<br/><b>Weekly minutes:</b> {weekly_minutes}",
                "style": {"color": "white"},
            },
        )

        st.pydeck_chart(deck, use_container_width=True)
        st.dataframe(score_df.head(20), use_container_width=True)


if __name__ == "__main__":
    main()
