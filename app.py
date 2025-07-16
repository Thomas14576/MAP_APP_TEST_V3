
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
from folium.plugins import Draw

st.set_page_config(layout="wide")
st.title("Google My Maps to SVG Exporter")

# --- Session State Defaults ---
if "kml_data" not in st.session_state:
    st.session_state.kml_data = None
if "map_bounds" not in st.session_state:
    st.session_state.map_bounds = None

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
        st.error("Failed to download KML file.")
        return None

def parse_kml_for_layers(kml_path):
    tree = ET.parse(kml_path)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    layers = {}
    for folder in root.findall(".//kml:Folder", ns):
        name_el = folder.find("kml:name", ns)
        if name_el is not None:
            name = name_el.text
            placemarks = folder.findall(".//kml:Placemark", ns)
            coords = []
            for placemark in placemarks:
                point = placemark.find("kml:Point/kml:coordinates", ns)
                if point is not None:
                    coord = point.text.strip().split(",")
                    coords.append((float(coord[1]), float(coord[0])))
            layers[name] = coords
    return layers

# --- UI ---
mymaps_url = st.text_input("Paste your Google My Maps URL")

if mymaps_url:
    map_id = extract_map_id(mymaps_url)
    if not map_id:
        st.error("Invalid URL. Could not extract map ID.")
    else:
        kml_path = download_kml(map_id)
        if kml_path:
            layers = parse_kml_for_layers(kml_path)
            st.session_state.kml_data = layers
            st.success(f"Loaded {sum(len(v) for v in layers.values())} pins from map.")

if st.session_state.kml_data:
    m = folium.Map(location=[-25.0, 135.0], zoom_start=4)
    layer_colors = {}

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Select layers and their colors")
    with col2:
        st.markdown("")

    selected_layers = []
    for layer_name, coords in st.session_state.kml_data.items():
        color = st.selectbox(
            f"Color for {layer_name}",
            options=["#FF5F2C", "#FF3119", "Custom"],
            key=f"color_{layer_name}",
        )
        if color == "Custom":
            color = st.text_input(f"Custom hex for {layer_name}", "#000000", key=f"custom_{layer_name}")
        layer_colors[layer_name] = color

        button_key = f"toggle_{layer_name}"
        if st.toggle(layer_name, value=True, key=button_key):
            selected_layers.append(layer_name)
            for lat, lon in coords:
                folium.CircleMarker(
                    location=(lat, lon),
                    radius=4,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=1
                ).add_to(m)

    with st.container():
        st_data = st_folium(m, height=500, width=1000)

    st.download_button("Download SVG", data="(pretend this is SVG)", file_name="map.svg", mime="image/svg+xml")
