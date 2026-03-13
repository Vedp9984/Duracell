"""
Emergency Facility Location Optimization Module
================================================
Given a pool of safe buildings (from osm_client) and at-risk ward populations,
finds optimal locations for three types of emergency facilities:

  1. Relief Camps       — maximize shelter access for high-population wards
  2. Temporary Hospitals— minimize distance to at-risk populations
  3. Community Kitchens — maximize central coverage across wards

Algorithm: Greedy P-Median (minimize total population-weighted distance).
Only numpy is required — no additional optimization library.

Coverage radius defaults:
  Relief camp:        3.0 km
  Temporary hospital: 5.0 km
  Community kitchen:  2.0 km
"""

import math
import json
import os
from typing import Optional

import numpy as np

try:
    from shapely.geometry import shape
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

# ============================================================================
# CONSTANTS
# ============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOD_ZONES_FILE = os.path.join(BASE_DIR, "geojson", "flood_zones.geojson")
DEM_PATH = os.path.join(BASE_DIR, "geojson", "zone-12-filled-dem.tif")

COVERAGE_RADIUS_KM = {
    "relief_camp": 3.0,
    "temp_hospital": 5.0,
    "community_kitchen": 2.0,
}

# CRITICAL wards get 2× population weight in optimization
CRITICAL_WEIGHT_MULTIPLIER = 2.0
HIGH_WEIGHT_MULTIPLIER = 1.5

# Eligible building types per facility role
FACILITY_ELIGIBILITY = {
    "relief_camp":       {"school", "college", "university", "stadium", "sports_centre", "community_centre"},
    "temp_hospital":     {"hospital", "clinic", "school", "community_centre"},
    "community_kitchen": {"place_of_worship", "marketplace", "community_centre", "school"},
}

DEFAULT_COUNTS = {
    "relief_camp": 5,
    "temp_hospital": 3,
    "community_kitchen": 4,
}


# ============================================================================
# HELPER: DISTANCE
# ============================================================================

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ============================================================================
# WARD CENTROIDS
# ============================================================================

def _polygon_centroid(geometry: dict) -> tuple:
    """Compute rough centroid of a GeoJSON polygon/multipolygon."""
    if SHAPELY_AVAILABLE:
        try:
            geom = shape(geometry)
            c = geom.centroid
            return c.y, c.x  # lat, lon
        except Exception:
            pass

    # Pure-python fallback: average of first ring coordinates
    geo_type = geometry.get("type", "")
    coords = geometry.get("coordinates", [])
    try:
        if geo_type == "Polygon":
            ring = coords[0]
        elif geo_type == "MultiPolygon":
            ring = coords[0][0]
        else:
            return 17.49, 78.43
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    except Exception:
        return 17.49, 78.43


def compute_ward_centroids(flood_zones_geojson: dict, risk_level_filter: Optional[list] = None) -> list:
    """
    Compute centroid and population weight for each ward.

    Args:
        flood_zones_geojson:  loaded flood_zones.geojson dict
        risk_level_filter:    if set, only include wards at these risk levels
                              e.g. ["medium", "high", "critical"]
    Returns:
        List of dicts: {ward_name, lat, lon, population, risk_level, weight}
    """
    centroids = []
    if risk_level_filter is None:
        risk_level_filter = ["low", "medium", "high", "critical"]

    for feat in flood_zones_geojson.get("features", []):
        props = feat["properties"]
        risk_level = props.get("risk_level", "low")

        if risk_level not in risk_level_filter:
            continue

        lat, lon = _polygon_centroid(feat["geometry"])
        population = props.get("population_at_risk", 0) or 0

        # Apply weight multiplier based on risk severity
        if risk_level == "critical":
            weight = population * CRITICAL_WEIGHT_MULTIPLIER
        elif risk_level == "high":
            weight = population * HIGH_WEIGHT_MULTIPLIER
        else:
            weight = float(population)

        centroids.append({
            "ward_name": props.get("name", "Unknown"),
            "lat": lat,
            "lon": lon,
            "population": population,
            "risk_level": risk_level,
            "weight": weight,
        })

    return centroids


# ============================================================================
# CANDIDATE FILTERING
# ============================================================================

def filter_candidates_by_type(safe_buildings: list, facility_type: str) -> list:
    """
    Return buildings eligible for the given facility type.
    Only SAFE buildings are considered.
    """
    eligible_types = FACILITY_ELIGIBILITY.get(facility_type, set())
    return [
        b for b in safe_buildings
        if b.get("status") == "safe"
        and b.get("osm_type") in eligible_types
    ]


