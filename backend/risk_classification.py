"""
Flood Risk Zone Classification Module
======================================
Dynamically classifies the 23 GHMC Zone 12 wards into flood risk levels
(LOW / MEDIUM / HIGH / CRITICAL) based on current rainfall and water level inputs.

Two-stage process:
1. Static vulnerability score per subbasin — computed once from physical basin properties
   (slope, relief, form factor, stream order, mouth elevation)
2. Dynamic hazard score — computed per simulation run from sensor inputs
   (per-basin discharge vs capacity, water level vs danger threshold)

Final ward risk = area-weighted average of subbasin risks within each ward.
"""

import json
import os
import math
from typing import Optional

try:
    from shapely.geometry import shape, Point
    from shapely.ops import unary_union
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

# ============================================================================
# PATH CONSTANTS
# ============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASINS_FILE = os.path.join(BASE_DIR, "geojson", "layers", "drainage_basins_enriched.geojson")
FLOOD_ZONES_FILE = os.path.join(BASE_DIR, "geojson", "flood_zones.geojson")

# ============================================================================
# RISK THRESHOLDS
# ============================================================================

RISK_THRESHOLDS = {
    "low":      (0.00, 0.25),
    "medium":   (0.25, 0.50),
    "high":     (0.50, 0.75),
    "critical": (0.75, 1.00),
}

RISK_COLORS = {
    "low":      "#27ae60",
    "medium":   "#f39c12",
    "high":     "#e74c3c",
    "critical": "#8e0000",
}

# Channel capacity estimates by Strahler order (m³/s)
CHANNEL_CAPACITY_BY_ORDER = {
    1: 5.0,
    2: 20.0,
    3: 80.0,
    4: 300.0,
}

# Water level danger thresholds (m) per sensor proximity
# Upstream / midstream / downstream from water_level_sensors.geojson
SENSOR_DANGER_LEVELS = {
    "upstream":   2.5,
    "midstream":  2.5,
    "downstream": 2.0,
}

# Sensor locations (lat, lon) for proximity assignment
SENSOR_LOCATIONS = [
    {"name": "upstream",   "lat": 17.5100, "lon": 78.3800},
    {"name": "midstream",  "lat": 17.4900, "lon": 78.4000},
    {"name": "downstream", "lat": 17.4700, "lon": 78.4200},
]

# ============================================================================
# MODULE-LEVEL CACHE (computed once at import time)
# ============================================================================

_basin_vulnerability_scores: dict = {}   # basin_id -> float 0-1
_basin_ward_mapping: dict = {}           # ward_name -> [(basin_id, overlap_frac), ...]
_flood_zones_geojson: Optional[dict] = None
_basins_geojson: Optional[dict] = None
_initialized: bool = False


# ============================================================================
# INITIALISATION
# ============================================================================

def initialize():
    """
    Load GeoJSON data, compute static vulnerability scores, and build the
    basin-ward spatial mapping.  Called once at server startup.
    """
    global _basin_vulnerability_scores, _basin_ward_mapping
    global _flood_zones_geojson, _basins_geojson, _initialized

    if _initialized:
        return

    try:
        with open(BASINS_FILE, "r") as f:
            _basins_geojson = json.load(f)
        with open(FLOOD_ZONES_FILE, "r") as f:
            _flood_zones_geojson = json.load(f)
    except FileNotFoundError as e:
        print(f"[risk_classification] WARNING: Could not load GeoJSON: {e}")
        _initialized = True
        return

    _basin_vulnerability_scores = _compute_all_vulnerability_scores(_basins_geojson)

    if SHAPELY_AVAILABLE:
        _basin_ward_mapping = _build_basin_ward_mapping(_basins_geojson, _flood_zones_geojson)
    else:
        # Fallback: assign every basin to every ward with equal weight
        print("[risk_classification] WARNING: shapely not available — using fallback mapping")
        _basin_ward_mapping = _fallback_mapping(_basins_geojson, _flood_zones_geojson)

    _initialized = True
    print(f"[risk_classification] Initialized: {len(_basin_vulnerability_scores)} basins, "
          f"{len(_basin_ward_mapping)} wards mapped")


# ============================================================================
# STATIC VULNERABILITY SCORING
# ============================================================================

