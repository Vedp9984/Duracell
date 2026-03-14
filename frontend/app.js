/**
 * Flood DAS - QGIS-like Layer System
 * Layer-based GIS application for flood monitoring
 */

// Configuration
const CONFIG = {
    API_URL: window.location.origin,
    WS_URL: `ws://${window.location.host}/ws`,
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
let featureCount = 0;
let selectedSubbasin = null;
let currentIntensity = 50;
let autoSimInFlight = false;
let lastAutoSimKey = null;
let statusRequestSeq = 0;
let lastAppliedStatusSeq = 0;
let alertsRequestSeq = 0;
let lastAppliedAlertsSeq = 0;
let manualSimHoldUntil = 0;
let simulationDashboardMode = false;

function enableManualSimHold(ms = 15000) {
    manualSimHoldUntil = Date.now() + ms;
}

// ========================================
// Initialization
// ========================================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('🌊 Flood DAS - Initializing QGIS-like Layer System...');

    initDateTime();
    initMap();

    await loadLayerConfig();
    initBasemaps();
    await loadAllLayers();
    buildLayerTree();
    buildLegend();

    initEventListeners();
    initWebSocket();
    startDataPolling();
    await initFloodSimulation();

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
                    {
                        id: 'watershed', name: 'Watershed Boundary', file: 'layers/watershed_boundary.geojson', type: 'polygon', visible: true,
                        style: { color: '#2980b9', weight: 3, fillColor: '#2980b9', fillOpacity: 0.1, dashArray: '10, 5' }, zIndex: 100
                    },
                    {
                        id: 'wards', name: 'Ward Boundaries', file: 'layers/ward_boundaries.geojson', type: 'polygon', visible: true,
                        style: { color: '#7f8c8d', weight: 1.5, fillColor: '#bdc3c7', fillOpacity: 0.05 }, zIndex: 90
                    }
                ]
            },
            {
                id: 'hydrology', name: 'Drainage Network', icon: 'water', expanded: true,
                layers: [
                    {
                        id: 'channels_4', name: 'Main Channels (Order 4)', file: 'layers/drainage_order_4.geojson', type: 'line', visible: true,
                        style: { color: '#0066cc', weight: 5, opacity: 0.9 }, zIndex: 200
                    },
                    {
                        id: 'channels_3', name: 'Secondary (Order 3)', file: 'layers/drainage_order_3.geojson', type: 'line', visible: true,
                        style: { color: '#3399ff', weight: 3.5, opacity: 0.8 }, zIndex: 190
                    },
                    {
                        id: 'channels_2', name: 'Tertiary (Order 2)', file: 'layers/drainage_order_2.geojson', type: 'line', visible: false,
                        style: { color: '#66b3ff', weight: 2.5, opacity: 0.7 }, zIndex: 180
                    },
                    {
                        id: 'channels_1', name: 'Minor (Order 1)', file: 'layers/drainage_order_1.geojson', type: 'line', visible: false,
                        style: { color: '#99ccff', weight: 1.5, opacity: 0.6 }, zIndex: 170
                    }
                ]
            },
            {
                id: 'risk', name: 'Flood Risk Zones', icon: 'exclamation-triangle', expanded: true,
                layers: [
                    {
                        id: 'risk_high', name: 'High Risk Zones', file: 'layers/flood_risk_high.geojson', type: 'polygon', visible: false,
                        style: { color: '#e74c3c', weight: 2, fillColor: '#e74c3c', fillOpacity: 0.4 }, zIndex: 150
                    },
                    {
                        id: 'risk_medium', name: 'Medium Risk Zones', file: 'layers/flood_risk_medium.geojson', type: 'polygon', visible: false,
                        style: { color: '#f39c12', weight: 2, fillColor: '#f39c12', fillOpacity: 0.3 }, zIndex: 140
                    },
                    {
                        id: 'risk_low', name: 'Low Risk Zones', file: 'layers/flood_risk_low.geojson', type: 'polygon', visible: false,
                        style: { color: '#27ae60', weight: 2, fillColor: '#27ae60', fillOpacity: 0.2 }, zIndex: 130
                    }
                ]
            },
            {
                id: 'sensors', name: 'Monitoring', icon: 'broadcast-tower', expanded: true,
                layers: [
                    {
                        id: 'rain_gauges', name: 'Rain Gauges', file: 'layers/rain_gauges.geojson', type: 'point', visible: true,
                        style: { color: '#3498db', icon: 'cloud-rain', size: 24 }, zIndex: 300
                    },
                    {
                        id: 'water_levels', name: 'Water Level Sensors', file: 'layers/water_level_sensors.geojson', type: 'point', visible: true,
                        style: { color: '#9b59b6', icon: 'water', size: 24 }, zIndex: 290
                    }
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
                if (layerDef.type === 'raster') {
                    await loadRasterLayer(layerDef);
                } else {
                    const response = await fetch(`${CONFIG.API_URL}/geojson/${layerDef.file}`);
                    if (!response.ok) continue;

                    const geojson = await response.json();
                    const layer = createLayer(geojson, layerDef);
                    layers[layerDef.id] = { leafletLayer: layer, config: layerDef, geojson: geojson };
                    featureCount += geojson.features?.length || 0;

                    if (layerDef.visible) {
                        layer.addTo(map);
                    }
                }
            } catch (error) {
                console.warn(`Could not load layer: ${layerDef.id}`, error);
            }
        }
    }

    if (loadingEl) loadingEl.remove();
}

