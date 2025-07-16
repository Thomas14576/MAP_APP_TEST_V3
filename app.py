
import streamlit as st
import requests
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
import os

st.set_page_config(layout="wide")
st.title("Google My Maps to SVG Exporter")

url = st.text_input("Paste your Google My Maps URL")

def download_kml_or_kmz(kml_url):
    response = requests.get(kml_url)
    if response.status_code != 200:
        raise Exception("Failed to download file.")
    if response.headers['Content-Type'] == 'application/vnd.google-earth.kmz':
        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".kml"):
                    return zf.read(name)
        raise Exception("No KML file found in KMZ.")
    return response.content

def extract_layers_from_kml(kml_data):
    try:
        root = ET.fromstring(kml_data)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        folders = root.findall(".//kml:Folder", ns)
        layers = {}
        for folder in folders:
            name = folder.find("kml:name", ns).text
            layers[name] = []
        return layers
    except Exception as e:
        st.error(f"Failed to parse KML: {e}")
        return {}

if url:
    if "mid=" in url:
        try:
            map_id = url.split("mid=")[1].split("&")[0]
            kml_url = f"https://www.google.com/maps/d/kml?mid={map_id}"
            kml_data = download_kml_or_kmz(kml_url)
            layers = extract_layers_from_kml(kml_data)
            if layers:
                st.success(f"Loaded {len(layers)} layers.")
                for name in layers:
                    st.button(name)
            else:
                st.warning("No layers found in KML.")
        except Exception as e:
            st.error(str(e))
    else:
        st.warning("Invalid My Maps URL.")
