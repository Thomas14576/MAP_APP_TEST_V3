
import streamlit as st
import zipfile
import os
import shutil
import xml.etree.ElementTree as ET
from xml.dom.minidom import Document
import re
from io import BytesIO
import folium
from streamlit_folium import st_folium

# Setup
st.set_page_config(layout="wide")
st.title("Google My Maps to SVG Exporter")

# Clean up and prepare folders
shutil.rmtree("svg_layers", ignore_errors=True)
os.makedirs("svg_layers", exist_ok=True)

# Input Google My Maps URL
url = st.text_input("Paste your Google My Maps URL")

# Extract Map ID
map_id = None
if "mid=" in url:
    match = re.search(r'mid=([^&]+)', url)
    if match:
        map_id = match.group(1)
        kml_download_url = f"https://www.google.com/maps/d/kml?mid={map_id}"
        kmz_path = "downloaded.kmz"
        with open(kmz_path, "wb") as f:
            import requests
            f.write(requests.get(kml_download_url).content)

        # Extract KML
        kml_file = None
        with zipfile.ZipFile(kmz_path, 'r') as kmz:
            for name in kmz.namelist():
                if name.endswith(".kml"):
                    kmz.extract(name, path=".")
                    kml_file = name
                    break

        # Parse KML
        tree = ET.parse(kml_file)
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
                    coords.append((lon, lat))
                    all_coords.append((lon, lat))
            if coords:
                folder_coords[folder_name] = coords

        if folder_coords:
            # Full export toggle
            export_all = st.checkbox("Export all pins (ignore zoom)", value=False)

            # Setup folium map
            center_lat = sum([lat for _, lat in all_coords]) / len(all_coords)
            center_lon = sum([lon for lon, _ in all_coords]) / len(all_coords)
            fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5)

            for coords in all_coords:
                folium.CircleMarker(location=(coords[1], coords[0]), radius=3, color='red').add_to(fmap)

            map_data = st_folium(fmap, height=500, returned_objects=[])
            bounds = map_data.get("bounds", {})

            export_ready = False
            if export_all:
                export_bounds = None
                export_ready = True
            elif "_southWest" in bounds and "_northEast" in bounds:
                sw = bounds["_southWest"]
                ne = bounds["_northEast"]
                export_bounds = (sw["lng"], ne["lng"], sw["lat"], ne["lat"])
                export_ready = True
            else:
                st.warning("Incomplete map bounds detected. Try zooming or panning again.")
                export_ready = False

            st.markdown("---")
            st.subheader("Select layers and their colors")

            selected_folders = []
            folder_colors = {}
            predefined_colors = ["#FF5F2C", "#FF3119"]

            for folder in folder_coords:
                col1, col2 = st.columns([1, 2])
                with col1:
                    selected = st.checkbox(folder, value=True)
                with col2:
                    color_choice = st.selectbox(
                        f"Color for '{folder}'", predefined_colors + ["Custom HEX"], key=folder
                    )
                    if color_choice == "Custom HEX":
                        color_choice = st.text_input(f"Custom HEX for '{folder}'", "#000000", key=folder+"_custom")
                if selected:
                    selected_folders.append(folder)
                    folder_colors[folder] = color_choice

            if export_ready:
                width, height = 1000, 1000

                def normalize_coords(lon, lat, min_lon, max_lon, min_lat, max_lat):
                    x = (lon - min_lon) / (max_lon - min_lon) * width
                    y = height - (lat - min_lat) / (max_lat - min_lat) * height
                    return x, y

                # Determine bounds
                if export_all:
                    lons, lats = zip(*all_coords)
                    min_lon, max_lon = min(lons), max(lons)
                    min_lat, max_lat = min(lats), max(lats)
                else:
                    min_lon, max_lon, min_lat, max_lat = export_bounds

                for folder in selected_folders:
                    coords = folder_coords[folder]
                    if not export_all:
                        coords = [(lon, lat) for lon, lat in coords if (
                            min_lon <= lon <= max_lon and min_lat <= lat <= max_lat)]
                    norm_coords = [normalize_coords(lon, lat, min_lon, max_lon, min_lat, max_lat) for lon, lat in coords]

                    doc = Document()
                    svg = doc.createElement("svg")
                    svg.setAttribute("xmlns", "http://www.w3.org/2000/svg")
                    svg.setAttribute("width", str(width))
                    svg.setAttribute("height", str(height))
                    doc.appendChild(svg)

                    for x, y in norm_coords:
                        circle = doc.createElement("circle")
                        circle.setAttribute("cx", str(x))
                        circle.setAttribute("cy", str(y))
                        circle.setAttribute("r", "5")
                        circle.setAttribute("fill", folder_colors[folder])
                        svg.appendChild(circle)

                    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', folder)
                    filename = f"svg_layers/{safe_name}.svg"
                    with open(filename, "w") as f:
                        f.write(doc.toprettyxml())

                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for svg_file in os.listdir("svg_layers"):
                        path = os.path.join("svg_layers", svg_file)
                        zipf.write(path, svg_file)

                st.download_button("⬇️ Download SVG ZIP", data=zip_buf.getvalue(), file_name="svg_layers_export.zip", mime="application/zip")
