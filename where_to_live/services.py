from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

import requests
import streamlit as st
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

from where_to_live.constants import SPEED_KMPH_FALLBACK


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
            return seconds / 60
        except Exception as exc:
            st.session_state["ors_last_error"] = str(exc)

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
    out center;
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
