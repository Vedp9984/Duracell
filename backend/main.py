"""
Flood Data Acquisition System (DAS) - FastAPI Backend
======================================================
RESTful API for smart-city urban flood monitoring.
Target: Kukatpally Nala Sub-Catchment, Hyderabad

Features:
- Real-time rainfall and water level data ingestion
- Discharge computation using Rational Method
- Automated alert generation
- GeoJSON layer serving
- WebSocket support for live updates

Author: Flood DAS System
Date: 2024
"""

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import json
import asyncio
import os
import io
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from matplotlib import pyplot as plt
from fastapi.responses import Response, FileResponse, JSONResponse

# Local imports
from .database import get_db, engine, Base, SessionLocal
from .models import Rainfall, WaterLevel, DischargeEstimate, Alert, SimulationResult
from . import hydrology
from . import risk_classification
from . import osm_client
from . import facility_optimization

# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class RainfallCreate(BaseModel):
    """Schema for adding rainfall data"""
    station_name: str = Field(..., example="Kukatpally_Rain_Gauge_01")
    rainfall_mm: float = Field(..., ge=0, example=25.5)
    latitude: Optional[float] = Field(None, example=17.4947)
    longitude: Optional[float] = Field(None, example=78.3996)


class WaterLevelCreate(BaseModel):
    """Schema for adding water level data"""
    station_name: str = Field(..., example="Kukatpally_Stage_01")
    level_m: float = Field(..., ge=0, example=1.5)
    latitude: Optional[float] = Field(None, example=17.4850)
    longitude: Optional[float] = Field(None, example=78.4100)


class RainfallResponse(BaseModel):
    """Schema for rainfall response"""
    id: int
    station_name: str
    rainfall_mm: float
    timestamp: datetime
    
    class Config:
        from_attributes = True


class WaterLevelResponse(BaseModel):
    """Schema for water level response"""
    id: int
    station_name: str
    level_m: float
    timestamp: datetime
    
    class Config:
        from_attributes = True


class DischargeResponse(BaseModel):
    """Schema for discharge response"""
    id: int
    computed_discharge_m3s: float
    rainfall_intensity_mmhr: Optional[float]
    timestamp: datetime
    
    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    """Schema for alert response"""
    id: int
    alert_type: str
    message: str
    severity: str
    is_active: int
    timestamp: datetime
    
    class Config:
        from_attributes = True


class CurrentStatus(BaseModel):
    """Schema for current system status"""
    latest_rainfall_mm: float
    latest_water_level_m: float
    latest_discharge_m3s: float
    risk_level: str
    status_message: str
    active_alerts_count: int
    timestamp: datetime


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Flood Data Acquisition System (DAS)",
    description="""
    Smart City Urban Flood Monitoring System for GHMC Zone 12, Hyderabad.
    
    ## Features
    * Real-time sensor data ingestion
    * Rational Method discharge computation
    * Automated flood alerts
    * GIS layer integration (from QGIS GeoPackage data)
    * WebSocket live updates
    
    ## Catchment Parameters
    * Area: 104.3 km² (23 GHMC Zone 12 wards)
    * Runoff Coefficient: 0.85
    * Reference Event: 13 October 2020 Hyderabad Flood
    * Wards: Kukatpally, Miyapur, KPHB, Sanath Nagar, Chintal, etc.
    """,
    version="1.0.0",
    contact={
        "name": "Flood DAS Support",
        "email": "support@flooddas.local"
    }
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


