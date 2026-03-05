#!/usr/bin/env python3
"""
Create QGIS-like layer structure for Flood DAS
===============================================
Extracts and organizes GIS data into logical layers similar to QGIS project structure.

Layer Groups:
1. Base Layers
   - Ward Boundaries (Administrative)
   - Watershed Boundary
   
2. Hydrology Layers
   - Drainage Channels Order 4 (Main)
   - Drainage Channels Order 3 (Secondary)
   - Drainage Channels Order 2 (Tertiary)
   - Drainage Channels Order 1 (Minor)
   
3. Risk Assessment Layers
   - High Risk Zones
   - Medium Risk Zones
   - Low Risk Zones
   
4. Infrastructure Layers
   - Rain Gauges
   - Water Level Sensors
"""

import geopandas as gpd
import json
import os
from shapely.geometry import mapping
from shapely.ops import unary_union, transform

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(BASE_PATH, "geojson")
LAYERS_PATH = os.path.join(GEOJSON_PATH, "layers")

# Create layers directory
os.makedirs(LAYERS_PATH, exist_ok=True)

# GeoPackage files
GPKG_GHMC = os.path.join(GEOJSON_PATH, "zon-12-ghmc.gpkg")
GPKG_CHANNELS = os.path.join(GEOJSON_PATH, "zone-12-channels.gpkg")


def remove_z(geom):
    """Remove Z coordinate from geometry"""
    if geom.has_z:
        return transform(lambda x, y, z=None: (x, y), geom)
    return geom


def create_geojson(features, name, description=""):
    """Create a GeoJSON FeatureCollection"""
    return {
        "type": "FeatureCollection",
        "name": name,
        "description": description,
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }


def save_geojson(data, filename):
    """Save GeoJSON to file"""
    filepath = os.path.join(LAYERS_PATH, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ Saved {filename} ({len(data['features'])} features)")
    return filepath


def create_ward_boundaries():
    """Create ward boundaries layer"""
    print("\n📍 Creating Ward Boundaries Layer...")
    gdf = gpd.read_file(GPKG_GHMC)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    features = []
    for idx, row in gdf.iterrows():
        name = row.get('name', f'Ward {idx+1}') or f'Ward {idx+1}'
        geom = remove_z(row.geometry)
        
        features.append({
            "type": "Feature",
            "properties": {
                "id": idx + 1,
                "name": name,
                "osm_id": row.get('osm_id'),
                "admin_level": row.get('admin_level', '10'),
                "layer_type": "ward_boundary"
            },
            "geometry": mapping(geom)
        })
    
    geojson = create_geojson(features, "Ward_Boundaries", "GHMC Zone 12 Ward Administrative Boundaries")
    save_geojson(geojson, "ward_boundaries.geojson")
    return gdf


def create_watershed_boundary(ward_gdf):
    """Create watershed boundary from merged wards"""
    print("\n🌊 Creating Watershed Boundary Layer...")
    
    watershed_geom = unary_union(ward_gdf.geometry)
    watershed_geom = remove_z(watershed_geom)
    
    # Calculate area
    area_km2 = round(ward_gdf.to_crs("EPSG:32644").geometry.area.sum() / 1e6, 1)
    
    features = [{
        "type": "Feature",
        "properties": {
            "id": 1,
            "name": "GHMC Zone 12 Watershed",
            "area_km2": area_km2,
            "runoff_coeff": 0.736,
            "land_use": "Urban/Mixed",
            "layer_type": "watershed"
        },
        "geometry": mapping(watershed_geom)
    }]
    
    geojson = create_geojson(features, "Watershed_Boundary", f"Total catchment area: {area_km2} km²")
    save_geojson(geojson, "watershed_boundary.geojson")
    return area_km2


def create_drainage_channels():
    """Create separate layers for each Strahler order"""
    print("\n🔵 Creating Drainage Channel Layers...")
    
    gdf = gpd.read_file(GPKG_CHANNELS)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    # Style configuration for each order (QGIS-like)
    order_config = {
        4: {"name": "Main Channels", "color": "#0066cc", "weight": 5, "description": "Primary drainage - Strahler Order 4"},
        3: {"name": "Secondary Channels", "color": "#3399ff", "weight": 3.5, "description": "Secondary drainage - Strahler Order 3"},
        2: {"name": "Tertiary Channels", "color": "#66b3ff", "weight": 2.5, "description": "Tertiary drainage - Strahler Order 2"},
        1: {"name": "Minor Channels", "color": "#99ccff", "weight": 1.5, "description": "Minor tributaries - Strahler Order 1"}
    }
    
    for order in sorted(gdf['ORDER'].unique(), reverse=True):
        order = int(order)
        config = order_config.get(order, {"name": f"Order {order}", "color": "#aaddff", "weight": 1})
        
        order_gdf = gdf[gdf['ORDER'] == order]
        features = []
        
        for idx, row in order_gdf.iterrows():
            geom = remove_z(row.geometry)
            length_km = round((row.get('LENGTH', 0) or 0) / 1000, 3)
            
            features.append({
                "type": "Feature",
                "properties": {
                    "id": int(row.get('SEGMENT_ID', idx)),
                    "name": f"{config['name']} - Segment {row.get('SEGMENT_ID', idx)}",
                    "strahler_order": order,
                    "length_km": length_km,
                    "basin": int(row.get('BASIN', 1) or 1),
                    "style_color": config['color'],
                    "style_weight": config['weight'],
                    "layer_type": "drainage_channel"
                },
                "geometry": mapping(geom)
            })
        
        geojson = create_geojson(features, f"Drainage_Order_{order}", config['description'])
        save_geojson(geojson, f"drainage_order_{order}.geojson")


def create_flood_risk_zones(ward_gdf):
    """Create separate layers for each risk level"""
    print("\n⚠️ Creating Flood Risk Zone Layers...")
    
    # Known flood-prone areas
    high_risk_keywords = ['kukatpally', 'erragadda', 'moosapet', 'balanagar', 'sanath nagar', 'old bowenpally']
    medium_risk_keywords = ['kphb', 'miyapur', 'chintal', 'pragathi', 'jntu', 'bachupally', 'lingampally']
    
    risk_config = {
        "high": {"color": "#e74c3c", "opacity": 0.5, "depth_range": (1.5, 2.5), "pop_range": (25000, 50000)},
        "medium": {"color": "#f39c12", "opacity": 0.4, "depth_range": (0.5, 1.5), "pop_range": (15000, 35000)},
        "low": {"color": "#27ae60", "opacity": 0.3, "depth_range": (0.1, 0.5), "pop_range": (10000, 20000)}
    }
    
    import random
    risk_features = {"high": [], "medium": [], "low": []}
    
    for idx, row in ward_gdf.iterrows():
        name = (row.get('name', '') or '').lower()
        geom = remove_z(row.geometry)
        
        if any(kw in name for kw in high_risk_keywords):
            risk = "high"
            history = "Severely affected in Oct 2020 floods"
        elif any(kw in name for kw in medium_risk_keywords):
            risk = "medium"
            history = "Partial flooding in major events"
        else:
            risk = "low"
            history = "Occasional waterlogging"
        
        config = risk_config[risk]
        depth = round(random.uniform(*config['depth_range']), 1)
        pop = random.randint(*config['pop_range'])
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": idx + 1,
                "name": row.get('name', f'Zone {idx+1}') or f'Zone {idx+1}',
                "risk_level": risk,
                "flood_depth_m": depth,
                "population_at_risk": pop,
                "history": history,
                "style_color": config['color'],
                "style_opacity": config['opacity'],
                "layer_type": "flood_risk"
            },
            "geometry": mapping(geom)
        }
        risk_features[risk].append(feature)
    
    for risk, features in risk_features.items():
        if features:
            geojson = create_geojson(features, f"Flood_Risk_{risk.title()}", 
                                    f"{risk.title()} flood risk zones - {len(features)} areas")
            save_geojson(geojson, f"flood_risk_{risk}.geojson")


