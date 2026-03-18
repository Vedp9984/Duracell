#  Urban Flood Monitoring and Response Planning

## Git repo:
https://github.com/vedp9984/Duracell
## Dataset drive link:
 https://drive.google.com/drive/folders/1LE1PaOYxpbxzUULtvMvNBMc1rcWdfMIx?usp=sharing
## 1. System Purpose

It is a geospatial decision-support system for urban flood monitoring, dynamic risk visualization, and emergency facility planning.

The system combines:

- Real-time telemetry ingestion (rainfall and water level)
- Hydrologic thresholding and alerting
- Dynamic flood risk classification by ward
- Building exposure classification (at-risk vs safe)
- Facility optimization for relief camps, temporary hospitals, and community kitchens
- Interactive simulation workflows for planning and demonstration

The current implementation is configured for GHMC Zone 12 (Hyderabad) and can be adapted to other urban catchments with equivalent geospatial inputs.

## 2. What the System Does

At a high level, Flood DAS performs the following pipeline:

1. Collects or simulates rainfall and water-level observations.
2. Computes discharge and threshold violations.
3. Produces active alerts with severity levels.
4. Reclassifies wards into dynamic flood-risk categories.
5. Classifies buildings as at-risk or safe.
6. Optimizes emergency facility placement for affected populations.
7. Renders all outputs in a map-centric operational dashboard.

## 3. Technical Architecture

### 3.1 Backend

- Framework: FastAPI
- ORM: SQLAlchemy
- Database: SQLite by default (`flood_das.db`), with optional PostgreSQL/PostGIS support
- Key modules:
	- `backend/main.py`: API routes and orchestration
	- `backend/hydrology.py`: discharge and threshold logic
	- `backend/risk_classification.py`: dynamic ward risk computation
	- `backend/osm_client.py`: OSM building fetch/classification
	- `backend/facility_optimization.py`: emergency facility optimization
	- `backend/simulator.py`: telemetry simulator

### 3.2 Frontend

- Plain JavaScript, Leaflet-based GIS map UI
- Layered geospatial visualization with simulation controls
- Supports:
	- Manual scenario simulation
	- Auto-run simulation from live telemetry
	- Dynamic alerts panel
	- Layer toggles for risk zones, buildings, and facilities

### 3.3 Data Storage

Runtime tables include rainfall, water levels, discharge estimates, alerts, and simulation results.

Important file:

- `flood_das.db`: local operational state database for development/demo

## 4. Data Used

### 4.1 Geospatial Base Data

From the `geojson/` and `geojson/layers/` folders:

- Watershed boundary
- Ward boundaries
- Drainage network by stream order
- Flood-zone polygons
- Sensor and gauge locations

### 4.2 Dynamic/External Data

- OSM buildings, fetched and cached (`geojson/cache/osm_buildings.geojson`)
- Live or simulated telemetry data through backend endpoints

### 4.3 Derived Data

Generated at runtime:

- Dynamic ward risk levels and scores
- Building exposure classes
- Recommended emergency facility locations
- Active alert states

## 5. Feature Reference

### 5.1 Real-Time Status Dashboard

Displays rainfall, water level, discharge, risk level, and status message.

In simulation mode, the dashboard reflects simulation context:

- `All Zone 12`: global simulated aggregates
- specific ward selected: ward-specific simulated values

### 5.2 Alerts Engine

Alert types include:

- Heavy Rainfall Alert
- Flood Risk Alert
- Critical Stage Alert

The system maintains active alerts from current conditions and resolves alerts when thresholds are no longer exceeded.

### 5.3 Dynamic Flood Simulation

Inputs:

- Rainfall intensity
- Water level
- Area filter (all zones or a selected ward)

Outputs:

- Dynamic risk zones
- At-risk and safe buildings
- Recommended emergency facilities
- Summary statistics

### 5.4 Area-Scoped Simulation Behavior

- `all`: full-zone simulation output across all wards
- specific ward: simulation output constrained to the selected ward context

### 5.5 Building Exposure Classification

Buildings are classified into:

- At-risk buildings
- Safe buildings

Classification uses risk severity and vulnerability logic designed for operational interpretability in urban flood scenarios.