def refresh_active_alerts(db: Session, managed_types: List[str], triggered_alerts: List[hydrology.AlertInfo]) -> None:
    """
    Keep active alerts in sync with latest conditions for the given alert types.

    Strategy:
    1. Resolve all currently active alerts in managed_types.
    2. Insert the alerts that are currently triggered.
    """
    managed_set = set(managed_types or [])
    triggered_by_type = {
        a.alert_type: a
        for a in triggered_alerts
        if a.alert_type in managed_set
    }

    # Resolve alerts of managed types that are no longer triggered.
    if managed_set:
        stale_types = list(managed_set - set(triggered_by_type.keys()))
        if stale_types:
            db.query(Alert).filter(
                Alert.is_active == 1,
                Alert.alert_type.in_(stale_types)
            ).update({Alert.is_active: 0}, synchronize_session=False)

    # Upsert active alerts for currently triggered types.
    for alert_type, alert_info in triggered_by_type.items():
        existing = db.query(Alert).filter(
            Alert.alert_type == alert_type,
            Alert.is_active == 1
        ).order_by(desc(Alert.timestamp)).first()

        if existing:
            existing.message = alert_info.message
            existing.severity = alert_info.severity
            existing.timestamp = datetime.now()
        else:
            db.add(Alert(
                alert_type=alert_info.alert_type,
                message=alert_info.message,
                severity=alert_info.severity,
                is_active=1,
            ))

    db.commit()


def sync_active_alerts_from_latest(db: Session) -> None:
    """Recompute active alerts from latest sensor/discharge values."""
    latest_rainfall = db.query(Rainfall).order_by(desc(Rainfall.timestamp)).first()
    latest_water = db.query(WaterLevel).order_by(desc(WaterLevel.timestamp)).first()
    latest_discharge = db.query(DischargeEstimate).order_by(desc(DischargeEstimate.timestamp)).first()

    rainfall_mm = latest_rainfall.rainfall_mm if latest_rainfall else None
    water_level_m = latest_water.level_m if latest_water else None
    discharge_m3s = latest_discharge.computed_discharge_m3s if latest_discharge else None

    triggered = hydrology.check_thresholds(
        rainfall_mm_hr=rainfall_mm,
        discharge_m3s=discharge_m3s,
        water_level_m=water_level_m,
    )

    refresh_active_alerts(
        db,
        managed_types=["Heavy Rainfall Alert", "Flood Risk Alert", "Critical Stage Alert"],
        triggered_alerts=triggered,
    )


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    print("=" * 60)
    print("🌊 FLOOD DATA ACQUISITION SYSTEM - STARTING")
    print("=" * 60)

    # Create tables
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables initialized")

    # Try to enable PostGIS
    try:
        db = SessionLocal()
        db.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        db.commit()
        db.close()
        print("✓ PostGIS extension enabled")
    except Exception as e:
        print(f"⚠ PostGIS setup note: {e}")

    # Pre-compute static vulnerability scores and basin-ward mapping
    risk_classification.initialize()
    print("✓ Risk classification module initialized")

    print("=" * 60)
    print("🚀 System ready at http://localhost:8000")
    print("📊 API docs at http://localhost:8000/docs")
    print("=" * 60)


# ============================================================================
# API ENDPOINTS
# ============================================================================

from fastapi.responses import RedirectResponse

@app.get("/", tags=["Root"])
async def root():
    """Redirect to dashboard"""
    return RedirectResponse(url="/frontend/index.html")

# Mount Static Files
# Frontend files (HTML, JS, CSS)
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/catchment_info", tags=["Info"])
async def get_catchment_info():
    """Get catchment parameters and thresholds"""
    return hydrology.get_catchment_info()


# ----------------------------------------------------------------------------
# RAINFALL ENDPOINTS
# ----------------------------------------------------------------------------