def _normalize(values: list) -> list:
    """Min-max normalize a list of floats to [0, 1]."""
    if not values:
        return values
    mn, mx = min(values), max(values)
    if mx == mn:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def _compute_all_vulnerability_scores(basins_geojson: dict) -> dict:
    """
    Compute static vulnerability score (0-1) for each subbasin.

    Scoring factors:
      - Avg_Slope_m_m    (25%) — steeper = faster runoff
      - Relief_m         (20%) — more elevation range = more flow energy
      - Form_Factor      (20%) — closer to 1 = more circular = flashier response
      - Max_Stream_Order (20%) — more drainage convergence
      - Mouth_Elevation_m(15%) — lower elevation = more downstream = more flood-prone (INVERTED)
    """
    features = basins_geojson.get("features", [])
    if not features:
        return {}

    slopes        = [f["properties"].get("Avg_Slope_m_m", 0) or 0 for f in features]
    reliefs       = [f["properties"].get("Relief_m", 0) or 0 for f in features]
    form_factors  = [f["properties"].get("Form_Factor", 0) or 0 for f in features]
    stream_orders = [float(f["properties"].get("Max_Stream_Order", 1) or 1) for f in features]
    mouth_elevs   = [f["properties"].get("Mouth_Elevation_m", 550) or 550 for f in features]

    n_slopes    = _normalize(slopes)
    n_reliefs   = _normalize(reliefs)
    n_ff        = _normalize(form_factors)
    n_orders    = _normalize(stream_orders)
    n_mouths    = _normalize(mouth_elevs)
    # invert mouth elevation: lower elevation = higher risk
    n_mouths_inv = [1.0 - v for v in n_mouths]

    scores = {}
    weights = (0.25, 0.20, 0.20, 0.20, 0.15)

    for i, feat in enumerate(features):
        basin_id = feat["properties"].get("DN") or feat["properties"].get("Basin_ID") or i
        score = (
            weights[0] * n_slopes[i] +
            weights[1] * n_reliefs[i] +
            weights[2] * n_ff[i] +
            weights[3] * n_orders[i] +
            weights[4] * n_mouths_inv[i]
        )
        scores[basin_id] = round(score, 4)

    return scores


# ============================================================================
# SPATIAL JOIN: BASINS → WARDS
# ============================================================================

def _euclidean_distance(lat1, lon1, lat2, lon2) -> float:
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


def _polygon_centroid(coordinates) -> tuple:
    """Rough centroid of an exterior ring."""
    ring = coordinates[0][0] if isinstance(coordinates[0][0], list) else coordinates[0]
    if ring and isinstance(ring[0], list):
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return 17.49, 78.43  # fallback to zone center


def _build_basin_ward_mapping(basins_geojson: dict, flood_zones_geojson: dict) -> dict:
    """
    Compute how much of each drainage basin overlaps each ward polygon.
    Returns: {ward_name: [(basin_id, overlap_fraction), ...]}
    overlap_fraction sums to ≤1 per basin (a basin may straddle multiple wards).
    """
    mapping: dict = {}

    ward_shapes = []
    for feat in flood_zones_geojson.get("features", []):
        try:
            geom = shape(feat["geometry"])
            ward_name = feat["properties"].get("name", "Unknown")
            ward_shapes.append((ward_name, geom))
            if ward_name not in mapping:
                mapping[ward_name] = []
        except Exception:
            continue

    for feat in basins_geojson.get("features", []):
        basin_id = feat["properties"].get("DN") or feat["properties"].get("Basin_ID")
        try:
            basin_geom = shape(feat["geometry"])
            basin_area = basin_geom.area
            if basin_area == 0:
                continue
        except Exception:
            continue

        for ward_name, ward_geom in ward_shapes:
            try:
                intersection = basin_geom.intersection(ward_geom)
                overlap_frac = intersection.area / basin_area
                if overlap_frac > 0.01:   # ignore trivial overlaps (<1%)
                    mapping[ward_name].append((basin_id, round(overlap_frac, 4)))
            except Exception:
                continue

    return mapping