# ============================================================================
# DISTANCE MATRIX
# ============================================================================

def _get_elevation(lat: float, lon: float) -> Optional[float]:
    """Sample DEM elevation for a point (requires rasterio)."""
    try:
        import rasterio
        if not os.path.exists(DEM_PATH):
            return None
        with rasterio.open(DEM_PATH) as ds:
            vals = list(ds.sample([(lon, lat)]))
            if vals and vals[0][0] != ds.nodata:
                return float(vals[0][0])
    except Exception:
        pass
    return None


def build_distance_matrix(ward_centroids: list, candidates: list) -> np.ndarray:
    """
    Build a (n_wards × n_candidates) distance matrix.

    Distance = Haversine distance (km) × elevation penalty factor.
    Penalty: uphill to a higher-elevation candidate is harder during floods.
      penalty = 1 + 0.05 * max(0, elev_diff_per_10m)
    """
    n_wards = len(ward_centroids)
    n_cands = len(candidates)
    matrix = np.zeros((n_wards, n_cands), dtype=float)

    # Pre-fetch candidate elevations (optional, may return None)
    cand_elevations = [_get_elevation(c["lat"], c["lon"]) for c in candidates]
    ward_elevations = [_get_elevation(w["lat"], w["lon"]) for w in ward_centroids]

    for i, ward in enumerate(ward_centroids):
        w_elev = ward_elevations[i]
        for j, cand in enumerate(candidates):
            dist_km = _haversine_km(ward["lat"], ward["lon"], cand["lat"], cand["lon"])

            # Elevation penalty
            c_elev = cand_elevations[j]
            if w_elev is not None and c_elev is not None:
                elev_diff = c_elev - w_elev   # positive = uphill to reach shelter
                # For every 10m of uphill, add 5% to effective distance
                penalty = 1.0 + 0.05 * max(0, elev_diff / 10.0)
            else:
                penalty = 1.0

            matrix[i, j] = dist_km * penalty

    return matrix


# ============================================================================
# GREEDY P-MEDIAN
# ============================================================================

def greedy_p_median(distance_matrix: np.ndarray, population_weights: list, k: int) -> list:
    """
    Greedy facility selection minimizing total population-weighted distance.

    At each step, select the candidate that most reduces the sum of
    (population × distance-to-nearest-selected-facility) across all wards.

    Args:
        distance_matrix:    shape (n_wards, n_candidates)
        population_weights: list of n_wards weights
        k:                  number of facilities to select

    Returns:
        List of k candidate column indices (optimal facility locations)
    """
    n_wards, n_cands = distance_matrix.shape
    weights = np.array(population_weights, dtype=float)

    if k <= 0 or n_cands == 0:
        return []

    k = min(k, n_cands)

    selected = []
    # Current best distance for each ward (initialized to infinity)
    best_dist = np.full(n_wards, np.inf)

    for _ in range(k):
        best_candidate = -1
        best_total_cost = np.inf

        for j in range(n_cands):
            if j in selected:
                continue
            # If we add candidate j, what is the new best distance for each ward?
            new_best = np.minimum(best_dist, distance_matrix[:, j])
            total_cost = np.dot(weights, new_best)
            if total_cost < best_total_cost:
                best_total_cost = total_cost
                best_candidate = j

        if best_candidate == -1:
            break

        selected.append(best_candidate)
        best_dist = np.minimum(best_dist, distance_matrix[:, best_candidate])

    return selected


# ============================================================================
# COVERAGE ANALYSIS
# ============================================================================

