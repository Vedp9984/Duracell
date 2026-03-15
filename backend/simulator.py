"""
Sensor Simulation Engine for Flood DAS
=======================================
Generates realistic rainfall and water level data
to demonstrate real-time flood monitoring capabilities.

Simulates the 13 October 2020 Hyderabad Flood Event pattern:
- Initial moderate rainfall
- Sudden extreme rainfall spike (peak ~200mm/6hr)
- Gradual recession

Sensor Network Configuration:
- 4 Rain gauge stations across Kukatpally catchment
- 3 Water level monitoring stations along Kukatpally Nala
"""

import asyncio
import aiohttp
import random
import math
from datetime import datetime, timedelta
from typing import List, Tuple
import argparse
import sys
from urllib.parse import urlparse

# API Configuration
API_BASE_URL = "http://localhost:8000"


def normalize_api_url(api_url: str) -> str:
    """Normalize API URL for client usage.

    Notes:
    - `0.0.0.0` is a bind address for servers, not a routable client target.
      We map it to `127.0.0.1` for local simulation clients.
    - Accepts values with or without scheme.
    """
    raw = (api_url or "").strip()
    if not raw:
        return API_BASE_URL

    if "://" not in raw:
        raw = f"http://{raw}"

    parsed = urlparse(raw)
    host = parsed.hostname or "localhost"
    if host == "0.0.0.0":
        host = "127.0.0.1"

    scheme = parsed.scheme or "http"
    netloc = host
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"

    return f"{scheme}://{netloc}"

# ============================================================================
# SENSOR CONFIGURATION
# ============================================================================

# Rain gauge stations with coordinates (Kukatpally area)
RAIN_GAUGE_STATIONS = [
    {"name": "Kukatpally_Rain_01", "lat": 17.4947, "lon": 78.3996, "description": "KPHB Colony"},
    {"name": "Kukatpally_Rain_02", "lat": 17.4850, "lon": 78.4150, "description": "Kukatpally Bus Stand"},
    {"name": "Kukatpally_Rain_03", "lat": 17.5050, "lon": 78.3850, "description": "Miyapur Junction"},
    {"name": "Kukatpally_Rain_04", "lat": 17.4750, "lon": 78.4250, "description": "Moosapet Area"},
]

# Water level stations along Kukatpally Nala
WATER_LEVEL_STATIONS = [
    {"name": "Nala_Stage_01_Upstream", "lat": 17.5100, "lon": 78.3800, "description": "Upstream - Miyapur"},
    {"name": "Nala_Stage_02_Middle", "lat": 17.4900, "lon": 78.4000, "description": "Mid-stream - KPHB"},
    {"name": "Nala_Stage_03_Downstream", "lat": 17.4700, "lon": 78.4200, "description": "Downstream - Erragadda"},
]


# ============================================================================
# SIMULATION PATTERNS
# ============================================================================

class RainfallPattern:
    """
    Generates realistic rainfall patterns based on historical events.
    
    Pattern Types:
    1. NORMAL: Light intermittent rainfall (5-15 mm/hr)
    2. MODERATE: Steady moderate rainfall (15-40 mm/hr)
    3. HEAVY: Heavy rainfall event (40-80 mm/hr)
    4. EXTREME: Extreme event like 13 Oct 2020 (80-200 mm/hr)
    """
    
    NORMAL = "normal"
    MODERATE = "moderate"
    HEAVY = "heavy"
    EXTREME = "extreme"
    
    @staticmethod
    def generate_rainfall(pattern: str, time_step: int, total_steps: int) -> float:
        """
        Generate rainfall intensity based on pattern and time step.
        
        Args:
            pattern: Rainfall pattern type
            time_step: Current simulation step
            total_steps: Total simulation steps
            
        Returns:
            Rainfall intensity in mm/hr
        """
        # Progress through event (0 to 1)
        progress = time_step / total_steps
        
        # Add natural variability
        noise = random.gauss(1.0, 0.15)
        
        if pattern == RainfallPattern.NORMAL:
            # Light rainfall with random fluctuations
            base = 5 + 10 * math.sin(progress * math.pi)
            return max(0, base * noise)
            
        elif pattern == RainfallPattern.MODERATE:
            # Steady moderate rainfall
            base = 20 + 20 * math.sin(progress * math.pi)
            return max(0, base * noise)
            
        elif pattern == RainfallPattern.HEAVY:
            # Heavy rainfall with peak in middle
            base = 40 + 40 * math.sin(progress * math.pi)
            return max(0, base * noise)
            
        elif pattern == RainfallPattern.EXTREME:
            # Extreme event - sharp peak simulating 13 Oct 2020
            # Builds up, peaks, then slowly recedes
            if progress < 0.3:
                # Building phase
                base = 20 + 60 * (progress / 0.3)
            elif progress < 0.5:
                # Peak phase
                base = 80 + 120 * ((progress - 0.3) / 0.2)
            else:
                # Recession phase
                base = 200 * math.exp(-3 * (progress - 0.5))
            return max(0, base * noise)
        
        return 0