def _fallback_mapping(basins_geojson: dict, flood_zones_geojson: dict) -> dict:
    """
    When shapely is unavailable: assign each basin to its nearest ward centroid.
    This is a coarse approximation only.
    """
    mapping: dict = {}
    ward_centroids = []

    for feat in flood_zones_geojson.get("features", []):
        ward_name = feat["properties"].get("name", "Unknown")
        mapping[ward_name] = []
        try:
            lat, lon = _polygon_centroid(feat["geometry"]["coordinates"])
            ward_centroids.append((ward_name, lat, lon))
        except Exception:
            pass

    for feat in basins_geojson.get("features", []):
        basin_id = feat["properties"].get("DN") or feat["properties"].get("Basin_ID")
        try:
            lat, lon = _polygon_centroid(feat["geometry"]["coordinates"])
        except Exception:
            continue

        if not ward_centroids:
            continue
        nearest = min(ward_centroids, key=lambda w: _euclidean_distance(lat, lon, w[1], w[2]))
        mapping[nearest[0]].append((basin_id, 1.0))

    return mapping


# ============================================================================
# DYNAMIC HAZARD SCORING
# ============================================================================

def _nearest_sensor(basin_props: dict) -> str:
    """
    Assign basin to upstream / midstream / downstream sensor
    based on basin mouth elevation or stream order as a proxy.
    """
    order = basin_props.get("Max_Stream_Order", 1) or 1
    mouth_elev = basin_props.get("Mouth_Elevation_m", 540) or 540

    if mouth_elev > 545:
        return "upstream"
    elif mouth_elev > 535:
        return "midstream"
    else:
        return "downstream"


def _derive_runoff_coeff(basin_props: dict) -> float:
    """
    Derive per-basin runoff coefficient from slope.
    Scales around the global watershed average of 0.736.
    Clamped between 0.5 and 0.95.
    """
    slope = basin_props.get("Avg_Slope_m_m", 0.05) or 0.05
    # Empirical scaling: higher slope → higher C
    c = 0.6 + (slope * 3.5)
    return max(0.50, min(0.95, c))


def _compute_dynamic_hazard(basin_props: dict, rainfall_mm: float, water_level_m: float) -> float:
    """
    Compute dynamic hazard score for a single subbasin.

    discharge_ratio = per-basin Q / estimated channel capacity  (capped 0-1)
    water_level_ratio = water_level_m / sensor_danger_level     (capped 0-1)
    hazard = 0.6 * discharge_ratio + 0.4 * water_level_ratio
    """
    area_km2 = basin_props.get("Area_km2", 1.0) or 1.0
    c = _derive_runoff_coeff(basin_props)
    # Rational Method: Q = C * i * A, i in m/s, A in m²
    intensity_ms = rainfall_mm * (0.001 / 3600)
    discharge = c * intensity_ms * area_km2 * 1e6

    stream_order = int(basin_props.get("Max_Stream_Order", 1) or 1)
    capacity = CHANNEL_CAPACITY_BY_ORDER.get(stream_order, 5.0)
    discharge_ratio = min(1.0, discharge / capacity)

    sensor_key = _nearest_sensor(basin_props)
    danger_level = SENSOR_DANGER_LEVELS[sensor_key]
    water_ratio = min(1.0, water_level_m / danger_level)

    hazard = 0.6 * discharge_ratio + 0.4 * water_ratio
    return round(min(1.0, hazard), 4)


# ============================================================================
# WARD CLASSIFICATION
# ============================================================================

def _score_to_risk_level(score: float) -> str:
    for level, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= score <= hi:
            return level
    return "critical" if score > 0.75 else "low"


