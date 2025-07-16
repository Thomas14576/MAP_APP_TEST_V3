import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
import base64
from xml.dom.minidom import parseString
from collections import defaultdict

st.set_page_config(layout="wide")

st.title("Google My Maps to SVG Exporter")

# Input
url = st.text_input("Paste your Google My Maps URL")

def download_kml(kml_url):
    if "mid=" not in kml_url:
        st.error("Invalid My Maps URL")
        return None
    map_id = kml_url.split("mid=")[-1].split("&")[0]
    download_url = f"https://www.google.com/maps/d/kml?forcekml=1&mid={map_id}"
    response = requests.get(download_url)
    if response.status_code != 200:
        st.error("Failed to download KML")
        return None
    if b"<?xml" not in response.content:
        st.error("Not valid KML data")
        return None
    return response.content

def parse_kml(kml_data):
    layers = defaultdict(list)
    try:
        tree = ET.fromstring(kml_data)
        for doc in tree.iter("{http://www.opengis.net/kml/2.2}Document"):
            for folder in doc.findall("{http://www.opengis.net/kml/2.2}Folder"):
                name_elem = folder.find("{http://www.opengis.net/kml/2.2}name")
                if name_elem is None:
                    continue
                folder_name = name_elem.text
                for pm in folder.findall("{http://www.opengis.net/kml/2.2}Placemark"):
                    coords = pm.find(".//{http://www.opengis.net/kml/2.2}coordinates")
                    if coords is not None:
                        try:
                            lon, lat = map(float, coords.text.strip().split(",")[:2])
                            layers[folder_name].append((lat, lon))
                        except:
                            continue
    except ET.ParseError as e:
        st.error(f"XML Parse Error: {e}")
    return layers

# If URL is provided, download and parse KML
if url:
    kml = download_kml(url)
    if kml:
        layers = parse_kml(kml)
        st.success(f"Loaded {sum(len(p) for p in layers.values())} pins from map.")
    else:
        layers = {}
else:
    layers = {}

# Choose layers
selected_layers = st.multiselect("Select layers to export", list(layers.keys()), default=list(layers.keys()))

# Map + bounds detection
with st.container():
    m = folium.Map(location=[-25, 135], zoom_start=4, control_scale=True)
    for lname in selected_layers:
        for lat, lon in layers[lname]:
            folium.CircleMarker([lat, lon], radius=5, color="orange", fill=True).add_to(m)

    # Add draw control
    Draw(export=True).add_to(m)
    st_data = st_folium(m, width=700, height=500)

# Bounds info
if st_data and "bounds" in st_data and st_data["bounds"]:
    st.success(f"DEBUG: Map bounds received.
Raw bounds: {st_data['bounds']}")
else:
    st.warning("DEBUG: Incomplete map bounds detected. Try zooming or panning again.")

# Download stub
if st.button("Download SVG"):
    st.write("This will later trigger SVG generation...")
