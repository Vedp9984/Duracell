"""
SQLAlchemy Models for Flood DAS
================================
Database models for rainfall, water level, discharge, and alerts.
Uses GeoAlchemy2 for PostGIS spatial column support.

Kukatpally Nala Sub-Catchment Parameters:
- Area: 167 km²
- Runoff Coefficient: 0.9
- Reference Event: 13 Oct 2020 extreme rainfall
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
from sqlalchemy.sql import func
from .database import Base, DATABASE_URL
import enum

# Use String for geometry if using SQLite (for local monitoring without PostGIS)
IS_SQLITE = DATABASE_URL.startswith("sqlite")
if IS_SQLITE:
    GeometryColumn = Text
else:
    from geoalchemy2 import Geometry
    GeometryColumn = Geometry


class SeverityLevel(enum.Enum):
    """Alert severity levels for flood monitoring"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Rainfall(Base):
    """
    Rainfall measurement from monitoring stations.
    
    Stores rainfall data with spatial location for each gauge station.
    Used for Rational Method discharge calculation.
    """
    __tablename__ = "rainfall"
    
    id = Column(Integer, primary_key=True, index=True)
    station_name = Column(String(100), nullable=False, index=True)
    rainfall_mm = Column(Float, nullable=False)  # Rainfall in millimeters
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # PostGIS Point geometry (EPSG:4326 - WGS84)
    geom = Column(GeometryColumn)
    
    def __repr__(self):
        return f"<Rainfall(station={self.station_name}, rainfall={self.rainfall_mm}mm)>"


class WaterLevel(Base):
    """
    Water level measurement from stream gauging stations.
    
    Monitors stage height at key points along Kukatpally Nala.
    Critical threshold: 2.5m
    """
    __tablename__ = "water_level"
    
    id = Column(Integer, primary_key=True, index=True)
    station_name = Column(String(100), nullable=False, index=True)
    level_m = Column(Float, nullable=False)  # Water level in meters
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # PostGIS Point geometry (EPSG:4326 - WGS84)
    geom = Column(GeometryColumn)
    
    def __repr__(self):
        return f"<WaterLevel(station={self.station_name}, level={self.level_m}m)>"


class DischargeEstimate(Base):
    """
    Computed discharge estimates using Rational Method.
    
    Q = C × i × A
    Where:
    - Q = Discharge (m³/s)
    - C = Runoff coefficient (0.9 for Kukatpally urbanized area)
    - i = Rainfall intensity (m/hr)
    - A = Catchment area (167 × 10⁶ m²)
    """
    __tablename__ = "discharge_estimates"
    
    id = Column(Integer, primary_key=True, index=True)
    computed_discharge_m3s = Column(Float, nullable=False)  # Discharge in m³/s
    rainfall_intensity_mmhr = Column(Float, nullable=True)  # Input rainfall intensity
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<Discharge(Q={self.computed_discharge_m3s:.2f} m³/s)>"


class Alert(Base):
    """
    Flood monitoring alerts.
    
    Alert Types:
    - Heavy Rainfall: rainfall > 50 mm/hr
    - Flood Risk: discharge > 300 m³/s
    - Critical Stage: water_level > 2.5m
    """
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="medium")
    is_active = Column(Integer, default=1)  # 1 = active, 0 = resolved
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<Alert(type={self.alert_type}, severity={self.severity})>"


# Spatial layers storage (optional - for dynamic layer management)
class SpatialLayer(Base):
    """
    Storage for GIS layers (watershed, streams, flood zones).
    Allows dynamic layer management through the API.
    """
    __tablename__ = "spatial_layers"
    
    id = Column(Integer, primary_key=True, index=True)
    layer_name = Column(String(100), nullable=False, unique=True)
    layer_type = Column(String(50), nullable=False)  # watershed, stream, flood_zone
    geom = Column(GeometryColumn)  # Generic geometry
    properties = Column(Text)  # JSON properties
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<SpatialLayer(name={self.layer_name}, type={self.layer_type})>"
