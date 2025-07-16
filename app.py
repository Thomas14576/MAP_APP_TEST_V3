
import streamlit as st
from streamlit_folium import st_folium
import folium
import zipfile
import simplekml
import xml.etree.ElementTree as ET
import io
import base64

st.set_page_config(layout="wide")
st.title("Google My Maps to SVG Exporter")

# Input: Google My Maps URL
map_url = st.text_input("Paste your Google My Maps URL:", "")

# Export pins checkbox
export_all = st.checkbox("Export all pins (ignore zoom)", value=False)

# Initialize layer toggles and colors
layer_names = [
    "Fly - WA.xlsx", "Large Format - WA.xlsx", "Retail - WA.xlsx",
    "Street Digital - WA.xlsx", "Office - WA.xlsx", "Study - WA.xlsx", "Commute Posters AU - WA.xlsx"
]
hex_presets = ["#FF5F2C", "#FF3119"]

st.markdown("### Select layers and their colors")

selected_layers = []
layer_colors = {}

cols = st.columns([2, 2])
for idx, name in enumerate(layer_names):
    button_key = f"btn_{name}"
    if cols[0].toggle(name, key=button_key, value=True):
        selected_layers.append(name)
        color_key = f"color_{name}"
        choice = cols[1].selectbox(f"Color for {name}", options=hex_presets + ["Custom"], key=color_key)
        if choice == "Custom":
            custom_key = f"custom_{name}"
            custom_hex = cols[1].text_input(f"Custom HEX for {name}", "#FF0000", key=custom_key)
            layer_colors[name] = custom_hex
        else:
            layer_colors[name] = choice

# Create Folium map
m = folium.Map(location=[-25.0, 134.0], zoom_start=5, control_scale=True)

# Display folium map with zoom and pan
with st.container():
    st.markdown("### Map Preview (Pan & Zoom to crop)")
    map_state = st_folium(m, height=500, returned_objects=["bounds", "zoom"])

bounds = map_state.get("bounds")

if bounds:
    st.success("Map bounds received.")
    st.code(str(bounds))
    download_ready = True
else:
    download_ready = False
    st.warning("Incomplete map bounds detected. Try zooming or panning again.")

# Download button logic
if st.button("Download SVG + Pins", disabled=not download_ready and not export_all):
    # Dummy SVG & CSV content for now
    svg_content = "<svg><circle cx='50' cy='50' r='40' fill='orange' /></svg>"
    csv_content = "Name,Lat,Lng\nSample Pin,-33.86,151.20"

    # Create zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("map.svg", svg_content)
        zf.writestr("pins.csv", csv_content)

    b64 = base64.b64encode(zip_buffer.getvalue()).decode()
    href = f'<a href="data:application/zip;base64,{b64}" download="map_export.zip">Click to download ZIP</a>'
    st.markdown(href, unsafe_allow_html=True)
