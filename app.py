import streamlit as st

st.set_page_config(page_title="Where To Live Optimizer", page_icon="🏠", layout="wide")

st.title("🏠 Where To Live Optimizer")
st.subheader("Find better neighborhoods based on your real weekly life patterns.")

st.markdown(
    """
### What this tool does
This app helps you identify **general areas to live** by modeling your weekly travel needs:
- fixed destinations (like work or a partner's house),
- flexible place types (like gym, grocery, parks, trails),
- transportation modes,
- routines that happen after specific anchors (for example, work → gym),
- average vs worst-case commute assumptions.

### How it works
1. You define your anchors in the **Tool** page.
2. The app geocodes exact addresses and fetches POIs for place types.
3. It scores candidate home cells by total weekly travel time.
4. It visualizes results with color-coded markers (green = lower travel burden, red = higher).

### Intended use case
Use this as a **decision-support map** to narrow down neighborhoods before you evaluate housing options.
It is best for finding high-fit regions, not exact door-to-door predictions.

➡️ Open the **Tool** page in the left sidebar to start.
"""
)

st.info(
    "Tip: add an OpenRouteService API key on the Tool page for better route realism. "
    "Without a key, the app uses a distance/speed fallback."
)
