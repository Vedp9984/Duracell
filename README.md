

**Smart City Urban Flood Monitoring System for Kukatpally Nala Sub-Catchment, Hyderabad**

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-teal)
![PostGIS](https://img.shields.io/badge/PostGIS-enabled-orange)

---

## 📋 Overview

This project implements a semi-realistic **Flood Data Acquisition System (DAS)** for urban flood monitoring. It demonstrates integration of:

- **Hydrological computation** using the Rational Method
- **Spatial database** with PostgreSQL + PostGIS
- **Real-time sensor data** simulation
- **Web GIS dashboard** with Leaflet.js
- **Automated alert generation**

### Target Catchment: Kukatpally Nala Sub-Catchment

| Parameter | Value |
|-----------|-------|
| Area | 167 km² |
| Runoff Coefficient | 0.9 |
| Land Use | Urban/Mixed |
| Reference Event | 13 October 2020 Hyderabad Flood |

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLOOD DAS ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌───────────┐     ┌───────────────┐     ┌─────────────────┐   │
│   │  Sensor   │────▶│   FastAPI     │────▶│   PostgreSQL    │   │
│   │ Simulator │     │   Backend     │     │   + PostGIS     │   │
│   └───────────┘     └───────────────┘     └─────────────────┘   │
│                            │                       │            │
│                            │                       │            │
│                            ▼                       │            │
│                    ┌───────────────┐               │            │
│                    │  Hydrology    │               │            │
│                    │  Engine       │               │            │
│                    │ (Rational     │               │            │
│                    │  Method)      │               │            │
│                    └───────────────┘               │            │
│                            │                       │            │
│                            ▼                       │            │
│                    ┌───────────────┐               │            │
│                    │    Alert      │               │            │
│                    │   System      │               │            │
│                    └───────────────┘               │            │
│                            │                       │            │
│                            ▼                       ▼            │
│                    ┌─────────────────────────────────┐          │
│                    │      Web GIS Dashboard          │          │
│                    │  (Leaflet + Chart.js)          │          │
│                    └─────────────────────────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
flood_das/
│
├── backend/
│   ├── __init__.py         # Package initialization
│   ├── main.py             # FastAPI application & endpoints
│   ├── models.py           # SQLAlchemy database models
│   ├── database.py         # Database configuration
│   ├── hydrology.py        # Rational Method computations
│   └── simulator.py        # Sensor data simulation engine
│
├── frontend/
│   ├── index.html          # Dashboard HTML
│   ├── styles.css          # Dashboard styling
│   └── app.js              # Dashboard JavaScript
│
├── geojson/
│   ├── watershed.geojson   # Catchment boundary
│   ├── streams.geojson     # Stream network
│   ├── flood_zones.geojson # Flood risk zones
│   └── sensors.geojson     # Sensor locations
│
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

---

### Core Components
- **Spatial Processing (`extract_gpkg.py`, `create_layers.py`, `process_basins.py`)**: Python utilities that process raw QGIS `.gpkg` and shapefiles. They strip 3D geometries, apply CRS transformations (to `EPSG:4326`), enrich them with historical flood data/characteristics, and output static `.geojson` layer structures into the `geojson/` folder.
- **Backend API (`backend/main.py`)**: A FastAPI application providing REST endpoints for real-time sensor metrics injection and fetching. Calculates discharge thresholds via the Rational Method. Provides a WebSocket (`/ws`) implementation that pushes live data and alerts to connected UI clients.
- **Simulation Engine (`backend/simulator.py`)**: Background script to iteratively ping the REST endpoints with faked precipitation / water stage events to load-test the application and trigger threshold alerts on the UI.
- **Frontend SPA (`create_frontend.py`, `frontend/`)**: Generates an HTML/JS/CSS single-page application wrapping `Leaflet.js` and `Chart.js`. The UI pulls generated GeoJSONs locally, plots risk maps and hydrological matrices on a canvas, listens to the WebSocket for live events, and renders notifications.

### Data Storage
The backend uses SQLAlchemy. While built for PostGIS, the default configuration falls back directly to an embedded SQLite database (`flood_das.db`) storing sensor telemetry, discharge estimates, alerts, and feature geometries as generic WKT format text.

---

## 🚀 How to Run locally

### Prerequisites
- Python 3.9+

### 1. Clone and Setup Environment

```bash
git clone <repository_url>
cd flood_das

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Backend API

The system automatically initializes an SQLite database fallback out-of-the-box (`flood_das.db`).

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
- API Docs: `http://localhost:8000/docs`
- UI Dashboard: **Automatically served at `http://localhost:8000`**

### 3. Run Sensor Simulation (Separate Terminal)

To load-test the application and see the dashboard react, we use a simulation script. This script acts as virtual weather/water sensors, programmatically firing HTTP POST requests via the `aiohttp` library to the Backend's `/add_rainfall` and `/add_water_level` endpoints.

This simulates:
1. **Rainfall Events**: Ramping up rainfall intensity (mm/hr) in synthetic rain gauges. 
2. **Rising Water Levels**: Simulating Nala stream stages rising linearly or exponentially depending on the profile.
3. **Triggering the Rules Engine**: Driving the hydrological equations (Rational Method) past safe thresholds to automatically trigger WebSockets Alerts, which the UI receives and turns into red "Critical Risk" visual warnings.

```bash
source .venv/bin/activate
# Standard run (gradual rain buildup)
python -m backend.simulator
# Extreme storm burst scenario (fast flash flood simulation)
python -m backend.simulator --pattern extreme --duration 15
```

## 💧 Hydrological Logic

### Rational Method

The system uses the **Rational Method** for peak discharge estimation:

```
Q = C × i × A
```

Where:
- **Q** = Peak discharge (m³/s)
- **C** = Runoff coefficient (0.9 for highly urbanized catchment)
- **i** = Rainfall intensity (m/s)
- **A** = Catchment area (167 × 10⁶ m²)

### Threshold Alert Logic

| Condition | Alert Type | Severity |
|-----------|------------|----------|
| Rainfall > 50 mm/hr | Heavy Rainfall Alert | Medium-Critical |
| Discharge > 300 m³/s | Flood Risk Alert | Medium-Critical |
| Water Level > 2.5 m | Critical Stage Alert | Medium-Critical |

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | System information |
| GET | `/catchment_info` | Catchment parameters |
| POST | `/add_rainfall` | Add rainfall data |
| POST | `/add_water_level` | Add water level data |
| GET | `/current_status` | Current system status |
| GET | `/alerts` | Active alerts |
| GET | `/discharge` | Discharge estimates |
| GET | `/geojson/{layer}` | GeoJSON layers |
| WS | `/ws` | WebSocket for real-time updates |

Full API documentation available at `/docs` when server is running.

---

## 🗺️ GIS Layers

The dashboard displays the following spatial layers:

1. **Watershed Boundary** - Kukatpally Nala catchment extent
2. **Stream Network** - Main channel and tributaries
3. **Flood Risk Zones** - High/Medium/Low risk areas
4. **Sensor Locations** - Rain gauges and water level sensors

Layers can be toggled using the map control buttons.

---

## 📊 Dashboard Features

- **Real-time map** with GIS overlay
- **Live metrics** display (rainfall, water level, discharge)
- **Risk level indicator** with color coding
- **Alert panel** with severity classification
- **Time-series charts** for trend visualization
- **WebSocket** support for instant updates

---

## 🔧 Configuration

### Environment Variables

```bash
# Database URL
DATABASE_URL=postgresql://user:pass@localhost:5432/flood_das

# API Port
PORT=8000
```

### Threshold Configuration

Edit `backend/hydrology.py` to adjust thresholds:

```python
RAINFALL_THRESHOLD_MM_HR = 50    # mm/hr
DISCHARGE_THRESHOLD_M3S = 300   # m³/s
WATER_LEVEL_THRESHOLD_M = 2.5   # meters
```

---

## 🧪 Testing the System

### 1. Basic API Test

```bash
curl http://localhost:8000/current_status
```

### 2. Add Rainfall Data

```bash
curl -X POST "http://localhost:8000/add_rainfall" \
  -H "Content-Type: application/json" \
  -d '{"station_name": "Test_Station", "rainfall_mm": 75.5, "latitude": 17.49, "longitude": 78.40}'
```

### 3. Trigger Alerts

```bash
# Simulate extreme rainfall
python -m backend.simulator --extreme
```

---

## 📚 References

- **Rational Method**: Urban Hydrology for Small Watersheds (TR-55), USDA-NRCS
- **October 2020 Event**: Hyderabad recorded ~200mm rainfall in 6 hours
- **PostGIS**: https://postgis.net/
- **Leaflet.js**: https://leafletjs.com/
- **Chart.js**: https://www.chartjs.org/

---

## 👨‍💻 Author
Team 4 - Hydrological Informatics Project

---

## 🙏 Acknowledgments

- India Meteorological Department (IMD) for rainfall data references
- Greater Hyderabad Municipal Corporation (GHMC) for urban drainage insights
- OpenStreetMap contributors for basemap data
