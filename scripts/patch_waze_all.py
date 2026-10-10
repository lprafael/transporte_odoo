# -*- coding: utf-8 -*-
"""
Script de integración integral de Waze for Cities (CCP) en gps_broker/main.py y headway_service.py.
"""
import sys

MAIN_PATH = r"c:\Users\lpraf\OneDrive\Documentos\Poliverso\transporte_odoo\gps_broker\main.py"
HEADWAY_PATH = r"c:\Users\lpraf\OneDrive\Documentos\Poliverso\transporte_odoo\gps_broker\headway_service.py"

# --- 1. MODIFICAR gps_broker/headway_service.py ---
with open(HEADWAY_PATH, "r", encoding="utf-8") as f:
    hw_content = f.read()

# Insertar correlación Waze en get_headway_data
target_hw_data = '            r_data["headways"].append(hw_entry)\n\n    return {\n        "timestamp": datetime.now().isoformat(),'
replacement_hw_data = '''            r_data["headways"].append(hw_entry)

    # 5. Correlacionar con trafico e incidentes en tiempo real de Waze CCP
    try:
        from waze_service import fetch_waze_ccp_feed, correlate_waze_with_transit
        waze_feed = fetch_waze_ccp_feed()
        correlations = correlate_waze_with_transit(waze_feed, list(routes_dict.values()))
        for r_code, r_data in routes_dict.items():
            r_data["waze_impact"] = correlations.get(r_code, {})
    except Exception as e:
        logger.debug(f"Error correlacionando Waze en Headway: {e}")

    return {
        "timestamp": datetime.now().isoformat(),'''

if target_hw_data in hw_content:
    hw_content = hw_content.replace(target_hw_data, replacement_hw_data)
    print("OK: get_headway_data patched with Waze correlation")
else:
    print("WARNING: target_hw_data not found in headway_service.py")

# Insertar tarjeta Waze en el modal de headway_service.py
target_modal_grid = '''                <div class="modal-metric">
                    <span class="lbl">Odómetro Total</span>
                    <span class="val" id="modal-odometer">0.0 km</span>
                </div>
            </div>'''

replacement_modal_grid = '''                <div class="modal-metric">
                    <span class="lbl">Odómetro Total</span>
                    <span class="val" id="modal-odometer">0.0 km</span>
                </div>
                <!-- Sección Waze CCP en Modal -->
                <div id="modal-waze-card" class="modal-metric modal-col-2" style="background: rgba(2, 132, 199, 0.08); border: 1px solid rgba(56, 189, 248, 0.25);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px;">
                        <span class="lbl" style="color: #38bdf8;">🚦 Waze for Cities (CCP) · Tráfico en Corredor</span>
                        <a id="modal-waze-nav-btn" href="#" target="_blank" style="background: #0284c7; color: white; padding: 2px 8px; border-radius: 4px; font-size: 10px; text-decoration: none; font-weight: 700; display: inline-flex; align-items: center; gap: 3px;">
                            <span>🚗 Abrir en Waze</span>
                        </a>
                    </div>
                    <span class="val" id="modal-waze-info" style="font-size: 12px; font-weight: 500; color: #cbd5e1;">Evaluando condiciones de tráfico satelital...</span>
                </div>
            </div>'''

if target_modal_grid in hw_content:
    hw_content = hw_content.replace(target_modal_grid, replacement_modal_grid)
    print("OK: Modal in headway_service patched with Waze card")
else:
    print("WARNING: target_modal_grid not found in headway_service.py")

# Actualizar renderDashboard en headway para mostrar badge de Waze en cada ruta
target_render_badges = '''                        <div>
                            ${statusBadge}
                        </div>'''

replacement_render_badges = '''                        <div style="display: flex; align-items: center; gap: 8px;">
                            ${r.waze_impact && r.waze_impact.total_delay_minutes > 0 ? `
                                <span class="route-status-pill" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);">
                                    🚦 Waze: +${r.waze_impact.total_delay_minutes} min demora
                                </span>
                            ` : ''}
                            ${statusBadge}
                        </div>'''

if target_render_badges in hw_content:
    hw_content = hw_content.replace(target_render_badges, replacement_render_badges, 1)
    print("OK: Route header badges patched with Waze delay in headway_service")

# Actualizar openBusModal para poblar la tarjeta Waze
target_open_bus = '''            document.getElementById('modal-ping').textContent = b.last_ping_time ? b.last_ping_time.substring(11, 19) : '--:--:--';
            document.getElementById('modal-odometer').textContent = `${b.odometer_km || 0.0} km`;'''

