TRANSPORT_OPTIONS = {
    "Drive": "driving-car",
    "Bike": "cycling-regular",
    "Walk": "foot-walking",
    "Public Transit": "transit",
}

PLACE_TYPE_TO_OVERPASS = {
    "Grocery Store": [
        '"shop"="supermarket"',
        '"shop"="grocery"',
        '"shop"="convenience"',
    ],
    "Gym / Fitness": [
        '"leisure"="fitness_centre"',
        '"amenity"="gym"',
        '"sport"="fitness"',
    ],
    "Coffee Shop": ['"amenity"="cafe"', '"shop"="coffee"'],
    "Mountain / Trail": ['"natural"="peak"', '"highway"="path"', '"route"="hiking"'],
    "Park": ['"leisure"="park"'],
}

PLACE_TYPE_TO_NOMINATIM_QUERY = {
    "Grocery Store": "grocery supermarket",
    "Gym / Fitness": "gym fitness centre",
    "Coffee Shop": "coffee shop cafe",
    "Mountain / Trail": "trailhead hiking trail",
    "Park": "public park",
}

TIME_PROFILES = ["Average", "Worst Case", "Custom Departure Time"]
SPEED_KMPH_FALLBACK = {
    "driving-car": 40,
    "cycling-regular": 18,
    "foot-walking": 5,
    "transit": 25,
}