async function loadRasterLayer(config) {
    try {
        const response = await fetch(`${CONFIG.API_URL}/raster_metadata/${config.raster}`);
        if (!response.ok) throw new Error('Metadata not found');
        const metadata = await response.json();

        const bounds = [
            [metadata.bounds.south, metadata.bounds.west],
            [metadata.bounds.north, metadata.bounds.east]
        ];

        const imageUrl = `${CONFIG.API_URL}/raster/${config.raster}?colormap=${config.colormap || 'terrain'}`;
        const layer = L.imageOverlay(imageUrl, bounds, {
            opacity: config.visible ? (config.style?.opacity || 0.7) : 0,
            interactive: true,
            zIndex: config.zIndex || 10
        });

        layers[config.id] = { leafletLayer: layer, config: config };

        if (config.visible) {
            layer.addTo(map);
        }
    } catch (error) {
        console.error(`Failed to load raster ${config.raster}:`, error);
    }
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
            style: (feature) => {
                return {
                    ...config.style,
                    fillOpacity: config.style.fillOpacity !== undefined ? config.style.fillOpacity : 0.5,
                    color: config.style.color,
                    weight: config.style.weight,
                    opacity: config.style.opacity !== undefined ? config.style.opacity : 1
                };
            },
            onEachFeature: (feature, layer) => {
                bindPopup(feature, layer);
            }
        });
    }
}

function selectSubbasin(layer) {
    // Reset previous selection
    if (selectedSubbasin) {
        const prevLayer = selectedSubbasin;
        prevLayer.setStyle({
            color: prevLayer.options.originalColor || '#8e44ad',
            weight: 2.5,
            fillOpacity: 0.2
        });
    }

    selectedSubbasin = layer;
    layer.options.originalColor = layer.options.originalColor || layer.options.color;
    layer.setStyle({
        color: '#ff0000',
        weight: 4,
        fillOpacity: 0.6
    });
    layer.bringToFront();

    // Show simulation results
    document.getElementById('no-selection-msg').style.display = 'none';
    const resultsEl = document.getElementById('simulation-results');
    resultsEl.style.display = 'block';
    document.getElementById('selected-basin-id').textContent = layer.feature.properties.DN || layer.feature.properties.Basin_ID;

    // Populate subbasin details grid
    const detailsContainer = document.getElementById('subbasin-details');
    const props = layer.feature.properties;

    // Kirpich Equation: Tc = 0.0195 * L^0.77 * S^-0.385
    // Use Watershed_Slope_m_m if available, else fall back to Relief/Length
    const L = props.Watershed_Length_m || 0;
    const S_kirpich = props.Watershed_Slope_m_m > 0 ? props.Watershed_Slope_m_m : (props.Relief_m || 1) / Math.max(L, 1);
    let tc = 0;
    if (L > 0 && S_kirpich > 0) {
        tc = 0.0195 * Math.pow(L, 0.77) * Math.pow(S_kirpich, -0.385);
    }

    // --- Watershed Geometry section ---
    const watershedMetrics = [
        { label: 'Area', value: props.Area_km2?.toFixed(3), unit: 'km²' },
        { label: 'Perimeter', value: props.Perimeter_km?.toFixed(2), unit: 'km' },
        { label: 'W. Length', value: props.Watershed_Length_m?.toFixed(0), unit: 'm' },
        { label: 'W. Slope', value: props.Watershed_Slope_m_m?.toFixed(4), unit: 'm/m' },
        { label: 'Relief', value: props.Relief_m?.toFixed(1), unit: 'm' },
        { label: 'Mouth Elev.', value: props.Mouth_Elevation_m?.toFixed(1), unit: 'm' }
    ];

    // --- Channel / Drainage section ---
    const channelMetrics = [
        { label: 'Channel Len.', value: props.Channel_Length_m?.toFixed(1), unit: 'm' },
        { label: 'Channel Slope', value: props.Channel_Slope_m_m?.toFixed(4), unit: 'm/m' },
        { label: 'Stream Length', value: props.Total_Stream_Length_m?.toFixed(1), unit: 'm' },
        { label: 'Stream Order', value: props.Max_Stream_Order, unit: '' },
        { label: 'Form Factor', value: props.Form_Factor?.toFixed(3), unit: '' },
        { label: 'Tc', value: tc.toFixed(1), unit: 'min' }
    ];

    detailsContainer.innerHTML =
        `<div class="detail-section-title">🏔️ Watershed Geometry</div>` +
        watershedMetrics.map(m => `
            <div class="detail-item">
                <span class="detail-label">${m.label}</span>
                <span class="detail-value">${m.value ?? '--'} ${m.unit}</span>
            </div>
        `).join('') +
        `<div class="detail-section-title" style="margin-top:8px">🌊 Channel / Drainage</div>` +
        channelMetrics.map(m => `
            <div class="detail-item">
                <span class="detail-label">${m.label}</span>
                <span class="detail-value">${m.value ?? '--'} ${m.unit}</span>
            </div>
        `).join('');

    updateSimulation();
}

