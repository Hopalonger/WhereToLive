from typing import Dict, List, Tuple

import streamlit as st

from where_to_live.constants import PLACE_TYPE_TO_OVERPASS, TIME_PROFILES, TRANSPORT_OPTIONS
from where_to_live.models import Anchor
from where_to_live.services import geocode_address


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


def render_anchor_editor() -> List[Anchor]:
    initialize_anchor_state()
    anchors_raw = st.session_state.anchors

    st.subheader("Your Life Anchors")
    st.write("Add important weekly destinations and habits.")

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
