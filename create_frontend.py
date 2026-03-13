#!/usr/bin/env python3
"""
Create new QGIS-like frontend files
"""
import os

FRONTEND_PATH = '/home/ved_maurya/college/sem6/Hydro_informatics/flood_das/frontend'

# HTML Content
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flood DAS - GHMC Zone 12 Monitoring</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Orbitron:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header class="dashboard-header">
        <div class="header-left">
            <i class="fas fa-water header-icon"></i>
            <div class="header-title">
                <h1>FLOOD DAS</h1>
                <p>GHMC Zone 12 Flood Monitoring</p>
            </div>
        </div>
        <div class="header-center">
            <div class="location-info">
                <i class="fas fa-map-marker-alt"></i>
                <span>GHMC Zone 12 | Hyderabad</span>
            </div>
        </div>
        <div class="header-right">
            <div class="datetime">
                <div class="date" id="current-date"></div>
                <div class="time" id="current-time"></div>
            </div>
            <div class="connection-status" id="connection-status">
                <i class="fas fa-circle"></i>
                <span>Connecting...</span>
            </div>
        </div>
    </header>

    <div class="dashboard-container">
        <!-- Left Panel - QGIS Layer Tree -->
        <aside class="left-panel">
            <div class="panel-section">
                <div class="panel-header">
                    <i class="fas fa-layer-group"></i>
                    <span>LAYERS</span>
                    <div class="panel-actions">
                        <button class="panel-btn" id="btn-expand-all" title="Expand All"><i class="fas fa-expand-alt"></i></button>
                        <button class="panel-btn" id="btn-collapse-all" title="Collapse All"><i class="fas fa-compress-alt"></i></button>
                    </div>
                </div>
                <div class="layer-tree" id="layer-tree">
                    <div class="loading-layers"><i class="fas fa-spinner fa-spin"></i> Loading layers...</div>
                </div>
            </div>
            
            <div class="panel-section">
                <div class="panel-header collapsible expanded" data-target="basemap-content">
                    <i class="fas fa-map"></i>
                    <span>BASEMAP</span>
                    <i class="fas fa-chevron-down toggle-icon"></i>
                </div>
                <div class="basemap-content" id="basemap-content"></div>
            </div>
            
            <div class="panel-section">
                <div class="panel-header collapsible expanded" data-target="legend-content">
                    <i class="fas fa-palette"></i>
                    <span>LEGEND</span>
                    <i class="fas fa-chevron-down toggle-icon"></i>
                </div>
                <div class="legend-content" id="legend-content"></div>
            </div>
        </aside>

        <!-- Center - Map -->
        <main class="center-panel">
            <div class="map-container">
                <div id="map"></div>
                <div class="map-toolbar">
                    <button class="toolbar-btn" id="btn-zoom-fit" title="Fit Extent"><i class="fas fa-expand"></i></button>
                    <button class="toolbar-btn" id="btn-zoom-in" title="Zoom In"><i class="fas fa-search-plus"></i></button>
                    <button class="toolbar-btn" id="btn-zoom-out" title="Zoom Out"><i class="fas fa-search-minus"></i></button>
                </div>
                <div class="map-info-bar">
                    <div class="map-coords" id="map-coords"><i class="fas fa-crosshairs"></i> <span>Lat: --, Lon: --</span></div>
                    <div class="map-scale" id="map-scale">Scale: 1:--</div>
                    <div class="map-zoom" id="map-zoom">Zoom: --</div>
                    <div class="map-crs">EPSG:4326</div>
                </div>
            </div>
        </main>

        <!-- Right Panel - Status -->
        <aside class="right-panel">
            <div class="status-card risk-card normal" id="risk-card">
                <div class="card-header"><i class="fas fa-exclamation-triangle"></i> FLOOD RISK</div>
                <div class="card-body">
                    <div class="risk-level" id="risk-level">NORMAL</div>
                    <div class="risk-message" id="risk-message">All systems operational</div>
                </div>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-icon rainfall"><i class="fas fa-cloud-rain"></i></div>
                    <div class="metric-data">
                        <div class="metric-value" id="rainfall-value">0.0</div>
                        <div class="metric-label">Rainfall (mm/hr)</div>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-icon water"><i class="fas fa-water"></i></div>
                    <div class="metric-data">
                        <div class="metric-value" id="water-level-value">0.00</div>
                        <div class="metric-label">Water Level (m)</div>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-icon discharge"><i class="fas fa-tachometer-alt"></i></div>
                    <div class="metric-data">
                        <div class="metric-value" id="discharge-value">0.0</div>
                        <div class="metric-label">Discharge (m³/s)</div>
                    </div>
                </div>
            </div>
            
            <div class="info-card">
                <div class="card-header"><i class="fas fa-info-circle"></i> CATCHMENT INFO</div>
                <div class="info-grid">
                    <div class="info-item"><span class="info-label">Area</span><span class="info-value">104.3 km²</span></div>
                    <div class="info-item"><span class="info-label">Runoff</span><span class="info-value">0.736</span></div>
                    <div class="info-item"><span class="info-label">Wards</span><span class="info-value">23</span></div>
                    <div class="info-item"><span class="info-label">Channels</span><span class="info-value">153</span></div>
                </div>
            </div>
            
            <div class="alert-panel">
                <div class="card-header"><i class="fas fa-bell"></i> ALERTS <span class="alert-badge" id="alert-count">0</span></div>
                <div class="alert-list" id="alert-list">
                    <div class="no-alerts"><i class="fas fa-check-circle"></i><p>No active alerts</p></div>
                </div>
            </div>
            
            <div class="chart-panel">
                <div class="card-header"><i class="fas fa-chart-line"></i> TRENDS</div>
                <div class="mini-charts">
                    <div class="mini-chart"><canvas id="rainfall-chart"></canvas><span class="chart-label">Rainfall</span></div>
                    <div class="mini-chart"><canvas id="water-level-chart"></canvas><span class="chart-label">Water Level</span></div>
                </div>
            </div>
        </aside>
    </div>

    <footer class="dashboard-footer">
        <div class="footer-left">Flood DAS v2.0 | Layer-Based System</div>
        <div class="footer-center">GHMC Zone 12 | <span id="layer-count">0</span> layers | <span id="feature-count">0</span> features</div>
        <div class="footer-right">Update: <span id="last-update">-</span></div>
    </footer>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="app.js"></script>
