# Where To Live Optimizer

A Python web app that helps people find better places to live using real weekly anchors (work, gym, grocery, trails, etc.) and a visual commute heatmap.

## What this implements

- Weighted scoring model using weekly trip frequency.
- Mixed anchors: exact addresses + flexible place types.
- Sequencing support (`Usually Happens After`) for routines like work → gym.
- Time-of-day scenario controls (`Average`, `Worst Case`, or `Custom Departure Time`).
- Live map that loads by default, shows anchor pins, and overlays colored candidate cells.

## Inputs supported

For each anchor, the UI supports:

1. **Transportation Mode** (Drive, Bike, Walk, Public Transit)
2. **Trips Per Week**
3. **Location Type** (`Exact Address` or `Type of Place`)
4. **Usually Happens After** (optional sequencing)
5. **Transit Time Scenario** (`Average`, `Worst Case`, `Custom Departure Time`)

Behavior:

- If `Location Type = Exact Address`, you enter a full address.
- If `Location Type = Type of Place`, you select a place category (e.g., Grocery Store, Gym / Fitness).

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

## Troubleshooting

- `streamlit is not recognized`: run with `py -m streamlit run app.py` (Windows) or `python -m streamlit run app.py`.
- `source is not recognized` on Windows: use `.\.venv\Scripts\Activate.ps1` (PowerShell) or `.venv\Scripts\activate.bat` (cmd).
- If `py` is not found, install Python from python.org and enable **Add Python to PATH**.

## API notes

- Optional OpenRouteService API key for realistic drive/bike/walk routing.
- Without a key, the app uses distance/speed estimation fallback.
- Place-type lookup uses Overpass (OpenStreetMap).

## Current limitations

- Sequencing currently requires `Usually Happens After` to refer to a named exact-address anchor.
- Public transit routing is estimated in fallback mode.