function bindPopup(feature, layer) {
    const props = feature.properties;
    const isSubbasin = props.Area_km2 !== undefined;

    let title = props.name || (isSubbasin ? `Subbasin ${props.DN || props.Basin_ID}` : 'Feature');
    let content = `<div class="popup-title">${title}</div>`;

    if (isSubbasin) {
        // --- Watershed Geometry ---
        content += `<div class="popup-section-header">🏔️ Watershed Geometry</div>`;
        const geomMetrics = [
            { label: 'Drainage Area', value: props.Area_km2?.toFixed(3), unit: 'km²' },
            { label: 'Perimeter', value: props.Perimeter_km?.toFixed(2), unit: 'km' },
            { label: 'Watershed Length', value: props.Watershed_Length_m?.toFixed(0), unit: 'm' },
            { label: 'Watershed Slope', value: props.Watershed_Slope_m_m?.toFixed(4), unit: 'm/m' },
            { label: 'Relief', value: props.Relief_m?.toFixed(1), unit: 'm' },
            { label: 'Avg DEM Slope', value: props.Avg_Slope_m_m?.toFixed(4), unit: 'm/m' },
            { label: 'Mouth Elevation', value: props.Mouth_Elevation_m?.toFixed(1), unit: 'm' }
        ];
        geomMetrics.forEach(m => {
            if (m.value !== undefined && m.value !== null && m.value !== 'undefined')
                content += `<div class="popup-row"><span class="popup-label">${m.label}:</span><span class="popup-value">${m.value} ${m.unit}</span></div>`;
        });

        // --- Channel / Drainage ---
        content += `<div class="popup-section-header">🌊 Channel / Drainage</div>`;
        const chanMetrics = [
            { label: 'Channel Length', value: props.Channel_Length_m?.toFixed(1), unit: 'm' },
            { label: 'Channel Slope', value: props.Channel_Slope_m_m?.toFixed(4), unit: 'm/m' },
            { label: 'Total Stream Length', value: props.Total_Stream_Length_m?.toFixed(1), unit: 'm' },
            { label: 'Max Stream Order', value: props.Max_Stream_Order, unit: '' },
            { label: 'Form Factor', value: props.Form_Factor?.toFixed(3), unit: '' },
            { label: 'Circularity Ratio', value: props.Circularity_Ratio?.toFixed(3), unit: '' }
        ];
        chanMetrics.forEach(m => {
            if (m.value !== undefined && m.value !== null && m.value !== 'undefined')
                content += `<div class="popup-row"><span class="popup-label">${m.label}:</span><span class="popup-value">${m.value} ${m.unit}</span></div>`;
        });
    } else {
        Object.entries(props).forEach(([key, value]) => {
            if (key !== 'name' && key !== 'layer_type' && !key.startsWith('style')) {
                // Prettify labels
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                content += `<div class="popup-row"><span class="popup-label">${label}:</span><span class="popup-value">${value}</span></div>`;
            }
        });
    }

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

    // Opacity sliders
    document.querySelectorAll('.opacity-slider').forEach(slider => {
        slider.oninput = () => updateLayerOpacity(slider.dataset.layer, slider.value / 100);
    });
}

function createLayerItemHTML(layer) {
    const colorStyle = layer.type === 'line' ? 'line' : layer.type === 'point' ? 'point' : layer.type === 'raster' ? 'raster' : '';
    const count = layers[layer.id]?.geojson?.features?.length || 0;
    const initialOpacity = (layer.type === 'raster' ? (layer.style?.opacity || 0.7) : (layer.style?.fillOpacity || layer.style?.opacity || 0.5)) * 100;

    return `
        <div class="layer-item-container">
            <div class="layer-item" data-layer="${layer.id}">
                <input type="checkbox" class="layer-checkbox" data-layer="${layer.id}" ${layer.visible ? 'checked' : ''}>
                <div class="layer-color ${colorStyle}" style="background: ${layer.style?.fillColor || layer.style?.color || '#3498db'}"></div>
                <span class="layer-name" title="${layer.name}">${layer.name}</span>
                ${layer.type !== 'raster' ? `<span class="layer-count">(${count})</span>` : ''}
            </div>
            <div class="layer-controls">
                <i class="fas fa-adjust slider-icon"></i>
                <input type="range" class="opacity-slider" data-layer="${layer.id}" min="0" max="100" value="${initialOpacity}">
            </div>
        </div>
    `;
}

function toggleLayer(layerId, visible) {
    const layerData = layers[layerId];
    if (!layerData) return;

    if (visible) {
        layerData.leafletLayer.addTo(map);
        // Restore opacity if it's a raster
        if (layerData.config.type === 'raster') {
            const slider = document.querySelector(`.opacity-slider[data-layer="${layerId}"]`);
            const opacity = slider ? slider.value / 100 : 0.7;
            layerData.leafletLayer.setOpacity(opacity);
        }
    } else {
        map.removeLayer(layerData.leafletLayer);
    }
    layerData.config.visible = visible;
    buildLegend();
}

function updateLayerOpacity(layerId, opacity) {
    const layerData = layers[layerId];
    if (!layerData) return;

    if (layerData.config.type === 'raster') {
        layerData.leafletLayer.setOpacity(opacity);
    } else {
        layerData.leafletLayer.setStyle({
            fillOpacity: opacity,
            opacity: opacity > 0.1 ? 1 : opacity // keep border visible unless very low
        });
    }

    // Update config
    if (layerData.config.style) {
        if (layerData.config.type === 'raster') {
            layerData.config.style.opacity = opacity;
        } else {
            layerData.config.style.fillOpacity = opacity;
        }
    } else {
        layerData.config.style = { opacity: opacity };
    }
}