</body>
</html>
'''

# CSS Content
CSS_CONTENT = '''/* Flood DAS - QGIS-like Layer System Styles */
:root {
    --bg-primary: #0a0e14;
    --bg-secondary: #131920;
    --bg-card: #1a2332;
    --bg-card-hover: #212d3d;
    --accent-cyan: #00d4ff;
    --accent-blue: #3498db;
    --accent-purple: #9b59b6;
    --accent-green: #27ae60;
    --accent-yellow: #f39c12;
    --accent-red: #e74c3c;
    --text-primary: #ffffff;
    --text-secondary: #a0aec0;
    --text-muted: #718096;
    --border-color: #2d3748;
    --risk-normal: #27ae60;
    --risk-low: #3498db;
    --risk-medium: #f39c12;
    --risk-high: #e67e22;
    --risk-critical: #e74c3c;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Roboto', sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

/* Header */
.dashboard-header {
    background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
    border-bottom: 1px solid var(--border-color);
    padding: 10px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-left { display: flex; align-items: center; gap: 12px; }
.header-icon { font-size: 32px; color: var(--accent-cyan); text-shadow: 0 0 15px var(--accent-cyan); }
.header-title h1 { font-family: 'Orbitron', sans-serif; font-size: 22px; color: var(--accent-cyan); letter-spacing: 2px; }
.header-title p { font-size: 10px; color: var(--text-secondary); text-transform: uppercase; }
.header-center .location-info { display: flex; align-items: center; gap: 8px; padding: 6px 14px; background: var(--bg-card); border-radius: 16px; font-size: 12px; color: var(--text-secondary); }
.header-center .location-info i { color: var(--accent-red); }
.header-right { display: flex; align-items: center; gap: 20px; }
.datetime { text-align: right; }
.datetime .date { font-size: 11px; color: var(--text-muted); }
.datetime .time { font-family: 'Orbitron', sans-serif; font-size: 18px; color: var(--accent-cyan); }
.connection-status { display: flex; align-items: center; gap: 6px; padding: 5px 10px; background: var(--bg-card); border-radius: 12px; font-size: 11px; }
.connection-status.connected i { color: var(--accent-green); animation: blink 1s infinite; }
.connection-status.disconnected i { color: var(--accent-red); }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Main Layout */
.dashboard-container {
    flex: 1;
    display: grid;
    grid-template-columns: 280px 1fr 300px;
    gap: 12px;
    padding: 12px;
    max-height: calc(100vh - 100px);
    overflow: hidden;
}

/* Left Panel - Layer Tree */
.left-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border-color) transparent;
}

.panel-section {
    background: var(--bg-card);
    border-radius: 8px;
    border: 1px solid var(--border-color);
    overflow: hidden;
}

.panel-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.3);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-color);
}

