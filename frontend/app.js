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
let charts = {};
let featureCount = 0;
let selectedSubbasin = null;
let currentIntensity = 50;

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
    initSimulationListeners();

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
                        id: 'risk_high', name: 'High Risk Zones', file: 'layers/flood_risk_high.geojson', type: 'polygon', visible: true,
                        style: { color: '#e74c3c', weight: 2, fillColor: '#e74c3c', fillOpacity: 0.4 }, zIndex: 150
                    },
                    {
                        id: 'risk_medium', name: 'Medium Risk Zones', file: 'layers/flood_risk_medium.geojson', type: 'polygon', visible: true,
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
                const isSelected = selectedSubbasin && selectedSubbasin.feature.properties.DN === feature.properties.DN;
                return {
                    ...config.style,
                    fillOpacity: isSelected ? 0.6 : (config.style.fillOpacity !== undefined ? config.style.fillOpacity : 0.5),
                    color: isSelected ? '#ff0000' : config.style.color,
                    weight: isSelected ? 4 : config.style.weight,
                    opacity: config.style.opacity !== undefined ? config.style.opacity : 1
                };
            },
            onEachFeature: (feature, layer) => {
                bindPopup(feature, layer);
                if (config.id === 'subbasins') {
                    layer.on('click', (e) => {
                        L.DomEvent.stopPropagation(e);
                        selectSubbasin(layer);
                    });
                }
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
    const rainfall = data.latest_rainfall_mm || 0;
    currentIntensity = rainfall;

    document.getElementById('rainfall-value').textContent = rainfall.toFixed(1);
    document.getElementById('water-level-value').textContent = data.latest_water_level_m?.toFixed(2) || '0.00';
    document.getElementById('discharge-value').textContent = data.latest_discharge_m3s?.toFixed(1) || '0.0';
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();

    // Update simulation if a basin is selected
    if (selectedSubbasin) {
        updateSimulation();
    }

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

// ========================================
// Simulation Logic
// ========================================

function initSimulationListeners() {
    console.log('Subbasin analysis enabled. Select a basin to view characteristics.');
}

function updateSimulation() {
    if (!selectedSubbasin) return;

    const props = selectedSubbasin.feature.properties;
    const areaKm2 = props.Area_km2 || 0;
    const C = 0.736; // Rational Method Runoff Coefficient

    // Q = C * i * A
    // i in m/s = intensity_mm_hr / (1000 * 3600)
    // A in m2 = area_km2 * 1,000,000
    // Q = C * (i/3600) * (A) / 1000
    // Simplified: Q = (C * i * A) / 360
    const intensity_mm_hr = currentIntensity;
    const discharge = (C * intensity_mm_hr * areaKm2) / 3.6; // Correct conversion for m3/s

    document.getElementById('est-discharge-value').textContent = `${discharge.toFixed(2)} m³/s`;
}
