# -*- coding: utf-8 -*-
"""
Servicio de ETA Predictivo por Parada (Tiempo de Espera en Tiempo Real)
=======================================================================
Calcula cuanto falta para que llegue el proximo bus electrico a cada parada,
usando posicion GPS real + velocidad media historica por tramo PostGIS.

Expone:
  - /api/v1/eta/{stop_code}   - JSON con ETA de proximos buses
  - /parada/{stop_code}       - Pagina movil HTML con QR embebido
  - /api/v1/eta/all           - ETA de todas las paradas activas

Tecnologia:
  - PostGIS ST_LineLocatePoint para ubicacion exacta en el shape
  - Redis cache con TTL de 20s para baja latencia
  - Velocidad media historica calculada desde telemetry_ping (ultimas 4h)
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("eta_service")

PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB   = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

DEFAULT_CITY_SPEED_KMH = 22.0
MAX_BUSES_PER_STOP = 3
ETA_CACHE_TTL = 20

ELECTRIC_ROUTES = ['020c', '020d', '020e', '020f', '0210', '0211']


def _pg_connect():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS, connect_timeout=3
    )


def get_stop_catalog() -> List[Dict[str, Any]]:
    """Retorna todas las paradas activas con su posicion en cada shape de ruta."""
    try:
        conn = _pg_connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                s.id            AS stop_id,
                s.stop_code,
                s.name          AS stop_name,
                s.stop_type,
                s.address,
                s.radius_meters,
                ST_Y(s.geom)    AS latitude,
                ST_X(s.geom)    AS longitude,
                r.code          AS route_code,
                r.name          AS route_name,
                r.direction,
                sh.total_km     AS route_total_km,
                ST_LineLocatePoint(sh.geom, s.geom) AS stop_fraction
            FROM transit_stop s
            JOIN transit_route r ON r.code = ANY(%s)
            JOIN transit_route_shape sh
                ON sh.route_id = r.id
               AND sh.valid_from <= CURRENT_DATE
               AND (sh.valid_until IS NULL OR sh.valid_until > CURRENT_DATE)
            WHERE s.valid_from <= CURRENT_DATE
              AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
            ORDER BY s.stop_code, r.code, stop_fraction;
        """, (ELECTRIC_ROUTES,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error cargando catalogo de paradas: {e}")
        return []


def get_avg_speed_for_route(route_code: str) -> float:
    """
    Calcula la velocidad media (km/h) de un ramal en las ultimas 4 horas
    a partir del historico de telemetry_ping. Si no hay datos, usa el default.
    """
    try:
        conn = _pg_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT AVG(speed_kmh)
            FROM telemetry_ping
            WHERE route_id = %s
              AND recorded_at >= NOW() - INTERVAL '4 hours'
              AND speed_kmh > 2
              AND speed_kmh < 80
        """, (route_code,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0] is not None:
            return max(5.0, float(row[0]))
    except Exception as e:
        logger.debug(f"No se pudo calcular velocidad media para {route_code}: {e}")
    return DEFAULT_CITY_SPEED_KMH


def compute_eta_for_stop(stop_code: str, active_vehicles: List[Dict], redis_client=None) -> Dict[str, Any]:
    """
    Calcula los ETAs de todos los buses activos que se dirigen a una parada.

    Logica:
      1. Obtener la fraccion de la parada en el shape (0.0 a 1.0 via ST_LineLocatePoint)
      2. Para cada bus activo en la misma ruta con fraccion < stop_fraction:
         - distancia_restante = (stop_fraction - bus_fraction) * route_total_km
         - eta_min = distancia_restante / velocidad_media * 60
      3. Ordenar por ETA ascendente -> primer bus = proximo en llegar
    """
    # Cache Redis
    if redis_client:
        try:
            cached = redis_client.get(f"eta:stop:{stop_code}")
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    stop_info = None
    stop_route_fractions: Dict[str, float] = {}
    stop_route_total_km: Dict[str, float] = {}

    try:
        conn = _pg_connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                s.stop_code, s.name, s.address,
                ST_Y(s.geom) AS latitude,
                ST_X(s.geom) AS longitude,
                r.code AS route_code,
                sh.total_km,
                ST_LineLocatePoint(sh.geom, s.geom) AS stop_fraction
            FROM transit_stop s
            JOIN transit_route r ON r.code = ANY(%s)
            JOIN transit_route_shape sh
                ON sh.route_id = r.id
               AND sh.valid_from <= CURRENT_DATE
               AND (sh.valid_until IS NULL OR sh.valid_until > CURRENT_DATE)
            WHERE s.stop_code = %s
              AND s.valid_from <= CURRENT_DATE
              AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
        """, (ELECTRIC_ROUTES, stop_code))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return {"error": f"Parada '{stop_code}' no encontrada", "stop_code": stop_code}

        first = rows[0]
        stop_info = {
            "stop_code": first["stop_code"],
            "stop_name": first["name"],
            "address": first["address"] or "",
            "latitude": float(first["latitude"]),
            "longitude": float(first["longitude"]),
        }
        for r in rows:
            stop_route_fractions[r["route_code"]] = float(r["stop_fraction"])
            stop_route_total_km[r["route_code"]] = float(r["total_km"]) if r["total_km"] else 18.5

    except Exception as e:
        logger.error(f"Error obteniendo parada {stop_code}: {e}")
        return {"error": str(e), "stop_code": stop_code}

    upcoming: List[Dict] = []
    speed_cache: Dict[str, float] = {}

    for v in active_vehicles:
        route_code = (v.get("route_id") or "").lower()
        if route_code not in stop_route_fractions:
            continue

        stop_fraction = stop_route_fractions[route_code]
        total_km = stop_route_total_km[route_code]

        dist_km = float(v.get("distance_traveled_km") or 0.0)
        bus_fraction = min(1.0, dist_km / total_km) if total_km > 0 else float(v.get("progress_percent", 0.0)) / 100.0

        # Solo buses que aun NO pasaron la parada
        if bus_fraction >= stop_fraction:
            continue

        remaining_km = max(0.05, (stop_fraction - bus_fraction) * total_km)

        if route_code not in speed_cache:
            speed_cache[route_code] = get_avg_speed_for_route(route_code)
        avg_speed = speed_cache[route_code]

        eta_min = (remaining_km / avg_speed) * 60.0

        state = v.get("current_state") or v.get("state") or "IN_TRANSIT"
        if state == "AT_ORIGIN":
            eta_min += 3.0  # tiempo estimado de espera en cabecera

        upcoming.append({
            "bus_id": v.get("bus_id"),
            "license_plate": v.get("license_plate") or f"COCHE-{v.get('bus_id')}",
            "route_code": route_code,
            "state": state,
            "remaining_km": round(remaining_km, 2),
            "eta_minutes": round(eta_min, 1),
            "eta_label": _format_eta_label(eta_min),
            "speed_kmh": float(v.get("speed_kmh") or v.get("last_speed_kmh") or 0.0),
            "street_name": v.get("street_name") or "",
            "status_display": v.get("status_display") or "En Circulacion",
            "last_ping": v.get("last_ping_time") or "",
        })

    upcoming.sort(key=lambda x: x["eta_minutes"])
    upcoming = upcoming[:MAX_BUSES_PER_STOP]

    result = {
        "stop_code": stop_code,
        "stop_name": stop_info["stop_name"],
        "address": stop_info["address"],
        "latitude": stop_info["latitude"],
        "longitude": stop_info["longitude"],
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "next_buses": upcoming,
        "has_arrivals": len(upcoming) > 0,
    }

    if redis_client:
        try:
            redis_client.set(f"eta:stop:{stop_code}", json.dumps(result), ex=ETA_CACHE_TTL)
        except Exception:
            pass

    return result


