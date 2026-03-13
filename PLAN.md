# Flood DAS — Project Plan
## Smart City Flood Risk Zoning & Emergency Response System
### GHMC Zone 12, Kukatpally Nala Sub-Catchment, Hyderabad

---

## Table of Contents

1. [Project Requirements](#1-project-requirements)
2. [What Is Already Built](#2-what-is-already-built)
3. [Available Datasets](#3-available-datasets)
4. [What Needs to Be Built](#4-what-needs-to-be-built)
5. [Architecture Overview](#5-architecture-overview)
6. [Detailed Implementation Plan](#6-detailed-implementation-plan)
7. [New Files Summary](#7-new-files-summary)
8. [Dependencies](#8-dependencies)

---

## 1. Project Requirements

Three requirements drive the new work, unified into a single system:

**Requirement A — Faculty Aim (Flood Risk Zoning):**
> Using historical flood data and environmental variables such as rainfall and river levels, develop a model to classify regions into different flood risk zones.

**Requirement B — Faculty Aim (Emergency Facility Planning):**
> Identify optimal locations for relief camps or emergency hospitals based on accessibility and population distribution.

**Requirement C — Additional Simulation Requirement:**
> Build a system that can simulate conditions in any given area, such as heavy rainfall or flooding. During such events, the system should identify and highlight important buildings such as schools and hospitals, and mark different zones based on their level of vulnerability. It should also indicate suitable locations for setting up relief camps, temporary hospitals, and community kitchens.

**How these fit together:** Requirements A, B, and C are not separate features — they are one unified simulation workflow. The user describes a scenario (area + conditions), the system classifies zone vulnerability, identifies which buildings are at risk and which are safe, then recommends safe buildings as the three types of emergency facilities.

---

## 2. What Is Already Built

### 2.1 Backend (`backend/`)

| File | Status | What It Does |
|---|---|---|
| `main.py` | ✅ Complete | FastAPI server, all endpoints listed below |
| `hydrology.py` | ✅ Complete | Rational Method discharge: Q = C × i × A, threshold checks, severity classification |
| `models.py` | ✅ Complete | SQLAlchemy ORM: `Rainfall`, `WaterLevel`, `DischargeEstimate`, `Alert`, `SpatialLayer` |
| `database.py` | ✅ Complete | PostgreSQL + PostGIS with automatic SQLite fallback |
| `simulator.py` | ✅ Complete | Generates realistic rainfall/water level data with 4 patterns (NORMAL/MODERATE/HEAVY/EXTREME) |

#### Existing API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/add_rainfall` | POST | Ingest rainfall reading, auto-compute discharge, auto-generate alerts |
| `/rainfall` | GET | Retrieve rainfall history with filtering |
| `/rainfall/latest` | GET | Most recent readings from all stations |
| `/add_water_level` | POST | Ingest water level reading, auto-generate alerts |
| `/water_level` | GET | Retrieve water level history |
| `/water_level/latest` | GET | Most recent readings |
| `/discharge` | GET | Computed discharge history |
| `/discharge/latest` | GET | Most recent discharge |
| `/compute_discharge` | POST | Manually compute Q for a given rainfall intensity |
| `/alerts` | GET | Active/historical alerts with severity filter |
| `/alerts/{id}/resolve` | POST | Mark alert as resolved |
| `/alerts/count` | GET | Count by severity |
| `/current_status` | GET | Full system status snapshot (polled every 5s by frontend) |
| `/catchment_info` | GET | Static catchment parameters |
| `/geojson/{layer_path}` | GET | Serve any GeoJSON file from `geojson/` directory |
| `/geojson_layers` | GET | List all available GeoJSON layers |
| `/raster/{name}` | GET | Render raster as PNG image for Leaflet overlay |
| `/raster_metadata/{name}` | GET | Get bounds/CRS metadata for a raster |
| `/history` | GET | Time-series data for charting (configurable hours) |
| `/ws` | WebSocket | Real-time broadcast of sensor updates and alerts |

#### Existing Hydrology (`hydrology.py`)
- `calculate_discharge_rational(rainfall_mm_hr)` — uses global catchment: Area=104.3 km², C=0.736
- `check_thresholds(rainfall, discharge, water_level)` — 3 alert types with severity classification
- `get_flood_risk_status(rainfall, water_level)` → overall risk: NORMAL / LOW / MEDIUM / HIGH / CRITICAL
- `estimate_time_of_concentration()` — Kirpich formula
- Thresholds: Rainfall >50 mm/hr, Discharge >200 m³/s, Water Level >2.5m

#### Existing Simulator (`simulator.py`)
- **4 rain gauges**: KPHB Colony (17.4947°N 78.3996°E), Kukatpally Bus Stand, Miyapur Junction, Moosapet Area
- **3 water level stations**: Upstream/Miyapur, Midstream/KPHB, Downstream/Erragadda
- **4 patterns**: NORMAL (5–15 mm/hr), MODERATE (15–40), HEAVY (40–80), EXTREME (80–200)
- Simulates Oct 13, 2020 Hyderabad flood event (peak ~200 mm in 6 hours)

---

### 2.2 Frontend (`frontend/`)

| File | Status | What It Does |
|---|---|---|
| `index.html` | ✅ Complete | QGIS-style layout: left layer panel, center map, right status panel |
| `app.js` | ✅ Complete | Leaflet map, layer tree, WebSocket client, polling, Chart.js trends |
| `styles.css` | ✅ Complete | Dark theme, responsive grid, risk-level color coding, animations |

#### Existing Frontend Features
- Layer tree with visibility toggles and opacity sliders (QGIS-style)
- 4 basemap options (Dark/Light/OSM/Satellite)
- Real-time metric cards (rainfall, water level, discharge)
- Active alerts panel with badge count
- Mini time-series charts (rainfall, water level — last 20 readings)
- Subbasin click-to-analyze: computes per-basin Q using Rational Method
- WebSocket auto-reconnect
- Map coordinate/zoom/scale display

---

### 2.3 GIS Data (`geojson/`)

| File | Status | What It Contains |
|---|---|---|
| `layers/watershed_boundary.geojson` | ✅ Ready | Single polygon: 104.3 km², C=0.736, Kukatpally Nala extent |
| `layers/ward_boundaries.geojson` | ✅ Ready | 23 GHMC Zone 12 wards (geometry only, no population) |
| `layers/drainage_basins_enriched.geojson` | ✅ Ready | **25 subbasins** with full hydrological metrics (see Section 3) |
| `layers/drainage_order_1.geojson` | ✅ Ready | 85 minor tributaries (Strahler Order 1) |
| `layers/drainage_order_2.geojson` | ✅ Ready | 31 secondary channels (Order 2) |
| `layers/drainage_order_3.geojson` | ✅ Ready | 29 main tributaries (Order 3) |
| `layers/drainage_order_4.geojson` | ✅ Ready | 8 primary channels (Order 4) |
| `layers/flood_risk_high.geojson` | ✅ Ready | 5 pre-drawn high-risk zones (static) |
| `layers/flood_risk_medium.geojson` | ✅ Ready | 2 pre-drawn medium-risk zones (static) |
| `layers/flood_risk_low.geojson` | ✅ Ready | 16 pre-drawn low-risk zones (static) |
| `layers/rain_gauges.geojson` | ✅ Ready | 6 rain gauge locations with elevation_m |
| `layers/water_level_sensors.geojson` | ✅ Ready | 4 sensors with danger_level_m (2.0–2.5m) |
| `flood_zones.geojson` | ✅ Ready | **23 ward-level zones with population_at_risk** (key for facility planning) |
| `watershed.geojson` | ✅ Ready | Watershed polygon with area, runoff_coeff, description |
| `streams.geojson` | ✅ Ready | 153 stream segments (all orders) |
| `sensors.geojson` | ✅ Ready | 8 combined sensor points |

| Raster | Status | What It Contains |
|---|---|---|
| `zone-12-filled-dem.tif` | ✅ Ready | Hydrologically corrected DEM for Zone 12 — used for elevation lookups |
| `zone-12-drainage-basins.tif` | ✅ Ready | Rasterized basin IDs |
| `zone-12-strahler-order.tif` | ✅ Ready | Full Strahler stream order raster |
| `zone-12-strahler-order-threshold-7.tif` | ✅ Ready | Main channels only (threshold ≥7) |
| `P5_PAN_CD_N17_000_E078_000_DEM_30m.tif` | ✅ Ready | Full 30m DEM for Hyderabad region (50 MB) |

---

## 3. Available Datasets

### 3.1 The Two Key Spatial Frameworks

Everything in the new system works across two overlapping spatial frameworks:

**Framework 1 — 25 Drainage Subbasins** (`drainage_basins_enriched.geojson`)
This is the **computation unit**. Each subbasin has physical properties used for risk scoring:

| Property | Description | Use |
|---|---|---|
| `Area_km2` | Subbasin area | Per-basin Rational Method discharge |
| `Avg_Slope_m_m` | Average terrain slope | Runoff speed (steeper = faster = higher risk) |
| `Relief_m` | Elevation range within basin | Flow energy (higher = more risk) |
| `Form_Factor` | Shape index (area / length²) | Flash flood potential (circular = flashier) |
| `Circularity_Ratio` | Basin compactness | Flood response time |
| `Max_Stream_Order` | Highest Strahler order in basin | Drainage convergence |
| `Mouth_Elevation_m` | Outlet elevation | Downstream position (lower = more flood-prone) |
| `Channel_Slope_m_m` | Channel gradient | Flow velocity |
| `Total_Stream_Length_m` | Drainage density proxy | Runoff transmission speed |
| `Watershed_Length_m` | Main flow path length | Time of concentration input |

**Framework 2 — 23 Administrative Wards** (`flood_zones.geojson`)
This is the **output and planning unit**. Each ward has:

| Property | Description | Use |
|---|---|---|
| `name` | Ward name (e.g., "Ward 100 Sanath Nagar") | Display and selection |
| `risk_level` | Current classification: high/medium/low | Will be dynamically updated |
| `flood_depth_potential_m` | Historical flood depth estimate (1.5–2.4m) | Historical vulnerability anchor |
| `population_at_risk` | Population count at risk per ward | Facility planning demand weights |
| `history` | Text describing Oct 2020 flood impact | Context |
| `osm_id` | OpenStreetMap administrative boundary ID | Links to OSM data |

**The critical bridge:** The 25 subbasins and 23 wards use different spatial boundaries. The risk classification model computes scores in subbasin-space, then aggregates to ward-space via area-weighted spatial join.

### 3.2 Population Data

Population is available at ward level from `flood_zones.geojson`:
- Ward 100 Sanath Nagar: 32,581
- Ward 121 Kukatpally: 29,791
- ... (23 wards total)

This is the **demand side** for facility optimization. Ward centroids weighted by `population_at_risk` are the demand points in the p-median problem.

### 3.3 What Is NOT Available (and How We Handle It)

| Missing Data | How We Work Around It |
|---|---|
| Historical flood event records (structured spatial data) | `flood_depth_potential_m` in flood_zones.geojson encodes historical vulnerability — we use this as the historical signal instead of a separate table |
| Road network for travel time | Elevation-penalized Euclidean distance (uphill = harder to reach during floods). Approximation is acceptable for planning purposes. |
| Candidate facility sites layer | Fetched live from OSM Overpass API (schools, hospitals, community centers, places of worship, etc.) |
| Land use / per-zone soil infiltration | Per-basin slope-derived runoff coefficient replaces global C=0.736 for per-subbasin computation |
| Gridded population raster | Ward-level aggregate from flood_zones.geojson is sufficient for p-median |

---

## 4. What Needs to Be Built

### Summary Table

| Feature | Status | Priority |
|---|---|---|
| Real-time sensor monitoring | ✅ Complete | — |
| Threshold-based alert system | ✅ Complete | — |
| Discharge computation (whole watershed) | ✅ Complete | — |
| Web GIS dashboard | ✅ Complete | — |
| Static flood risk zone visualization | ✅ Complete | — |
| **Dynamic flood risk zone classification** | ❌ Missing | High |
| **OSM building identification** | ❌ Missing | High |
| **Building at-risk classification** | ❌ Missing | High |
| **Facility optimization (3 types)** | ❌ Missing | High |
| **Simulation control panel (UI)** | ❌ Missing | High |
| **Simulation result layers on map** | ❌ Missing | High |
| Per-subbasin discharge (Rational Method extended) | ❌ Missing | Medium |
| Elevation lookup from DEM | ❌ Missing | Medium |
| Spatial join: basins ↔ wards | ❌ Missing | Medium |

---

## 5. Architecture Overview

```
╔══════════════════════════════════════════════════════════════════╗
║  USER SELECTS: Area + Rainfall (mm/hr) + Water Level (m)        ║
║  Clicks: [▶ Run Simulation]                                      ║
╚══════════════════════╦═══════════════════════════════════════════╝
                       ║
                  POST /simulate
                       ║
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
risk_classification  osm_client     facility_optimization
       │               │                │
  Score 25 basins   Fetch buildings   Filter safe buildings
  via basin metrics  from Overpass    Run p-median (3 types):
  + sensor inputs    API (cached)       • Relief Camps
       │               │               • Temporary Hospitals
  Aggregate to       Classify each       • Community Kitchens
  23 wards via       building:             │
  spatial join       at_risk | safe       │
       │               │                │
       └───────────────┴────────────────┘
                       │
              Single JSON response
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
  Dynamic Risk     Classified        Recommended
  Zones GeoJSON    Buildings GeoJSON Facilities GeoJSON
  (23 wards,       (red = at_risk,   (3 types,
   new risk_level)  green = safe)     distinct icons)
```

### Existing system is untouched:
The real-time monitoring pipeline (sensor → API → alert → WebSocket → dashboard) continues to run independently. The simulation is a separate analytical layer on top, not a replacement.

---

## 6. Detailed Implementation Plan

### Step 1 — Spatial Join Utility (foundation for everything else)

**File:** `backend/risk_classification.py` (first function)

**What:** Compute which drainage basins overlap which wards, and by what fraction. This is a one-time geometric calculation done on server startup and cached in memory.

**How:**
- Load `drainage_basins_enriched.geojson` and `flood_zones.geojson` using Python's `json` module
- Use `shapely` to create Polygon objects for each basin and ward
- Compute `basin.intersection(ward).area / basin.area` for each basin-ward pair
- Store as dict: `{ward_name: [(basin_id, overlap_fraction), ...]}`

**Result:** A mapping that lets the risk model aggregate basin-level scores up to ward-level scores using area-weighted averaging.

---

### Step 2 — Dynamic Risk Zone Classification

**File:** `backend/risk_classification.py`

**Purpose:** Given rainfall intensity and water level from the simulation inputs, reclassify all 23 wards from LOW/MEDIUM/HIGH/CRITICAL.

#### 2.1 Static Vulnerability Score (computed once on startup)

For each of the 25 subbasins, compute a vulnerability score using normalized basin properties:

| Metric | Weight | Normalization Direction |
|---|---|---|
| `Avg_Slope_m_m` | 25% | Higher slope → higher score |
| `Relief_m` | 20% | Higher relief → higher score |
| `Form_Factor` | 20% | Higher value → higher score (more circular = flashier) |
| `Max_Stream_Order` | 20% | Higher order → higher score |
| `Mouth_Elevation_m` | 15% | Lower elevation → higher score (inverted) |

Each metric is min-max normalized: `(value - min) / (max - min)`. Final score is the weighted sum.

Additionally, the ward's own `flood_depth_potential_m` from `flood_zones.geojson` acts as a historical vulnerability anchor — wards with higher historical depth start with a higher base score.

#### 2.2 Dynamic Hazard Score (computed per simulation run)

For each subbasin:

1. **Per-basin discharge** using Rational Method with basin-specific parameters:
   - `C` = derived from basin slope (higher slope → higher C, scaled around the global 0.736)
   - `A` = basin's own `Area_km2`
   - `i` = simulation rainfall input (mm/hr)
   - `Q_basin = C_basin × i × A_basin`

2. **Estimated channel capacity** = derived from `Max_Stream_Order` × `Channel_Slope_m_m` × cross-section assumption. Higher order channels carry more. This gives a reference capacity to compare against.

3. **Discharge ratio** = `Q_basin / channel_capacity`, capped at 1.0

4. **Water level component** = `input_water_level_m / sensor_danger_level_m` for the nearest sensor. Each basin is assigned to its nearest water level sensor (upstream / midstream / downstream) based on location.

5. **Hazard Score** = `0.6 × discharge_ratio + 0.4 × water_level_ratio`

#### 2.3 Final Ward Risk Score

```
Basin_Risk = 0.4 × Vulnerability + 0.6 × Hazard

Ward_Risk = Σ (basin_overlap_fraction × Basin_Risk) for all basins in ward
           + 0.1 × normalized(flood_depth_potential_m)   ← historical anchor
```

Classification:
- 0.00–0.25 → **LOW** (green, `#27ae60`)
- 0.25–0.50 → **MEDIUM** (amber, `#f39c12`)
- 0.50–0.75 → **HIGH** (red, `#e74c3c`)
- 0.75–1.00 → **CRITICAL** (dark red, `#8e0000`, pulsing animation)

#### 2.4 Functions

```python
# backend/risk_classification.py

def build_basin_ward_mapping() -> dict
    # Loads both GeoJSON files, computes shapely intersections
    # Returns: {ward_name: [(basin_id, overlap_fraction), ...]}
    # Called once on startup

def compute_basin_vulnerability_scores() -> dict
    # Reads drainage_basins_enriched.geojson
    # Returns: {basin_id: vulnerability_score_0_to_1}
    # Called once on startup, result cached

def compute_dynamic_hazard(basin: dict, rainfall_mm: float, water_level_m: float) -> float
    # Per-basin hazard from simulation inputs
    # Returns: hazard_score 0 to 1

def classify_wards(rainfall_mm: float, water_level_m: float, area_filter: str = "all") -> dict
    # Main function — returns updated flood_zones.geojson as dict
    # Updates: risk_level, risk_score, dynamic_discharge_m3s per ward feature
    # area_filter: "all" or ward name for single-ward simulation
```

**New API endpoint:**
```
GET /dynamic_risk_zones?rainfall_mm=80&water_level_m=2.8&area=all
Response: GeoJSON FeatureCollection (flood_zones.geojson with updated risk properties)
```

---

### Step 3 — OSM Building Fetch and Classification

**File:** `backend/osm_client.py`

**Purpose:** Fetch real buildings (schools, hospitals, community centers, etc.) from OpenStreetMap for the simulation area, then classify each as AT-RISK or SAFE.

#### 3.1 Overpass API Query

Bounding box for all of Zone 12: `17.43,78.38,17.54,78.48`

Buildings to fetch (OSM tags):
```
amenity = school           → shelter, temp hospital (fallback), community kitchen
amenity = college          → large grounds for relief camp
amenity = hospital         → existing medical (mark if at-risk, use if safe)
amenity = clinic           → temp hospital candidate
amenity = community_centre → all three facility types
amenity = place_of_worship → community kitchen (used in Indian disaster response)
amenity = marketplace      → community kitchen (water access, central)
leisure = stadium          → large relief camp
leisure = sports_centre    → relief camp
amenity = fire_station     → coordination hub
amenity = police           → coordination hub
```

Query is sent asynchronously using `aiohttp` (already in requirements).

#### 3.2 Caching

OSM data is written to `geojson/cache/osm_buildings.geojson` after the first fetch. Cache is considered valid for 24 hours. This prevents hammering the Overpass API on every simulation run.

#### 3.3 Building Classification

A building is classified as **AT-RISK** if both conditions are true:
1. Its centroid falls within a ward classified HIGH or CRITICAL (spatial intersection using `shapely`)
2. Its elevation (sampled from `zone-12-filled-dem.tif` using `rasterio.sample()`) is less than or equal to the overlapping ward's `flood_depth_potential_m` above the base channel elevation

Otherwise it is classified as **SAFE** — and becomes a candidate for emergency facility recommendation.

#### 3.4 Functions

```python
# backend/osm_client.py

async def fetch_osm_buildings(bbox: tuple) -> list
    # Sends Overpass API query via aiohttp
    # Returns list of dicts: {name, amenity_type, lat, lon, osm_id}

def load_or_fetch_buildings(bbox: tuple) -> list
    # Checks cache age, returns cached data or triggers fresh fetch
    # Writes result to geojson/cache/osm_buildings.geojson

def get_elevation_at_point(lat: float, lon: float, dem_path: str) -> float
    # Uses rasterio.open + dataset.sample() to extract elevation
    # dem_path = "geojson/zone-12-filled-dem.tif"

def classify_buildings(buildings: list, risk_zones_geojson: dict, dem_path: str) -> list
    # For each building, determine at_risk or safe
    # Adds: status ("at_risk"|"safe"), overlapping_ward, ward_risk_level, elevation_m
    # Returns enriched buildings list

def buildings_to_geojson(classified_buildings: list) -> dict
    # Converts to GeoJSON FeatureCollection for API response
```

**New API endpoint:**
```
GET /osm_buildings
Response: GeoJSON FeatureCollection with status and recommended_as properties
```

---

### Step 4 — Emergency Facility Optimization (Three Types)

**File:** `backend/facility_optimization.py`

**Purpose:** From the pool of SAFE buildings, identify the optimal locations for relief camps, temporary hospitals, and community kitchens using a greedy p-median algorithm.

#### 4.1 Demand Side

23 ward centroids computed from `flood_zones.geojson` geometries, weighted by `population_at_risk`. During simulation, only wards classified MEDIUM/HIGH/CRITICAL contribute to demand. CRITICAL wards receive a 2× weight multiplier.

#### 4.2 Supply Side — Eligible Building Types per Facility

| Facility Type | Eligible OSM Types | Rationale |
|---|---|---|
| **Relief Camp** | school, college, stadium, sports_centre, community_centre | Needs large open/indoor area for mass shelter |
| **Temporary Hospital** | hospital (if safe), clinic (if safe), school (fallback), community_centre | Needs room for medical operations, water, electricity |
| **Community Kitchen** | place_of_worship, marketplace, community_centre, school | Needs water access, ground-floor accessibility, central location |

All candidates must be **SAFE** (not in HIGH/CRITICAL zone, elevation above flood threshold).

#### 4.3 Distance Matrix

For each (ward centroid, candidate) pair:
```
base_distance = Euclidean distance (km)
elevation_diff = max(0, candidate_elevation - ward_elevation)   ← uphill penalty
penalty_factor = 1 + 0.1 × elevation_diff_per_10m
weighted_distance = base_distance × penalty_factor
```

This approximates flood-time accessibility: reaching a higher-elevation shelter requires more effort.

#### 4.4 Greedy P-Median Algorithm

For each facility type independently:
1. Build weighted distance matrix: rows = at-risk ward centroids, columns = eligible candidates
2. Apply population weights to each row
3. Greedy selection: in each iteration, pick the candidate that minimizes the total remaining population-weighted distance to the nearest already-selected facility
4. Repeat until K facilities selected (default: K=5 relief camps, K=3 hospitals, K=4 community kitchens)
5. Compute coverage metrics: population within 3km of nearest selected facility

Only `numpy` is needed for this (already in requirements) — no additional optimization library required.

#### 4.5 Functions

```python
# backend/facility_optimization.py

def compute_ward_centroids(flood_zones_geojson: dict) -> list
    # Returns list of {ward_name, lat, lon, population, risk_level}
    # Only includes MEDIUM/HIGH/CRITICAL wards

def filter_candidates_by_type(safe_buildings: list, facility_type: str) -> list
    # Returns eligible buildings for the given facility type

def build_distance_matrix(ward_centroids: list, candidates: list, dem_path: str) -> np.ndarray
    # rows = wards, cols = candidates
    # Values = elevation-penalized Euclidean distance (km)

def greedy_p_median(distance_matrix: np.ndarray, population_weights: list, k: int) -> list
    # Returns list of k candidate indices (optimal facility locations)
    # Pure numpy implementation

def compute_coverage(selected_facilities: list, ward_centroids: list, radius_km: float) -> dict
    # Returns: {ward_name: nearest_facility, distance_km, is_covered}

def optimize_all_facilities(safe_buildings, ward_zones, k_relief=5, k_hospital=3, k_kitchen=4) -> dict
    # Runs greedy_p_median for all 3 types
    # Returns: {relief_camps: [...], temp_hospitals: [...], community_kitchens: [...]}
    # Each entry: {name, lat, lon, osm_type, population_served, avg_distance_km, coverage_pct}
```

**New API endpoints:**
```
GET /candidate_sites?type=relief_camp
Response: GeoJSON of safe filtered candidates for the given type

POST /optimize_facilities
Body: {"k_relief": 5, "k_hospital": 3, "k_kitchen": 4, "rainfall_mm": 80, "water_level_m": 2.8}
Response: {relief_camps: [...], temp_hospitals: [...], community_kitchens: [...]} as GeoJSON
```

---

### Step 5 — Unified Simulation Endpoint

**File:** `backend/main.py` (new endpoint added)

This endpoint wires together Steps 2, 3, and 4 into a single call for the frontend.

```
POST /simulate
Body: {
  "area": "all" | "<ward name>",
  "rainfall_mm": 80.0,
  "water_level_m": 2.8,
  "k_relief": 5,
  "k_hospital": 3,
  "k_kitchen": 4
}

Response: {
  "risk_zones": {GeoJSON — 23 wards with updated risk_level, risk_score, dynamic_discharge_m3s},
  "buildings": {GeoJSON — all OSM buildings with status, recommended_as, elevation_m},
  "facilities": {
    "relief_camps":       [{name, lat, lon, osm_type, population_served, avg_distance_km, coverage_pct}],
    "temp_hospitals":     [{name, lat, lon, osm_type, population_served, avg_distance_km, coverage_pct}],
    "community_kitchens": [{name, lat, lon, osm_type, population_served, avg_distance_km, coverage_pct}]
  },
  "summary": {
    "wards_critical": int,
    "wards_high": int,
    "wards_medium": int,
    "wards_low": int,
    "buildings_at_risk": int,
    "buildings_safe": int,
    "total_population_at_risk": int,
    "coverage": {
      "relief_camp_pct": float,
      "hospital_pct": float,
      "kitchen_pct": float
    }
  }
}
```

---

### Step 6 — Database Addition

**File:** `backend/models.py` (add one table)

```python
class SimulationResult(Base):
    """Stores the most recent simulation run for session persistence"""
    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, index=True)
    rainfall_mm = Column(Float)
    water_level_m = Column(Float)
    area_filter = Column(String(100))
    risk_zones_json = Column(Text)       # serialized GeoJSON
    buildings_json = Column(Text)        # serialized GeoJSON
    facilities_json = Column(Text)       # serialized JSON
    summary_json = Column(Text)          # serialized JSON
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
```

This allows the frontend to reload the last simulation result on page refresh.

**New endpoint:**
```
GET /simulation/latest
Response: most recent SimulationResult row
```

---

### Step 7 — Frontend Simulation Panel

**File:** `frontend/index.html` — add simulation panel HTML to right panel

**File:** `frontend/app.js` — add simulation logic and new layer rendering

**File:** `frontend/styles.css` — add panel and marker styles

#### 7.1 Simulation Control Panel

Inserted in the right panel, above the existing Subbasin Analysis card:

```
┌──────────────────────────────────┐
│ ⚡ FLOOD SIMULATION               │
├──────────────────────────────────┤
│ Area: [ All Zone 12 ▼ ]          │  ← dropdown: "All Zone 12" + 23 ward names
│                                  │
│ [NORMAL] [MODERATE] [HEAVY] [EXTREME]  ← preset buttons
│                                  │
│ Rainfall:  ●──────────── 80mm/hr │  ← slider 0–200
│ Water Level: ●──────────── 2.8m  │  ← slider 0–4
│                                  │
│         [ ▶ Run Simulation ]     │
├──────────────────────────────────┤
│  (results appear here after run) │
│  ⚠  8 wards HIGH/CRITICAL        │
│  🏫 23 buildings at risk          │
│  👥 2,14,000 population           │
├──────────────────────────────────┤
│  Recommended Sites:              │
│  ⛺  5 Relief Camps               │
│  🏥  3 Temporary Hospitals        │
│  🍲  4 Community Kitchens         │
└──────────────────────────────────┘
```

Preset buttons fill the sliders with values matching `simulator.py` patterns:
- **NORMAL**: rainfall=10, water_level=0.8
- **MODERATE**: rainfall=30, water_level=1.5
- **HEAVY**: rainfall=70, water_level=2.2
- **EXTREME**: rainfall=150, water_level=3.5 (replicates Oct 2020)

#### 7.2 New Map Layer Group: "Simulation Results"

Added to the existing layer tree (existing groups unchanged):

| Layer | Style | Description |
|---|---|---|
| Dynamic Risk Zones | Ward polygons colored by new classification | Replaces static flood_risk layers during simulation |
| At-Risk Buildings | Red markers, icon by building type | Schools/hospitals/etc. in flood zones |
| Safe Buildings | Green markers, icon by building type | Safe buildings (can be toggled off) |
| Relief Camps | Blue tent icon, 3km coverage circle | Recommended locations |
| Temporary Hospitals | Red cross icon, 5km coverage circle | Recommended locations |
| Community Kitchens | Orange bowl icon, 2km coverage circle | Recommended locations |

Coverage circles visually show service areas — gaps between circles indicate underserved populations.

#### 7.3 New JavaScript Functions

```javascript
// frontend/app.js additions

function initSimulationPanel()           // bind sliders, presets, run button
function setSimulationPreset(preset)     // fill sliders from preset name
async function runSimulation()           // POST /simulate, handle response
function renderDynamicRiskZones(geojson) // update ward layer colors + popups
function renderClassifiedBuildings(geojson) // draw red/green building markers
function renderFacilityLayer(facilities, type) // draw facility markers + coverage circles
function renderSimulationSummary(summary)  // update summary stats in panel
function clearSimulationLayers()         // remove all simulation result layers
```

Building marker popups show:
```
[🏫 SCHOOL — AT RISK]
Zilla Parishad High School
Ward: 121 Kukatpally (HIGH risk)
Elevation: 537m
Status: Below flood threshold
```

Facility marker popups show:
```
[⛺ RECOMMENDED RELIEF CAMP]
St. Joseph's High School
Population served: 18,420
Avg. distance: 1.8 km
Coverage: 94% within 3km
```

---

## 7. New Files Summary

| File | Action | Purpose |
|---|---|---|
| `backend/risk_classification.py` | **Create** | Spatial join, vulnerability scoring, dynamic ward classification |
| `backend/osm_client.py` | **Create** | OSM Overpass API fetch, building caching, elevation lookup, at-risk classification |
| `backend/facility_optimization.py` | **Create** | Candidate filtering, distance matrix, greedy p-median (3 facility types) |
| `backend/main.py` | **Modify** | Add `/simulate`, `/dynamic_risk_zones`, `/osm_buildings`, `/candidate_sites`, `/optimize_facilities`, `/simulation/latest` |
| `backend/models.py` | **Modify** | Add `SimulationResult` table |
| `frontend/index.html` | **Modify** | Add simulation panel HTML block |
| `frontend/app.js` | **Modify** | Simulation trigger, new layer rendering, preset buttons |
| `frontend/styles.css` | **Modify** | Simulation panel styles, building marker styles, facility icon styles |
| `geojson/cache/` | **Auto-created** | Directory for OSM buildings cache (`osm_buildings.geojson`) |

---

## 8. Dependencies

### Already in `requirements.txt`

| Package | Used For |
|---|---|
| `fastapi` | API framework |
| `rasterio` | Elevation lookup from `zone-12-filled-dem.tif` |
| `numpy` | Distance matrix computation, p-median algorithm |
| `aiohttp` | Async HTTP requests to OSM Overpass API |
| `geoalchemy2` | PostGIS support (also brings in `shapely` as dependency) |
| `sqlalchemy` | ORM |
| `matplotlib` | Raster rendering to PNG |
| `pydantic` | Request/response validation |
| `uvicorn` | ASGI server |

### Need to Add

| Package | Why Needed | Install |
|---|---|---|
| `shapely` | Explicit dependency for point-in-polygon, intersection area, spatial join. Already a transitive dep via geoalchemy2 but should be declared explicitly. | `pip install shapely` |
| `geopandas` | Spatial join between basin and ward GeoJSON geometries (optional — can be replaced with pure shapely loops if keeping dependencies minimal) | `pip install geopandas` |

**Note:** If avoiding `geopandas` to keep dependencies minimal, the spatial join in `risk_classification.py` can be implemented using `shapely` alone with a nested loop over basins and wards. The result is the same; `geopandas` just makes it more concise. The choice is yours.

---

## 9. What Stays Unchanged

The following are **not modified** in any way:

- The real-time sensor monitoring pipeline (POST /add_rainfall, POST /add_water_level)
- The WebSocket broadcast system
- The existing alert generation and threshold logic in `hydrology.py`
- The existing static GIS layers (they remain as a separate layer group and are still visible)
- The existing subbasin click-to-analyze interaction
- The time-series trend charts
- The existing layer tree, opacity controls, basemap selector

The simulation results appear as a **separate, togglable layer group** called "Simulation Results". It does not replace the monitoring view — both can be active simultaneously.

---

*Last updated: 2026-03-13*