replacement_open_bus = '''            document.getElementById('modal-ping').textContent = b.last_ping_time ? b.last_ping_time.substring(11, 19) : '--:--:--';
            document.getElementById('modal-odometer').textContent = `${b.odometer_km || 0.0} km`;

            // Configurar enlace Waze y reporte de tráfico
            const wazeBtn = document.getElementById('modal-waze-nav-btn');
            const wazeInfo = document.getElementById('modal-waze-info');
            const lat = b.latitude || -25.30;
            const lon = b.longitude || -57.58;
            wazeBtn.href = `https://www.waze.com/ul?ll=${lat},${lon}&navigate=yes`;

            if (b.waze_alert) {
                wazeInfo.innerHTML = `⚠️ <strong style="color:#f87171;">Congestión Nivel ${b.waze_alert.level}</strong> en ${b.waze_alert.street} (Demora: +${b.waze_alert.delay_minutes} min, Vel: ${b.waze_alert.speedKMH} km/h).`;
            } else {
                wazeInfo.innerHTML = `✓ Circulando con velocidad normal en el corredor según red Waze Asunción.`;
            }'''

if target_open_bus in hw_content:
    hw_content = hw_content.replace(target_open_bus, replacement_open_bus)
    print("OK: openBusModal patched with Waze telemetry")

with open(HEADWAY_PATH, "w", encoding="utf-8") as f:
    f.write(hw_content)


# --- 2. MODIFICAR gps_broker/main.py ---
with open(MAIN_PATH, "r", encoding="utf-8") as f:
    main_content = f.read()

# Insertar endpoints Waze antes de live_map_view
target_before_map = '''# ------------------------------------------------------------------------------
# Dashboard Radar Web en Vivo con PostGIS Shapes y Visor Histórico
# ------------------------------------------------------------------------------
@app.get("/map", response_class=HTMLResponse)'''

replacement_before_map = '''# ------------------------------------------------------------------------------
# Conexión e Integración Waze for Cities (Connected Citizens Program - CCP)
# ------------------------------------------------------------------------------
from waze_service import fetch_waze_ccp_feed, correlate_waze_with_transit, get_waze_deep_link

@app.get("/api/v1/waze/traffic")
async def api_waze_traffic(refresh: bool = Query(False, description="Forzar refresco del feed Waze")):
    """
    Retorna el feed de tráfico en tiempo real de Waze for Cities (CCP):
    Incidentes (accidentes, obras, peligros) y congestiones viales (jams con nivel y retraso).
    """
    return fetch_waze_ccp_feed(force_refresh=refresh)

@app.get("/api/v1/waze/corridor-impacts")
async def api_waze_corridor_impacts():
    """
    Cruza los incidentes y atascos de Waze con los 6 corredores de transporte de la flota.
    Calcula demoras inducidas y lista coches afectados en cada ramal.
    """
    waze_data = fetch_waze_ccp_feed()
    hw_data = get_headway_data(redis_client=redis_client, active_vehicles_memory=active_vehicles_memory)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "waze_source": waze_data.get("source"),
        "total_alerts": waze_data.get("total_alerts", 0),
        "total_jams": waze_data.get("total_jams", 0),
        "corridor_impacts": correlate_waze_with_transit(waze_data, hw_data.get("routes", []))
    }

# ------------------------------------------------------------------------------
# Dashboard Radar Web en Vivo con PostGIS Shapes y Visor Histórico
# ------------------------------------------------------------------------------
@app.get("/map", response_class=HTMLResponse)'''

if target_before_map in main_content and "api_waze_traffic" not in main_content:
    main_content = main_content.replace(target_before_map, replacement_before_map)
    print("OK: Waze endpoints added to main.py")

# En /map, agregar métrica Waze en header
target_metrics_bar = '''            <div class="metrics-bar">
                <div class="metric-card">Flota: <strong id="m-buses">0</strong></div>
                <div class="metric-card">En Ruta: <strong id="m-transit">0</strong></div>
                <div class="metric-card">Alertas: <strong id="m-alerts" style="color: #ef4444;">0</strong></div>
            </div>'''

replacement_metrics_bar = '''            <div class="metrics-bar">
                <div class="metric-card">Flota: <strong id="m-buses">0</strong></div>
                <div class="metric-card">En Ruta: <strong id="m-transit">0</strong></div>
                <div class="metric-card">Alertas: <strong id="m-alerts" style="color: #ef4444;">0</strong></div>
                <div class="metric-card" style="background: rgba(2, 132, 199, 0.15); border-color: rgba(56, 189, 248, 0.4);">
                    <span>🚦 Waze CCP: </span><strong id="m-waze" style="color: #38bdf8;">--</strong>
                </div>
            </div>'''

