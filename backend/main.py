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
from .models import Rainfall, WaterLevel, DischargeEstimate, Alert
from . import hydrology

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
    
    for alert_info in alerts:
        alert = Alert(
            alert_type=alert_info.alert_type,
            message=alert_info.message,
            severity=alert_info.severity
        )
        db.add(alert)
    db.commit()
    
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
    
    for alert_info in alerts:
        alert = Alert(
            alert_type=alert_info.alert_type,
            message=alert_info.message,
            severity=alert_info.severity
        )
        db.add(alert)
    db.commit()
    
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
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
