
import streamlit as st
import zipfile
import os
import requests
import xml.etree.ElementTree as ET
import tempfile
import json
import base64
from streamlit_folium import st_folium
import folium

st.set_page_config(layout="wide")
st.title("Google My Maps to SVG Exporter")

# --- Session State Defaults ---
if "kml_data" not in st.session_state:
    st.session_state.kml_data = None

# --- Helper Functions ---
def extract_map_id(mymaps_url):
    import re
    match = re.search(r"mid=([^&]+)", mymaps_url)
    return match.group(1) if match else None

def download_kml(map_id):
    url = f"https://www.google.com/maps/d/kml?mid={map_id}"
    response = requests.get(url)
    if response.status_code == 200:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".kml") as tmp:
            tmp.write(response.content)
            return tmp.name
    else:
        st.error("Failed to download KML")
        return None

def parse_kml(kml_file):
    try:
        tree = ET.parse(kml_file)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        placemarks = []
        for pm in root.findall(".//kml:Placemark", ns):
            name = pm.find("kml:name", ns)
            point = pm.find("kml:Point/kml:coordinates", ns)
            if name is not None and point is not None:
                coords = point.text.strip().split(",")
                placemarks.append({
                    "name": name.text,
                    "lon": float(coords[0]),
                    "lat": float(coords[1])
                })
        return placemarks
    except Exception as e:
        st.error(f"Error parsing KML: {e}")
        return []

# --- Interface ---
url = st.text_input("Paste your Google My Maps URL")
export_all = st.checkbox("Export all pins (ignore zoom)")

color_options = ["#FF5F2C", "#FF3119"]
selected_layers = []
custom_colors = {}

# --- Load KML ---
if url and not st.session_state.kml_data:
    map_id = extract_map_id(url)
    if map_id:
        kml_file = download_kml(map_id)
        if kml_file:
            pins = parse_kml(kml_file)
            st.session_state.kml_data = pins
            st.success(f"Loaded {len(pins)} pins from map.")

# --- Layer Controls ---
if st.session_state.kml_data:
    st.markdown("### Select layers and their colors")
    for i, layer in enumerate(sorted(set(p["name"] for p in st.session_state.kml_data))):
        col1, col2 = st.columns([1, 2])
        with col1:
            toggle = st.toggle(layer, True, key=f"layer_{i}")
            if toggle:
                selected_layers.append(layer)
        with col2:
            hex_code = st.selectbox(
                f"Color for {layer}",
                color_options + ["Custom..."],
                key=f"color_{i}"
            )
            if hex_code == "Custom...":
                hex_code = st.text_input(f"Enter custom hex for {layer}", "#000000", key=f"custom_{i}")
            custom_colors[layer] = hex_code

# --- Map Display ---
if st.session_state.kml_data:
    m = folium.Map(location=[-25, 135], zoom_start=4)
    for p in st.session_state.kml_data:
        if export_all or p["name"] in selected_layers:
            color = custom_colors.get(p["name"], "#FF5F2C")
            folium.CircleMarker(
                location=[p["lat"], p["lon"]],
                radius=6,
                color=color,
                fill=True,
                fill_opacity=0.9,
                tooltip=p["name"]
            ).add_to(m)

    st_folium(m, height=500)

    # --- SVG Download ---
    if st.button("Download SVG"):
        svg_output = "<svg xmlns='http://www.w3.org/2000/svg' width='1000' height='1000'>\n"
        for p in st.session_state.kml_data:
            if export_all or p["name"] in selected_layers:
                color = custom_colors.get(p["name"], "#FF5F2C")
                svg_output += f"<circle cx='50%' cy='50%' r='6' fill='{color}' />\n"
        svg_output += "</svg>"
        b64 = base64.b64encode(svg_output.encode()).decode()
        href = f'<a href="data:image/svg+xml;base64,{b64}" download="map.svg">Click to Download SVG</a>'
        st.markdown(href, unsafe_allow_html=True)
