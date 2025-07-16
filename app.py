
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import zipfile
import re
from xml.dom.minidom import Document
from io import BytesIO
import os

st.set_page_config(layout="wide")
st.title("Google My Maps SVG Export Tool")

# UI Inputs
with st.form("link_form"):
    map_url = st.text_input("Paste your Google My Maps URL")
    export_all = st.checkbox("Export all pins (ignore zoom)")
    submitted = st.form_submit_button("Load Map")

# Layer state storage
if "selected_layers" not in st.session_state:
    st.session_state.selected_layers = set()
if "layer_colors" not in st.session_state:
    st.session_state.layer_colors = {}

PRESET_COLORS = {
    "FF5F2C": "#FF5F2C",
    "FF3119": "#FF3119",
}

def parse_kml_from_kmz(data):
    with zipfile.ZipFile(BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.endswith(".kml"):
                return zf.read(name)
    raise Exception("No .kml file found in KMZ.")

def download_kml(url):
    match = re.search(r"mid=([^&]+)", url)
    if not match:
        raise ValueError("Invalid URL: Could not find 'mid='.")
    map_id = match.group(1)
    kml_url = f"https://www.google.com/maps/d/kml?mid={map_id}"
    r = requests.get(kml_url)
    if "html" in r.headers.get("Content-Type", ""):
        raise Exception("Google returned HTML instead of KML/KMZ. Is your map set to public?")
    return r.content

def parse_kml(kml_bytes):
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    root = ET.fromstring(kml_bytes)
    folders = root.findall(".//kml:Folder", ns)
    all_coords = []
    folder_coords = {}

    for folder in folders:
        name = folder.find("kml:name", ns).text if folder.find("kml:name", ns) is not None else "Unnamed"
        placemarks = folder.findall(".//kml:Placemark", ns)
        coords = []
        for pm in placemarks:
            point = pm.find(".//kml:Point", ns)
            if point is not None:
                coord_text = point.find(".//kml:coordinates", ns).text.strip()
                lon, lat, *_ = map(float, coord_text.split(","))
                coords.append((lon, lat))
                all_coords.append((lon, lat))
        if coords:
            folder_coords[name] = coords

    return folder_coords, all_coords

def normalize_coords(lon, lat, min_lon, max_lon, min_lat, max_lat, width=1000, height=1000):
    x = (lon - min_lon) / (max_lon - min_lon) * width
    y = height - (lat - min_lat) / (max_lat - min_lat) * height
    return x, height - y

if submitted:
    try:
        kml_data = download_kml(map_url)
        if kml_data[:2] == b"PK":
            kml_data = parse_kml_from_kmz(kml_data)
        folder_coords, all_coords = parse_kml(kml_data)

        if not all_coords:
            st.warning("No coordinates found in the map.")
        else:
            lons, lats = zip(*all_coords)
            min_lon, max_lon = min(lons), max(lons)
            min_lat, max_lat = min(lats), max(lats)

            st.subheader("Layer Controls")
            for folder in folder_coords:
                col1, col2 = st.columns([1, 2])
                with col1:
                    toggled = st.toggle(folder, value=True)
                with col2:
                    color = st.selectbox(
                        f"Color for {folder}",
                        options=list(PRESET_COLORS.values()) + ["Custom"],
                        key=f"color_{folder}",
                    )
                    if color == "Custom":
                        color = st.text_input(f"Custom HEX for {folder}", "#000000", key=f"custom_{folder}")
                if toggled:
                    st.session_state.selected_layers.add(folder)
                else:
                    st.session_state.selected_layers.discard(folder)
                st.session_state.layer_colors[folder] = color

            # --- SVG Export ---
            st.subheader("Download")
            output = BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipf:
                for folder, coords in folder_coords.items():
                    if folder not in st.session_state.selected_layers:
                        continue
                    doc = Document()
                    svg = doc.createElement("svg")
                    svg.setAttribute("xmlns", "http://www.w3.org/2000/svg")
                    svg.setAttribute("width", "1000")
                    svg.setAttribute("height", "1000")
                    doc.appendChild(svg)
                    for lon, lat in coords if export_all else [(lon, lat) for lon, lat in coords if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat]:
                        x, y = normalize_coords(lon, lat, min_lon, max_lon, min_lat, max_lat)
                        circle = doc.createElement("circle")
                        circle.setAttribute("cx", str(x))
                        circle.setAttribute("cy", str(y))
                        circle.setAttribute("r", "5")
                        circle.setAttribute("fill", st.session_state.layer_colors.get(folder, "#FF3119"))
                        svg.appendChild(circle)
                    svg_filename = re.sub(r"[^a-zA-Z0-9]", "_", folder) + ".svg"
                    zipf.writestr(svg_filename, doc.toprettyxml())

            st.download_button("Download All SVGs", output.getvalue(), file_name="map_layers_export.zip", mime="application/zip")

    except Exception as e:
        st.error(str(e))
