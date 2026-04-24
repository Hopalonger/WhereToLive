import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import folium
import numpy as np
import requests
import streamlit as st
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

st.set_page_config(page_title="Where To Live Optimizer", page_icon="🏠", layout="wide")

TRANSPORT_OPTIONS = {
    "Drive": "driving-car",
    "Bike": "cycling-regular",
    "Walk": "foot-walking",
    "Public Transit": "transit",
}

PLACE_TYPE_TO_OVERPASS = {
    "Grocery Store": '(node["shop"="supermarket"];node["shop"="grocery"];)',
    "Gym / Fitness": '(node["leisure"="fitness_centre"];node["amenity"="gym"];)',
    "Coffee Shop": '(node["amenity"="cafe"];)',
    "Mountain / Trail": '(node["natural"="peak"];node["highway"="path"];node["route"="hiking"];)',
    "Park": '(node["leisure"="park"];)',
}

TIME_PROFILES = ["Average", "Worst Case", "Custom Departure Time"]
SPEED_KMPH_FALLBACK = {"driving-car": 40, "cycling-regular": 18, "foot-walking": 5, "transit": 25}


@dataclass
class Anchor:
    name: str
    location_type: str
    address: str
    place_type: str
    transport_mode_label: str
    trips_per_week: float
    after_anchor: Optional[str]
    time_profile: str
    custom_departure: Optional[str]


@st.cache_resource
def geocoder() -> Nominatim:
    return Nominatim(user_agent="where-to-live-optimizer")


@st.cache_data(show_spinner=False)
def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    result = geocoder().geocode(address, timeout=15)
    if not result:
        return None
    return (result.latitude, result.longitude)


def time_profile_multiplier(profile: str, custom_departure: Optional[str]) -> float:
    if profile == "Worst Case":
        return 1.5
    if profile == "Custom Departure Time" and custom_departure:
        hour = int(custom_departure.split(":")[0])
        if 7 <= hour <= 9 or 16 <= hour <= 19:
            return 1.3
        if 0 <= hour <= 5:
            return 1.15
        return 0.95
    return 1.0


@lru_cache(maxsize=12000)
def route_minutes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    mode_code: str,
    ors_api_key: Optional[str],
) -> float:
    if ors_api_key and mode_code != "transit":
        url = f"https://api.openrouteservice.org/v2/directions/{mode_code}"
        headers = {"Authorization": ors_api_key, "Content-Type": "application/json"}
        body = {
            "coordinates": [[origin_lon, origin_lat], [dest_lon, dest_lat]],
            "instructions": False,
        }
        try:
            response = requests.post(url, headers=headers, json=body, timeout=20)
            response.raise_for_status()
            seconds = response.json()["routes"][0]["summary"]["duration"]
            return seconds / 60
        except Exception:
            pass

    distance_km = geodesic((origin_lat, origin_lon), (dest_lat, dest_lon)).km
    speed_kmph = SPEED_KMPH_FALLBACK.get(mode_code, 25)
    return (distance_km / speed_kmph) * 60


@st.cache_data(show_spinner=False)
def fetch_pois(center_lat: float, center_lon: float, radius_m: int, overpass_filter: str) -> List[Tuple[float, float]]:
    query = f"""
    [out:json][timeout:25];
    (
      {overpass_filter}
    )(around:{radius_m},{center_lat},{center_lon});
    out body;
    """
    try:
        response = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": query},
            timeout=35,
        )
        response.raise_for_status()
        elements = response.json().get("elements", [])
        return [(el["lat"], el["lon"]) for el in elements if "lat" in el and "lon" in el]
    except Exception:
        return []


def generate_grid(center: Tuple[float, float], radius_km: float, points_per_side: int) -> List[Tuple[float, float]]:
    lat, lon = center
    lat_range = radius_km / 111
    lon_range = radius_km / (111 * max(math.cos(math.radians(lat)), 0.2))
    lats = np.linspace(lat - lat_range, lat + lat_range, points_per_side)
    lons = np.linspace(lon - lon_range, lon + lon_range, points_per_side)
    return [(float(la), float(lo)) for la in lats for lo in lons]


def color_for_minutes(avg_minutes_per_trip: float) -> str:
    # Green <= 20 mins, red >= 60 mins.
    ratio = max(0.0, min(1.0, (avg_minutes_per_trip - 20) / 40))
    red = int(255 * ratio)
    green = int(255 * (1 - ratio))
    return f"#{red:02x}{green:02x}33"