.panel-header i:first-child { color: var(--accent-cyan); }
.panel-header .panel-actions { margin-left: auto; display: flex; gap: 4px; }
.panel-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px 6px;
    border-radius: 4px;
    transition: all 0.2s;
}
.panel-btn:hover { color: var(--accent-cyan); background: rgba(0, 212, 255, 0.1); }

.panel-header.collapsible { cursor: pointer; }
.panel-header.collapsible .toggle-icon { margin-left: auto; transition: transform 0.2s; }
.panel-header.collapsible:not(.expanded) .toggle-icon { transform: rotate(-90deg); }

/* Layer Tree Styling (QGIS-like) */
.layer-tree {
    padding: 8px;
    max-height: 350px;
    overflow-y: auto;
}

.loading-layers {
    text-align: center;
    padding: 20px;
    color: var(--text-muted);
    font-size: 12px;
}

.layer-group {
    margin-bottom: 6px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
}

.layer-group-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    background: rgba(0, 0, 0, 0.2);
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    transition: background 0.2s;
}

.layer-group-header:hover { background: rgba(0, 212, 255, 0.1); }
.layer-group-header .group-toggle { color: var(--text-muted); font-size: 10px; transition: transform 0.2s; }
.layer-group-header .group-toggle.collapsed { transform: rotate(-90deg); }
.layer-group-header .group-icon { color: var(--accent-cyan); }
.layer-group-header .group-checkbox { accent-color: var(--accent-cyan); }

.layer-group-content {
    padding: 4px 8px;
    display: block;
}
.layer-group-content.collapsed { display: none; }

.layer-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    margin: 2px 0;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
}

.layer-item:hover { background: rgba(255, 255, 255, 0.05); }
.layer-item.active { background: rgba(0, 212, 255, 0.15); }

.layer-checkbox { accent-color: var(--accent-cyan); cursor: pointer; }
.layer-color {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.2);
}
.layer-color.line { width: 20px; height: 4px; border-radius: 2px; }
.layer-color.point { width: 12px; height: 12px; border-radius: 50%; }
.layer-name { flex: 1; color: var(--text-primary); }
.layer-count { color: var(--text-muted); font-size: 10px; }

/* Basemap Selector */
.basemap-content { padding: 8px; }
.basemap-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    margin: 4px 0;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
    transition: all 0.2s;
}
.basemap-option:hover { background: rgba(255, 255, 255, 0.05); }
.basemap-option.active { background: rgba(0, 212, 255, 0.15); border: 1px solid var(--accent-cyan); }
.basemap-option input[type="radio"] { accent-color: var(--accent-cyan); }

/* Legend */
.legend-content { padding: 8px; }
.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    font-size: 11px;
}
.legend-symbol { width: 20px; height: 14px; border-radius: 2px; }
.legend-symbol.line { height: 4px; }
.legend-symbol.point { width: 10px; height: 10px; border-radius: 50%; }

/* Center Panel - Map */
.center-panel { display: flex; flex-direction: column; min-height: 0; }
.map-container {
    flex: 1;
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border-color);
}
#map { width: 100%; height: 100%; background: var(--bg-secondary); }

/* Map Toolbar (QGIS-like) */
.map-toolbar {
    position: absolute;
    top: 10px;
    left: 10px;
    display: flex;
    gap: 2px;
    background: rgba(26, 35, 50, 0.95);
    padding: 4px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    z-index: 1000;
}

.toolbar-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s;
}
.toolbar-btn:hover { background: rgba(0, 212, 255, 0.2); color: var(--accent-cyan); }
.toolbar-btn.active { background: var(--accent-cyan); color: var(--bg-primary); }
.toolbar-divider { width: 1px; background: var(--border-color); margin: 4px 2px; }

/* Map Info Bar (QGIS-like) */
.map-info-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 6px 12px;
    background: rgba(26, 35, 50, 0.95);
    border-top: 1px solid var(--border-color);
    font-size: 11px;
    color: var(--text-secondary);
    z-index: 1000;
}
.map-coords i { color: var(--accent-cyan); margin-right: 6px; }
.map-crs { margin-left: auto; padding: 2px 8px; background: var(--bg-card); border-radius: 4px; }

/* Right Panel */
.right-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    scrollbar-width: thin;
}

.status-card, .info-card, .alert-panel, .chart-panel {
    background: var(--bg-card);
    border-radius: 8px;
    border: 1px solid var(--border-color);
    overflow: hidden;
}

.card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.2);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1px;
    color: var(--text-secondary);
}
.card-header i { color: var(--accent-cyan); }

.card-body { padding: 15px; text-align: center; }

