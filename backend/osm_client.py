"""
OSM Building Fetch and Classification Module
=============================================
Fetches real buildings (schools, hospitals, community centers, etc.) from
OpenStreetMap via the Overpass API for GHMC Zone 12, Hyderabad.

After fetching, each building is classified as:
  - at_risk  : centroid falls within a HIGH or CRITICAL risk ward AND
               elevation is at or below flood depth threshold
  - safe     : not in a high/critical zone — candidate for emergency facility use

Results are cached to geojson/cache/osm_buildings.geojson for 24 hours.
"""

import json
import os
import time
import math
from typing import Optional

import aiohttp

try:
    from shapely.geometry import shape, Point
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

# ============================================================================
# CONSTANTS
# ============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "geojson", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "osm_buildings.geojson")
CACHE_MAX_AGE_SECONDS = 86400  # 24 hours

DEM_PATH = os.path.join(BASE_DIR, "geojson", "zone-12-filled-dem.tif")

# Bounding box for GHMC Zone 12 (south, west, north, east)
ZONE12_BBOX = (17.43, 78.38, 17.54, 78.48)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# OSM amenity/leisure tags to fetch
BUILDING_TAGS = [
    ("amenity", "school"),
    ("amenity", "college"),
    ("amenity", "university"),
    ("amenity", "hospital"),
    ("amenity", "clinic"),
    ("amenity", "community_centre"),
    ("amenity", "place_of_worship"),
    ("amenity", "marketplace"),
    ("amenity", "fire_station"),
    ("amenity", "police"),
    ("leisure", "stadium"),
    ("leisure", "sports_centre"),
]

# Human-readable facility type labels
TYPE_LABELS = {
    "school": "School",
    "college": "College",
    "university": "University",
    "hospital": "Hospital",
    "clinic": "Clinic",
    "community_centre": "Community Centre",
    "place_of_worship": "Place of Worship",
    "marketplace": "Marketplace",
    "fire_station": "Fire Station",
    "police": "Police Station",
    "stadium": "Stadium",
    "sports_centre": "Sports Centre",
}

# Which facility types can serve which emergency role
FACILITY_ELIGIBILITY = {
    "relief_camp":    {"school", "college", "university", "stadium", "sports_centre", "community_centre"},
    "temp_hospital":  {"hospital", "clinic", "school", "community_centre"},
    "community_kitchen": {"place_of_worship", "marketplace", "community_centre", "school"},
}


# ============================================================================
# OVERPASS QUERY BUILDER
# ============================================================================

def _build_overpass_query(bbox: tuple) -> str:
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    tag_union = ""
    for key, value in BUILDING_TAGS:
        tag_union += f'  node["{key}"="{value}"]({bbox_str});\n'
        tag_union += f'  way["{key}"="{value}"]({bbox_str});\n'

    return f"""
[out:json][timeout:30];
(
{tag_union}
);
out center;
"""


# ============================================================================
# OSM FETCH
# ============================================================================

async def fetch_osm_buildings(bbox: tuple = ZONE12_BBOX) -> list:
    """
    Asynchronously fetch buildings from Overpass API.
    Returns list of dicts: {name, osm_type, lat, lon, osm_id, tags}.
    """
    query = _build_overpass_query(bbox)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=aiohttp.ClientTimeout(total=35)
            ) as response:
                if response.status != 200:
                    print(f"[osm_client] Overpass returned HTTP {response.status}")
                    return []
                data = await response.json(content_type=None)
    except Exception as e:
        print(f"[osm_client] Overpass API error: {e}")
        return []

    buildings = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("name:en") or "Unnamed"

        # Determine lat/lon (node vs way with center)
        if element["type"] == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
            center = element.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue

        # Determine building type
        osm_type = None
        for key, value in BUILDING_TAGS:
            if tags.get(key) == value:
                osm_type = value
                break

        if osm_type is None:
            continue

        buildings.append({
            "name": name,
            "osm_type": osm_type,
            "type_label": TYPE_LABELS.get(osm_type, osm_type.title()),
            "lat": lat,
            "lon": lon,
            "osm_id": element.get("id"),
            "eligible_as": [role for role, types in FACILITY_ELIGIBILITY.items() if osm_type in types],
        })

    print(f"[osm_client] Fetched {len(buildings)} buildings from Overpass API")
    return buildings


# ============================================================================
# CACHE
# ============================================================================

def _cache_is_valid() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    age = time.time() - os.path.getmtime(CACHE_FILE)
    return age < CACHE_MAX_AGE_SECONDS


def _write_cache(buildings: list):
    os.makedirs(CACHE_DIR, exist_ok=True)
    features = [_building_to_feature(b) for b in buildings]
    geojson = {"type": "FeatureCollection", "features": features}
    with open(CACHE_FILE, "w") as f:
        json.dump(geojson, f)


def _read_cache() -> list:
    with open(CACHE_FILE, "r") as f:
        geojson = json.load(f)
    buildings = []
    for feat in geojson.get("features", []):
        p = feat["properties"]
        coords = feat["geometry"]["coordinates"]
        buildings.append({
            "name": p.get("name"),
            "osm_type": p.get("osm_type"),
            "type_label": p.get("type_label"),
            "lat": coords[1],
            "lon": coords[0],
            "osm_id": p.get("osm_id"),
            "eligible_as": p.get("eligible_as", []),
            "status": p.get("status"),
            "elevation_m": p.get("elevation_m"),
            "overlapping_ward": p.get("overlapping_ward"),
            "ward_risk_level": p.get("ward_risk_level"),
            "recommended_as": p.get("recommended_as"),
        })
    return buildings


