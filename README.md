# 🌊 Flood Data Acquisition System (DAS)

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

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 12+ with PostGIS extension
- Modern web browser

### 1. Clone and Setup

```bash
# Navigate to project directory
cd flood_das

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```sql
-- Connect to PostgreSQL and create database
CREATE DATABASE flood_das;

-- Connect to flood_das and enable PostGIS
\c flood_das
CREATE EXTENSION postgis;
```

Update `backend/database.py` with your database credentials if needed:

```python
DATABASE_URL = "postgresql://username:password@localhost:5432/flood_das"
```

### 3. Start the Backend

```bash
# From flood_das directory
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: `http://localhost:8000`
API Documentation: `http://localhost:8000/docs`

### 4. Open the Dashboard

Simply open `frontend/index.html` in your web browser, or serve it:

```bash
# Serve frontend (optional)
cd frontend
python -m http.server 3000
```

Dashboard will be at: `http://localhost:3000`

### 5. Run Sensor Simulation

```bash
# In a new terminal
cd flood_das
source venv/bin/activate

# Run default simulation (heavy rainfall)
python -m backend.simulator

# Run extreme event simulation
python -m backend.simulator --pattern extreme --duration 15

# Quick demo - single extreme event
python -m backend.simulator --extreme
```

---

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
