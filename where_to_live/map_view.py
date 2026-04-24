from typing import Dict, List, Optional, Tuple

import folium
from streamlit_folium import st_folium


def build_map(
    center: Tuple[float, float],
    address_coords: Dict[str, Tuple[float, float]],
    score_rows: Optional[List[Dict[str, float]]] = None,
) -> None:
    fmap = folium.Map(location=[center[0], center[1]], zoom_start=11, tiles="CartoDB positron")

    for name, coord in address_coords.items():
        folium.Marker(
            location=[coord[0], coord[1]],
            popup=name,
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