def _format_eta_label(eta_min: float) -> str:
    if eta_min < 0.8:
        return "Llegando ahora"
    elif eta_min < 2.0:
        return f"~{round(eta_min)} min"
    elif eta_min < 5.0:
        return f"~{round(eta_min)} min"
    elif eta_min < 15.0:
        return f"~{round(eta_min)} min"
    else:
        return f"~{round(eta_min)} min"


def get_all_stop_etas(active_vehicles: List[Dict], redis_client=None) -> List[Dict]:
    """Calcula ETAs para todas las paradas activas."""
    stops = get_stop_catalog()
    seen_codes = set()
    results = []
    for s in stops:
        code = s["stop_code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        eta_data = compute_eta_for_stop(code, active_vehicles, redis_client)
        if "error" not in eta_data:
            results.append(eta_data)
    return results


# ==============================================================================
# HTML pagina movil de parada (sin app, QR embebido, auto-refresh 15s)
# ==============================================================================
def get_stop_page_html(stop_code: str, host_url: str = "") -> str:
    """
    Genera la pagina HTML movil-first para una parada especifica.
    Incluye ETA en tiempo real, QR code para compartir, diseno oscuro premium.
    """
    qr_url = f"{host_url}/parada/{stop_code}"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    <meta name="theme-color" content="#060b14">
    <title>Parada {stop_code} | Electricos Linea 20</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
    <style>
        :root {{
            --bg: #060b14; --card: #0d1527; --border: #1e293b;
            --primary: #38bdf8; --accent: #818cf8;
            --success: #10b981; --warning: #f59e0b; --danger: #ef4444;
            --text: #f8fafc; --muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; padding-bottom: 40px; }}
        .header {{ background: linear-gradient(135deg, #0c1a3a, #0d1527); border-bottom: 1px solid var(--border); padding: 20px 20px 16px; text-align: center; }}
        .electric-badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(56,189,248,.15); border: 1px solid rgba(56,189,248,.3); color: var(--primary); padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 10px; }}
        .stop-name {{ font-size: 22px; font-weight: 900; letter-spacing: -.02em; line-height: 1.2; }}
        .stop-address {{ font-size: 13px; color: var(--muted); margin-top: 4px; }}
        .stop-code-pill {{ display: inline-block; background: rgba(129,140,248,.2); border: 1px solid rgba(129,140,248,.4); color: var(--accent); font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; margin-top: 8px; letter-spacing: .05em; }}
        .live-bar {{ display: flex; align-items: center; justify-content: space-between; padding: 10px 20px; background: rgba(16,185,129,.08); border-bottom: 1px solid rgba(16,185,129,.15); }}
        .live-dot {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--success); }}
        .live-dot::before {{ content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--success); animation: pulse 1.5s infinite; }}
        @keyframes pulse {{ 0%,100% {{ opacity:1; transform:scale(1); }} 50% {{ opacity:.5; transform:scale(1.4); }} }}
        .refresh-timer {{ font-size: 11px; color: var(--muted); }}
        .content {{ padding: 16px 16px 0; }}
        .bus-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px; margin-bottom: 12px; position: relative; overflow: hidden; }}
        .bus-card.first {{ border-color: rgba(16,185,129,.5); background: linear-gradient(135deg, rgba(16,185,129,.08), var(--card) 60%); }}
        .bus-card.first::before {{ content: 'PROXIMO'; position: absolute; top: 10px; right: 12px; font-size: 9px; font-weight: 800; letter-spacing: .12em; color: var(--success); background: rgba(16,185,129,.15); padding: 2px 7px; border-radius: 8px; border: 1px solid rgba(16,185,129,.3); }}
        .bus-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
        .bus-icon {{ width: 44px; height: 44px; border-radius: 12px; background: linear-gradient(135deg, #0284c7, #6366f1); display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }}
        .bus-info {{ flex: 1; min-width: 0; }}
        .bus-plate {{ font-size: 15px; font-weight: 800; letter-spacing: .04em; }}
        .bus-route {{ font-size: 12px; color: var(--muted); margin-top: 1px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .eta-big {{ text-align: center; padding: 12px 0 8px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); margin: 0 -4px; }}
        .eta-value {{ font-size: 48px; font-weight: 900; letter-spacing: -.04em; line-height: 1; }}
        .eta-unit {{ font-size: 14px; color: var(--muted); margin-top: 2px; }}
        .bus-details {{ display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }}
        .detail-chip {{ display: flex; align-items: center; gap: 5px; background: rgba(255,255,255,.04); border: 1px solid var(--border); border-radius: 8px; padding: 5px 10px; font-size: 12px; color: var(--muted); }}
        .detail-chip span {{ color: var(--text); font-weight: 600; }}
        .progress-bar {{ height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; margin-top: 10px; }}
        .progress-fill {{ height: 100%; border-radius: 2px; transition: width .5s ease; }}
        .no-buses {{ background: var(--card); border: 1px dashed var(--border); border-radius: 16px; padding: 40px 20px; text-align: center; color: var(--muted); }}
        .no-buses-icon {{ font-size: 48px; margin-bottom: 12px; }}
        .no-buses-title {{ font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 6px; }}
        .qr-section {{ margin: 24px 16px 0; background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; display: flex; align-items: center; gap: 16px; }}
        .qr-canvas-wrap {{ background: white; border-radius: 10px; padding: 8px; flex-shrink: 0; }}
        .qr-info {{ flex: 1; }}
        .qr-title {{ font-size: 13px; font-weight: 700; margin-bottom: 4px; }}
        .qr-desc {{ font-size: 11px; color: var(--muted); line-height: 1.5; }}
        .footer {{ text-align: center; padding: 24px 16px 0; font-size: 11px; color: var(--muted); }}
        .footer a {{ color: var(--primary); text-decoration: none; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="electric-badge">&#9889; Servicio Electrico Linea 20</div>
        <div class="stop-name" id="stop-name">Cargando...</div>
        <div class="stop-address" id="stop-address"></div>
        <div class="stop-code-pill">PARADA {stop_code}</div>
    </div>
    <div class="live-bar">
        <div class="live-dot">EN VIVO</div>
        <div class="refresh-timer" id="refresh-timer">Actualizando...</div>
    </div>
    <div class="content" id="buses-container">
        <div class="no-buses"><div class="no-buses-icon">&#128260;</div><div class="no-buses-title">Cargando...</div></div>
    </div>
    <div class="qr-section">
        <div class="qr-canvas-wrap"><canvas id="qr-canvas"></canvas></div>
        <div class="qr-info">
            <div class="qr-title">&#128241; Compartir esta parada</div>
            <div class="qr-desc">Escaneá el QR para ver el tiempo de espera en cualquier celular, sin app.</div>
        </div>
    </div>
    <div class="footer">
        <p>Poliverso Transit &middot; Linea 20 Electricos</p>
        <p style="margin-top:4px"><a href="/map">&#128506; Ver mapa</a> &middot; <a href="/headway">&#128202; Frecuencias</a> &middot; <a href="/compliance">&#9989; Cumplimiento VMT</a></p>
    </div>

    <script>
        const STOP_CODE = '{stop_code}';
        let countdown = 15;
        let ticker = null;

        try {{
            QRCode.toCanvas(document.getElementById('qr-canvas'), '{qr_url}', {{
                width: 80, margin: 1,
                color: {{ dark: '#000000', light: '#ffffff' }}
            }});
        }} catch(e) {{}}

        function etaColor(m) {{
            if (m < 2) return '#10b981';
            if (m < 5) return '#f59e0b';
            if (m < 15) return '#f97316';
            return '#ef4444';
        }}

        function renderBuses(data) {{
            document.getElementById('stop-name').textContent = data.stop_name || 'Parada ' + STOP_CODE;
            document.getElementById('stop-address').textContent = data.address || '';
            const container = document.getElementById('buses-container');
            const buses = data.next_buses || [];
            if (!buses.length) {{
                container.innerHTML = '<div class="no-buses"><div class="no-buses-icon">&#128336;</div><div class="no-buses-title">Sin buses en camino</div><p style="font-size:13px;margin-top:8px">No hay electricos en circulacion hacia esta parada ahora.</p></div>';
                return;
            }}
            container.innerHTML = buses.map((bus, idx) => {{
                const color = etaColor(bus.eta_minutes);
                const pct = Math.max(5, Math.min(95, 100 - (bus.eta_minutes / 30) * 100));
                const loc = bus.street_name || bus.status_display;
                return '<div class="bus-card' + (idx===0?' first':'') + '">' +
                    '<div class="bus-header">' +
                        '<div class="bus-icon">&#128652;</div>' +
                        '<div class="bus-info">' +
                            '<div class="bus-plate">' + bus.license_plate + '</div>' +
                            '<div class="bus-route">Ramal ' + bus.route_code.toUpperCase() + ' &middot; ' + loc + '</div>' +
                        '</div></div>' +
                    '<div class="eta-big">' +
                        '<div class="eta-value" style="color:' + color + '">' + (bus.eta_minutes < 1 ? '<1' : Math.round(bus.eta_minutes)) + '</div>' +
                        '<div class="eta-unit">min' + (Math.round(bus.eta_minutes)!==1?'utos':'uto') + ' de espera &middot; ' + bus.eta_label + '</div>' +
                    '</div>' +
                    '<div class="bus-details">' +
                        '<div class="detail-chip">&#128739; <span>' + bus.remaining_km + ' km</span> restantes</div>' +
                        '<div class="detail-chip">&#9889; <span>' + Math.round(bus.speed_kmh) + ' km/h</span></div>' +
                    '</div>' +
                    '<div class="progress-bar"><div class="progress-fill" style="width:' + pct + '%;background:' + color + '"></div></div>' +
                '</div>';
            }}).join('');
        }}

        async function fetchETA() {{
            try {{
                const r = await fetch('/api/v1/eta/' + STOP_CODE);
                const d = await r.json();
                renderBuses(d);
            }} catch(e) {{ console.warn('ETA fetch error:', e); }}
        }}

        function startCountdown() {{
            countdown = 15;
            if (ticker) clearInterval(ticker);
            ticker = setInterval(() => {{
                countdown--;
                document.getElementById('refresh-timer').textContent = 'Actualiza en ' + countdown + 's';
                if (countdown <= 0) {{ fetchETA(); countdown = 15; }}
            }}, 1000);
        }}

        fetchETA().then(startCountdown);
    </script>
</body>
</html>
"""
