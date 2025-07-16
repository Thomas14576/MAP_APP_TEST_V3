import streamlit as st
import requests
import xml.etree.ElementTree as ET
from xml.dom.minidom import Document
import re
import os
import zipfile
from io import BytesIO
import pandas as pd

st.set_page_config(layout="wide")
st.title("Interactive Google My Maps Pin Exporter")

# Input section
url = st.text_input("Paste your Google My Maps URL (must include 'mid=')")

def get_kml_url(maps_url):
    match = re.search(r'mid=([^&]+)', maps_url)
    return f"https://www.google.com/maps/d/kml?mid={match.group(1)}" if match else None

def download_kml(kml_url):
    response = requests.get(kml_url)
    if response.status_code == 200:
        return response.content
    return None

def parse_kml(kml_data):
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    root = ET.fromstring(kml_data)
    folders = root.findall(".//kml:Folder", ns)
    folder_coords = {}
    all_coords = []
    for folder in folders:
        name_elem = folder.find("kml:name", ns)
        name = name_elem.text.strip() if name_elem is not None else "Unnamed Layer"
        placemarks = folder.findall(".//kml:Placemark", ns)
        coords = []
        for placemark in placemarks:
            coord_elem = placemark.find(".//kml:coordinates", ns)
            if coord_elem is not None:
                lon, lat, *_ = map(float, coord_elem.text.strip().split(","))
                coords.append((lon, lat))
                all_coords.append((lon, lat))
        if coords:
            folder_coords[name] = coords
    return folder_coords, all_coords

def normalize_coords(lon, lat, bounds, width=1000, height=1000):
    min_lon, max_lon, min_lat, max_lat = bounds
    x = (lon - min_lon) / (max_lon - min_lon) * width
    y = height - (lat - min_lat) / (max_lat - min_lat) * height
    return x, y

if url:
    kml_url = get_kml_url(url)
    if kml_url:
        kml_data = download_kml(kml_url)
        if kml_data:
            try:
                folder_coords, all_coords = parse_kml(kml_data)
                if not folder_coords:
                    st.warning("No placemarks found in the KML.")
                else:
                    st.success(f"Found {sum(len(v) for v in folder_coords.values())} pins across {len(folder_coords)} layers.")

                    # Bounds for SVG scaling
                    lons, lats = zip(*all_coords)
                    bounds = (min(lons), max(lons), min(lats), max(lats))

                    # Layer toggles and color pickers
                    st.subheader("Layer Controls")
                    selected_layers = []
                    layer_colors = {}
                    presets = ['#FF5F2C', '#FF3119']
                    for i, (layer, coords) in enumerate(folder_coords.items()):
                        col1, col2 = st.columns([2, 2])
                        with col1:
                            if st.toggle(layer, key=layer):
                                selected_layers.append(layer)
                        with col2:
                            default_color = presets[i % len(presets)]
                            custom = st.selectbox(
                                f"Color for {layer}",
                                options=["#FF5F2C", "#FF3119", "Custom"],
                                key=f"color_select_{layer}"
                            )
                            color = default_color if custom != "Custom" else st.text_input(f"Custom hex for {layer}", value=default_color, key=f"custom_hex_{layer}")
                            layer_colors[layer] = color

                    export_all = st.checkbox("Export all pins (ignore zoom)")

                    # SVG + CSV generation
                    svg_output = {}
                    csv_rows = []
                    for layer in selected_layers:
                        coords = folder_coords[layer]
                        svg_doc = Document()
                        svg = svg_doc.createElement('svg')
                        svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
                        svg.setAttribute('width', '1000')
                        svg.setAttribute('height', '1000')
                        svg_doc.appendChild(svg)

                        for lon, lat in coords:
                            x, y = normalize_coords(lon, lat, bounds)
                            circle = svg_doc.createElement('circle')
                            circle.setAttribute('cx', str(x))
                            circle.setAttribute('cy', str(y))
                            circle.setAttribute('r', '5')
                            circle.setAttribute('fill', layer_colors[layer])
                            svg.appendChild(circle)
                            csv_rows.append({"layer": layer, "lat": lat, "lon": lon})

                        svg_output[layer] = svg_doc.toprettyxml()

                    # ZIP everything
                    mem_zip = BytesIO()
                    with zipfile.ZipFile(mem_zip, 'w') as zf:
                        for name, svg_data in svg_output.items():
                            zf.writestr(f"{name}.svg", svg_data)
                        df = pd.DataFrame(csv_rows)
                        zf.writestr("all_pins.csv", df.to_csv(index=False))

                    st.download_button(
                        label="Download SVG + All Pins ZIP",
                        data=mem_zip.getvalue(),
                        file_name="exported_layers.zip",
                        mime="application/zip"
                    )
            except Exception as e:
                st.error(f"Failed to parse KML: {e}")
        else:
            st.error("Failed to download KML file.")
    else:
        st.warning("Invalid URL format. Please ensure it contains 'mid='.")