/* Risk Card */
.risk-card { border: 2px solid; }
.risk-card.normal { border-color: var(--risk-normal); background: linear-gradient(135deg, var(--bg-card), rgba(39, 174, 96, 0.1)); }
.risk-card.low { border-color: var(--risk-low); }
.risk-card.medium { border-color: var(--risk-medium); }
.risk-card.high { border-color: var(--risk-high); }
.risk-card.critical { border-color: var(--risk-critical); animation: pulse 1s infinite; }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 15px rgba(231, 76, 60, 0.3); } 50% { box-shadow: 0 0 30px rgba(231, 76, 60, 0.6); } }

.risk-level { font-family: 'Orbitron', sans-serif; font-size: 24px; font-weight: 700; letter-spacing: 2px; }
.risk-card.normal .risk-level { color: var(--risk-normal); }
.risk-card.medium .risk-level { color: var(--risk-medium); }
.risk-card.high .risk-level { color: var(--risk-high); }
.risk-card.critical .risk-level { color: var(--risk-critical); }
.risk-message { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }

/* Metrics Grid */
.metrics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.metric-card {
    background: var(--bg-card);
    border-radius: 8px;
    border: 1px solid var(--border-color);
    padding: 12px 8px;
    text-align: center;
}
.metric-icon { font-size: 20px; margin-bottom: 6px; }
.metric-icon.rainfall { color: var(--accent-blue); }
.metric-icon.water { color: var(--accent-purple); }
.metric-icon.discharge { color: var(--accent-cyan); }
.metric-value { font-family: 'Orbitron', sans-serif; font-size: 18px; font-weight: 700; }
.metric-label { font-size: 9px; color: var(--text-muted); margin-top: 2px; }

/* Info Grid */
.info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; padding: 12px; }
.info-item { display: flex; flex-direction: column; gap: 2px; }
.info-label { font-size: 10px; color: var(--text-muted); }
.info-value { font-size: 13px; font-weight: 500; color: var(--text-primary); }

/* Alert Panel */
.alert-badge {
    margin-left: auto;
    background: var(--accent-red);
    color: white;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
}
.alert-list { padding: 10px; max-height: 120px; overflow-y: auto; }
.no-alerts { text-align: center; color: var(--text-muted); padding: 15px; font-size: 12px; }
.no-alerts i { color: var(--accent-green); font-size: 20px; display: block; margin-bottom: 6px; }

/* Mini Charts */
.mini-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 10px; }
.mini-chart { position: relative; height: 80px; }
.mini-chart canvas { width: 100% !important; height: 60px !important; }
.chart-label { display: block; text-align: center; font-size: 10px; color: var(--text-muted); margin-top: 4px; }

/* Footer */
.dashboard-footer {
    display: flex;
    justify-content: space-between;
    padding: 8px 20px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
    font-size: 11px;
    color: var(--text-muted);
}

/* Leaflet Customization */
.leaflet-popup-content-wrapper {
    background: var(--bg-card);
    color: var(--text-primary);
    border-radius: 8px;
}
.leaflet-popup-content { margin: 12px; }
.leaflet-popup-tip { background: var(--bg-card); }
.popup-title { font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--accent-cyan); }
.popup-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 11px; border-bottom: 1px solid var(--border-color); }
.popup-row:last-child { border-bottom: none; }
.popup-label { color: var(--text-muted); }
.popup-value { color: var(--text-primary); font-weight: 500; }

/* Sensor Markers */
.sensor-marker { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: var(--bg-card); border: 2px solid; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
'''

# JavaScript Content
JS_CONTENT = '''/**
 * Flood DAS - QGIS-like Layer System
 * Layer-based GIS application for flood monitoring
 */

// Configuration
const CONFIG = {
    API_URL: 'http://localhost:8000',
    GEOJSON_URL: '/home/ved_maurya/college/sem6/Hydro_informatics/flood_das/geojson',
    WS_URL: 'ws://localhost:8000/ws',
    UPDATE_INTERVAL: 5000,
    MAP_CENTER: [17.4898, 78.4340],
    MAP_ZOOM: 12
};

// Global State
let map = null;
let layerConfig = null;
let layers = {};
let basemapLayers = {};
let currentBasemap = null;
let charts = {};
let featureCount = 0;

// ========================================
// Initialization
// ========================================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('🌊 Flood DAS - Initializing QGIS-like Layer System...');
    
    initDateTime();
    initMap();
    initCharts();
    
    await loadLayerConfig();
    initBasemaps();
    await loadAllLayers();
    buildLayerTree();
    buildLegend();
    
    initEventListeners();
    initWebSocket();
    startDataPolling();
    
    updateLayerCount();
    console.log('✓ Flood DAS - Ready');
});

