# Where To Live Optimizer

A simple Python web app that helps people find better places to live using anchor points in their weekly life (work, gym, grocery, trails, etc.).

## What this MVP implements

This covers the week 1 to week 3 goals:

- **Week 1:** Input model + weighted scoring engine.
- **Week 2:** POI lookup for place types + interactive map heat coloring.
- **Week 3:** Sequencing via `after_anchor` (example: work -> gym).

## Inputs supported

Each anchor row includes:

1. `mode` (driving, cycling, walking, transit)
2. `frequency_per_week`
3. `kind` (`address` or `place_type`)
4. `after_anchor` (optional; usually for chained habits like work -> gym)

Behavior:

- If `kind=address`, routing is to that specific address.
- If `kind=place_type`, any matching POI can satisfy the trip; the app chooses the best nearby option.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the local Streamlit URL shown in terminal.

## API notes

- You can provide an **OpenRouteService API key** for real route-time estimates.
- Without a key, the app falls back to distance/speed approximations.
- Place type search is done using Overpass (OpenStreetMap data).

## Current limitations

- `after_anchor` currently expects a named **address anchor** for route chaining.
- Transit mode is estimated unless your ORS key/profile setup supports your region.
- This is an MVP and does not yet include housing listing overlays.
