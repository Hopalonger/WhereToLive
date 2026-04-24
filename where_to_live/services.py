import math
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

import requests
import streamlit as st
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

from where_to_live.constants import PLACE_TYPE_TO_NOMINATIM_QUERY, SPEED_KMPH_FALLBACK


@st.cache_resource
def geocoder() -> Nominatim:
    return Nominatim(user_agent="where-to-live-optimizer")


@st.cache_data(show_spinner=False)
def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    result = geocoder().geocode(address, timeout=15)
    if not result:
        return None
    return (result.latitude, result.longitude)


@lru_cache(maxsize=12000)
def route_minutes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    mode_code: str,
    ors_api_key: Optional[str],
) -> float:
    st.session_state["ors_request_count"] = int(st.session_state.get("ors_request_count", 0))

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
            st.session_state["ors_request_succeeded"] = True
            st.session_state["ors_request_count"] += 1
            return seconds / 60
        except Exception as exc:
            st.session_state["ors_last_error"] = str(exc)
            st.session_state["ors_unroutable_count"] = int(st.session_state.get("ors_unroutable_count", 0)) + 1
            return math.inf

    distance_km = geodesic((origin_lat, origin_lon), (dest_lat, dest_lon)).km
    speed_kmph = SPEED_KMPH_FALLBACK.get(mode_code, 25)
    return (distance_km / speed_kmph) * 60


@st.cache_data(show_spinner=False)
def fetch_pois(
    center_lat: float,
    center_lon: float,
    radius_m: int,
    overpass_filters: Sequence[str],
) -> List[Tuple[float, float]]:
    if not overpass_filters:
        return []

    filter_lines = [f"nwr[{filter_expr}](around:{radius_m},{center_lat},{center_lon});" for filter_expr in overpass_filters]

    query = f"""
    [out:json][timeout:25];
    (
      {" ".join(filter_lines)}
    );
    out body center;
    """
    try:
        response = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": query},
            timeout=35,
        )
        response.raise_for_status()
        elements = response.json().get("elements", [])
        points: List[Tuple[float, float]] = []
        for el in elements:
            if "lat" in el and "lon" in el:
                points.append((el["lat"], el["lon"]))
            elif "center" in el and "lat" in el["center"] and "lon" in el["center"]:
                points.append((el["center"]["lat"], el["center"]["lon"]))

        # Keep unique results while preserving order.
        return list(dict.fromkeys(points))
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def fetch_pois_nominatim(
    center_lat: float,
    center_lon: float,
    radius_m: int,
    place_type: str,
) -> List[Tuple[float, float]]:
    query = PLACE_TYPE_TO_NOMINATIM_QUERY.get(place_type)
    if not query:
        return []

    approx_lat_delta = radius_m / 111000
    approx_lon_delta = radius_m / (111000 * max(abs(math.cos(math.radians(center_lat))), 0.2))
    viewbox = f"{center_lon - approx_lon_delta},{center_lat + approx_lat_delta},{center_lon + approx_lon_delta},{center_lat - approx_lat_delta}"

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 80,
                "bounded": 1,
                "viewbox": viewbox,
            },
            headers={"User-Agent": "where-to-live-optimizer"},
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()
        points = []
        for row in rows:
            lat = row.get("lat")
            lon = row.get("lon")
            if lat is None or lon is None:
                continue
            points.append((float(lat), float(lon)))
        return list(dict.fromkeys(points))
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def fetch_isochrone_geojson(
    origin_lat: float,
    origin_lon: float,
    mode_code: str,
    max_minutes: int,
    ors_api_key: Optional[str],
) -> Optional[dict]:
    if not ors_api_key or mode_code == "transit":
        return None

    try:
        response = requests.post(
            f"https://api.openrouteservice.org/v2/isochrones/{mode_code}",
            headers={"Authorization": ors_api_key, "Content-Type": "application/json"},
            json={
                "locations": [[origin_lon, origin_lat]],
                "range": [max_minutes * 60],
                "location_type": "start",
                "smoothing": 0.2,
            },
            timeout=30,
        )
        response.raise_for_status()
        st.session_state["ors_request_succeeded"] = True
        st.session_state["ors_request_count"] = int(st.session_state.get("ors_request_count", 0)) + 1
        return response.json()
    except Exception as exc:
        st.session_state["ors_last_error"] = str(exc)
        return None