def _normalize_area_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def classify_wards(rainfall_mm: float, water_level_m: float, area_filter: str = "all") -> dict:
    """
    Main function: compute dynamic risk classification for all (or one) wards.

    Args:
        rainfall_mm:   Simulation rainfall intensity (mm/hr)
        water_level_m: Simulation water level at sensor (m)
        area_filter:   "all" or a ward name to restrict output

    Returns:
        Updated GeoJSON FeatureCollection (flood_zones.geojson) with new properties:
          - risk_level    (low/medium/high/critical)
          - risk_score    (0-1)
          - risk_color
          - dynamic_discharge_m3s  (estimated peak discharge for this ward)
    """
    if not _initialized:
        initialize()

    if _flood_zones_geojson is None:
        return {"type": "FeatureCollection", "features": []}

    all_ward_names = [
        f.get("properties", {}).get("name", "")
        for f in _flood_zones_geojson.get("features", [])
    ]

    normalized_filter = _normalize_area_name(area_filter)
    selected_ward = None
    if normalized_filter not in ("", "all", "all zone 12", "zone 12"):
        # Exact normalized match first
        for wn in all_ward_names:
            if _normalize_area_name(wn) == normalized_filter:
                selected_ward = wn
                break

        # Fuzzy fallback: substring match either direction
        if selected_ward is None:
            for wn in all_ward_names:
                nwn = _normalize_area_name(wn)
                if normalized_filter in nwn or nwn in normalized_filter:
                    selected_ward = wn
                    break

        # Last fallback: avoid blank map if caller sends unknown ward label
        if selected_ward is None:
            print(f"[risk_classification] Unknown area filter '{area_filter}', using all wards")

    basins_by_id: dict = {}
    if _basins_geojson:
        for feat in _basins_geojson.get("features", []):
            bid = feat["properties"].get("DN") or feat["properties"].get("Basin_ID")
            basins_by_id[bid] = feat["properties"]

    updated_features = []

    for feat in _flood_zones_geojson.get("features", []):
        ward_name = feat["properties"].get("name", "")

        if selected_ward is not None and ward_name != selected_ward:
            continue

        basin_refs = _basin_ward_mapping.get(ward_name, [])

        if basin_refs and basins_by_id:
            # Weighted aggregation over overlapping basins
            total_weight = 0.0
            weighted_vuln = 0.0
            weighted_hazard = 0.0
            total_discharge = 0.0

            for basin_id, frac in basin_refs:
                props = basins_by_id.get(basin_id, {})
                vuln = _basin_vulnerability_scores.get(basin_id, 0.5)
                hazard = _compute_dynamic_hazard(props, rainfall_mm, water_level_m)

                # Compute basin discharge for reporting
                area_km2 = props.get("Area_km2", 1.0) or 1.0
                c = _derive_runoff_coeff(props)
                q = c * rainfall_mm * (0.001 / 3600) * area_km2 * 1e6
                total_discharge += q * frac

                weighted_vuln += vuln * frac
                weighted_hazard += hazard * frac
                total_weight += frac

            if total_weight > 0:
                weighted_vuln /= total_weight
                weighted_hazard /= total_weight
            else:
                weighted_vuln = 0.3
                weighted_hazard = 0.3

        else:
            # No basin mapping — use simple threshold-based fallback
            weighted_vuln = 0.3
            intensity_ms = rainfall_mm * (0.001 / 3600)
            area_km2 = feat["properties"].get("Area_km2", 4.5) or 4.5
            q = 0.736 * intensity_ms * area_km2 * 1e6
            capacity = CHANNEL_CAPACITY_BY_ORDER[3]
            discharge_ratio = min(1.0, q / capacity)
            water_ratio = min(1.0, water_level_m / 2.5)
            weighted_hazard = 0.6 * discharge_ratio + 0.4 * water_ratio
            total_discharge = q

        # Historical anchor: flood_depth_potential_m normalized by max observed (2.4m)
        hist_depth = feat["properties"].get("flood_depth_potential_m", 0.5) or 0.5
        hist_score = min(1.0, hist_depth / 2.4) * 0.1  # 10% anchor weight

        risk_score = round(
            (0.4 * weighted_vuln + 0.6 * weighted_hazard) * 0.9 + hist_score,
            4
        )
        risk_level = _score_to_risk_level(risk_score)

        new_props = dict(feat["properties"])
        new_props["risk_level"] = risk_level
        new_props["risk_score"] = risk_score
        new_props["risk_color"] = RISK_COLORS[risk_level]
        new_props["dynamic_discharge_m3s"] = round(total_discharge, 1)
        new_props["simulation_rainfall_mm"] = rainfall_mm
        new_props["simulation_water_level_m"] = water_level_m

        updated_features.append({
            "type": "Feature",
            "properties": new_props,
            "geometry": feat["geometry"]
        })

    return {
        "type": "FeatureCollection",
        "name": "Dynamic_Flood_Risk_Zones",
        "features": updated_features
    }


def get_ward_summary(classified_geojson: dict) -> dict:
    """Return count of wards per risk level and total population at risk."""
    counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    total_pop = 0

    for feat in classified_geojson.get("features", []):
        level = feat["properties"].get("risk_level", "low")
        counts[level] = counts.get(level, 0) + 1
        if level in ("medium", "high", "critical"):
            total_pop += feat["properties"].get("population_at_risk", 0) or 0

    return {
        "wards_low": counts["low"],
        "wards_medium": counts["medium"],
        "wards_high": counts["high"],
        "wards_critical": counts["critical"],
        "total_population_at_risk": total_pop,
    }