def create_sensor_layers(ward_gdf):
    """Create separate layers for each sensor type"""
    print("\n📡 Creating Sensor Layers...")
    
    bounds = ward_gdf.total_bounds
    min_lon, min_lat, max_lon, max_lat = bounds
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    
    # Rain Gauges
    rain_gauges = [
        {"id": 1, "name": "RG01_Kukatpally", "location": "Kukatpally Bus Stand", 
         "lat": center_lat + 0.015, "lon": center_lon - 0.025, "elevation": 538},
        {"id": 2, "name": "RG02_KPHB", "location": "KPHB Colony Phase 3",
         "lat": center_lat + 0.035, "lon": center_lon + 0.015, "elevation": 542},
        {"id": 3, "name": "RG03_Miyapur", "location": "Miyapur Metro Station",
         "lat": max_lat - 0.025, "lon": min_lon + 0.035, "elevation": 556},
        {"id": 4, "name": "RG04_Moosapet", "location": "Moosapet Circle",
         "lat": center_lat - 0.025, "lon": center_lon + 0.025, "elevation": 535},
        {"id": 5, "name": "RG05_Balanagar", "location": "Balanagar Industrial Area",
         "lat": min_lat + 0.025, "lon": min_lon + 0.025, "elevation": 530},
        {"id": 6, "name": "RG06_Chintal", "location": "Chintal Cross Roads",
         "lat": center_lat + 0.04, "lon": center_lon - 0.01, "elevation": 548},
    ]
    
    rain_features = []
    for rg in rain_gauges:
        rain_features.append({
            "type": "Feature",
            "properties": {
                "id": rg["id"],
                "name": rg["name"],
                "sensor_type": "rain_gauge",
                "location": rg["location"],
                "elevation_m": rg["elevation"],
                "resolution_mm": 0.2,
                "status": "active",
                "style_icon": "cloud-rain",
                "style_color": "#3498db",
                "layer_type": "rain_gauge"
            },
            "geometry": {"type": "Point", "coordinates": [round(rg["lon"], 6), round(rg["lat"], 6)]}
        })
    
    geojson = create_geojson(rain_features, "Rain_Gauges", "Tipping bucket rain gauges - 0.2mm resolution")
    save_geojson(geojson, "rain_gauges.geojson")
    
    # Water Level Sensors
    water_sensors = [
        {"id": 1, "name": "WL01_Upstream", "location": "Upstream - Miyapur Side", "danger": 2.5,
         "lat": max_lat - 0.035, "lon": center_lon - 0.015},
        {"id": 2, "name": "WL02_Midstream", "location": "Midstream - KPHB Area", "danger": 2.5,
         "lat": center_lat + 0.005, "lon": center_lon + 0.005},
        {"id": 3, "name": "WL03_Downstream", "location": "Downstream - Erragadda Side", "danger": 2.5,
         "lat": min_lat + 0.035, "lon": max_lon - 0.025},
        {"id": 4, "name": "WL04_Junction", "location": "Channel Junction - Kukatpally", "danger": 2.0,
         "lat": center_lat - 0.01, "lon": center_lon - 0.02},
    ]
    
    wl_features = []
    for wl in water_sensors:
        wl_features.append({
            "type": "Feature",
            "properties": {
                "id": wl["id"],
                "name": wl["name"],
                "sensor_type": "water_level",
                "location": wl["location"],
                "danger_level_m": wl["danger"],
                "accuracy_cm": 1,
                "status": "active",
                "style_icon": "water",
                "style_color": "#9b59b6",
                "layer_type": "water_level"
            },
            "geometry": {"type": "Point", "coordinates": [round(wl["lon"], 6), round(wl["lat"], 6)]}
        })
    
    geojson = create_geojson(wl_features, "Water_Level_Sensors", "Ultrasonic water level sensors - 1cm accuracy")
    save_geojson(geojson, "water_level_sensors.geojson")


