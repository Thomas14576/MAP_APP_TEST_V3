import streamlit as st
import requests
import xml.etree.ElementTree as ET
import zipfile
import os
import shutil
from io import BytesIO
import folium
from streamlit_folium import st_folium
import uuid

st.set_page_config(layout="wide")
st.title("Google My Maps to SVG Exporter")

# Get user URL
map_url = st.text_input("Paste your Google My Maps URL", "")

def extract_mid(url):
    import re
    match = re.search(r"mid=([^&]+)", url)
    return match.group(1) if match else None

@st.cache_data(show_spinner=False)
def fetch_kml(mid):
    kml_url = f"https://www.google.com/maps/d/kml?mid={mid}&forcekml=1"
    response = requests.get(kml_url)
    if response.status_code != 200:
        st.error("Failed to fetch KML. Check if your map is set to 'Anyone with the link can view'.")
        return None
    return response.content

def parse_kml(kml_data):
    tree = ET.ElementTree(ET.fromstring(kml_data))
    root = tree.getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    placemarks = root.findall(".//kml:Placemark", ns)
    points = []
    for pm in placemarks:
        name = pm.find("kml:name", ns)
        point = pm.find(".//kml:Point/kml:coordinates", ns)
        if point is not None:
            coords = point.text.strip().split(",")
            points.append({
                "name": name.text if name is not None else "Unnamed",
                "lon": float(coords[0]),
                "lat": float(coords[1])
            })
    return points

if map_url:
    mid = extract_mid(map_url)
    if mid:
        kml_data = fetch_kml(mid)
        if kml_data:
            pins = parse_kml(kml_data)
            if pins:
                st.success(f"Loaded {len(pins)} pins from map.")
                avg_lat = sum(p['lat'] for p in pins) / len(pins)
                avg_lon = sum(p['lon'] for p in pins) / len(pins)
                m = folium.Map(location=[avg_lat, avg_lon], zoom_start=5)
                for p in pins:
                    folium.CircleMarker(location=(p["lat"], p["lon"]), radius=6, fill=True, color="#FF5F2C", popup=p["name"]).add_to(m)
                st_folium(m, height=500, width=1000)
            else:
                st.warning("No pins found in KML.")
        else:
            st.warning("Could not download KML file.")
    else:
        st.warning("Could not extract map ID from the URL.")
else:
    st.info("Paste a Google My Maps shareable URL above.")