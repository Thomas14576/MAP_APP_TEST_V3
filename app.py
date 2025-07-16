import streamlit as st
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import base64

st.set_page_config(page_title="Google My Maps to SVG Exporter", layout="wide")
st.title("Google My Maps to SVG Exporter")

# Input field
user_input = st.text_input("Paste your Google My Maps URL")

# Function to extract KML URL
def extract_kml_url(viewer_url):
    match = re.search(r"mid=([^&]+)", viewer_url)
    if not match:
        return None
    map_id = match.group(1)
    return f"https://www.google.com/maps/d/kml?mid={map_id}"

# Function to download and unzip KMZ/KML
def fetch_kml(kml_url):
    response = requests.get(kml_url)
    if response.status_code != 200:
        return None, "Failed to fetch KML."
    if response.headers.get("Content-Type", "").startswith("application/vnd.google-earth.kmz"):
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".kml"):
                    return zf.read(name), None
        return None, "KMZ file found, but no KML inside."
    return response.content, None

# Function to extract folders and placemarks
def parse_kml(kml_data):
    try:
        root = ET.fromstring(kml_data)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        folders = root.findall(".//kml:Folder", ns)
        data = {}
        for folder in folders:
            name = folder.find("kml:name", ns).text
            placemarks = folder.findall("kml:Placemark", ns)
            data[name] = placemarks
        return data
    except Exception as e:
        return {}

# SVG exporter
def generate_svg(placemarks, color="#FF5F2C"):
    svg = minidom.Document()
    svg_el = svg.createElement("svg")
    svg_el.setAttribute("xmlns", "http://www.w3.org/2000/svg")
    svg_el.setAttribute("width", "800")
    svg_el.setAttribute("height", "600")
    svg.appendChild(svg_el)

    for pm in placemarks:
        name = pm.find("name").text if pm.find("name") is not None else "No Name"
        point = pm.find(".//Point/coordinates")
        if point is not None:
            coords = point.text.strip().split(",")
            x = float(coords[0]) % 800
            y = float(coords[1]) % 600
            circle = svg.createElement("circle")
            circle.setAttribute("cx", str(x))
            circle.setAttribute("cy", str(y))
            circle.setAttribute("r", "5")
            circle.setAttribute("fill", color)
            circle.setAttribute("title", name)
            svg_el.appendChild(circle)

    return svg.toprettyxml(indent="  ")

if user_input:
    kml_url = extract_kml_url(user_input)
    if kml_url:
        kml_data, err = fetch_kml(kml_url)
        if err:
            st.error(err)
        else:
            layers = parse_kml(kml_data)
            if not layers:
                st.error("No layers found or KML parsing failed.")
            else:
                selected = st.multiselect("Select layers to export", list(layers.keys()), default=list(layers.keys()))
                color = st.color_picker("Select pin color", "#FF5F2C")

                if st.button("Download SVG"):
                    svg_data = ""
                    for layer_name in selected:
                        svg_data += generate_svg(layers[layer_name], color=color)

                    b64 = base64.b64encode(svg_data.encode()).decode()
                    href = f'<a href="data:image/svg+xml;base64,{b64}" download="export.svg">Click to download SVG</a>'
                    st.markdown(href, unsafe_allow_html=True)
    else:
        st.error("Could not extract a valid map ID from the URL.")