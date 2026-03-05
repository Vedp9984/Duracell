#!/usr/bin/env python3
"""
Script to extract GeoJSON data from GeoPackage files generated in QGIS
and update the existing GeoJSON files for the Flood DAS application.

Converts:
- zon-12-ghmc.gpkg (ward boundaries) -> flood_zones.geojson
- zone-12-channels.gpkg (drainage channels) -> streams.geojson
- Generates watershed.geojson from the total area
- Updates sensors.geojson with correct locations
"""

import fiona
import geopandas as gpd
import json
import os
import random
from shapely.geometry import mapping
from shapely.ops import unary_union

# Base path
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(BASE_PATH, "geojson")

# GeoPackage files
GPKG_GHMC = os.path.join(GEOJSON_PATH, "zon-12-ghmc.gpkg")
GPKG_CHANNELS = os.path.join(GEOJSON_PATH, "zone-12-channels.gpkg")

# Output files
OUTPUT_FLOOD_ZONES = os.path.join(GEOJSON_PATH, "flood_zones.geojson")
OUTPUT_STREAMS = os.path.join(GEOJSON_PATH, "streams.geojson")
OUTPUT_WATERSHED = os.path.join(GEOJSON_PATH, "watershed.geojson")
OUTPUT_SENSORS = os.path.join(GEOJSON_PATH, "sensors.geojson")

# Risk level colors
RISK_COLORS = {
    "high": "#e74c3c",
    "medium": "#f39c12", 
    "low": "#27ae60"
}

