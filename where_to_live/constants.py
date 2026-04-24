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
SPEED_KMPH_FALLBACK = {
    "driving-car": 40,
    "cycling-regular": 18,
    "foot-walking": 5,
    "transit": 25,
}