async def load_or_fetch_buildings() -> list:
    """
    Return cached buildings if fresh, otherwise fetch from Overpass and cache.
    """
    if _cache_is_valid():
        print("[osm_client] Using cached OSM buildings")
        return _read_cache()

    buildings = await fetch_osm_buildings()
    if buildings:
        _write_cache(buildings)
    return buildings


# ============================================================================
# ELEVATION LOOKUP
# ============================================================================

def get_elevation_at_point(lat: float, lon: float) -> Optional[float]:
    """
    Sample elevation from zone-12-filled-dem.tif at a given coordinate.
    Returns elevation in metres, or None if rasterio is unavailable.
    """
    if not RASTERIO_AVAILABLE or not os.path.exists(DEM_PATH):
        return None
    try:
        with rasterio.open(DEM_PATH) as ds:
            # rasterio.sample expects [(lon, lat)] in the dataset's CRS
            values = list(ds.sample([(lon, lat)]))
            if values and values[0][0] != ds.nodata:
                return float(values[0][0])
    except Exception as e:
        print(f"[osm_client] Elevation lookup failed: {e}")
    return None


# ============================================================================
# BUILDING CLASSIFICATION
# ============================================================================

def _ward_polygon_shapes(risk_zones_geojson: dict) -> list:
    """Return list of (ward_name, risk_level, flood_depth_m, shapely_geom)."""
    shapes = []
    for feat in risk_zones_geojson.get("features", []):
        props = feat["properties"]
        try:
            geom = shape(feat["geometry"]) if SHAPELY_AVAILABLE else None
            shapes.append({
                "name": props.get("name", ""),
                "risk_level": props.get("risk_level", "low"),
                "flood_depth_m": props.get("flood_depth_potential_m", 0.5) or 0.5,
                "geom": geom,
                "centroid_lat": props.get("_centroid_lat"),
                "centroid_lon": props.get("_centroid_lon"),
            })
        except Exception:
            continue
    return shapes


def _point_in_ward(lat: float, lon: float, ward_shapes: list) -> Optional[dict]:
    """Return the ward that contains the point, or the nearest ward."""
    if SHAPELY_AVAILABLE:
        pt = Point(lon, lat)
        for ward in ward_shapes:
            if ward["geom"] and ward["geom"].contains(pt):
                return ward
        # fallback: nearest centroid
        best, best_d = None, float("inf")
        for ward in ward_shapes:
            if ward["geom"]:
                c = ward["geom"].centroid
                d = math.sqrt((c.y - lat) ** 2 + (c.x - lon) ** 2)
                if d < best_d:
                    best_d, best = d, ward
        return best
    else:
        # No shapely: assign to nearest ward centroid (rough)
        return None


def classify_buildings(buildings: list, risk_zones_geojson: dict) -> list:
    """
    Classify each building as 'at_risk' or 'safe' based on current risk zones.

    A building is AT-RISK if:
      1. Its centroid falls within a HIGH or CRITICAL risk ward
      2. AND its elevation ≤ (base channel elevation + flood_depth_potential_m)
         i.e. it could be inundated

    A building is SAFE otherwise → candidate for emergency facility use.
    """
    ward_shapes = _ward_polygon_shapes(risk_zones_geojson)
    classified = []

    for b in buildings:
        lat, lon = b["lat"], b["lon"]

        # Elevation lookup
        elevation_m = get_elevation_at_point(lat, lon)
        b["elevation_m"] = elevation_m

        ward = _point_in_ward(lat, lon, ward_shapes)
        ward_name = ward["name"] if ward else "Unknown"
        ward_risk = ward["risk_level"] if ward else "low"
        flood_depth = ward["flood_depth_m"] if ward else 0.5

        b["overlapping_ward"] = ward_name
        b["ward_risk_level"] = ward_risk

        # Classification logic
        in_danger_zone = ward_risk in ("high", "critical")

        elevation_at_risk = False
        if elevation_m is not None:
            # Approximate flood stage: base elevation ~530m + flood depth
            # A building is at-risk if its floor elevation ≤ flood stage
            BASE_CHANNEL_ELEV = 530.0
            flood_stage = BASE_CHANNEL_ELEV + flood_depth
            elevation_at_risk = elevation_m <= flood_stage
        else:
            # No DEM data → rely on zone classification alone
            elevation_at_risk = in_danger_zone

        if in_danger_zone and elevation_at_risk:
            b["status"] = "at_risk"
            b["recommended_as"] = None
        else:
            b["status"] = "safe"
            # Assign primary recommended use (first eligible role)
            b["recommended_as"] = b["eligible_as"][0] if b["eligible_as"] else None

        classified.append(b)

    at_risk_count = sum(1 for b in classified if b["status"] == "at_risk")
    safe_count = len(classified) - at_risk_count
    print(f"[osm_client] Classified: {at_risk_count} at-risk, {safe_count} safe")
    return classified


# ============================================================================
# GEOJSON CONVERSION
# ============================================================================

def _building_to_feature(b: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [b["lon"], b["lat"]]
        },
        "properties": {
            "name": b.get("name"),
            "osm_type": b.get("osm_type"),
            "type_label": b.get("type_label"),
            "osm_id": b.get("osm_id"),
            "eligible_as": b.get("eligible_as", []),
            "status": b.get("status"),
            "elevation_m": b.get("elevation_m"),
            "overlapping_ward": b.get("overlapping_ward"),
            "ward_risk_level": b.get("ward_risk_level"),
            "recommended_as": b.get("recommended_as"),
        }
    }


def buildings_to_geojson(classified_buildings: list) -> dict:
    """Convert classified buildings list to GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": [_building_to_feature(b) for b in classified_buildings]
    }