@app.post("/add_rainfall", response_model=RainfallResponse, tags=["Rainfall"])
async def add_rainfall(data: RainfallCreate, db: Session = Depends(get_db)):
    """
    Add new rainfall measurement.
    
    Automatically:
    - Computes discharge using Rational Method
    - Checks thresholds and generates alerts
    - Broadcasts update via WebSocket
    """
    # Create geometry if coordinates provided
    geom = None
    if data.latitude and data.longitude:
        geom = f"SRID=4326;POINT({data.longitude} {data.latitude})"
    
    # Create rainfall record
    rainfall = Rainfall(
        station_name=data.station_name,
        rainfall_mm=data.rainfall_mm,
        geom=geom
    )
    db.add(rainfall)
    db.commit()
    db.refresh(rainfall)
    
    # Compute discharge (assuming intensity = last hour's rainfall for demo)
    rainfall_intensity = data.rainfall_mm  # Simplified: treating as mm/hr
    discharge = hydrology.calculate_discharge_rational(rainfall_intensity)
    
    # Store discharge estimate
    discharge_record = DischargeEstimate(
        computed_discharge_m3s=discharge,
        rainfall_intensity_mmhr=rainfall_intensity
    )
    db.add(discharge_record)
    db.commit()
    
    # Check thresholds and create alerts
    alerts = hydrology.check_thresholds(
        rainfall_mm_hr=rainfall_intensity,
        discharge_m3s=discharge
    )
    
    refresh_active_alerts(
        db,
        managed_types=["Heavy Rainfall Alert", "Flood Risk Alert"],
        triggered_alerts=alerts
    )
    
    # Broadcast update via WebSocket
    await manager.broadcast({
        "type": "rainfall_update",
        "station": data.station_name,
        "rainfall_mm": data.rainfall_mm,
        "discharge_m3s": discharge,
        "timestamp": datetime.now().isoformat(),
        "alerts": [{"type": a.alert_type, "severity": a.severity} for a in alerts]
    })
    
    return rainfall