// ========================================
// Legend
// ========================================

function buildLegend() {
    const container = document.getElementById('legend-content');
    if (!container) return;
    
    container.innerHTML = '';

    layerConfig.groups.forEach(group => {
        group.layers.forEach(layer => {
            if (!layer.visible) return;

            const symbolClass = layer.type === 'line' ? 'line' : layer.type === 'point' ? 'point' : layer.type === 'raster' ? 'raster' : '';
            const item = document.createElement('div');
            item.className = 'legend-item';

            // Safe color retrieval
            const color = layer.style ? (layer.style.fillColor || layer.style.color) : (layer.type === 'raster' ? 'linear-gradient(45deg, #27ae60, #f39c12, #e74c3c)' : '#7f8c8d');

            item.innerHTML = `
                <div class="legend-symbol ${symbolClass}" style="background: ${color}"></div>
                <span>${layer.name}</span>
            `;
            container.appendChild(item);
        });
    });

    // Dynamically add Simulation Legends if they exist on the map
    if (Object.values(simLayers).some(layer => layer !== null)) {
        const itemHeader = document.createElement('div');
        itemHeader.style.marginTop = '10px';
        itemHeader.style.fontWeight = 'bold';
        itemHeader.style.fontSize = '11px';
        itemHeader.style.color = 'var(--text-muted)';
        itemHeader.textContent = 'SIMULATION RESULTS';
        container.appendChild(itemHeader);

        const simLegends = [
            { id: 'tog-relief', label: 'Relief Camp', color: '#3498db' },
            { id: 'tog-hospitals', label: 'Temp. Hospital', color: '#e74c3c' },
            { id: 'tog-kitchens', label: 'Comm. Kitchen', color: '#e67e22' },
            { id: 'tog-at-risk', label: 'At-Risk Building', color: '#e74c3c' },
            { id: 'tog-safe', label: 'Safe Building', color: '#27ae60' },
            { id: 'tog-risk-zones', label: 'Flood Risk Zone', color: 'linear-gradient(45deg, #27ae60, #f39c12, #e74c3c)' }
        ];

        simLegends.forEach(legend => {
            const toggle = document.getElementById(legend.id);
            if (toggle && toggle.checked) {
                const item = document.createElement('div');
                item.className = 'legend-item';
                item.innerHTML = `
                    <div class="legend-symbol ${legend.color.includes('gradient') ? 'raster' : 'point'}" style="background: ${legend.color}"></div>
                    <span>${legend.label}</span>
                `;
                container.appendChild(item);
            }
        });
    }
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
    const requestSeq = ++statusRequestSeq;
    try {
        const response = await fetch(`${CONFIG.API_URL}/current_status`);
        if (response.ok) {
            const data = await response.json();

            // Ignore stale responses that arrive late.
            if (requestSeq < lastAppliedStatusSeq) return;
            lastAppliedStatusSeq = requestSeq;

            updateMetrics(data);
            if (!simulationDashboardMode) {
                fetchActiveAlerts(requestSeq);
            }
        }
    } catch (error) {
        console.warn('Could not fetch status');
    }
}

function updateMetrics(data) {
    const rainfall = data.latest_rainfall_mm || 0;
    currentIntensity = rainfall;

    if (!simulationDashboardMode) {
        document.getElementById('rainfall-value').textContent = rainfall.toFixed(1);
        document.getElementById('water-level-value').textContent = data.latest_water_level_m?.toFixed(2) || '0.00';
        document.getElementById('discharge-value').textContent = data.latest_discharge_m3s?.toFixed(1) || '0.0';
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();

        // Update risk level
        const risk = data.risk_level?.toLowerCase() || 'normal';
        const riskCard = document.getElementById('risk-card');
        riskCard.className = `status-card risk-card ${risk}`;
        document.getElementById('risk-level').textContent = risk.toUpperCase();
        document.getElementById('risk-message').textContent = data.status_message || 'System operational';
    }

    // --- AUTO SYNC LIVE TELEMETRY TO FLOOD SIMULATOR ---
    const wl = data.latest_water_level_m || 0;
    const rainfallSlider = document.getElementById('sim-rainfall');
    const wlSlider = document.getElementById('sim-water-level');
    const autoRunToggle = document.getElementById('auto-sim-toggle');
    const areaSelect = document.getElementById('sim-area');

    // Only force the sliders and simulation if 'Auto-Run' is checked
    if (autoRunToggle && autoRunToggle.checked) {
        if (Date.now() < manualSimHoldUntil) return;

        if (rainfallSlider && wlSlider) {
            rainfallSlider.value = rainfall.toFixed(1);
            wlSlider.value = wl.toFixed(2);
            rainfallSlider.dispatchEvent(new Event('input'));
            wlSlider.dispatchEvent(new Event('input'));
        }

        const areaValue = areaSelect?.value || areaSelect?.options?.[0]?.value || '';
        if (!areaValue) return;

        const simKey = `${rainfall.toFixed(1)}|${wl.toFixed(2)}|${areaValue}`;
        if (autoSimInFlight || simKey === lastAutoSimKey) return;

        // Debounce the call to avoid spamming the backend
        if (window.autoSimTimeout) clearTimeout(window.autoSimTimeout);
        window.autoSimTimeout = setTimeout(async () => {
            const runBtn = document.getElementById('sim-run-btn');
            if (runBtn && !runBtn.disabled) {
                autoSimInFlight = true;
                try {
                    await runFloodSimulation({ isAutoRun: true });
                    lastAutoSimKey = simKey;
                } catch (err) {
                    console.error('Auto simulation failed:', err);
                } finally {
                    autoSimInFlight = false;
                }
            }
        }, 1200);
    }
}