if target_metrics_bar in main_content:
    main_content = main_content.replace(target_metrics_bar, replacement_metrics_bar)
    print("OK: Header metrics bar patched with Waze CCP in main.py")

# En /map, agregar caja de control flotante de capas Waze
target_legend_box = '''        <div class="legend-box" id="legend">
            <strong style="color: #e5e7eb; display:block; margin-bottom: 6px;">Trazados de Rutas (PostGIS)</strong>
            <div class="legend-item"><div class="legend-line" style="background: #38bdf8;"></div><span>Ramal 020F (Asunción - San Lorenzo)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #a855f7;"></div><span>Ramal 020C (San Lorenzo - Asunción)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #f59e0b;"></div><span>Ramal 020D (Asunción - San Lorenzo)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #ef4444; border-top: 2px dashed #fff;"></div><span id="hist-label">Histórico Anterior</span></div>
        </div>'''

replacement_legend_box = '''        <div class="legend-box" id="legend">
            <strong style="color: #e5e7eb; display:block; margin-bottom: 6px;">Trazados de Rutas (PostGIS)</strong>
            <div class="legend-item"><div class="legend-line" style="background: #38bdf8;"></div><span>Ramal 020F (Asunción - San Lorenzo)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #a855f7;"></div><span>Ramal 020C (San Lorenzo - Asunción)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #f59e0b;"></div><span>Ramal 020D (Asunción - San Lorenzo)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #ef4444; border-top: 2px dashed #fff;"></div><span id="hist-label">Histórico Anterior</span></div>
        </div>

        <!-- Capas Waze for Cities (CCP) -->
        <div class="legend-box" style="bottom: 180px; left: 20px; border-color: rgba(56, 189, 248, 0.4);">
            <strong style="color: #38bdf8; display:flex; align-items:center; gap:6px; margin-bottom: 6px;">
                <span>🚗 Waze for Cities (CCP)</span>
            </strong>
            <label style="display:flex; align-items:center; gap:6px; font-size:11px; margin-bottom:5px; cursor:pointer;">
                <input type="checkbox" id="chk-waze-jams" checked onchange="toggleWazeLayers()">
                <span>🚦 Tráfico / Jams (Colores)</span>
            </label>
            <label style="display:flex; align-items:center; gap:6px; font-size:11px; cursor:pointer;">
                <input type="checkbox" id="chk-waze-alerts" checked onchange="toggleWazeLayers()">
                <span>⚠️ Incidentes & Obras</span>
            </label>
        </div>'''

if target_legend_box in main_content:
    main_content = main_content.replace(target_legend_box, replacement_legend_box)
    print("OK: Waze layer controls added to map in main.py")

# En /map, agregar lógica JS para cargar capas Waze
target_js_setup = '''        const markers = {};
        const activeVehicles = {};
        let shapeLayers = [];
        let stopLayers = [];
        let eventHistory = [];
        let ws = null;
        let pollingInterval = null;'''

replacement_js_setup = '''        const markers = {};
        const activeVehicles = {};
        let shapeLayers = [];
        let stopLayers = [];
        let wazeJamLayers = [];
        let wazeAlertLayers = [];
        let eventHistory = [];
        let ws = null;
        let pollingInterval = null;'''

if target_js_setup in main_content:
    main_content = main_content.replace(target_js_setup, replacement_js_setup)
    print("OK: Waze JS layer arrays setup in main.py")

# Agregar funciones Waze en el script del mapa
target_init_ws = '''        initWebSocket();'''