@app.get("/rainfall", response_model=List[RainfallResponse], tags=["Rainfall"])
async def get_rainfall(
    limit: int = 100,
    station_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get rainfall data with optional filtering"""
    query = db.query(Rainfall).order_by(desc(Rainfall.timestamp))
    
    if station_name:
        query = query.filter(Rainfall.station_name == station_name)
    
    return query.limit(limit).all()


@app.get("/rainfall/latest", tags=["Rainfall"])
async def get_latest_rainfall(db: Session = Depends(get_db)):
    """Get most recent rainfall readings from all stations"""
    # Get latest reading per station using subquery
    subquery = db.query(
        Rainfall.station_name,
        db.query(Rainfall.timestamp)
        .filter(Rainfall.station_name == Rainfall.station_name)
        .order_by(desc(Rainfall.timestamp))
        .limit(1)
        .correlate(Rainfall)
        .scalar_subquery()
        .label("max_timestamp")
    ).distinct()
    
    latest = db.query(Rainfall).order_by(desc(Rainfall.timestamp)).limit(10).all()
    
    return [{
        "id": r.id,
        "station_name": r.station_name,
        "rainfall_mm": r.rainfall_mm,
        "timestamp": r.timestamp
    } for r in latest]


# ----------------------------------------------------------------------------
# WATER LEVEL ENDPOINTS
# ----------------------------------------------------------------------------

@app.post("/add_water_level", response_model=WaterLevelResponse, tags=["Water Level"])
async def add_water_level(data: WaterLevelCreate, db: Session = Depends(get_db)):
    """
    Add new water level measurement.
    
    Automatically:
    - Checks against critical threshold (2.5m)
    - Generates alerts if threshold exceeded
    - Broadcasts update via WebSocket
    """
    # Create geometry if coordinates provided
    geom = None
    if data.latitude and data.longitude:
        geom = f"SRID=4326;POINT({data.longitude} {data.latitude})"
    
    # Create water level record
    water_level = WaterLevel(
        station_name=data.station_name,
        level_m=data.level_m,
        geom=geom
    )
    db.add(water_level)
    db.commit()
    db.refresh(water_level)
    
    # Check water level threshold
    alerts = hydrology.check_thresholds(water_level_m=data.level_m)
    
    refresh_active_alerts(
        db,
        managed_types=["Critical Stage Alert"],
        triggered_alerts=alerts
    )
    
    # Broadcast update via WebSocket
    await manager.broadcast({
        "type": "water_level_update",
        "station": data.station_name,
        "level_m": data.level_m,
        "timestamp": datetime.now().isoformat(),
        "alerts": [{"type": a.alert_type, "severity": a.severity} for a in alerts]
    })
    
    return water_level


@app.get("/water_level", response_model=List[WaterLevelResponse], tags=["Water Level"])
async def get_water_level(
    limit: int = 100,
    station_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get water level data with optional filtering"""
    query = db.query(WaterLevel).order_by(desc(WaterLevel.timestamp))
    
    if station_name:
        query = query.filter(WaterLevel.station_name == station_name)
    
    return query.limit(limit).all()


@app.get("/water_level/latest", tags=["Water Level"])
async def get_latest_water_level(db: Session = Depends(get_db)):
    """Get most recent water level readings"""
    latest = db.query(WaterLevel).order_by(desc(WaterLevel.timestamp)).limit(10).all()
    
    return [{
        "id": r.id,
        "station_name": r.station_name,
        "level_m": r.level_m,
        "timestamp": r.timestamp
    } for r in latest]


# ----------------------------------------------------------------------------
# DISCHARGE ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/discharge", response_model=List[DischargeResponse], tags=["Discharge"])
async def get_discharge(limit: int = 100, db: Session = Depends(get_db)):
    """Get computed discharge estimates"""
    return db.query(DischargeEstimate).order_by(
        desc(DischargeEstimate.timestamp)
    ).limit(limit).all()


@app.get("/discharge/latest", tags=["Discharge"])
async def get_latest_discharge(db: Session = Depends(get_db)):
    """Get most recent discharge estimate"""
    latest = db.query(DischargeEstimate).order_by(
        desc(DischargeEstimate.timestamp)
    ).first()
    
    if not latest:
        return {"computed_discharge_m3s": 0, "message": "No discharge data available"}
    
    return {
        "computed_discharge_m3s": latest.computed_discharge_m3s,
        "rainfall_intensity_mmhr": latest.rainfall_intensity_mmhr,
        "timestamp": latest.timestamp,
        "is_flood_risk": latest.computed_discharge_m3s > hydrology.DISCHARGE_THRESHOLD_M3S
    }


@app.post("/compute_discharge", tags=["Discharge"])
async def compute_discharge(
    rainfall_mm_hr: float,
    db: Session = Depends(get_db)
):
    """
    Manually compute discharge for given rainfall intensity.
    
    Uses Rational Method: Q = C × i × A
    """
    result = hydrology.compute_discharge_with_metadata(rainfall_mm_hr)
    
    # Store in database
    discharge_record = DischargeEstimate(
        computed_discharge_m3s=result.discharge_m3s,
        rainfall_intensity_mmhr=rainfall_mm_hr
    )
    db.add(discharge_record)
    db.commit()
    
    return {
        "rainfall_intensity_mmhr": rainfall_mm_hr,
        "computed_discharge_m3s": result.discharge_m3s,
        "runoff_coefficient": result.runoff_coefficient,
        "catchment_area_km2": result.catchment_area_km2,
        "is_flood_risk": result.is_flood_risk,
        "threshold_m3s": hydrology.DISCHARGE_THRESHOLD_M3S
    }


# ----------------------------------------------------------------------------
# ALERTS ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/alerts", response_model=List[AlertResponse], tags=["Alerts"])
async def get_alerts(
    limit: int = 50,
    active_only: bool = True,
    severity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get flood alerts with optional filtering"""
    sync_active_alerts_from_latest(db)

    query = db.query(Alert).order_by(desc(Alert.timestamp))
    
    if active_only:
        query = query.filter(Alert.is_active == 1)
    
    if severity:
        query = query.filter(Alert.severity == severity)
    
    return query.limit(limit).all()


@app.post("/alerts/{alert_id}/resolve", tags=["Alerts"])
async def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """Mark an alert as resolved"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_active = 0
    db.commit()
    
    return {"message": f"Alert {alert_id} resolved", "alert_type": alert.alert_type}


@app.get("/alerts/count", tags=["Alerts"])
async def get_alerts_count(db: Session = Depends(get_db)):
    """Get count of active alerts by severity"""
    sync_active_alerts_from_latest(db)

    counts = {
        "total": db.query(Alert).filter(Alert.is_active == 1).count(),
        "critical": db.query(Alert).filter(Alert.is_active == 1, Alert.severity == "critical").count(),
        "high": db.query(Alert).filter(Alert.is_active == 1, Alert.severity == "high").count(),
        "medium": db.query(Alert).filter(Alert.is_active == 1, Alert.severity == "medium").count(),
        "low": db.query(Alert).filter(Alert.is_active == 1, Alert.severity == "low").count()
    }
    return counts


# ----------------------------------------------------------------------------
# CURRENT STATUS ENDPOINT
# ----------------------------------------------------------------------------

@app.get("/current_status", response_model=CurrentStatus, tags=["Status"])
async def get_current_status(db: Session = Depends(get_db)):
    """
    Get comprehensive current system status.
    
    Returns latest sensor readings, computed discharge,
    risk level, and active alerts count.
    """
    # Get latest rainfall
    latest_rainfall = db.query(Rainfall).order_by(desc(Rainfall.timestamp)).first()
    rainfall_mm = latest_rainfall.rainfall_mm if latest_rainfall else 0.0
    
    # Get latest water level
    latest_water = db.query(WaterLevel).order_by(desc(WaterLevel.timestamp)).first()
    water_level_m = latest_water.level_m if latest_water else 0.0
    
    # Get latest discharge
    latest_discharge = db.query(DischargeEstimate).order_by(desc(DischargeEstimate.timestamp)).first()
    discharge_m3s = latest_discharge.computed_discharge_m3s if latest_discharge else 0.0
    
    # Re-sync active alerts to latest values and then count.
    sync_active_alerts_from_latest(db)

    # Get active alerts count
    active_alerts = db.query(Alert).filter(Alert.is_active == 1).count()
    
    # Determine overall risk level
    risk_level, status_message, _ = hydrology.get_flood_risk_status(
        rainfall_mm, water_level_m
    )
    
    return CurrentStatus(
        latest_rainfall_mm=rainfall_mm,
        latest_water_level_m=water_level_m,
        latest_discharge_m3s=discharge_m3s,
        risk_level=risk_level,
        status_message=status_message,
        active_alerts_count=active_alerts,
        timestamp=datetime.now()
    )


# ----------------------------------------------------------------------------
# GEOJSON ENDPOINTS
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# GEOSPATIAL RASTER ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/raster/{raster_name}", tags=["GIS"])
async def get_raster_image(raster_name: str, colormap: str = "terrain"):
    """
    Serve a raster layer as a PNG image for Leaflet ImageOverlay.
    Returns the image data and the geographic bounds in WGS84.
    """
    raster_map = {
        "dem": "backend/raster_data/dem.tif",
        "strahler": "backend/raster_data/strahler.tif",
        "basins": "backend/raster_data/basins.tif",
        "filled_dem": "backend/raster_data/filled_dem.tif"
    }
    
    if raster_name not in raster_map:
        raise HTTPException(status_code=404, detail="Raster not found")
    
    file_path = raster_map[raster_name]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {file_path} not found")

    try:
        with rasterio.open(file_path) as src:
            # Get bounds in 4326
            bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
            
            # Read first band
            data = src.read(1)
            
            # Mask nodata
            if src.nodata is not None:
                data = np.ma.masked_equal(data, src.nodata)
            
            # Normalize and colormap
            plt.figure(figsize=(10, 10))
            plt.imshow(data, cmap=colormap)
            plt.axis('off')
            
            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
            plt.close()
            buf.seek(0)
            
            # Return image with bounds in headers (or consider a separate metadata endpoint)
            # For simplicity, we'll return just the image here and the frontend will 
            # get bounds from a metadata endpoint or we'll embed them.
            # Let's provide a metadata endpoint too.
            return Response(content=buf.getvalue(), media_type="image/png", headers={
                "X-Raster-Bounds": json.dumps(bounds)
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/raster_metadata/{raster_name}", tags=["GIS"])
async def get_raster_metadata(raster_name: str):
    """Get geographic bounds and metadata for a raster resource"""
    raster_map = {
        "dem": "backend/raster_data/dem.tif",
        "strahler": "backend/raster_data/strahler.tif",
        "basins": "backend/raster_data/basins.tif",
        "filled_dem": "backend/raster_data/filled_dem.tif"
    }
    
    if raster_name not in raster_map:
        raise HTTPException(status_code=404, detail="Raster not found")
        
    file_path = raster_map[raster_name]
    try:
        with rasterio.open(file_path) as src:
            bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
            return {
                "name": raster_name,
                "crs": str(src.crs),
                "width": src.width,
                "height": src.height,
                "bounds": {
                    "west": bounds[0],
                    "south": bounds[1],
                    "east": bounds[2],
                    "north": bounds[3]
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/geojson/{layer_path:path}", tags=["GIS"])
async def get_geojson_layer(layer_path: str):
    """
    Serve GeoJSON layers and config files for Web GIS display.
    
    Supports nested paths like:
    - layers/watershed_boundary.geojson
    - layers/drainage_order_4.geojson
    - layer_config.json
    - watershed.geojson (legacy)
    """
    # Get path to geojson directory
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Handle both .geojson and .json extensions
    if not (layer_path.endswith('.geojson') or layer_path.endswith('.json')):
        layer_path = f"{layer_path}.geojson"
    
    geojson_path = os.path.join(base_path, "geojson", layer_path)
    
    if not os.path.exists(geojson_path):
        raise HTTPException(
            status_code=404,
            detail=f"Layer '{layer_path}' not found"
        )
    
    with open(geojson_path, 'r') as f:
        data = json.load(f)
    
    return JSONResponse(content=data)


@app.get("/geojson_layers", tags=["GIS"])
async def list_geojson_layers():
    """List available GeoJSON layers including nested layers"""
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    geojson_dir = os.path.join(base_path, "geojson")
    layers_dir = os.path.join(geojson_dir, "layers")
    
    result = {"root_layers": [], "layer_files": []}
    
    # Root level geojson files
    if os.path.exists(geojson_dir):
        for f in os.listdir(geojson_dir):
            if f.endswith('.geojson'):
                result["root_layers"].append(f.replace('.geojson', ''))
    
    # Layers subfolder
    if os.path.exists(layers_dir):
        for f in os.listdir(layers_dir):
            if f.endswith('.geojson'):
                result["layer_files"].append(f"layers/{f}")
    
    return result


# ----------------------------------------------------------------------------
# WEBSOCKET ENDPOINT
# ----------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Clients receive:
    - rainfall_update
    - water_level_update
    - alert notifications
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for ping/pong
            await websocket.send_json({"type": "pong", "received": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ----------------------------------------------------------------------------
# HISTORICAL DATA ENDPOINT
# ----------------------------------------------------------------------------

@app.get("/history", tags=["History"])
async def get_historical_data(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get historical data for charting"""
    cutoff = datetime.now() - timedelta(hours=hours)
    
    rainfall_data = db.query(Rainfall).filter(
        Rainfall.timestamp >= cutoff
    ).order_by(Rainfall.timestamp).all()
    
    water_level_data = db.query(WaterLevel).filter(
        WaterLevel.timestamp >= cutoff
    ).order_by(WaterLevel.timestamp).all()
    
    discharge_data = db.query(DischargeEstimate).filter(
        DischargeEstimate.timestamp >= cutoff
    ).order_by(DischargeEstimate.timestamp).all()
    
    return {
        "rainfall": [{"timestamp": r.timestamp, "value": r.rainfall_mm} for r in rainfall_data],
        "water_level": [{"timestamp": w.timestamp, "value": w.level_m} for w in water_level_data],
        "discharge": [{"timestamp": d.timestamp, "value": d.computed_discharge_m3s} for d in discharge_data]
    }


# ============================================================================
# SIMULATION PYDANTIC SCHEMAS
# ============================================================================

class SimulateRequest(BaseModel):
    rainfall_mm: float = Field(..., ge=0, le=400, example=80.0, description="Rainfall intensity in mm/hr")
    water_level_m: float = Field(..., ge=0, le=6, example=2.8, description="Water level at sensor in metres")
    area: str = Field("all", example="all", description="'all' or a ward name e.g. 'Ward 100 Sanath Nagar'")
    k_relief: int = Field(5, ge=1, le=15, description="Number of relief camps to recommend")
    k_hospital: int = Field(3, ge=1, le=10, description="Number of temporary hospitals to recommend")
    k_kitchen: int = Field(4, ge=1, le=15, description="Number of community kitchens to recommend")


# ============================================================================
# SIMULATION ENDPOINTS
# ============================================================================

@app.post("/simulate", tags=["Simulation"])
async def run_simulation(request: SimulateRequest, db: Session = Depends(get_db)):
    """
    Master simulation endpoint.

    Given rainfall intensity and water level, this endpoint:
    1. Dynamically reclassifies all 23 Zone 12 wards into LOW/MEDIUM/HIGH/CRITICAL
    2. Fetches (or serves cached) OSM buildings for the zone
    3. Classifies each building as at-risk or safe
    4. Runs greedy p-median optimization to recommend:
       - K relief camp locations
       - K temporary hospital locations
       - K community kitchen locations
    5. Persists the result to the database
    6. Returns everything in a single response
    """
    # Step 1 — Risk zone classification
    risk_zones = risk_classification.classify_wards(
        request.rainfall_mm, request.water_level_m, request.area
    )
    ward_summary = risk_classification.get_ward_summary(risk_zones)

    # Step 2 & 3 — OSM buildings fetch + classification
    try:
        buildings_raw = await osm_client.load_or_fetch_buildings()
    except Exception as e:
        print(f"[simulate] OSM fetch error: {e}")
        buildings_raw = []

    # Ward-focus mode: restrict buildings to selected ward geometry.
    # Only apply when classification actually returned a single ward.
    if len(risk_zones.get("features", [])) == 1:
        buildings_raw = osm_client.filter_buildings_to_risk_zones(buildings_raw, risk_zones)

    classified_buildings = osm_client.classify_buildings(buildings_raw, risk_zones)
    buildings_geojson = osm_client.buildings_to_geojson(classified_buildings)

    safe_buildings = [b for b in classified_buildings if b.get("status") == "safe"]
    at_risk_count = len(classified_buildings) - len(safe_buildings)

    # Step 4 — Facility optimization
    try:
        optimization_result = facility_optimization.optimize_all_facilities(
            safe_buildings=safe_buildings,
            risk_zones_geojson=risk_zones,
            k_relief=request.k_relief,
            k_hospital=request.k_hospital,
            k_kitchen=request.k_kitchen,
        )
    except Exception as e:
        print(f"[simulate] Optimization error: {e}")
        optimization_result = {
            "relief_camps": [], "temp_hospitals": [],
            "community_kitchens": [], "coverage": {}
        }

    # Build coverage summary
    coverage = optimization_result.get("coverage", {})
    relief_cov = coverage.get("relief_camp", {}).get("_summary", {})
    hosp_cov = coverage.get("temp_hospital", {}).get("_summary", {})
    kitchen_cov = coverage.get("community_kitchen", {}).get("_summary", {})

    summary = {
        **ward_summary,
        "buildings_at_risk": at_risk_count,
        "buildings_safe": len(safe_buildings),
        "relief_camps_count": len(optimization_result["relief_camps"]),
        "temp_hospitals_count": len(optimization_result["temp_hospitals"]),
        "community_kitchens_count": len(optimization_result["community_kitchens"]),
        "coverage": {
            "relief_camp_pct": relief_cov.get("coverage_pct", 0),
            "temp_hospital_pct": hosp_cov.get("coverage_pct", 0),
            "community_kitchen_pct": kitchen_cov.get("coverage_pct", 0),
        }
    }

    # Convert facilities to GeoJSON
    facilities_geojson = {
        "relief_camps":       facility_optimization.facilities_to_geojson(optimization_result["relief_camps"]),
        "temp_hospitals":     facility_optimization.facilities_to_geojson(optimization_result["temp_hospitals"]),
        "community_kitchens": facility_optimization.facilities_to_geojson(optimization_result["community_kitchens"]),
    }

    # Step 5 — Persist to DB
    try:
        sim_record = SimulationResult(
            rainfall_mm=request.rainfall_mm,
            water_level_m=request.water_level_m,
            area_filter=request.area,
            k_relief=request.k_relief,
            k_hospital=request.k_hospital,
            k_kitchen=request.k_kitchen,
            risk_zones_json=json.dumps(risk_zones),
            buildings_json=json.dumps(buildings_geojson),
            facilities_json=json.dumps(facilities_geojson),
            summary_json=json.dumps(summary),
        )
        db.add(sim_record)
        db.commit()
    except Exception as e:
        print(f"[simulate] DB persist error: {e}")

    return {
        "risk_zones": risk_zones,
        "buildings": buildings_geojson,
        "facilities": facilities_geojson,
        "summary": summary,
    }


@app.get("/dynamic_risk_zones", tags=["Simulation"])
async def get_dynamic_risk_zones(
    rainfall_mm: float = 0.0,
    water_level_m: float = 0.0,
    area: str = "all"
):
    """
    Return dynamically classified ward risk zones for given conditions.
    Lightweight endpoint — no OSM fetch or optimization.
    """
    result = risk_classification.classify_wards(rainfall_mm, water_level_m, area)
    return JSONResponse(content=result)


@app.get("/osm_buildings", tags=["Simulation"])
async def get_osm_buildings():
    """
    Return cached OSM buildings for Zone 12.
    Triggers a fresh Overpass API fetch if cache is stale (>24h).
    """
    try:
        buildings = await osm_client.load_or_fetch_buildings()
        return osm_client.buildings_to_geojson(buildings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OSM fetch failed: {str(e)}")


@app.get("/candidate_sites", tags=["Simulation"])
async def get_candidate_sites(facility_type: str = "relief_camp"):
    """
    Return safe OSM buildings eligible for a given facility type.
    facility_type: relief_camp | temp_hospital | community_kitchen
    """
    valid_types = {"relief_camp", "temp_hospital", "community_kitchen"}
    if facility_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"facility_type must be one of {valid_types}")

    try:
        buildings = await osm_client.load_or_fetch_buildings()
        # Use a neutral risk zone (all low) just to get safe buildings
        base_zones = risk_classification.classify_wards(0, 0)
        classified = osm_client.classify_buildings(buildings, base_zones)
        candidates = facility_optimization.filter_candidates_by_type(classified, facility_type)
        return osm_client.buildings_to_geojson(candidates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/simulation/latest", tags=["Simulation"])
async def get_latest_simulation(db: Session = Depends(get_db)):
    """Return the most recent simulation result from the database."""
    latest = db.query(SimulationResult).order_by(
        desc(SimulationResult.timestamp)
    ).first()

    if not latest:
        return JSONResponse(content={"message": "No simulation results yet"}, status_code=404)

    return {
        "id": latest.id,
        "rainfall_mm": latest.rainfall_mm,
        "water_level_m": latest.water_level_m,
        "area_filter": latest.area_filter,
        "timestamp": latest.timestamp.isoformat(),
        "risk_zones": json.loads(latest.risk_zones_json) if latest.risk_zones_json else None,
        "buildings": json.loads(latest.buildings_json) if latest.buildings_json else None,
        "facilities": json.loads(latest.facilities_json) if latest.facilities_json else None,
        "summary": json.loads(latest.summary_json) if latest.summary_json else None,
    }


@app.get("/simulation/presets", tags=["Simulation"])
async def get_simulation_presets():
    """Return preset simulation scenarios matching the simulator.py patterns."""
    return [
        {
            "name": "NORMAL",
            "label": "Normal Conditions",
            "rainfall_mm": 10.0,
            "water_level_m": 0.8,
            "description": "Light intermittent rainfall — baseline monitoring"
        },
        {
            "name": "MODERATE",
            "label": "Moderate Rainfall",
            "rainfall_mm": 30.0,
            "water_level_m": 1.5,
            "description": "Steady moderate rainfall — elevated vigilance"
        },
        {
            "name": "HEAVY",
            "label": "Heavy Rainfall",
            "rainfall_mm": 70.0,
            "water_level_m": 2.2,
            "description": "Heavy rain event — prepare relief assets"
        },
        {
            "name": "EXTREME",
            "label": "Extreme Event (Oct 2020)",
            "rainfall_mm": 150.0,
            "water_level_m": 3.5,
            "description": "Replicates 13 Oct 2020 Hyderabad flood — full emergency response"
        },
    ]


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
