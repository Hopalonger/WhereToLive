from dataclasses import dataclass
from typing import Optional


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
