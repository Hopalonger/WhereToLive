# Where To Live Optimizer

A Python Streamlit app that helps people find better places to live using weekly anchors (work, gym, grocery, trails, etc.) and a visual commute heatmap.

## App structure

This project now uses a multi-file, multi-page layout:

- `app.py` → **Home page** (overview, how it works, intended use case)
- `pages/1_Tool.py` → **Tool page** (all optimizer inputs + map + scoring)
- `where_to_live/constants.py` → options and configuration constants
- `where_to_live/models.py` → typed data model(s)
- `where_to_live/services.py` → geocoding/routing/POI integrations
- `where_to_live/scoring.py` → grid + scoring logic
- `where_to_live/ui.py` → anchor form/editor + validation
- `where_to_live/map_view.py` → map rendering helpers

## Features

- Weighted scoring model using weekly trip frequency.
- Mixed anchors: exact addresses + flexible place types.
- Sequencing support (`Usually Happens After`) for routines like work → gym.
- Time-of-day scenario controls (`Average`, `Worst Case`, `Custom Departure Time`).
- Live map that loads by default, shows anchor pins, and overlays colored candidate cells.

## Running locally

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

If PowerShell blocks activation, run this once and retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Windows (Command Prompt / cmd)

```bat
py -m venv .venv
.venv\Scripts\activate.bat
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## API notes

- Optional OpenRouteService API key for realistic drive/bike/walk routing.
- Without a key, the app uses distance/speed estimation fallback.
- Place-type lookup uses Overpass (OpenStreetMap).