class WaterLevelSimulator:
    """
    Simulates water level response to rainfall.
    
    Uses simplified hydrological lag:
    - Upstream responds faster
    - Downstream has delayed, attenuated response
    """
    
    def __init__(self):
        self.base_levels = {
            "Nala_Stage_01_Upstream": 0.5,    # Base level at upstream
            "Nala_Stage_02_Middle": 0.8,       # Base level at middle
            "Nala_Stage_03_Downstream": 1.0,   # Base level at downstream
        }
        self.rainfall_history: List[float] = []
        
    def update_level(
        self,
        station_name: str,
        current_rainfall: float,
        position: str = "middle"
    ) -> float:
        """
        Calculate water level based on rainfall history.
        
        Args:
            station_name: Station identifier
            current_rainfall: Current rainfall intensity (mm/hr)
            position: upstream/middle/downstream
            
        Returns:
            Water level in meters
        """
        # Add to rainfall history
        self.rainfall_history.append(current_rainfall)
        
        # Keep last 30 time steps (simulate lag)
        if len(self.rainfall_history) > 30:
            self.rainfall_history.pop(0)
        
        # Get base level
        base = self.base_levels.get(station_name, 0.8)
        
        # Calculate response based on position
        if "Upstream" in station_name:
            # Upstream responds to recent rainfall
            avg_rainfall = sum(self.rainfall_history[-5:]) / max(len(self.rainfall_history[-5:]), 1)
            response = avg_rainfall * 0.03  # Response factor
            
        elif "Middle" in station_name:
            # Middle section has medium lag
            window = self.rainfall_history[-15:-5] if len(self.rainfall_history) > 15 else self.rainfall_history
            avg_rainfall = sum(window) / max(len(window), 1)
            response = avg_rainfall * 0.035
            
        else:  # Downstream
            # Downstream has longest lag, attenuated response
            window = self.rainfall_history[:-10] if len(self.rainfall_history) > 10 else self.rainfall_history
            avg_rainfall = sum(window) / max(len(window), 1)
            response = avg_rainfall * 0.04
        
        # Add noise
        noise = random.gauss(1.0, 0.05)
        level = base + response * noise
        
        return round(level, 3)


# ============================================================================
# DATA SUBMISSION
# ============================================================================

async def submit_rainfall(
    session: aiohttp.ClientSession,
    station: dict,
    rainfall_mm: float
) -> bool:
    """Submit rainfall data to API"""
    try:
        payload = {
            "station_name": station["name"],
            "rainfall_mm": round(rainfall_mm, 2),
            "latitude": station["lat"],
            "longitude": station["lon"]
        }
        
        async with session.post(
            f"{API_BASE_URL}/add_rainfall",
            json=payload
        ) as response:
            if response.status == 200:
                print(f"  ✓ Rainfall: {station['name']} = {rainfall_mm:.1f} mm/hr")
                return True
            else:
                print(f"  ✗ Failed: {station['name']} - {response.status}")
                return False
    except Exception as e:
        print(f"  ✗ Error submitting rainfall: {e}")
        return False


async def submit_water_level(
    session: aiohttp.ClientSession,
    station: dict,
    level_m: float
) -> bool:
    """Submit water level data to API"""
    try:
        payload = {
            "station_name": station["name"],
            "level_m": round(level_m, 3),
            "latitude": station["lat"],
            "longitude": station["lon"]
        }
        
        async with session.post(
            f"{API_BASE_URL}/add_water_level",
            json=payload
        ) as response:
            if response.status == 200:
                print(f"  ✓ Water Level: {station['name']} = {level_m:.2f} m")
                return True
            else:
                print(f"  ✗ Failed: {station['name']} - {response.status}")
                return False
    except Exception as e:
        print(f"  ✗ Error submitting water level: {e}")
        return False


# ============================================================================
# MAIN SIMULATION LOOP
# ============================================================================

