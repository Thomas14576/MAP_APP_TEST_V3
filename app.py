
import streamlit as st
import zipfile
import os
import shutil
import xml.etree.ElementTree as ET
from xml.dom.minidom import Document
from io import BytesIO
import re
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("DEBUG MODE – Google My Maps to SVG Exporter (Interactive)")

shutil.rmtree("svg_layers", ignore_errors=True)
os.makedirs("svg_layers", exist_ok=True)

input_url = st.text_input("Paste your Google My Maps URL")

if input_url:
    match = re.search(r"mid=([^&]+)", input_url)
    if not match:
        st.error("Invalid URL: couldn't extract map ID.")
    else:
        map_id = match.group(1)
        kml_download_url = f"https://www.google.com/maps/d/kml?mid={map_id}"

        try:
            response = requests.get(kml_download_url)
            response.raise_for_status()
            kmz_filename = "downloaded_map.kmz"
            with open(kmz_filename, "wb") as f:
                f.write(response.content)
        except:
            st.error("Failed to download KMZ. Check if your map is public.")
            st.stop()

        kml_filename = None
        with zipfile.ZipFile(kmz_filename, 'r') as kmz:
            for name in kmz.namelist():
                if name.endswith('.kml'):
                    kml_filename = name
                    kmz.extract(name, path=".")
                    break

        if not kml_filename:
            st.error("No KML file found in KMZ.")
            st.stop()

        tree = ET.parse(kml_filename)
        root = tree.getroot()
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}

        folders = root.findall('.//kml:Folder', ns)
        all_coords = []
        folder_coords = {}

        for folder in folders:
            folder_name_elem = folder.find('kml:name', ns)
            folder_name = folder_name_elem.text.strip() if folder_name_elem is not None else 'Unnamed'
            coords = []

            for placemark in folder.findall('.//kml:Placemark', ns):
                for point in placemark.findall('.//kml:Point', ns):
                    coord_text = point.find('.//kml:coordinates', ns).text.strip()
                    lon, lat, *_ = map(float, coord_text.split(','))
                    coords.append((lat, lon))
                    all_coords.append((lat, lon))

            if coords:
                folder_coords[folder_name] = coords

        if not all_coords:
            st.error("No coordinates found in KML.")
            st.stop()

        selected_folders = st.multiselect("Select folders to display/export", options=list(folder_coords.keys()), default=list(folder_coords.keys()))

        avg_lat = sum(lat for lat, _ in all_coords) / len(all_coords)
        avg_lon = sum(lon for _, lon in all_coords) / len(all_coords)
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=5)

        for folder_name in selected_folders:
            for lat, lon in folder_coords[folder_name]:
                folium.CircleMarker(location=(lat, lon), radius=5, color='red', fill=True, fill_opacity=0.8).add_to(m)

        map_data = st_folium(m, width=700, height=500)

        # --- DEBUG OUTPUT ---
        if map_data:
            if "bounds" not in map_data or not map_data["bounds"]:
                st.warning("DEBUG: No map bounds returned yet.")
            else:
                bounds = map_data["bounds"]
                st.success("DEBUG: Map bounds received.")
                st.text(f"Raw bounds: {bounds}")
        else:
            st.warning("DEBUG: No map_data received at all.")