async function fetchActiveAlerts(parentStatusSeq = null) {
    const requestSeq = ++alertsRequestSeq;
    try {
        const response = await fetch(`${CONFIG.API_URL}/alerts?active_only=true&limit=10`);
        if (!response.ok) return;

        const alerts = await response.json();

        // If tied to a status request, ignore alerts from older status cycles.
        if (parentStatusSeq !== null && parentStatusSeq < lastAppliedStatusSeq) return;

        // Ignore stale alert responses that arrive late.
        if (requestSeq < lastAppliedAlertsSeq) return;
        lastAppliedAlertsSeq = requestSeq;

        renderAlerts(alerts);
    } catch (error) {
        console.warn('Could not fetch alerts');
    }
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderAlerts(alerts) {
    const list = document.getElementById('alert-list');
    const count = document.getElementById('alert-count');
    if (!list || !count) return;

    const activeAlerts = Array.isArray(alerts) ? alerts : [];
    count.textContent = activeAlerts.length;

    if (!activeAlerts.length) {
        list.innerHTML = '<div class="no-alerts"><i class="fas fa-check-circle"></i><p>No active alerts</p></div>';
        return;
    }

    list.innerHTML = activeAlerts.map(alert => {
        const sev = (alert.severity || 'low').toLowerCase();
        const time = alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : '--';
        return `
            <div class="alert-item ${sev}">
                <div class="alert-item-header">
                    <span class="alert-severity">${escapeHtml(sev.toUpperCase())}</span>
                    <span class="alert-time">${escapeHtml(time)}</span>
                </div>
                <div class="alert-message">${escapeHtml(alert.message || 'Alert')}</div>
            </div>
        `;
    }).join('');
}

function computeSimRiskLevel(summary, riskZones) {
    const features = riskZones?.features || [];
    if (features.length === 1) {
        return (features[0]?.properties?.risk_level || 'low').toLowerCase();
    }

    if ((summary?.wards_critical || 0) > 0) return 'critical';
    if ((summary?.wards_high || 0) > 0) return 'high';
    if ((summary?.wards_medium || 0) > 0) return 'medium';
    return 'low';
}

function computeSimDischarge(area, riskZones) {
    const features = riskZones?.features || [];
    if (!features.length) return 0;

    if (area === 'all') {
        const values = features
            .map(f => Number(f?.properties?.dynamic_discharge_m3s || 0))
            .filter(v => Number.isFinite(v));
        if (!values.length) return 0;
        return values.reduce((a, b) => a + b, 0) / values.length;
    }

    return Number(features[0]?.properties?.dynamic_discharge_m3s || 0);
}

function severityRainfall(r) {
    if (r > 150) return 'critical';
    if (r > 100) return 'high';
    if (r > 50) return 'medium';
    return 'low';
}

function severityDischarge(q) {
    if (q > 1000) return 'critical';
    if (q > 500) return 'high';
    if (q > 300) return 'medium';
    return 'low';
}

function severityWaterLevel(w) {
    if (w > 4.0) return 'critical';
    if (w > 3.0) return 'high';
    if (w > 2.5) return 'medium';
    return 'low';
}

function buildSimulationAlerts(rainfall, discharge, waterLevel) {
    const now = new Date().toISOString();
    const alerts = [];

    if (rainfall > 50) {
        alerts.push({
            severity: severityRainfall(rainfall),
            message: `Simulated rainfall ${rainfall.toFixed(1)} mm/hr exceeds threshold 50 mm/hr`,
            timestamp: now,
        });
    }
    if (discharge > 200) {
        alerts.push({
            severity: severityDischarge(discharge),
            message: `Simulated discharge ${discharge.toFixed(1)} m3/s exceeds threshold 200 m3/s`,
            timestamp: now,
        });
    }
    if (waterLevel > 2.5) {
        alerts.push({
            severity: severityWaterLevel(waterLevel),
            message: `Simulated water level ${waterLevel.toFixed(2)} m exceeds danger mark 2.5 m`,
            timestamp: now,
        });
    }

    return alerts;
}

function applySimulationDashboard(data, rainfall, waterLevel, area) {
    simulationDashboardMode = true;

    const riskLevel = computeSimRiskLevel(data.summary, data.risk_zones);
    const discharge = computeSimDischarge(area, data.risk_zones);

    document.getElementById('rainfall-value').textContent = rainfall.toFixed(1);
    document.getElementById('water-level-value').textContent = waterLevel.toFixed(2);
    document.getElementById('discharge-value').textContent = discharge.toFixed(1);
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();

    const riskCard = document.getElementById('risk-card');
    riskCard.className = `status-card risk-card ${riskLevel}`;
    document.getElementById('risk-level').textContent = riskLevel.toUpperCase();

    if (area === 'all') {
        document.getElementById('risk-message').textContent = 'Simulated global view (all wards average discharge)';
    } else {
        document.getElementById('risk-message').textContent = `Simulated ward view: ${area}`;
    }

    const simAlerts = buildSimulationAlerts(rainfall, discharge, waterLevel);
    renderAlerts(simAlerts);
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

// ========================================
// Subbasin Analysis (existing)
// ========================================

function initSimulationListeners() {
    console.log('Subbasin analysis enabled. Select a basin to view characteristics.');
}

function updateSimulation() {
    if (!selectedSubbasin) return;

    const props = selectedSubbasin.feature.properties;
    const areaKm2 = props.Area_km2 || 0;
    const C = 0.736;
    const intensity_mm_hr = currentIntensity;
    const discharge = (C * intensity_mm_hr * areaKm2) / 3.6;

    document.getElementById('est-discharge-value').textContent = `${discharge.toFixed(2)} m³/s`;
}

// ========================================
// FLOOD SIMULATION PANEL
// ========================================

// Layer refs for simulation results
const simLayers = {
    riskZones:        null,   // dynamic ward risk zones
    atRiskBuildings:  null,   // red building markers
    safeBuildings:    null,   // green building markers
    reliefCamps:      null,   // blue tent markers + circles
    tempHospitals:    null,   // red cross markers + circles
    communityKitchens:null,   // orange markers + circles
};

// Simulation preset values (match simulator.py patterns)
const SIM_PRESETS = {
    NORMAL:   { rainfall_mm: 10,  water_level_m: 0.8  },
    MODERATE: { rainfall_mm: 30,  water_level_m: 1.5  },
    HEAVY:    { rainfall_mm: 70,  water_level_m: 2.2  },
    EXTREME:  { rainfall_mm: 150, water_level_m: 3.5  },
};

// Risk level → fill colour
const RISK_COLORS = {
    low:      '#27ae60',
    medium:   '#f39c12',
    high:     '#e74c3c',
    critical: '#8e0000',
};

async function initFloodSimulation() {
    // Populate ward dropdown
    try {
        const resp = await fetch(`${CONFIG.API_URL}/geojson/flood_zones.geojson`);
        if (resp.ok) {
            const geojson = await resp.json();
            const select = document.getElementById('sim-area');
            geojson.features.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.properties.name;
                opt.textContent = f.properties.name;
                select.appendChild(opt);
            });

            if (!select.value && select.options.length > 0) {
                select.value = select.options[0].value;
            }
        }
    } catch (e) { /* optional — ward list is nice-to-have */ }

    // Slider live labels
    const rainfallSlider = document.getElementById('sim-rainfall');
    const wlSlider       = document.getElementById('sim-water-level');
    rainfallSlider.addEventListener('input', () => {
        enableManualSimHold();
        document.getElementById('rainfall-badge').textContent = `${rainfallSlider.value} mm/hr`;
    });
    wlSlider.addEventListener('input', () => {
        enableManualSimHold();
        document.getElementById('wl-badge').textContent = `${parseFloat(wlSlider.value).toFixed(1)} m`;
    });

    const areaSelect = document.getElementById('sim-area');
    if (areaSelect) {
        areaSelect.addEventListener('change', () => enableManualSimHold());
    }

    // Preset buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            enableManualSimHold();
            const p = SIM_PRESETS[btn.dataset.preset];
            if (!p) return;
            rainfallSlider.value = p.rainfall_mm;
            wlSlider.value       = p.water_level_m;
            rainfallSlider.dispatchEvent(new Event('input'));
            wlSlider.dispatchEvent(new Event('input'));
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // Run button
    document.getElementById('sim-run-btn').addEventListener('click', () => {
        enableManualSimHold();
        runFloodSimulation();
    });

    // Clear button
    document.getElementById('sim-clear-btn').addEventListener('click', clearSimulationLayers);
}