// ========================================
// DateTime Display
// ========================================

function initDateTime() {
    updateDateTime();
    setInterval(updateDateTime, 1000);
}

function updateDateTime() {
    const now = new Date();
    document.getElementById('current-date').textContent = now.toLocaleDateString('en-IN', {
        weekday: 'short', day: '2-digit', month: 'short', year: 'numeric'
    });
    document.getElementById('current-time').textContent = now.toLocaleTimeString('en-IN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}

// ========================================
// Map Initialization
// ========================================

function initMap() {
    map = L.map('map', {
        center: CONFIG.MAP_CENTER,
        zoom: CONFIG.MAP_ZOOM,
        zoomControl: false
    });
    
    // Mouse move for coordinates
    map.on('mousemove', (e) => {
        document.querySelector('#map-coords span').textContent = 
            `Lat: ${e.latlng.lat.toFixed(5)}, Lon: ${e.latlng.lng.toFixed(5)}`;
    });
    
    // Zoom change
    map.on('zoomend', () => {
        const zoom = map.getZoom();
        document.getElementById('map-zoom').textContent = `Zoom: ${zoom}`;
        const scale = Math.round(591657550.5 / Math.pow(2, zoom));
        document.getElementById('map-scale').textContent = `Scale: 1:${scale.toLocaleString()}`;
    });
    
    map.fire('zoomend');
    console.log('✓ Map initialized');
}

// ========================================
// Layer Configuration
// ========================================

async function loadLayerConfig() {
    try {
        const response = await fetch(`${CONFIG.API_URL}/geojson/layer_config.json`);
        if (!response.ok) throw new Error('Config not found');
        layerConfig = await response.json();
    } catch (error) {
        console.warn('Loading default layer config');
        layerConfig = getDefaultLayerConfig();
    }
}

function getDefaultLayerConfig() {
    return {
        groups: [
            {
                id: 'base', name: 'Base Layers', icon: 'layer-group', expanded: true,
                layers: [
                    { id: 'watershed', name: 'Watershed Boundary', file: 'layers/watershed_boundary.geojson', type: 'polygon', visible: true,
                      style: { color: '#2980b9', weight: 3, fillColor: '#2980b9', fillOpacity: 0.1, dashArray: '10, 5' }, zIndex: 100 },
                    { id: 'wards', name: 'Ward Boundaries', file: 'layers/ward_boundaries.geojson', type: 'polygon', visible: true,
                      style: { color: '#7f8c8d', weight: 1.5, fillColor: '#bdc3c7', fillOpacity: 0.05 }, zIndex: 90 }
                ]
            },
            {
                id: 'hydrology', name: 'Drainage Network', icon: 'water', expanded: true,
                layers: [
                    { id: 'channels_4', name: 'Main Channels (Order 4)', file: 'layers/drainage_order_4.geojson', type: 'line', visible: true,
                      style: { color: '#0066cc', weight: 5, opacity: 0.9 }, zIndex: 200 },
                    { id: 'channels_3', name: 'Secondary (Order 3)', file: 'layers/drainage_order_3.geojson', type: 'line', visible: true,
                      style: { color: '#3399ff', weight: 3.5, opacity: 0.8 }, zIndex: 190 },
                    { id: 'channels_2', name: 'Tertiary (Order 2)', file: 'layers/drainage_order_2.geojson', type: 'line', visible: false,
                      style: { color: '#66b3ff', weight: 2.5, opacity: 0.7 }, zIndex: 180 },
                    { id: 'channels_1', name: 'Minor (Order 1)', file: 'layers/drainage_order_1.geojson', type: 'line', visible: false,
                      style: { color: '#99ccff', weight: 1.5, opacity: 0.6 }, zIndex: 170 }
                ]
            },
            {
                id: 'risk', name: 'Flood Risk Zones', icon: 'exclamation-triangle', expanded: true,
                layers: [
                    { id: 'risk_high', name: 'High Risk Zones', file: 'layers/flood_risk_high.geojson', type: 'polygon', visible: true,
                      style: { color: '#e74c3c', weight: 2, fillColor: '#e74c3c', fillOpacity: 0.4 }, zIndex: 150 },
                    { id: 'risk_medium', name: 'Medium Risk Zones', file: 'layers/flood_risk_medium.geojson', type: 'polygon', visible: true,
                      style: { color: '#f39c12', weight: 2, fillColor: '#f39c12', fillOpacity: 0.3 }, zIndex: 140 },
                    { id: 'risk_low', name: 'Low Risk Zones', file: 'layers/flood_risk_low.geojson', type: 'polygon', visible: false,
                      style: { color: '#27ae60', weight: 2, fillColor: '#27ae60', fillOpacity: 0.2 }, zIndex: 130 }
                ]
            },
            {
                id: 'sensors', name: 'Monitoring', icon: 'broadcast-tower', expanded: true,
                layers: [
                    { id: 'rain_gauges', name: 'Rain Gauges', file: 'layers/rain_gauges.geojson', type: 'point', visible: true,
                      style: { color: '#3498db', icon: 'cloud-rain', size: 24 }, zIndex: 300 },
                    { id: 'water_levels', name: 'Water Level Sensors', file: 'layers/water_level_sensors.geojson', type: 'point', visible: true,
                      style: { color: '#9b59b6', icon: 'water', size: 24 }, zIndex: 290 }
                ]
            }
        ],
        basemaps: [
            { id: 'dark', name: 'Dark', url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', default: true },
            { id: 'light', name: 'Light', url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png' },
            { id: 'osm', name: 'OpenStreetMap', url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' },
            { id: 'satellite', name: 'Satellite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}' }
        ]
    };
}

// ========================================
// Basemap Management
// ========================================

function initBasemaps() {
    const container = document.getElementById('basemap-content');
    container.innerHTML = '';
    
    layerConfig.basemaps.forEach(bm => {
        basemapLayers[bm.id] = L.tileLayer(bm.url, {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        });
        
        const option = document.createElement('div');
        option.className = `basemap-option ${bm.default ? 'active' : ''}`;
        option.innerHTML = `
            <input type="radio" name="basemap" value="${bm.id}" ${bm.default ? 'checked' : ''}>
            <span>${bm.name}</span>
        `;
        option.onclick = () => setBasemap(bm.id);
        container.appendChild(option);
        
        if (bm.default) {
            basemapLayers[bm.id].addTo(map);
            currentBasemap = bm.id;
        }
    });
}

function setBasemap(id) {
    if (currentBasemap) {
        map.removeLayer(basemapLayers[currentBasemap]);
    }
    basemapLayers[id].addTo(map);
    currentBasemap = id;
    
    document.querySelectorAll('.basemap-option').forEach(opt => {
        opt.classList.toggle('active', opt.querySelector('input').value === id);
        opt.querySelector('input').checked = opt.querySelector('input').value === id;
    });
}

// ========================================
// Layer Loading
// ========================================

async function loadAllLayers() {
    const loadingEl = document.querySelector('.loading-layers');
    
    for (const group of layerConfig.groups) {
        for (const layerDef of group.layers) {
            try {
                const response = await fetch(`${CONFIG.API_URL}/geojson/${layerDef.file}`);
                if (!response.ok) continue;
                
                const geojson = await response.json();
                const layer = createLayer(geojson, layerDef);
                layers[layerDef.id] = { leafletLayer: layer, config: layerDef, geojson: geojson };
                featureCount += geojson.features?.length || 0;
                
                if (layerDef.visible) {
                    layer.addTo(map);
                }
            } catch (error) {
                console.warn(`Could not load layer: ${layerDef.id}`, error);
            }
        }
    }
    
    if (loadingEl) loadingEl.remove();
}

function createLayer(geojson, config) {
    if (config.type === 'point') {
        return L.geoJSON(geojson, {
            pointToLayer: (feature, latlng) => {
                const icon = L.divIcon({
                    html: `<div class="sensor-marker" style="border-color: ${config.style.color}">
                             <i class="fas fa-${config.style.icon}" style="color: ${config.style.color}; font-size: 14px;"></i>
                           </div>`,
                    className: '',
                    iconSize: [28, 28],
                    iconAnchor: [14, 14]
                });
                return L.marker(latlng, { icon });
            },
            onEachFeature: (feature, layer) => bindPopup(feature, layer)
        });
    } else {
        return L.geoJSON(geojson, {
            style: () => config.style,
            onEachFeature: (feature, layer) => bindPopup(feature, layer)
        });
    }
}

function bindPopup(feature, layer) {
    const props = feature.properties;
    let content = `<div class="popup-title">${props.name || 'Feature'}</div>`;
    
    Object.entries(props).forEach(([key, value]) => {
        if (key !== 'name' && key !== 'layer_type' && !key.startsWith('style')) {
            content += `<div class="popup-row"><span class="popup-label">${key}:</span><span class="popup-value">${value}</span></div>`;
        }
    });
    
    layer.bindPopup(content);
}

// ========================================
// Layer Tree UI (QGIS-like)
// ========================================

function buildLayerTree() {
    const container = document.getElementById('layer-tree');
    container.innerHTML = '';
    
    layerConfig.groups.forEach(group => {
        const groupEl = document.createElement('div');
        groupEl.className = 'layer-group';
        groupEl.innerHTML = `
            <div class="layer-group-header" data-group="${group.id}">
                <i class="fas fa-chevron-down group-toggle"></i>
                <input type="checkbox" class="group-checkbox" checked>
                <i class="fas fa-${group.icon} group-icon"></i>
                <span class="group-name">${group.name}</span>
            </div>
            <div class="layer-group-content" id="group-${group.id}">
                ${group.layers.map(layer => createLayerItemHTML(layer)).join('')}
            </div>
        `;
        container.appendChild(groupEl);
        
        // Group toggle
        const header = groupEl.querySelector('.layer-group-header');
        header.onclick = (e) => {
            if (e.target.classList.contains('group-checkbox')) return;
            const content = groupEl.querySelector('.layer-group-content');
            const toggle = header.querySelector('.group-toggle');
            content.classList.toggle('collapsed');
            toggle.classList.toggle('collapsed');
        };
        
        // Group checkbox
        const groupCheckbox = header.querySelector('.group-checkbox');
        groupCheckbox.onchange = () => {
            group.layers.forEach(l => toggleLayer(l.id, groupCheckbox.checked));
            groupEl.querySelectorAll('.layer-checkbox').forEach(cb => cb.checked = groupCheckbox.checked);
        };
    });
    
    // Individual layer toggles
    document.querySelectorAll('.layer-checkbox').forEach(cb => {
        cb.onchange = () => toggleLayer(cb.dataset.layer, cb.checked);
    });
}

function createLayerItemHTML(layer) {
    const colorStyle = layer.type === 'line' ? 'line' : layer.type === 'point' ? 'point' : '';
    const count = layers[layer.id]?.geojson?.features?.length || 0;
    
    return `
        <div class="layer-item" data-layer="${layer.id}">
            <input type="checkbox" class="layer-checkbox" data-layer="${layer.id}" ${layer.visible ? 'checked' : ''}>
            <div class="layer-color ${colorStyle}" style="background: ${layer.style.fillColor || layer.style.color}"></div>
            <span class="layer-name">${layer.name}</span>
            <span class="layer-count">(${count})</span>
        </div>
    `;
}

function toggleLayer(layerId, visible) {
    const layerData = layers[layerId];
    if (!layerData) return;
    
    if (visible) {
        layerData.leafletLayer.addTo(map);
    } else {
        map.removeLayer(layerData.leafletLayer);
    }
    layerData.config.visible = visible;
    buildLegend();
}

// ========================================
// Legend
// ========================================

function buildLegend() {
    const container = document.getElementById('legend-content');
    container.innerHTML = '';
    
    layerConfig.groups.forEach(group => {
        group.layers.forEach(layer => {
            if (!layer.visible) return;
            
            const symbolClass = layer.type === 'line' ? 'line' : layer.type === 'point' ? 'point' : '';
            const item = document.createElement('div');
            item.className = 'legend-item';
            item.innerHTML = `
                <div class="legend-symbol ${symbolClass}" style="background: ${layer.style.fillColor || layer.style.color}"></div>
                <span>${layer.name}</span>
            `;
            container.appendChild(item);
        });
    });
}

// ========================================
// Event Listeners
// ========================================

function initEventListeners() {
    // Toolbar buttons
    document.getElementById('btn-zoom-fit').onclick = () => {
        if (layers.watershed?.leafletLayer) {
            map.fitBounds(layers.watershed.leafletLayer.getBounds());
        } else {
            map.setView(CONFIG.MAP_CENTER, CONFIG.MAP_ZOOM);
        }
    };
    document.getElementById('btn-zoom-in').onclick = () => map.zoomIn();
    document.getElementById('btn-zoom-out').onclick = () => map.zoomOut();
    
    // Expand/Collapse all
    document.getElementById('btn-expand-all').onclick = () => {
        document.querySelectorAll('.layer-group-content').forEach(el => el.classList.remove('collapsed'));
        document.querySelectorAll('.group-toggle').forEach(el => el.classList.remove('collapsed'));
    };
    document.getElementById('btn-collapse-all').onclick = () => {
        document.querySelectorAll('.layer-group-content').forEach(el => el.classList.add('collapsed'));
        document.querySelectorAll('.group-toggle').forEach(el => el.classList.add('collapsed'));
    };
    
    // Collapsible panels
    document.querySelectorAll('.panel-header.collapsible').forEach(header => {
        header.onclick = () => {
            header.classList.toggle('expanded');
            const target = document.getElementById(header.dataset.target);
            if (target) target.style.display = header.classList.contains('expanded') ? 'block' : 'none';
        };
    });
}

// ========================================
// Charts
// ========================================

function initCharts() {
    const chartConfig = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        scales: { x: { display: false }, y: { display: false } },
        plugins: { legend: { display: false } }
    };
    
    charts.rainfall = new Chart(document.getElementById('rainfall-chart'), {
        type: 'line',
        data: { labels: [], datasets: [{ data: [], borderColor: '#3498db', backgroundColor: 'rgba(52, 152, 219, 0.2)', fill: true, tension: 0.4, pointRadius: 0 }] },
        options: chartConfig
    });
    
    charts.waterLevel = new Chart(document.getElementById('water-level-chart'), {
        type: 'line',
        data: { labels: [], datasets: [{ data: [], borderColor: '#9b59b6', backgroundColor: 'rgba(155, 89, 182, 0.2)', fill: true, tension: 0.4, pointRadius: 0 }] },
        options: chartConfig
    });
}

// ========================================
// WebSocket & Data Polling
// ========================================

function initWebSocket() {
    try {
        const ws = new WebSocket(CONFIG.WS_URL);
        ws.onopen = () => setConnectionStatus(true);
        ws.onclose = () => {
            setConnectionStatus(false);
            setTimeout(initWebSocket, 5000);
        };
        ws.onmessage = (e) => handleRealtimeData(JSON.parse(e.data));
    } catch (error) {
        setConnectionStatus(false);
    }
}

function setConnectionStatus(connected) {
    const el = document.getElementById('connection-status');
    el.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
    el.querySelector('span').textContent = connected ? 'Live' : 'Offline';
}

function startDataPolling() {
    fetchCurrentStatus();
    setInterval(fetchCurrentStatus, CONFIG.UPDATE_INTERVAL);
}

async function fetchCurrentStatus() {
    try {
        const response = await fetch(`${CONFIG.API_URL}/current_status`);
        if (response.ok) {
            const data = await response.json();
            updateMetrics(data);
        }
    } catch (error) {
        console.warn('Could not fetch status');
    }
}

function updateMetrics(data) {
    document.getElementById('rainfall-value').textContent = data.latest_rainfall_mm?.toFixed(1) || '0.0';
    document.getElementById('water-level-value').textContent = data.latest_water_level_m?.toFixed(2) || '0.00';
    document.getElementById('discharge-value').textContent = data.latest_discharge_m3s?.toFixed(1) || '0.0';
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    
    // Update risk level
    const risk = data.risk_level?.toLowerCase() || 'normal';
    const riskCard = document.getElementById('risk-card');
    riskCard.className = `status-card risk-card ${risk}`;
    document.getElementById('risk-level').textContent = risk.toUpperCase();
    document.getElementById('risk-message').textContent = data.status_message || 'System operational';
    
    // Update charts
    addChartData(data.latest_rainfall_mm || 0, data.latest_water_level_m || 0);
}

function addChartData(rainfall, waterLevel) {
    const maxPoints = 20;
    const time = new Date().toLocaleTimeString();
    
    charts.rainfall.data.labels.push(time);
    charts.rainfall.data.datasets[0].data.push(rainfall);
    if (charts.rainfall.data.labels.length > maxPoints) {
        charts.rainfall.data.labels.shift();
        charts.rainfall.data.datasets[0].data.shift();
    }
    charts.rainfall.update('none');
    
    charts.waterLevel.data.labels.push(time);
    charts.waterLevel.data.datasets[0].data.push(waterLevel);
    if (charts.waterLevel.data.labels.length > maxPoints) {
        charts.waterLevel.data.labels.shift();
        charts.waterLevel.data.datasets[0].data.shift();
    }
    charts.waterLevel.update('none');
}

function handleRealtimeData(data) {
    if (data.type === 'rainfall_update' || data.type === 'water_level_update') {
        fetchCurrentStatus();
    }
}

function updateLayerCount() {
    document.getElementById('layer-count').textContent = Object.keys(layers).length;
    document.getElementById('feature-count').textContent = featureCount;
}
'''

# Write files
with open(os.path.join(FRONTEND_PATH, 'index.html'), 'w') as f:
    f.write(HTML_CONTENT)
print("✓ Created index.html")

with open(os.path.join(FRONTEND_PATH, 'styles.css'), 'w') as f:
    f.write(CSS_CONTENT)
print("✓ Created styles.css")

with open(os.path.join(FRONTEND_PATH, 'app.js'), 'w') as f:
    f.write(JS_CONTENT)
print("✓ Created app.js")

print("\\n✅ Frontend files created successfully!")