async def run_simulation(
    pattern: str = RainfallPattern.HEAVY,
    duration_minutes: int = 30,
    interval_seconds: int = 10,
    api_url: str = API_BASE_URL
):
    """
    Run the sensor simulation.
    
    Args:
        pattern: Rainfall pattern to simulate
        duration_minutes: Total simulation duration
        interval_seconds: Time between sensor readings
        api_url: API base URL
    """
    global API_BASE_URL
    API_BASE_URL = normalize_api_url(api_url)
    
    total_steps = (duration_minutes * 60) // interval_seconds
    water_sim = WaterLevelSimulator()
    
    print("=" * 70)
    print("🌧️  FLOOD DAS - SENSOR SIMULATION ENGINE")
    print("=" * 70)
    print(f"Pattern: {pattern.upper()}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"Interval: {interval_seconds} seconds")
    print(f"API URL: {API_BASE_URL}")
    print(f"Rain Gauges: {len(RAIN_GAUGE_STATIONS)}")
    print(f"Stage Monitors: {len(WATER_LEVEL_STATIONS)}")
    print("=" * 70)
    print()
    
    async with aiohttp.ClientSession() as session:
        # Check API connectivity
        try:
            async with session.get(f"{API_BASE_URL}/") as response:
                if response.status != 200:
                    print("❌ Cannot connect to API. Is the server running?")
                    return
                print("✓ Connected to Flood DAS API")
        except Exception as e:
            print(f"❌ API connection failed: {e}")
            print("Please start the API server first: uvicorn backend.main:app --reload")
            return
        
        print("\n🚀 Starting simulation...\n")
        
        for step in range(total_steps):
            timestamp = datetime.now()
            progress = (step + 1) / total_steps * 100
            
            print(f"[{timestamp.strftime('%H:%M:%S')}] Step {step + 1}/{total_steps} ({progress:.1f}%)")
            
            # Generate base rainfall for this timestep
            base_rainfall = RainfallPattern.generate_rainfall(pattern, step, total_steps)
            
            # Submit rainfall for each station (with spatial variation)
            for i, station in enumerate(RAIN_GAUGE_STATIONS):
                # Add spatial variation (±20%)
                variation = random.uniform(0.8, 1.2)
                rainfall = base_rainfall * variation
                await submit_rainfall(session, station, rainfall)
            
            # Update and submit water levels
            for station in WATER_LEVEL_STATIONS:
                level = water_sim.update_level(station["name"], base_rainfall)
                await submit_water_level(session, station, level)
            
            print()
            
            # Wait for next interval (if not last step)
            if step < total_steps - 1:
                await asyncio.sleep(interval_seconds)
    
    print("=" * 70)
    print("✅ SIMULATION COMPLETE")
    print("=" * 70)


async def run_single_extreme_event(api_url: str = API_BASE_URL):
    """
    Simulate a single extreme rainfall event.
    Useful for quick demonstration of alert system.
    """
    print("\n⚡ SIMULATING EXTREME RAINFALL EVENT")
    print("=" * 50)

    global API_BASE_URL
    API_BASE_URL = normalize_api_url(api_url)
    
    async with aiohttp.ClientSession() as session:
        # Submit single extreme rainfall reading
        station = RAIN_GAUGE_STATIONS[0]
        extreme_rainfall = 150.0  # mm/hr - extreme
        
        payload = {
            "station_name": station["name"],
            "rainfall_mm": extreme_rainfall,
            "latitude": station["lat"],
            "longitude": station["lon"]
        }
        
        async with session.post(f"{API_BASE_URL}/add_rainfall", json=payload) as response:
            if response.status == 200:
                print(f"✓ Extreme rainfall submitted: {extreme_rainfall} mm/hr")
                result = await response.json()
                print(f"  Record ID: {result.get('id')}")
            else:
                print(f"✗ Failed: {response.status}")
        
        # Submit high water level
        wl_station = WATER_LEVEL_STATIONS[1]
        critical_level = 3.5  # meters - above critical threshold
        
        payload = {
            "station_name": wl_station["name"],
            "level_m": critical_level,
            "latitude": wl_station["lat"],
            "longitude": wl_station["lon"]
        }
        
        async with session.post(f"{API_BASE_URL}/add_water_level", json=payload) as response:
            if response.status == 200:
                print(f"✓ Critical water level submitted: {critical_level} m")
            else:
                print(f"✗ Failed: {response.status}")
        
        # Check alerts
        async with session.get(f"{API_BASE_URL}/alerts?limit=5") as response:
            if response.status == 200:
                alerts = await response.json()
                print(f"\n📢 Active Alerts ({len(alerts)}):")
                for alert in alerts:
                    print(f"  - [{alert['severity'].upper()}] {alert['alert_type']}")
    
    print("\n" + "=" * 50)


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Command-line interface for simulator"""
    parser = argparse.ArgumentParser(
        description="Flood DAS Sensor Simulation Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python simulator.py                    # Default heavy rainfall simulation
  python simulator.py --pattern extreme  # Simulate 13 Oct 2020 type event
  python simulator.py --pattern normal --duration 60  # Normal rainfall, 1 hour
  python simulator.py --extreme         # Single extreme event for demo
        """
    )
    
    parser.add_argument(
        "--pattern",
        choices=["normal", "moderate", "heavy", "extreme"],
        default="heavy",
        help="Rainfall pattern to simulate (default: heavy)"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Simulation duration in minutes (default: 30)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Interval between readings in seconds (default: 10)"
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--extreme",
        action="store_true",
        help="Run single extreme event simulation for quick demo"
    )
    
    args = parser.parse_args()
    
    if args.extreme:
        asyncio.run(run_single_extreme_event(api_url=args.api_url))
    else:
        asyncio.run(run_simulation(
            pattern=args.pattern,
            duration_minutes=args.duration,
            interval_seconds=args.interval,
            api_url=args.api_url
        ))


if __name__ == "__main__":
    main()
