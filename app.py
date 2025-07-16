
# Streamlit App: KML Viewer with Folium Interactive Map and SVG Export (Final with Silent Debug)

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
st.title("Google My Maps to SVG Exporter (Interactive)")

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

        debug_log = {}

        if not map_data.get("bounds"):
            st.info("Zoom or move the map to activate export.")
            debug_log["map_bounds"] = "missing"
        else:
            bounds = map_data["bounds"]
            if not all(k in bounds for k in ("north", "south", "east", "west")):
                st.warning("Incomplete map bounds detected. Try zooming or panning again.")
                debug_log["map_bounds"] = bounds
            else:
                north, south = bounds["north"], bounds["south"]
                east, west = bounds["east"], bounds["west"]
                debug_log["map_bounds"] = bounds

                def normalize_coords(lon, lat, width=1000, height=1000):
                    x = (lon - west) / (east - west) * width
                    y = height - (lat - south) / (north - south) * height
                    return x, y

                has_visible_data = False

                for folder_name in selected_folders:
                    coords = folder_coords[folder_name]
                    visible_coords = [(lat, lon) for lat, lon in coords if south < lat < north and west < lon < east]
                    if not visible_coords:
                        continue
                    has_visible_data = True
                    norm_coords = [normalize_coords(lon, lat) for lat, lon in visible_coords]

                    doc = Document()
                    svg = doc.createElement('svg')
                    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
                    svg.setAttribute('width', '1000')
                    svg.setAttribute('height', '1000')
                    doc.appendChild(svg)

                    for x, y in norm_coords:
                        circle = doc.createElement('circle')
                        circle.setAttribute('cx', str(x))
                        circle.setAttribute('cy', str(y))
                        circle.setAttribute('r', '5')
                        circle.setAttribute('fill', 'red')
                        svg.appendChild(circle)

                    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', folder_name)
                    filename = f"svg_layers/{safe_name}.svg"
                    with open(filename, "w") as f:
                        f.write(doc.toprettyxml())

                if has_visible_data:
                    zip_buf = BytesIO()
                    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for svg_file in os.listdir("svg_layers"):
                            path = os.path.join("svg_layers", svg_file)
                            zipf.write(path, svg_file)

                    st.markdown("### Download Export")
                    st.download_button(
                        label="Download SVG ZIP",
                        data=zip_buf.getvalue(),
                        file_name="svg_layers_export.zip",
                        mime="application/zip"
                    )
                else:
                    st.warning("No visible points in the current map view. Zoom or pan to include data.")
