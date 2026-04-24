import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from geopy.distance import geodesic

from where_to_live.constants import TRANSPORT_OPTIONS
from where_to_live.models import Anchor
from where_to_live.services import route_minutes


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


def generate_grid(center: Tuple[float, float], radius_km: float, points_per_side: int) -> List[Tuple[float, float]]:
    lat, lon = center
    lat_range = radius_km / 111
    lon_range = radius_km / (111 * max(math.cos(math.radians(lat)), 0.2))
    lats = np.linspace(lat - lat_range, lat + lat_range, points_per_side)
    lons = np.linspace(lon - lon_range, lon + lon_range, points_per_side)
    return [(float(la), float(lo)) for la in lats for lo in lons]


def _point_in_ring(lat: float, lon: float, ring: List[List[float]]) -> bool:
    inside = False
    if not ring:
        return False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][1], ring[i][0]
        xj, yj = ring[j][1], ring[j][0]
        crosses = (yi > lat) != (yj > lat)
        if crosses:
            xinters = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
            if lon < xinters:
                inside = not inside
        j = i
    return inside


def _point_in_polygon(lat: float, lon: float, polygon_coords: List[List[List[float]]]) -> bool:
    if not polygon_coords:
        return False
    if not _point_in_ring(lat, lon, polygon_coords[0]):
        return False
    # Holes should exclude points.
    for hole in polygon_coords[1:]:
        if _point_in_ring(lat, lon, hole):
            return False
    return True


def point_in_geojson(lat: float, lon: float, geometry: dict) -> bool:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        return _point_in_polygon(lat, lon, coords)
    if gtype == "MultiPolygon":
        return any(_point_in_polygon(lat, lon, poly) for poly in coords)
    return False


def color_for_minutes(avg_minutes_per_trip: float) -> str:
    ratio = max(0.0, min(1.0, (avg_minutes_per_trip - 20) / 40))
    red = int(255 * ratio)
    green = int(255 * (1 - ratio))
    return f"#{red:02x}{green:02x}33"


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