def build_anchor_from_state(item: Dict[str, str]) -> Anchor:
    return Anchor(
        name=item.get("name", "").strip(),
        location_type=item.get("location_type", "Exact Address"),
        address=item.get("address", "").strip(),
        place_type=item.get("place_type", "Grocery Store"),
        transport_mode_label=item.get("transport_mode_label", "Drive"),
        trips_per_week=float(item.get("trips_per_week", 1) or 0),
        after_anchor=item.get("after_anchor") or None,
        time_profile=item.get("time_profile", "Average"),
        custom_departure=item.get("custom_departure") or None,
    )


def compute_score_for_home(
    home: Tuple[float, float],
    anchors: List[Anchor],
    address_coords: Dict[str, Tuple[float, float]],
    pois_by_type: Dict[str, List[Tuple[float, float]]],
    ors_api_key: Optional[str],
) -> float:
    total_weekly_minutes = 0.0

    for anchor in anchors:
        if anchor.trips_per_week <= 0:
            continue

        if anchor.after_anchor:
            origin = address_coords.get(anchor.after_anchor)
            if not origin:
                continue
        else:
            origin = home

        mode_code = TRANSPORT_OPTIONS[anchor.transport_mode_label]

        if anchor.location_type == "Exact Address":
            destination = address_coords.get(anchor.name)
            if not destination:
                continue
            minutes = route_minutes(origin[0], origin[1], destination[0], destination[1], mode_code, ors_api_key)
        else:
            poi_candidates = pois_by_type.get(anchor.place_type, [])
            if not poi_candidates:
                continue

            nearest_candidates = sorted(poi_candidates, key=lambda p: geodesic(origin, p).km)[:12]
            minutes = min(
                route_minutes(origin[0], origin[1], p[0], p[1], mode_code, ors_api_key)
                for p in nearest_candidates
            )

        minutes *= time_profile_multiplier(anchor.time_profile, anchor.custom_departure)
        total_weekly_minutes += minutes * anchor.trips_per_week

    return total_weekly_minutes


def initialize_anchor_state() -> None:
    if "anchors" not in st.session_state:
        st.session_state.anchors = [
            {
                "name": "Work",
                "location_type": "Exact Address",
                "address": "1 Market St, San Francisco, CA",
                "place_type": "Grocery Store",
                "transport_mode_label": "Drive",
                "trips_per_week": 5,
                "after_anchor": "",
                "time_profile": "Average",
                "custom_departure": "08:00",
            },
            {
                "name": "Gym",
                "location_type": "Type of Place",
                "address": "",
                "place_type": "Gym / Fitness",
                "transport_mode_label": "Drive",
                "trips_per_week": 4,
                "after_anchor": "Work",
                "time_profile": "Average",
                "custom_departure": "18:00",
            },
        ]


