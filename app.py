
import streamlit as st
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from io import BytesIO
import zipfile
import base64

st.set_page_config(layout="wide")
st.title("Google My Maps to SVG Exporter")

# Step 1: Enter KML URL
kml_url = st.text_input("Paste your Google My Maps URL", "")

def extract_kml_url(url):
    import re
    match = re.search(r'mid=([^&]+)', url)
    if not match:
        return None
    mid = match.group(1)
    return f"https://www.google.com/maps/d/kml?mid={mid}"

def download_kml(kml_link):
    try:
        resp = requests.get(kml_link)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        st.error(f"Error downloading KML: {e}")
    return None

def parse_kml(kml_data):
    try:
        root = ET.fromstring(kml_data)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        folders = root.findall(".//kml:Folder", ns)
        layers = {}
        for folder in folders:
            name_elem = folder.find("kml:name", ns)
            name = name_elem.text if name_elem is not None else "Unnamed Folder"
            placemarks = folder.findall(".//kml:Placemark", ns)
            points = []
            for placemark in placemarks:
                coords = placemark.find(".//kml:coordinates", ns)
                if coords is not None:
                    coord_text = coords.text.strip().split(",")
                    if len(coord_text) >= 2:
                        lng, lat = coord_text[:2]
                        points.append((lat, lng))
            if points:
                layers[name] = points
        return layers
    except Exception as e:
        st.error(f"Error parsing KML: {e}")
        return {}

# Step 2: Process the KML
if kml_url:
    kml_download_url = extract_kml_url(kml_url)
    if not kml_download_url:
        st.error("Invalid Google My Maps URL.")
    else:
        kml_data = download_kml(kml_download_url)
        if kml_data:
            layers_data = parse_kml(kml_data)
            st.success(f"Loaded {sum(len(p) for p in layers_data.values())} pins from map.")

            # Step 3: Layer Controls
            st.subheader("Select layers and their colors")
            selected_layers = []
            layer_colors = {}
            default_colors = ['#FF5F2C', '#FF3119']
            color_input = {}

            for i, (layer, pins) in enumerate(layers_data.items()):
                col1, col2 = st.columns([1, 2])
                with col1:
                    if st.toggle(layer, value=True, key=layer):
                        selected_layers.append(layer)
                with col2:
                    default = default_colors[i % len(default_colors)]
                    layer_colors[layer] = st.text_input(f"Color for {layer}", value=default)

            # Step 4: Generate SVG
            def create_svg(layers, bounds=None):
                doc = minidom.Document()
                svg = doc.createElement('svg')
                svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
                svg.setAttribute('width', '1000')
                svg.setAttribute('height', '1000')
                doc.appendChild(svg)

                for layer, coords in layers.items():
                    color = layer_colors.get(layer, '#FF0000')
                    for lat, lng in coords:
                        cx = str(500 + (float(lng) % 360 - 180) * 2)
                        cy = str(500 - (float(lat) % 180 - 90) * 2)
                        circle = doc.createElement('circle')
                        circle.setAttribute('cx', cx)
                        circle.setAttribute('cy', cy)
                        circle.setAttribute('r', '4')
                        circle.setAttribute('fill', color)
                        svg.appendChild(circle)

                return doc.toprettyxml(indent="  ")

            if st.button("Download SVG"):
                filtered_layers = {k: v for k, v in layers_data.items() if k in selected_layers}
                svg_code = create_svg(filtered_layers)
                b = BytesIO()
                b.write(svg_code.encode())
                b.seek(0)
                st.download_button("Download SVG", data=b, file_name="export.svg", mime="image/svg+xml")