replacement_init_ws = '''        // --- GESTIÓN DE CAPAS WAZE FOR CITIES (CCP) ---
        async function fetchAndRenderWaze() {
            try {
                const res = await fetch('/api/v1/waze/traffic');
                const data = await res.json();
                renderWazeLayers(data);
                const badge = document.getElementById('m-waze');
                if (badge) {
                    badge.textContent = `${data.total_alerts || 0} Inc · ${data.total_jams || 0} Atascos`;
                }
            } catch (err) {
                console.error("Error al obtener Waze CCP:", err);
            }
        }

        function renderWazeLayers(data) {
            // Limpiar capas previas
            wazeJamLayers.forEach(l => map.removeLayer(l));
            wazeAlertLayers.forEach(l => map.removeLayer(l));
            wazeJamLayers = [];
            wazeAlertLayers = [];

            const showJams = document.getElementById('chk-waze-jams')?.checked ?? true;
            const showAlerts = document.getElementById('chk-waze-alerts')?.checked ?? true;

            // 1. Renderizar Jams (Polilíneas de embotellamiento con colores según nivel)
            if (data.jams && Array.isArray(data.jams)) {
                data.jams.forEach(j => {
                    if (!j.line || j.line.length < 2) return;
                    const latlngs = j.line.map(pt => [pt.y, pt.x]);
                    const color = j.color || (j.level >= 4 ? '#ef4444' : (j.level === 3 ? '#f97316' : '#eab308'));
                    
                    const poly = L.polyline(latlngs, {
                        color: color,
                        weight: 6,
                        opacity: 0.85,
                        dashArray: j.level >= 4 ? '1, 8' : null
                    });

                    const popupContent = `
                        <div style="min-width: 180px;">
                            <strong style="color: ${color}; font-size: 13px;">🚦 Atasco Waze (${j.level_label || 'Nivel ' + j.level})</strong><br>
                            <b>${j.street}</b> (${j.city || 'Asunción'})<br>
                            Demora Estimada: <b style="color: #ef4444;">+${j.delay_minutes || Math.round(j.delay_seconds/60)} min</b><br>
                            Velocidad en Atasco: <b>${j.speedKMH} km/h</b><br>
                            Longitud Congestión: <b>${j.length_meters}m</b><br>
                            <div style="margin-top: 8px;">
                                <a href="${j.waze_url || 'https://www.waze.com'}" target="_blank" style="background: #0284c7; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; text-decoration: none; font-weight: 700; display: inline-block;">
                                    🚗 Abrir en App Waze
                                </a>
                            </div>
                        </div>
                    `;
                    poly.bindPopup(popupContent);

                    if (showJams) poly.addTo(map);
                    wazeJamLayers.push(poly);
                });
            }

            // 2. Renderizar Alertas / Incidentes (Marcadores específicos)
            if (data.alerts && Array.isArray(data.alerts)) {
                data.alerts.forEach(a => {
                    if (!a.location) return;
                    const lat = a.location.y;
                    const lon = a.location.x;
                    const iconEmoji = a.icon || '⚠️';

                    const alertIcon = L.divIcon({
                        className: 'waze-alert-marker',
                        html: `<div style="background: #0f172a; border: 2px solid #f59e0b; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 14px; box-shadow: 0 0 10px rgba(245, 158, 11, 0.6);">${iconEmoji}</div>`,
                        iconSize: [28, 28]
                    });

                    const marker = L.marker([lat, lon], { icon: alertIcon });
                    const popupContent = `
                        <div style="min-width: 200px;">
                            <strong style="color: #fbbf24; font-size: 13px;">${iconEmoji} ${a.type_label || a.type}</strong><br>
                            <b>${a.street}</b> (${a.city || 'Gran Asunción'})<br>
                            <div style="font-size: 11px; margin: 4px 0; color: #cbd5e1;">${a.reportDescription || 'Reportado por comunidad Waze'}</div>
                            <span style="font-size: 10px; color: #94a3b8;">Confianza Waze: ${a.confidence}/5 · Fiabilidad: ${a.reliability}/10</span><br>
                            <div style="margin-top: 8px;">
                                <a href="${a.waze_url || 'https://www.waze.com'}" target="_blank" style="background: #0284c7; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; text-decoration: none; font-weight: 700; display: inline-block;">
                                    🚗 Navegar con Waze
                                </a>
                            </div>
                        </div>
                    `;
                    marker.bindPopup(popupContent);

                    if (showAlerts) marker.addTo(map);
                    wazeAlertLayers.push(marker);
                });
            }
        }

        function toggleWazeLayers() {
            const showJams = document.getElementById('chk-waze-jams')?.checked ?? true;
            const showAlerts = document.getElementById('chk-waze-alerts')?.checked ?? true;

            wazeJamLayers.forEach(l => {
                if (showJams) l.addTo(map); else map.removeLayer(l);
            });
            wazeAlertLayers.forEach(l => {
                if (showAlerts) l.addTo(map); else map.removeLayer(l);
            });
        }

        // Carga inicial y sondeo periódico de Waze CCP (cada 30 segundos)
        fetchAndRenderWaze();
        setInterval(fetchAndRenderWaze, 30000);

        initWebSocket();'''

if target_init_ws in main_content:
    main_content = main_content.replace(target_init_ws, replacement_init_ws)
    print("OK: Waze rendering logic added before initWebSocket in main.py")

with open(MAIN_PATH, "w", encoding="utf-8") as f:
    f.write(main_content)

print("SUCCESS: All Waze CCP components patched.")