def render_anchor_editor() -> List[Anchor]:
    initialize_anchor_state()
    anchors_raw = st.session_state.anchors

    st.subheader("Your Life Anchors")
    st.write("Add important weekly destinations and habits. All labels are user-friendly and configurable.")

    cols = st.columns([1, 1, 6])
    if cols[0].button("➕ Add Anchor"):
        anchors_raw.append(
            {
                "name": f"Anchor {len(anchors_raw) + 1}",
                "location_type": "Exact Address",
                "address": "",
                "place_type": "Grocery Store",
                "transport_mode_label": "Drive",
                "trips_per_week": 1,
                "after_anchor": "",
                "time_profile": "Average",
                "custom_departure": "08:00",
            }
        )
        st.rerun()

    if cols[1].button("➖ Remove Last") and anchors_raw:
        anchors_raw.pop()
        st.rerun()

    anchor_names = [a.get("name", "") for a in anchors_raw if a.get("name", "")]

    for idx, item in enumerate(anchors_raw):
        with st.expander(f"Anchor {idx + 1}: {item.get('name', '') or 'Unnamed'}", expanded=True):
            c1, c2, c3 = st.columns(3)
            item["name"] = c1.text_input("Anchor Name", value=item.get("name", ""), key=f"name_{idx}")
            item["location_type"] = c2.selectbox(
                "Location Type",
                ["Exact Address", "Type of Place"],
                index=0 if item.get("location_type") == "Exact Address" else 1,
                key=f"type_{idx}",
            )
            item["transport_mode_label"] = c3.selectbox(
                "Transportation Mode",
                list(TRANSPORT_OPTIONS.keys()),
                index=list(TRANSPORT_OPTIONS.keys()).index(item.get("transport_mode_label", "Drive")),
                key=f"mode_{idx}",
            )

            c4, c5, c6 = st.columns(3)
            item["trips_per_week"] = c4.number_input(
                "Trips Per Week",
                min_value=0,
                step=1,
                value=int(item.get("trips_per_week", 1)),
                key=f"freq_{idx}",
            )
            after_options = ["None"] + anchor_names
            current_after = item.get("after_anchor") or "None"
            if current_after not in after_options:
                current_after = "None"
            item["after_anchor"] = c5.selectbox(
                "Usually Happens After",
                after_options,
                index=after_options.index(current_after),
                key=f"after_{idx}",
            )
            if item["after_anchor"] == "None":
                item["after_anchor"] = ""

            item["time_profile"] = c6.selectbox(
                "Transit Time Scenario",
                TIME_PROFILES,
                index=TIME_PROFILES.index(item.get("time_profile", "Average")),
                key=f"profile_{idx}",
            )

            if item["location_type"] == "Exact Address":
                item["address"] = st.text_input(
                    "Address",
                    value=item.get("address", ""),
                    key=f"address_{idx}",
                    placeholder="123 Main St, City, State",
                )
            else:
                item["place_type"] = st.selectbox(
                    "Place Type",
                    list(PLACE_TYPE_TO_OVERPASS.keys()),
                    index=list(PLACE_TYPE_TO_OVERPASS.keys()).index(item.get("place_type", "Grocery Store")),
                    key=f"place_{idx}",
                )

            if item["time_profile"] == "Custom Departure Time":
                t = st.time_input("Typical Departure Time", value=None, key=f"custom_time_{idx}")
                item["custom_departure"] = t.strftime("%H:%M") if t else "08:00"

    st.session_state.anchors = anchors_raw
    return [build_anchor_from_state(item) for item in anchors_raw]


def resolve_addresses(anchors: List[Anchor]) -> Tuple[Dict[str, Tuple[float, float]], List[str]]:
    errors: List[str] = []
    address_coords: Dict[str, Tuple[float, float]] = {}

    for anchor in anchors:
        if not anchor.name:
            errors.append("One anchor is missing a name.")
            continue
        if anchor.location_type == "Exact Address":
            if not anchor.address:
                errors.append(f"'{anchor.name}' needs an address.")
                continue
            coord = geocode_address(anchor.address)
            if not coord:
                errors.append(f"Could not locate address for '{anchor.name}'.")
                continue
            address_coords[anchor.name] = coord

    return address_coords, errors


def build_map(
    center: Tuple[float, float],
    address_coords: Dict[str, Tuple[float, float]],
    score_rows: Optional[List[Dict[str, float]]] = None,
) -> None:
    fmap = folium.Map(location=[center[0], center[1]], zoom_start=11, tiles="CartoDB positron")

    for name, coord in address_coords.items():
        folium.Marker(
            location=[coord[0], coord[1]],
            popup=f"{name}",
            tooltip=name,
            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
        ).add_to(fmap)

    if score_rows:
        for row in score_rows:
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=7,
                color=row["color"],
                fill=True,
                fill_opacity=0.55,
                popup=(
                    f"Avg minutes/trip: {row['avg_minutes_per_trip']:.1f}<br>"
                    f"Weekly minutes: {row['weekly_minutes']:.1f}"
                ),
            ).add_to(fmap)

    st_folium(fmap, use_container_width=True, height=560)


def main() -> None:
    st.title("🏠 Where To Live Optimizer")
    st.caption("Find the best areas to live based on your real routines: work, gym, groceries, trails, and more.")

    with st.sidebar:
        st.header("Settings")
        ors_api_key = st.text_input("OpenRouteService API Key (optional)", type="password")
        st.info("If no key is provided, the app estimates travel time using distance and average speeds.")
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
    st.write("Map loads immediately so you can explore. Pins mark any exact-address anchors.")
    build_map(center, address_coords)

    if address_errors:
        for msg in address_errors:
            st.warning(msg)

    if st.button("Generate Commute Heatmap", type="primary"):
        if not address_coords:
            st.error("Please add at least one valid exact address anchor before generating the heatmap.")
            return

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


if __name__ == "__main__":
    main()