async function runFloodSimulation(options = {}) {
    const isAutoRun = options.isAutoRun === true;
    const rainfall    = parseFloat(document.getElementById('sim-rainfall').value) || 0;
    const waterLevel  = parseFloat(document.getElementById('sim-water-level').value) || 0;
    const areaSelect  = document.getElementById('sim-area');
    const area        = areaSelect.value || areaSelect.options?.[0]?.value || '';

    if (!area) {
        console.warn('No simulation area selected');
        return;
    }

    // Show loading
    document.getElementById('sim-loading').style.display = 'block';
    if (!isAutoRun) {
        document.getElementById('sim-results').style.display  = 'none';
        document.getElementById('sim-run-btn').disabled       = true;
    }

    try {
        const resp = await fetch(`${CONFIG.API_URL}/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rainfall_mm:   rainfall,
                water_level_m: waterLevel,
                area:          area,
                k_relief:      5,
                k_hospital:    3,
                k_kitchen:     4,
            }),
        });

        if (!resp.ok) {
            console.error('Simulation API error', resp.status);
            return;
        }

        const data = await resp.json();
        renderSimulationResults(data);
        applySimulationDashboard(data, rainfall, waterLevel, area);

    } catch (err) {
        console.error('Simulation failed:', err);
    } finally {
        document.getElementById('sim-loading').style.display = 'none';
        if (!isAutoRun) {
            document.getElementById('sim-run-btn').disabled = false;
        }
    }
}

function renderSimulationResults(data) {
    clearSimulationLayers();

    const { risk_zones, buildings, facilities, summary } = data;

    // 1 — Dynamic risk zone layer
    if (risk_zones && risk_zones.features) {
        simLayers.riskZones = L.geoJSON(risk_zones, {
            style: feature => {
                const level = feature.properties.risk_level || 'low';
                const color = RISK_COLORS[level] || '#27ae60';
                return {
                    color:       color,
                    weight:      2,
                    fillColor:   color,
                    fillOpacity: level === 'critical' ? 0.55 : level === 'high' ? 0.45 : level === 'medium' ? 0.3 : 0.15,
                    opacity:     1,
                };
            },
            onEachFeature: (feature, layer) => {
                const p = feature.properties;
                layer.bindPopup(`
                    <div class="popup-title">${p.name || 'Ward'}</div>
                    <div class="popup-row"><span class="popup-label">Risk Level:</span>
                        <span class="popup-value" style="color:${RISK_COLORS[p.risk_level]};font-weight:bold">
                            ${(p.risk_level || 'low').toUpperCase()}
                        </span>
                    </div>
                    <div class="popup-row"><span class="popup-label">Risk Score:</span>
                        <span class="popup-value">${p.risk_score?.toFixed(3) ?? '--'}</span></div>
                    <div class="popup-row"><span class="popup-label">Est. Discharge:</span>
                        <span class="popup-value">${p.dynamic_discharge_m3s?.toFixed(1) ?? '--'} m³/s</span></div>
                    <div class="popup-row"><span class="popup-label">Population at Risk:</span>
                        <span class="popup-value">${(p.population_at_risk || 0).toLocaleString()}</span></div>
                    <div class="popup-row"><span class="popup-label">Flood Depth:</span>
                        <span class="popup-value">${p.flood_depth_potential_m ?? '--'} m</span></div>
                `);
            }
        }).addTo(map);
    }

    // 2 — Building layers
    if (buildings && buildings.features) {
        const atRisk = { type: 'FeatureCollection', features: buildings.features.filter(f => f.properties.status === 'at_risk') };
        const safe   = { type: 'FeatureCollection', features: buildings.features.filter(f => f.properties.status === 'safe') };

        simLayers.atRiskBuildings = L.geoJSON(atRisk, {
            pointToLayer: (feature, latlng) => L.marker(latlng, { icon: buildingIcon(feature.properties.osm_type, 'at_risk') }),
            onEachFeature: (feature, layer) => layer.bindPopup(buildingPopup(feature.properties, 'at_risk'))
        }).addTo(map);

        simLayers.safeBuildings = L.geoJSON(safe, {
            pointToLayer: (feature, latlng) => L.marker(latlng, { icon: buildingIcon(feature.properties.osm_type, 'safe') }),
            onEachFeature: (feature, layer) => layer.bindPopup(buildingPopup(feature.properties, 'safe'))
        });
        // Safe buildings are NOT added to map by default — user can toggle them on
    }

    // 3 — Facility layers
    if (facilities) {
        simLayers.reliefCamps        = renderFacilityLayer(facilities.relief_camps?.features       || [], 'relief_camp');
        simLayers.tempHospitals      = renderFacilityLayer(facilities.temp_hospitals?.features     || [], 'temp_hospital');
        simLayers.communityKitchens  = renderFacilityLayer(facilities.community_kitchens?.features || [], 'community_kitchen');
    }

    // 4 — Summary panel
    if (summary) {
        document.getElementById('stat-critical').textContent    = summary.wards_critical || 0;
        document.getElementById('stat-high').textContent        = summary.wards_high || 0;
        document.getElementById('stat-buildings').textContent   = summary.buildings_at_risk || 0;
        const pop = summary.total_population_at_risk || 0;
        document.getElementById('stat-population').textContent  = pop > 1000 ? `${(pop/1000).toFixed(1)}k` : pop;
        document.getElementById('stat-relief').textContent      = summary.relief_camps_count || 0;
        document.getElementById('stat-hospitals').textContent   = summary.temp_hospitals_count || 0;
        document.getElementById('stat-kitchens').textContent    = summary.community_kitchens_count || 0;
        document.getElementById('sim-results').style.display   = 'block';

        // Wire layer toggle checkboxes
        const toggleMap = [
            { id: 'tog-risk-zones',  layerKey: 'riskZones'         },
            { id: 'tog-at-risk',     layerKey: 'atRiskBuildings'    },
            { id: 'tog-safe',        layerKey: 'safeBuildings'      },
            { id: 'tog-relief',      layerKey: 'reliefCamps'        },
            { id: 'tog-hospitals',   layerKey: 'tempHospitals'      },
            { id: 'tog-kitchens',    layerKey: 'communityKitchens'  },
        ];
        toggleMap.forEach(({ id, layerKey }) => {
            const el = document.getElementById(id);
            if (!el) return;
            // Sync initial checkbox state with actual layer presence on map
            el.onchange = () => {
                const layer = simLayers[layerKey];
                if (!layer) return;
                if (el.checked) map.addLayer(layer);
                else            map.removeLayer(layer);
                buildLegend(); // Update legend when toggled
            };
        });
        
        // Build legend initially when simulation results load
        buildLegend();
    }
}

// ---- Facility layer renderer ----

const FACILITY_STYLES = {
    relief_camp:       { color: '#3498db', icon: 'fas fa-campground',    label: 'Relief Camp',        radius: 3.0 },
    temp_hospital:     { color: '#e74c3c', icon: 'fas fa-hospital',      label: 'Temp. Hospital',     radius: 5.0 },
    community_kitchen: { color: '#e67e22', icon: 'fas fa-utensils',      label: 'Community Kitchen',  radius: 2.0 },
};

function renderFacilityLayer(features, facilityType) {
    if (!features.length) return null;

    const style   = FACILITY_STYLES[facilityType];
    const radiusPx = style.radius * 1000; // km → metres for Leaflet circle

    const group = L.layerGroup();

    features.forEach(feature => {
        const p    = feature.properties;
        const lat  = feature.geometry.coordinates[1];
        const lon  = feature.geometry.coordinates[0];

        // Coverage circle
        L.circle([lat, lon], {
            radius:      radiusPx,
            color:       style.color,
            fillColor:   style.color,
            fillOpacity: 0.07,
            weight:      1.5,
            dashArray:   '6 4',
        }).addTo(group);

        // Marker
        const icon = L.divIcon({
            html: `<div class="facility-marker facility-marker--${facilityType}" style="background:${style.color}">
                     <i class="${style.icon}"></i>
                     <span class="facility-label">${style.label}</span>
                   </div>`,
            className: '',
            iconSize:  [52, 52],
            iconAnchor:[26, 26],
        });

        L.marker([lat, lon], { icon })
            .bindPopup(`
                <div class="popup-title">${p.name || 'Unnamed'}</div>
                <div class="popup-row"><span class="popup-label">Role:</span>
                    <span class="popup-value">${style.label}</span></div>
                <div class="popup-row"><span class="popup-label">Type:</span>
                    <span class="popup-value">${p.type_label || p.osm_type || '--'}</span></div>
                <div class="popup-row"><span class="popup-label">Population Served:</span>
                    <span class="popup-value">${(p.population_served || 0).toLocaleString()}</span></div>
                <div class="popup-row"><span class="popup-label">Avg Distance:</span>
                    <span class="popup-value">${p.avg_distance_km?.toFixed(2) ?? '--'} km</span></div>
                <div class="popup-row"><span class="popup-label">Coverage Radius:</span>
                    <span class="popup-value">${p.coverage_radius_km ?? '--'} km</span></div>
                ${p.elevation_m ? `<div class="popup-row"><span class="popup-label">Elevation:</span>
                    <span class="popup-value">${p.elevation_m.toFixed(0)} m</span></div>` : ''}
            `)
            .addTo(group);
    });

    group.addTo(map);
    return group;
}

// ---- Building icon + popup helpers ----

const BUILDING_ICONS = {
    school:           'fas fa-school',
    college:          'fas fa-university',
    university:       'fas fa-university',
    hospital:         'fas fa-hospital',
    clinic:           'fas fa-clinic-medical',
    community_centre: 'fas fa-building',
    place_of_worship: 'fas fa-place-of-worship',
    marketplace:      'fas fa-store',
    fire_station:     'fas fa-fire-extinguisher',
    police:           'fas fa-shield-alt',
    stadium:          'fas fa-running',
    sports_centre:    'fas fa-dumbbell',
};

function buildingIcon(osmType, status) {
    const color    = status === 'at_risk' ? '#e74c3c' : '#27ae60';
    const iconCls  = BUILDING_ICONS[osmType] || 'fas fa-map-marker-alt';
    return L.divIcon({
        html: `<div class="building-marker ${status}" style="border-color:${color}">
                 <i class="${iconCls}" style="color:${color};font-size:11px"></i>
               </div>`,
        className: '',
        iconSize:  [24, 24],
        iconAnchor:[12, 12],
    });
}

function buildingPopup(props, status) {
    const statusLabel = status === 'at_risk'
        ? '<span style="color:#e74c3c;font-weight:bold">⚠ AT RISK</span>'
        : '<span style="color:#27ae60;font-weight:bold">✓ SAFE</span>';
    return `
        <div class="popup-title">${props.type_label || props.osm_type || 'Building'}</div>
        <div class="popup-row"><span class="popup-label">Name:</span>
            <span class="popup-value">${props.name || 'Unnamed'}</span></div>
        <div class="popup-row"><span class="popup-label">Status:</span>
            <span class="popup-value">${statusLabel}</span></div>
        <div class="popup-row"><span class="popup-label">Ward:</span>
            <span class="popup-value">${props.overlapping_ward || '--'}</span></div>
        <div class="popup-row"><span class="popup-label">Ward Risk:</span>
            <span class="popup-value">${(props.ward_risk_level || '--').toUpperCase()}</span></div>
        ${props.elevation_m != null ? `<div class="popup-row"><span class="popup-label">Elevation:</span>
            <span class="popup-value">${props.elevation_m.toFixed(0)} m</span></div>` : ''}
        ${props.recommended_as ? `<div class="popup-row"><span class="popup-label">Recommended As:</span>
            <span class="popup-value" style="color:#27ae60">${props.recommended_as.replace(/_/g,' ')}</span></div>` : ''}
    `;
}

function clearSimulationLayers() {
    Object.values(simLayers).forEach(layer => {
        if (layer) map.removeLayer(layer);
    });
    Object.keys(simLayers).forEach(k => simLayers[k] = null);
    document.getElementById('sim-results').style.display = 'none';
    document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
    // Reset toggles to defaults
    ['tog-risk-zones','tog-at-risk','tog-relief','tog-hospitals','tog-kitchens'].forEach(id => {
        const el = document.getElementById(id); if (el) el.checked = true;
    });
    const safeTog = document.getElementById('tog-safe'); if (safeTog) safeTog.checked = false;

    // Return dashboard to live sensor mode.
    simulationDashboardMode = false;
    fetchCurrentStatus();
}