def create_layer_config():
    """Create layer configuration file for frontend (QGIS-like layer tree)"""
    print("\n📋 Creating Layer Configuration...")
    
    config = {
        "version": "1.0",
        "name": "Flood DAS - GHMC Zone 12",
        "description": "Layer-based flood monitoring system",
        "groups": [
            {
                "id": "base",
                "name": "Base Layers",
                "icon": "layer-group",
                "expanded": True,
                "layers": [
                    {
                        "id": "watershed",
                        "name": "Watershed Boundary",
                        "file": "layers/watershed_boundary.geojson",
                        "type": "polygon",
                        "visible": True,
                        "style": {
                            "color": "#2980b9",
                            "weight": 3,
                            "fillColor": "#2980b9",
                            "fillOpacity": 0.1,
                            "dashArray": "10, 5"
                        },
                        "zIndex": 100
                    },
                    {
                        "id": "wards",
                        "name": "Ward Boundaries",
                        "file": "layers/ward_boundaries.geojson",
                        "type": "polygon",
                        "visible": True,
                        "style": {
                            "color": "#7f8c8d",
                            "weight": 1.5,
                            "fillColor": "#bdc3c7",
                            "fillOpacity": 0.05
                        },
                        "zIndex": 90
                    }
                ]
            },
            {
                "id": "hydrology",
                "name": "Drainage Network",
                "icon": "water",
                "expanded": True,
                "layers": [
                    {
                        "id": "channels_4",
                        "name": "Main Channels (Order 4)",
                        "file": "layers/drainage_order_4.geojson",
                        "type": "line",
                        "visible": True,
                        "style": {"color": "#0066cc", "weight": 5, "opacity": 0.9},
                        "zIndex": 200
                    },
                    {
                        "id": "channels_3",
                        "name": "Secondary Channels (Order 3)",
                        "file": "layers/drainage_order_3.geojson",
                        "type": "line",
                        "visible": True,
                        "style": {"color": "#3399ff", "weight": 3.5, "opacity": 0.8},
                        "zIndex": 190
                    },
                    {
                        "id": "channels_2",
                        "name": "Tertiary Channels (Order 2)",
                        "file": "layers/drainage_order_2.geojson",
                        "type": "line",
                        "visible": False,
                        "style": {"color": "#66b3ff", "weight": 2.5, "opacity": 0.7},
                        "zIndex": 180
                    },
                    {
                        "id": "channels_1",
                        "name": "Minor Tributaries (Order 1)",
                        "file": "layers/drainage_order_1.geojson",
                        "type": "line",
                        "visible": False,
                        "style": {"color": "#99ccff", "weight": 1.5, "opacity": 0.6},
                        "zIndex": 170
                    }
                ]
            },
            {
                "id": "risk",
                "name": "Flood Risk Zones",
                "icon": "exclamation-triangle",
                "expanded": True,
                "layers": [
                    {
                        "id": "risk_high",
                        "name": "High Risk Zones",
                        "file": "layers/flood_risk_high.geojson",
                        "type": "polygon",
                        "visible": True,
                        "style": {
                            "color": "#e74c3c",
                            "weight": 2,
                            "fillColor": "#e74c3c",
                            "fillOpacity": 0.4
                        },
                        "zIndex": 150
                    },
                    {
                        "id": "risk_medium",
                        "name": "Medium Risk Zones",
                        "file": "layers/flood_risk_medium.geojson",
                        "type": "polygon",
                        "visible": True,
                        "style": {
                            "color": "#f39c12",
                            "weight": 2,
                            "fillColor": "#f39c12",
                            "fillOpacity": 0.3
                        },
                        "zIndex": 140
                    },
                    {
                        "id": "risk_low",
                        "name": "Low Risk Zones",
                        "file": "layers/flood_risk_low.geojson",
                        "type": "polygon",
                        "visible": False,
                        "style": {
                            "color": "#27ae60",
                            "weight": 2,
                            "fillColor": "#27ae60",
                            "fillOpacity": 0.2
                        },
                        "zIndex": 130
                    }
                ]
            },
            {
                "id": "sensors",
                "name": "Monitoring Infrastructure",
                "icon": "broadcast-tower",
                "expanded": True,
                "layers": [
                    {
                        "id": "rain_gauges",
                        "name": "Rain Gauges",
                        "file": "layers/rain_gauges.geojson",
                        "type": "point",
                        "visible": True,
                        "style": {"color": "#3498db", "icon": "cloud-rain", "size": 24},
                        "zIndex": 300
                    },
                    {
                        "id": "water_levels",
                        "name": "Water Level Sensors",
                        "file": "layers/water_level_sensors.geojson",
                        "type": "point",
                        "visible": True,
                        "style": {"color": "#9b59b6", "icon": "water", "size": 24},
                        "zIndex": 290
                    }
                ]
            },
            {
                "id": "rasters",
                "name": "Raster Data (DEM/DEM Derived)",
                "icon": "mountain",
                "expanded": True,
                "layers": [
                    {
                        "id": "dem",
                        "name": "Digital Elevation Model",
                        "raster": "dem",
                        "type": "raster",
                        "visible": True,
                        "colormap": "terrain",
                        "zIndex": 5
                    },
                    {
                        "id": "strahler",
                        "name": "Strahler Stream Order",
                        "raster": "strahler",
                        "type": "raster",
                        "visible": False,
                        "colormap": "jet",
                        "zIndex": 6
                    },
                    {
                        "id": "basins",
                        "name": "Drainage Basins",
                        "raster": "basins",
                        "type": "raster",
                        "visible": False,
                        "colormap": "tab20",
                        "zIndex": 4
                    }
                ]
            }
        ],
        "basemaps": [
            {"id": "dark", "name": "Dark", "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", "default": True},
            {"id": "light", "name": "Light", "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"},
            {"id": "osm", "name": "OpenStreetMap", "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"},
            {"id": "satellite", "name": "Satellite", "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"}
        ],
        "mapConfig": {
            "center": [17.4898, 78.4340],
            "zoom": 12,
            "minZoom": 10,
            "maxZoom": 18
        }
    }
    
    filepath = os.path.join(GEOJSON_PATH, "layer_config.json")
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"  ✓ Saved layer_config.json")


def main():
    print("=" * 60)
    print("🗺️  FLOOD DAS - QGIS-like Layer Generator")
    print("=" * 60)
    
    # Create ward boundaries and get GeoDataFrame
    ward_gdf = create_ward_boundaries()
    
    # Create watershed from merged wards
    create_watershed_boundary(ward_gdf)
    
    # Create drainage channels by Strahler order
    create_drainage_channels()
    
    # Create flood risk zones by level
    create_flood_risk_zones(ward_gdf)
    
    # Create sensor layers
    create_sensor_layers(ward_gdf)
    
    # Create layer configuration
    create_layer_config()
    
    print("\n" + "=" * 60)
    print("✅ All layers created successfully!")
    print(f"   Output directory: {LAYERS_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