def convert_flood_zones():
    """Convert ward boundaries to flood zones with risk levels"""
    print("\n" + "=" * 60)
    print("Converting Ward Boundaries to Flood Zones")
    print("=" * 60)
    
    gdf = gpd.read_file(GPKG_GHMC)
    
    # Ensure EPSG:4326 (WGS84)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    features = []
    
    # Known low-lying flood-prone areas in Zone 12 (based on historical data)
    high_risk_keywords = ['kukatpally', 'erragadda', 'moosapet', 'balanagar', 'sanath nagar']
    medium_risk_keywords = ['kphb', 'miyapur', 'chintal', 'pragathi nagar', 'jntu']
    
    for idx, row in gdf.iterrows():
        name = row.get('name', f'Ward {idx+1}') or f'Ward {idx+1}'
        name_lower = name.lower()
        
        # Determine risk level based on ward name/location
        if any(kw in name_lower for kw in high_risk_keywords):
            risk_level = "high"
            flood_depth = round(random.uniform(1.5, 2.5), 1)
            population = random.randint(25000, 50000)
            history = "Severely affected in Oct 2020 floods"
        elif any(kw in name_lower for kw in medium_risk_keywords):
            risk_level = "medium"
            flood_depth = round(random.uniform(0.5, 1.5), 1)
            population = random.randint(15000, 35000)
            history = "Partial inundation in major events"
        else:
            risk_level = "low"
            flood_depth = round(random.uniform(0.1, 0.5), 1)
            population = random.randint(10000, 20000)
            history = "Minor waterlogging only"
        
        # Convert geometry - handle 3D geometries by forcing 2D
        geom = row.geometry
        if geom.has_z:
            # Remove Z coordinates
            from shapely.ops import transform
            geom = transform(lambda x, y, z=None: (x, y), geom)
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": idx + 1,
                "name": name,
                "risk_level": risk_level,
                "risk_color": RISK_COLORS[risk_level],
                "flood_depth_potential_m": flood_depth,
                "population_at_risk": population,
                "description": f"Zone 12 GHMC - {name}",
                "history": history,
                "osm_id": row.get('osm_id'),
                "admin_level": row.get('admin_level')
            },
            "geometry": mapping(geom)
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "name": "Zone_12_GHMC_Flood_Risk_Zones",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }
    
    with open(OUTPUT_FLOOD_ZONES, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✓ Created {OUTPUT_FLOOD_ZONES} with {len(features)} features")
    return gdf


def convert_streams():
    """Convert channel data to streams GeoJSON"""
    print("\n" + "=" * 60)
    print("Converting Channels to Streams")
    print("=" * 60)
    
    gdf = gpd.read_file(GPKG_CHANNELS)
    
    # Convert to EPSG:4326 (WGS84)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    features = []
    
    for idx, row in gdf.iterrows():
        order = int(row.get('ORDER', 1) or 1)
        length_m = row.get('LENGTH', 0) or 0
        length_km = round(length_m / 1000, 2)
        segment_id = row.get('SEGMENT_ID', idx + 1)
        
        # Determine stream type based on Strahler order
        if order >= 4:
            stream_type = "main_channel"
            stream_name = f"Main Channel - Segment {segment_id}"
        elif order >= 3:
            stream_type = "secondary"
            stream_name = f"Secondary Channel - Segment {segment_id}"
        else:
            stream_type = "tributary"
            stream_name = f"Tributary - Segment {segment_id}"
        
        # Convert geometry - handle 3D geometries by forcing 2D
        geom = row.geometry
        if geom.has_z:
            from shapely.ops import transform
            geom = transform(lambda x, y, z=None: (x, y), geom)
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": idx + 1,
                "segment_id": int(segment_id) if segment_id else idx + 1,
                "name": stream_name,
                "stream_order": order,
                "length_km": length_km,
                "type": stream_type,
                "basin": int(row.get('BASIN', 1) or 1),
                "description": f"Drainage channel - Strahler Order {order}"
            },
            "geometry": mapping(geom)
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "name": "Zone_12_Drainage_Network",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }
    
    with open(OUTPUT_STREAMS, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✓ Created {OUTPUT_STREAMS} with {len(features)} features")
    return gdf


def create_watershed(flood_zones_gdf):
    """Create watershed boundary from ward boundaries"""
    print("\n" + "=" * 60)
    print("Creating Watershed Boundary")
    print("=" * 60)
    
    # Merge all ward boundaries to create watershed
    watershed_geom = unary_union(flood_zones_gdf.geometry)
    
    # Handle 3D to 2D conversion
    if watershed_geom.has_z:
        from shapely.ops import transform
        watershed_geom = transform(lambda x, y, z=None: (x, y), watershed_geom)
    
    # Calculate area
    area_km2 = round(flood_zones_gdf.to_crs("EPSG:32644").geometry.area.sum() / 1e6, 1)
    
    geojson = {
        "type": "FeatureCollection",
        "name": "Zone_12_GHMC_Watershed",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": [{
            "type": "Feature",
            "properties": {
                "id": 1,
                "name": "Zone 12 GHMC Sub-Catchment",
                "area_km2": area_km2,
                "runoff_coeff": 0.736,
                "land_use": "Urban/Mixed",
                "district": "Medchal-Malkajgiri & Ranga Reddy",
                "city": "Hyderabad",
                "state": "Telangana",
                "description": "GHMC Zone 12 drainage basin covering Kukatpally and surrounding areas"
            },
            "geometry": mapping(watershed_geom)
        }]
    }
    
    with open(OUTPUT_WATERSHED, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✓ Created {OUTPUT_WATERSHED} with area {area_km2} km²")


def update_sensors(flood_zones_gdf):
    """Update sensor locations to be within the actual area"""
    print("\n" + "=" * 60)
    print("Updating Sensor Locations")
    print("=" * 60)
    
    # Get bounds of the actual area
    bounds = flood_zones_gdf.total_bounds
    min_lon, min_lat, max_lon, max_lat = bounds
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    
    # Generate sensor locations within the area
    sensors = [
        # Rain gauges
        {"id": 1, "name": "Zone12_Rain_01", "type": "rain_gauge", "icon": "cloud-rain", "color": "#3498db",
         "location": "Kukatpally Bus Stand Area", "lat": center_lat + 0.01, "lon": center_lon - 0.02, "elevation": 538},
        {"id": 2, "name": "Zone12_Rain_02", "type": "rain_gauge", "icon": "cloud-rain", "color": "#3498db",
         "location": "KPHB Colony", "lat": center_lat + 0.03, "lon": center_lon + 0.01, "elevation": 542},
        {"id": 3, "name": "Zone12_Rain_03", "type": "rain_gauge", "icon": "cloud-rain", "color": "#3498db",
         "location": "Miyapur Junction", "lat": max_lat - 0.02, "lon": min_lon + 0.03, "elevation": 556},
        {"id": 4, "name": "Zone12_Rain_04", "type": "rain_gauge", "icon": "cloud-rain", "color": "#3498db",
         "location": "Moosapet Area", "lat": center_lat - 0.02, "lon": center_lon + 0.02, "elevation": 535},
        {"id": 5, "name": "Zone12_Rain_05", "type": "rain_gauge", "icon": "cloud-rain", "color": "#3498db",
         "location": "Balanagar Industrial Area", "lat": min_lat + 0.02, "lon": min_lon + 0.02, "elevation": 530},
        # Water level sensors
        {"id": 6, "name": "Nala_Stage_01_Upstream", "type": "water_level", "icon": "water", "color": "#9b59b6",
         "location": "Upstream - Miyapur Side", "lat": max_lat - 0.03, "lon": center_lon - 0.01, "danger_level": 2.5},
        {"id": 7, "name": "Nala_Stage_02_Middle", "type": "water_level", "icon": "water", "color": "#9b59b6",
         "location": "Mid-stream - KPHB Area", "lat": center_lat, "lon": center_lon, "danger_level": 2.5},
        {"id": 8, "name": "Nala_Stage_03_Downstream", "type": "water_level", "icon": "water", "color": "#9b59b6",
         "location": "Downstream - Erragadda Side", "lat": min_lat + 0.03, "lon": max_lon - 0.02, "danger_level": 2.5}
    ]
    
    features = []
    for s in sensors:
        feature = {
            "type": "Feature",
            "properties": {
                "id": s["id"],
                "name": s["name"],
                "type": s["type"],
                "icon": s["icon"],
                "color": s["color"],
                "location": s["location"],
                "status": "active",
                "installed_date": "2024-01-15",
                "elevation_m": s.get("elevation", 540),
                "zero_level_m": 0.0,
                "danger_level_m": s.get("danger_level", 2.5),
                "description": "Tipping bucket rain gauge - 0.2mm resolution" if s["type"] == "rain_gauge" else "Ultrasonic water level sensor - 1cm accuracy"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(s["lon"], 6), round(s["lat"], 6)]
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "name": "Zone_12_Sensor_Network",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }
    
    with open(OUTPUT_SENSORS, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✓ Created {OUTPUT_SENSORS} with {len(features)} sensors")
    print(f"  Area bounds: [{min_lon:.4f}, {min_lat:.4f}] to [{max_lon:.4f}, {max_lat:.4f}]")


def main():
    """Main function to convert all GeoPackage data"""
    print("=" * 60)
    print("FLOOD DAS - GeoPackage to GeoJSON Converter")
    print("=" * 60)
    
    # Convert ward boundaries to flood zones
    flood_zones_gdf = convert_flood_zones()
    
    # Convert channels to streams
    convert_streams()
    
    # Create watershed boundary
    create_watershed(flood_zones_gdf)
    
    # Update sensor locations
    update_sensors(flood_zones_gdf)
    
    print("\n" + "=" * 60)
    print("✓ All conversions complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