def compute_coverage(
    selected_facilities: list,
    ward_centroids: list,
    facility_type: str,
) -> dict:
    """
    For each ward, find nearest selected facility and check if within coverage radius.

    Returns:
        {
          ward_name: {nearest_facility_name, distance_km, is_covered}
          ...
          "_summary": {covered_wards, covered_population, coverage_pct}
        }
    """
    radius = COVERAGE_RADIUS_KM.get(facility_type, 3.0)
    result = {}
    covered_pop = 0
    total_pop = sum(w["population"] for w in ward_centroids)

    for ward in ward_centroids:
        if not selected_facilities:
            result[ward["ward_name"]] = {
                "nearest_facility": None,
                "distance_km": None,
                "is_covered": False
            }
            continue

        distances = [
            (_haversine_km(ward["lat"], ward["lon"], f["lat"], f["lon"]), f["name"])
            for f in selected_facilities
        ]
        nearest_dist, nearest_name = min(distances, key=lambda x: x[0])
        is_covered = nearest_dist <= radius

        if is_covered:
            covered_pop += ward["population"]

        result[ward["ward_name"]] = {
            "nearest_facility": nearest_name,
            "distance_km": round(nearest_dist, 2),
            "is_covered": is_covered,
        }

    coverage_pct = round(100 * covered_pop / total_pop, 1) if total_pop > 0 else 0
    result["_summary"] = {
        "covered_population": covered_pop,
        "total_population": total_pop,
        "coverage_pct": coverage_pct,
        "radius_km": radius,
    }
    return result


# ============================================================================
# MAIN OPTIMIZER
# ============================================================================

def optimize_all_facilities(
    safe_buildings: list,
    risk_zones_geojson: dict,
    k_relief: int = DEFAULT_COUNTS["relief_camp"],
    k_hospital: int = DEFAULT_COUNTS["temp_hospital"],
    k_kitchen: int = DEFAULT_COUNTS["community_kitchen"],
) -> dict:
    """
    Run greedy p-median optimization for all three facility types.

    Args:
        safe_buildings:      classified buildings with status='safe'
        risk_zones_geojson:  classified ward GeoJSON (from risk_classification)
        k_*:                 number of facilities to select per type

    Returns:
        {
          "relief_camps":       [facility_dict, ...],
          "temp_hospitals":     [facility_dict, ...],
          "community_kitchens": [facility_dict, ...],
          "coverage":           {type: coverage_dict, ...}
        }
    """
    # Ward demand points: include medium/high/critical wards
    ward_centroids = compute_ward_centroids(
        risk_zones_geojson,
        risk_level_filter=["medium", "high", "critical"]
    )

    if not ward_centroids:
        # Fallback: use all wards
        ward_centroids = compute_ward_centroids(risk_zones_geojson)

    weights = [w["weight"] for w in ward_centroids]

    results = {}
    coverages = {}

    for facility_type, k in [
        ("relief_camp", k_relief),
        ("temp_hospital", k_hospital),
        ("community_kitchen", k_kitchen),
    ]:
        candidates = filter_candidates_by_type(safe_buildings, facility_type)

        if not candidates or not ward_centroids:
            results[facility_type] = []
            coverages[facility_type] = {}
            continue

        dist_matrix = build_distance_matrix(ward_centroids, candidates)
        selected_indices = greedy_p_median(dist_matrix, weights, k)

        selected_facilities = []
        for idx in selected_indices:
            cand = candidates[idx]

            # Compute population served and average distance
            col_distances = dist_matrix[:, idx]
            pop_served = sum(
                w["population"] for i, w in enumerate(ward_centroids)
                if col_distances[i] <= COVERAGE_RADIUS_KM[facility_type]
            )
            if len(ward_centroids) > 0:
                avg_dist = float(np.average(col_distances, weights=weights))
            else:
                avg_dist = 0.0

            selected_facilities.append({
                "name": cand.get("name", "Unknown"),
                "lat": cand["lat"],
                "lon": cand["lon"],
                "osm_type": cand.get("osm_type"),
                "type_label": cand.get("type_label"),
                "facility_role": facility_type,
                "population_served": int(pop_served),
                "avg_distance_km": round(avg_dist, 2),
                "coverage_radius_km": COVERAGE_RADIUS_KM[facility_type],
                "overlapping_ward": cand.get("overlapping_ward"),
                "elevation_m": cand.get("elevation_m"),
            })

        results[facility_type] = selected_facilities
        coverages[facility_type] = compute_coverage(selected_facilities, ward_centroids, facility_type)

    return {
        "relief_camps": results.get("relief_camp", []),
        "temp_hospitals": results.get("temp_hospital", []),
        "community_kitchens": results.get("community_kitchen", []),
        "coverage": coverages,
    }


def facilities_to_geojson(facility_list: list) -> dict:
    """Convert a list of facility dicts to GeoJSON FeatureCollection."""
    features = []
    for f in facility_list:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [f["lon"], f["lat"]]
            },
            "properties": {k: v for k, v in f.items() if k not in ("lat", "lon")}
        })
    return {"type": "FeatureCollection", "features": features}