### 5.6 Facility Optimization

Recommends:

- Relief camps
- Temporary hospitals
- Community kitchens

Optimization runs against safe candidate sites and current risk/population context.

### 5.7 Auto-Run Mode

When enabled in the UI:

- latest telemetry values are fed into simulation repeatedly
- map layers and simulation results update continuously

Auto-run does not generate telemetry itself. It uses backend telemetry input (real or simulated).

## 6. Running the System

## 6.1 Prerequisites

- Python 3.10+
- Linux/macOS/Windows shell

## 6.2 Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6.3 Start Backend API

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

API and dashboard endpoints:

- API root/docs: `http://127.0.0.1:8000/docs`
- Frontend UI: `http://127.0.0.1:8000/frontend/index.html`

## 6.4 Start Backend Simulator

Run this in a second terminal while backend is running.

Default heavy pattern:

```bash
source .venv/bin/activate
python backend/simulator.py --api-url http://127.0.0.1:8000
```

Extreme scenario:

```bash
python backend/simulator.py --pattern extreme --duration 30 --interval 10 --api-url http://127.0.0.1:8000
```

Single extreme event trigger:

```bash
python backend/simulator.py --extreme --api-url http://127.0.0.1:8000
```

Notes:

- Use `127.0.0.1` or `localhost` for simulator client calls.
- `0.0.0.0` is a server bind address; client requests should target loopback host.

## 6.5 Frontend Simulation Workflow

1. Open dashboard in browser.
2. Set area (`all` or specific ward).
3. Set rainfall and water-level inputs, or choose a preset.
4. Click `Run Simulation`.
5. Optionally enable `Auto-Run` for continuous updates from telemetry.

## 7. Key API Endpoints

Telemetry ingestion:

- `POST /add_rainfall`
- `POST /add_water_level`

Operational status:

- `GET /current_status`
- `GET /alerts`
- `GET /alerts/count`

Simulation:

- `POST /simulate`
- `GET /dynamic_risk_zones`
- `GET /osm_buildings`

History:

- `GET /history`

## 8. Database and Reset Behavior

`flood_das.db` stores all runtime state.

If deleted:

- historical readings and alerts are removed
- simulation history is removed
- tables are recreated on backend restart

Reset steps:

1. Stop backend.
2. Remove or rename `flood_das.db`.
3. Restart backend.

## 9. Reproducibility Instructions

Use the steps below to reproduce the same workflow reliably across machines.

### 9.1 Environment Freeze

Use Python 3.10+ and install the pinned dependency versions from `requirements.txt`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 9.2 Clean-State Run

To avoid previous telemetry/history affecting results, reset the local database before each run:

```bash
rm -f flood_das.db
```

Then start the API:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 9.3 Fixed Scenario Commands

In a second terminal (with the same virtual environment), run a fixed simulator scenario:

```bash
python backend/simulator.py --pattern extreme --duration 30 --interval 10 --api-url http://127.0.0.1:8000
```

Use the same command, duration, interval, area selection, and UI actions for each run.

### 9.4 What Is Deterministic vs Variable

- Deterministic: code version, dependency versions, API endpoints, and scenario parameters.
- Variable: simulator includes stochastic noise by design, so exact telemetry values can differ slightly run-to-run.

For publication-grade reproducibility, store one run's API outputs (for example `GET /history` and `GET /dynamic_risk_zones`) as fixed reference artifacts and compare future runs against those baselines.

## 10. How the Backend Simulator Works

The simulator is pattern-driven with controlled stochastic variation.

It is not purely random.

- Rainfall follows scenario profiles (normal, moderate, heavy, extreme)
- noise and station-level variation are applied for realism
- water-level response uses lagged rainfall history (upstream/middle/downstream behavior)

This design produces plausible temporal dynamics suitable for dashboard and planning demonstrations.

## 11. Project Structure

```text
backend/
	main.py
	hydrology.py
	risk_classification.py
	osm_client.py
	facility_optimization.py
	simulator.py
	models.py
	database.py

frontend/
	index.html
	app.js
	styles.css

geojson/
	layer_config.json
	flood_zones.geojson
	layers/
	cache/
```
