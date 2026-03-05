"""
Hydrological Computation Module for Flood DAS
==============================================
Implements the Rational Method for discharge estimation
and flood threshold detection logic.

GHMC Zone 12 Sub-Catchment Parameters:
-----------------------------------------
- Catchment Area (A): 104.3 km² = 104.3 × 10⁶ m²
- Runoff Coefficient (C): 0.85 (highly urbanized)
- Reference: 13 October 2020 Hyderabad Flood Event
- Wards: 23 GHMC Zone 12 wards (Kukatpally, Miyapur, KPHB, etc.)

Rational Method Formula:
-----------------------
Q = C × i × A

Where:
- Q = Peak discharge (m³/s)
- C = Runoff coefficient (dimensionless)
- i = Rainfall intensity (m/s)
- A = Catchment area (m²)

Thresholds (Based on Historical Analysis):
-----------------------------------------
- Heavy Rainfall Alert: > 50 mm/hr
- Flood Risk Alert: Q > 200 m³/s
- Critical Water Level: > 2.5 m
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List
from datetime import datetime


# ============================================================================
# CATCHMENT PARAMETERS - GHMC Zone 12 Sub-Catchment
# ============================================================================

CATCHMENT_AREA_KM2 = 104.3  # km² (actual area from QGIS)
CATCHMENT_AREA_M2 = CATCHMENT_AREA_KM2 * 1e6  # 104.3 × 10⁶ m²
RUNOFF_COEFFICIENT = 0.736  # High urbanization

# Threshold values for alert generation
RAINFALL_THRESHOLD_MM_HR = 50  # mm/hr - Heavy rainfall threshold
DISCHARGE_THRESHOLD_M3S = 200  # m³/s - Flood risk threshold (scaled for area)
WATER_LEVEL_THRESHOLD_M = 2.5  # m - Critical stage threshold


@dataclass
class DischargeResult:
    """Result of discharge calculation with metadata"""
    discharge_m3s: float
    rainfall_intensity_mmhr: float
    runoff_coefficient: float
    catchment_area_km2: float
    timestamp: datetime
    is_flood_risk: bool
    
    
@dataclass
class AlertInfo:
    """Alert information structure"""
    alert_type: str
    message: str
    severity: str  # low, medium, high, critical
    triggered_value: float
    threshold_value: float


def mm_hr_to_m_s(rainfall_mm_hr: float) -> float:
    """
    Convert rainfall intensity from mm/hr to m/s.
    
    Conversion:
    - 1 mm = 0.001 m
    - 1 hr = 3600 s
    - Therefore: mm/hr × (0.001/3600) = m/s
    
    Args:
        rainfall_mm_hr: Rainfall intensity in mm/hr
        
    Returns:
        Rainfall intensity in m/s
    """
    return rainfall_mm_hr * (0.001 / 3600)


def calculate_discharge_rational(
    rainfall_mm_hr: float,
    runoff_coeff: float = RUNOFF_COEFFICIENT,
    area_m2: float = CATCHMENT_AREA_M2
) -> float:
    """
    Calculate peak discharge using the Rational Method.
    
    Q = C × i × A
    
    The Rational Method assumes:
    1. Peak discharge occurs when entire catchment contributes
    2. Rainfall intensity is uniform over the catchment
    3. Runoff coefficient accounts for imperviousness
    
    Args:
        rainfall_mm_hr: Rainfall intensity (mm/hr)
        runoff_coeff: Runoff coefficient (0-1)
        area_m2: Catchment area (m²)
        
    Returns:
        Peak discharge (m³/s)
        
    Example:
        For 50 mm/hr rainfall:
        i = 50 × (0.001/3600) = 1.39 × 10⁻⁵ m/s
        Q = 0.9 × 1.39×10⁻⁵ × 167×10⁶
        Q ≈ 2087 m³/s
    """
    # Convert rainfall intensity to m/s
    intensity_m_s = mm_hr_to_m_s(rainfall_mm_hr)
    
    # Apply Rational Method: Q = C × i × A
    discharge_m3s = runoff_coeff * intensity_m_s * area_m2
    
    return round(discharge_m3s, 2)


def compute_discharge_with_metadata(rainfall_mm_hr: float) -> DischargeResult:
    """
    Compute discharge with full result metadata.
    
    Args:
        rainfall_mm_hr: Rainfall intensity (mm/hr)
        
    Returns:
        DischargeResult with all computation details
    """
    discharge = calculate_discharge_rational(rainfall_mm_hr)
    
    return DischargeResult(
        discharge_m3s=discharge,
        rainfall_intensity_mmhr=rainfall_mm_hr,
        runoff_coefficient=RUNOFF_COEFFICIENT,
        catchment_area_km2=CATCHMENT_AREA_KM2,
        timestamp=datetime.now(),
        is_flood_risk=discharge > DISCHARGE_THRESHOLD_M3S
    )


def check_thresholds(
    rainfall_mm_hr: Optional[float] = None,
    discharge_m3s: Optional[float] = None,
    water_level_m: Optional[float] = None
) -> List[AlertInfo]:
    """
    Check all values against flood thresholds.
    
    Threshold Logic (based on Hyderabad flood analysis):
    
    1. Heavy Rainfall Alert (>50 mm/hr):
       - Indicates intense precipitation
       - Can lead to flash flooding
       - 13 Oct 2020 saw ~200 mm in 6 hours
       
    2. Flood Risk Alert (Q > 300 m³/s):
       - High discharge indicates flooding likely
       - Channel capacity may be exceeded
       
    3. Critical Stage Alert (>2.5 m):
       - Water level approaching danger mark
       - Immediate evacuation may be needed
    
    Args:
        rainfall_mm_hr: Current rainfall intensity
        discharge_m3s: Computed discharge
        water_level_m: Current water level
        
    Returns:
        List of AlertInfo for triggered thresholds
    """
    alerts = []
    
    # Check rainfall threshold
    if rainfall_mm_hr is not None and rainfall_mm_hr > RAINFALL_THRESHOLD_MM_HR:
        severity = _determine_rainfall_severity(rainfall_mm_hr)
        alerts.append(AlertInfo(
            alert_type="Heavy Rainfall Alert",
            message=f"Rainfall intensity {rainfall_mm_hr:.1f} mm/hr exceeds threshold of {RAINFALL_THRESHOLD_MM_HR} mm/hr",
            severity=severity,
            triggered_value=rainfall_mm_hr,
            threshold_value=RAINFALL_THRESHOLD_MM_HR
        ))
    
    # Check discharge threshold
    if discharge_m3s is not None and discharge_m3s > DISCHARGE_THRESHOLD_M3S:
        severity = _determine_discharge_severity(discharge_m3s)
        alerts.append(AlertInfo(
            alert_type="Flood Risk Alert",
            message=f"Discharge {discharge_m3s:.1f} m³/s exceeds flood threshold of {DISCHARGE_THRESHOLD_M3S} m³/s",
            severity=severity,
            triggered_value=discharge_m3s,
            threshold_value=DISCHARGE_THRESHOLD_M3S
        ))
    
    # Check water level threshold
    if water_level_m is not None and water_level_m > WATER_LEVEL_THRESHOLD_M:
        severity = _determine_water_level_severity(water_level_m)
        alerts.append(AlertInfo(
            alert_type="Critical Stage Alert",
            message=f"Water level {water_level_m:.2f} m exceeds danger mark of {WATER_LEVEL_THRESHOLD_M} m",
            severity=severity,
            triggered_value=water_level_m,
            threshold_value=WATER_LEVEL_THRESHOLD_M
        ))
    
    return alerts


def _determine_rainfall_severity(rainfall_mm_hr: float) -> str:
    """
    Determine alert severity based on rainfall intensity.
    
    Classification (IMD categories adapted):
    - 50-100 mm/hr: Medium (Heavy)
    - 100-150 mm/hr: High (Very Heavy)
    - >150 mm/hr: Critical (Extremely Heavy)
    """
    if rainfall_mm_hr > 150:
        return "critical"
    elif rainfall_mm_hr > 100:
        return "high"
    elif rainfall_mm_hr > 50:
        return "medium"
    return "low"


def _determine_discharge_severity(discharge_m3s: float) -> str:
    """
    Determine alert severity based on discharge.
    
    Classification:
    - 300-500 m³/s: Medium
    - 500-1000 m³/s: High
    - >1000 m³/s: Critical
    """
    if discharge_m3s > 1000:
        return "critical"
    elif discharge_m3s > 500:
        return "high"
    elif discharge_m3s > 300:
        return "medium"
    return "low"


def _determine_water_level_severity(level_m: float) -> str:
    """
    Determine alert severity based on water level.
    
    Classification:
    - 2.5-3.0 m: Medium (Danger)
    - 3.0-4.0 m: High (Severe)
    - >4.0 m: Critical (Extreme)
    """
    if level_m > 4.0:
        return "critical"
    elif level_m > 3.0:
        return "high"
    elif level_m > 2.5:
        return "medium"
    return "low"


def get_flood_risk_status(
    rainfall_mm_hr: float,
    water_level_m: float
) -> Tuple[str, str, float]:
    """
    Get overall flood risk status.
    
    Args:
        rainfall_mm_hr: Current rainfall intensity
        water_level_m: Current water level
        
    Returns:
        Tuple of (risk_level, status_message, discharge)
    """
    discharge = calculate_discharge_rational(rainfall_mm_hr)
    
    # Determine overall risk level
    if discharge > 1000 or water_level_m > 4.0:
        risk = "CRITICAL"
        status = "IMMEDIATE FLOOD RISK - EVACUATION RECOMMENDED"
    elif discharge > 500 or water_level_m > 3.0:
        risk = "HIGH"
        status = "HIGH FLOOD RISK - STAY ALERT"
    elif discharge > 300 or water_level_m > 2.5:
        risk = "MEDIUM"
        status = "MODERATE FLOOD RISK - MONITOR CLOSELY"
    elif discharge > 100 or water_level_m > 1.5:
        risk = "LOW"
        status = "LOW FLOOD RISK - NORMAL MONITORING"
    else:
        risk = "NORMAL"
        status = "NO FLOOD RISK - SYSTEM NORMAL"
    
    return risk, status, discharge


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def estimate_time_of_concentration(
    length_km: float = 25,  # Main channel length (estimated)
    slope: float = 0.003   # Average slope (estimated)
) -> float:
    """
    Estimate time of concentration using Kirpich formula.
    
    Tc = 0.0195 × L^0.77 × S^(-0.385)
    
    Where:
    - Tc = Time of concentration (minutes)
    - L = Channel length (m)
    - S = Average slope (m/m)
    
    Returns:
        Time of concentration in hours
    """
    length_m = length_km * 1000
    tc_minutes = 0.0195 * (length_m ** 0.77) * (slope ** -0.385)
    return round(tc_minutes / 60, 2)


def get_catchment_info() -> dict:
    """Return catchment parameters for API response."""
    return {
        "name": "Kukatpally Nala Sub-Catchment",
        "city": "Hyderabad",
        "area_km2": CATCHMENT_AREA_KM2,
        "runoff_coefficient": RUNOFF_COEFFICIENT,
        "rainfall_threshold_mm_hr": RAINFALL_THRESHOLD_MM_HR,
        "discharge_threshold_m3s": DISCHARGE_THRESHOLD_M3S,
        "water_level_threshold_m": WATER_LEVEL_THRESHOLD_M,
        "reference_event": "13 October 2020 Hyderabad Flood"
    }
