# -*- coding: utf-8 -*-
"""
Servicio del Tablero Lineal de Intervalos (Headway Monitoring & Bunching Detector)
Calcula la posición relativa de cada bus sobre el shape horizontal del ramal,
detecta pegonamiento (buses muy juntos) y genera la interfaz visual interactiva.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("headway_service")

PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def get_headway_data(redis_client=None, active_vehicles_memory=None) -> Dict[str, Any]:
    """Recopila rutas activas y calcula distancias relativas e intervalos entre buses."""
    routes_dict = {}
    
    # 1. Obtener catálogo oficial de ramales desde PostgreSQL
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT r.code, r.name, r.direction, r.origin, r.destination,
                   COALESCE(s.total_km, r.distance_km, 18.0) as distance_km
            FROM transit_route r
            LEFT JOIN LATERAL (
                SELECT total_km
                FROM transit_route_shape
                WHERE route_id = r.id
                  AND valid_from <= CURRENT_DATE
                  AND (valid_until IS NULL OR valid_until > CURRENT_DATE)
                ORDER BY version DESC
                LIMIT 1
            ) s ON TRUE
            WHERE r.code IN ('020c', '020d', '020e', '020f', '0210', '0211')
            ORDER BY r.code;
        """)
        for r in cur.fetchall():
            routes_dict[r['code']] = {
                "route_id": r['code'],
                "name": r['name'],
                "direction": r['direction'],
                "direction_label": "Ida" if r['direction'] == 'inbound' else ("Vuelta" if r['direction'] == 'outbound' else "Circular"),
                "origin": r['origin'] or "Cabecera Origen",
                "destination": r['destination'] or "Cabecera Destino",
                "distance_km": float(r['distance_km']) if r['distance_km'] else 18.02,
                "buses": [],
                "headways": [],
                "bunching_count": 0,
                "status": "NO_BUSES"
            }
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error consultando rutas en PG: {e}")
        # Fallback si PG tiene demora
        fallback_meta = {
            '020c': {'name': 'Ramal 020C - San Lorenzo a Asunción', 'direction': 'inbound', 'label': 'Ida', 'origin': 'San Lorenzo (Azara)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.28},
            '020d': {'name': 'Ramal 020D - Asunción a San Lorenzo', 'direction': 'outbound', 'label': 'Vuelta', 'origin': 'Asunción Centro (Puerto)', 'destination': 'San Lorenzo (Azara)', 'km': 18.02},
            '020e': {'name': 'Ramal 020E - San Lorenzo a Asunción (Variante)', 'direction': 'inbound', 'label': 'Ida', 'origin': 'San Lorenzo (Azara)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.92},
            '020f': {'name': 'Ramal 020F - Asunción a San Lorenzo (Variante)', 'direction': 'outbound', 'label': 'Vuelta', 'origin': 'Asunción Centro (Puerto)', 'destination': 'San Lorenzo (Azara)', 'km': 18.91},
            '0210': {'name': 'Ramal 0210 - Luque (Aeropuerto) a Asunción', 'direction': 'inbound', 'label': 'Ida', 'origin': 'Luque (Rotonda Aeropuerto)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.33},
            '0211': {'name': 'Ramal 0211 - Asunción a Luque (Aeropuerto)', 'direction': 'outbound', 'label': 'Vuelta', 'origin': 'Asunción Centro (Puerto)', 'destination': 'Luque (Rotonda Aeropuerto)', 'km': 18.84},
        }
        for code, m in fallback_meta.items():
            routes_dict[code] = {
                "route_id": code,
                "name": m['name'],
                "direction": m['direction'],
                "direction_label": m['label'],
                "origin": m['origin'],
                "destination": m['destination'],
                "distance_km": m['km'],
                "buses": [],
                "headways": [],
                "bunching_count": 0,
                "status": "NO_BUSES"
            }

    # 2. Obtener vehículos activos de Redis o Memoria
    active_buses = []
    if redis_client:
        try:
            keys = redis_client.keys("vehicle:*")
            for k in keys:
                val = redis_client.get(k)
                if val:
                    data = json.loads(val)
                    if (data.get("agency_id") or "004B") == "004B":
                        active_buses.append(data)
        except Exception as e:
            logger.debug(f"Error Redis headway: {e}")

    if not active_buses and active_vehicles_memory:
        active_buses = [b for b in active_vehicles_memory.values() if (b.get("agency_id") or "004B") == "004B"]

    if not active_buses:
        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
            )
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT DISTINCT ON (bus_internal_code)
                    bus_internal_code as bus_id,
                    license_plate,
                    route_id,
                    agency_id,
                    latitude,
                    longitude,
                    speed_kmh as last_speed_kmh,
                    odometer_km,
                    recorded_at as last_ping_time
                FROM telemetry_ping
                WHERE agency_id = '004B'
                  AND route_id IN ('020c', '020d', '020e', '020f', '0210', '0211')
                ORDER BY bus_internal_code, recorded_at DESC;
            """)
            for row in cur.fetchall():
                active_buses.append(dict(row))
            cur.close()
            conn.close()
        except Exception as e:
            logger.debug(f"Error fallback DB headway: {e}")

    total_active_buses = 0
    total_bunching_alerts = 0

    # 3. Asignar buses a sus ramales
    for b in active_buses:
        r_code = (b.get("route_id") or "").lower()
        if r_code in routes_dict:
            total_active_buses += 1
            total_km = routes_dict[r_code]["distance_km"]
            dist_km = float(b.get("distance_traveled_km") or 0.0)
            
            # Priorizar el porcentaje de avance exacto calculado por PostGIS sobre el shape
            postgis_pct = float(b.get("progress_percent") or 0.0)
            if postgis_pct > 0:
                pct = min(100.0, max(0.0, round(postgis_pct, 1)))
            elif total_km > 0:
                pct = min(100.0, max(0.0, round((dist_km / total_km) * 100.0, 1)))
            else:
                pct = 0.0

            state = b.get("state") or b.get("current_state") or "IN_TRANSIT"
            state_label = b.get("status_display") or ("En Circulación" if state == "IN_TRANSIT" else ("En Cabecera" if state == "AT_ORIGIN" else ("En Destino" if state == "AT_DESTINATION" else ("Desviado" if state == "OFF_ROUTE" else "En Depósito"))))

            lat = b.get("last_latitude") if b.get("last_latitude") is not None else b.get("latitude")
            lon = b.get("last_longitude") if b.get("last_longitude") is not None else b.get("longitude")
            speed = float(b.get("last_speed_kmh") if b.get("last_speed_kmh") is not None else (b.get("speed_kmh") or 0.0))

            bus_entry = {
                "bus_id": b.get("bus_id"),
                "license_plate": b.get("license_plate") or f"COCHE-{b.get('bus_id')}",
                "agency_id": b.get("agency_id", "004B"),
                "route_id": r_code,
                "route_name": routes_dict[r_code]["name"],
                "route_total_km": total_km,
                "direction_label": routes_dict[r_code]["direction_label"],
                "origin": routes_dict[r_code]["origin"],
                "destination": routes_dict[r_code]["destination"],
                "state": state,
                "state_label": state_label,
                "street_name": b.get("street_name") or "",
                "approaching": b.get("approaching") or "",
                "driver_id": b.get("driver_id") or "--",
                "odometer_km": round(float(b.get("odometer_km") or 0.0), 1),
                "latitude": float(lat) if lat is not None else None,
                "longitude": float(lon) if lon is not None else None,
                "speed_kmh": round(speed, 1),
                "distance_traveled_km": round(dist_km, 2),
                "progress_percent": pct,
                "deviation_meters": round(float(b.get("deviation_meters") or 0.0), 1),
                "last_ping_time": b.get("last_ping_time"),
                "is_bunching": False,
                "bunching_with": None,
                "bunching_gap_m": None,
                "bunching_gap_min": None,
            }
            routes_dict[r_code]["buses"].append(bus_entry)

    # 4. Ordenar buses a lo largo de cada carril y calcular Pegonamiento (Bunching)
    for r_code, r_data in routes_dict.items():
        # Ordenar por distancia recorrida (0 km a total_km)
        r_data["buses"].sort(key=lambda x: x["distance_traveled_km"])
        
        buses = r_data["buses"]
        n = len(buses)
        
        if n == 0:
            r_data["status"] = "SIN_BUSES"
        elif n == 1:
            r_data["status"] = "UN_BUS"
        else:
            r_data["status"] = "OPTIMO"

        # Calcular intervalos entre coches consecutivos
        for i in range(n - 1):
            b_leader = buses[i + 1]  # Bus más adelantado
            b_trailer = buses[i]     # Bus que viene detrás
            
            gap_km = round(b_leader["distance_traveled_km"] - b_trailer["distance_traveled_km"], 2)
            
            # Estimar minutos de separación (~25 km/h promedio en ciudad)
            est_minutes = round(gap_km * 2.4, 1)

            # 🛑 Obviar los pegonamientos en las terminales / cabeceras (espera o regulación programada)
            is_terminal_wait = (
                b_leader.get("state") in ("AT_ORIGIN", "AT_DESTINATION", "DEPOT", "GPS_FAULT") or
                b_trailer.get("state") in ("AT_ORIGIN", "AT_DESTINATION", "DEPOT", "GPS_FAULT") or
                b_leader.get("progress_percent", 0.0) <= 4.0 or b_leader.get("progress_percent", 0.0) >= 96.0 or
                b_trailer.get("progress_percent", 0.0) <= 4.0 or b_trailer.get("progress_percent", 0.0) >= 96.0 or
                b_leader.get("distance_traveled_km", 0.0) <= 0.6 or
                b_trailer.get("distance_traveled_km", 0.0) <= 0.6 or
                (total_km > 0 and (total_km - b_leader.get("distance_traveled_km", 0.0)) <= 0.6) or
                (total_km > 0 and (total_km - b_trailer.get("distance_traveled_km", 0.0)) <= 0.6)
            )

            # 🛑 Obviar pegonamiento si un bus está operando en parada de pasajeros (detenido a <= 5 km/h)
            # y el coche que viene detrás aún se encuentra a una distancia prudencial (gap >= 250m)
            is_stop_dwell = (
                (b_leader.get("speed_kmh", 0.0) <= 5.0 or b_trailer.get("speed_kmh", 0.0) <= 5.0) and
                gap_km >= 0.25
            )

            # Clasificación de Intervalo y Detección Real de Pegonamiento
            if is_terminal_wait:
                severity = "TERMINAL_WAIT"  # 🟡 En espera en cabecera / terminal (obviar pegonamiento)
            elif is_stop_dwell:
                severity = "STOP_DWELL"     # 🚏 En parada (ascenso/descenso de pasajeros a distancia prudencial)
            elif gap_km < 0.30:             # 🚨 Pegonamiento real en calle (< 300 metros = en la misma cuadra pegados)
                severity = "CRITICAL" # 🚨 Pegonamiento real en ruta
                b_leader["is_bunching"] = True
                b_trailer["is_bunching"] = True
                b_leader["bunching_with"] = b_trailer["bus_id"]
                b_trailer["bunching_with"] = b_leader["bus_id"]
                b_leader["bunching_gap_m"] = int(gap_km * 1000)
                b_trailer["bunching_gap_m"] = int(gap_km * 1000)
                b_leader["bunching_gap_min"] = est_minutes
                b_trailer["bunching_gap_min"] = est_minutes
                r_data["bunching_count"] += 1
                total_bunching_alerts += 1
                r_data["status"] = "PEGONAMIENTO"
            elif gap_km <= 0.80:
                severity = "WARNING"  # ⚠️ Intervalo corto (300m - 800m) - Precaución preventiva pero no pegonamiento crítico
                if r_data["status"] != "PEGONAMIENTO":
                    r_data["status"] = "ADVERTENCIA"
            elif gap_km <= 5.5:
                severity = "OPTIMAL"  # 🟢 Intervalo regular
            else:
                severity = "GAP"      # ⏳ Hueco excesivo

            hw_entry = {
                "trailer_id": b_trailer["bus_id"],
                "leader_id": b_leader["bus_id"],
                "gap_km": gap_km,
                "gap_meters": int(gap_km * 1000),
                "est_minutes": est_minutes,
                "severity": severity,
                "left_pct": b_trailer["progress_percent"],
                "width_pct": max(1.0, round(b_leader["progress_percent"] - b_trailer["progress_percent"], 1))
            }
            r_data["headways"].append(hw_entry)

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
        "timestamp": datetime.now().isoformat(),
        "total_active_buses": total_active_buses,
        "total_bunching_alerts": total_bunching_alerts,
        "routes": list(routes_dict.values())
    }

def get_headway_html() -> str:
    """Retorna la página HTML interactiva del Tablero Lineal."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poliverso Transit | Tablero Lineal de Intervalos & Pegonamiento</title>
    <link rel="icon" href="data:,">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #060b14;
            --bg-card: #0d1527;
            --bg-card-hover: #131d36;
            --border: #1e293b;
            --border-glow: rgba(56, 189, 248, 0.3);
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.4);
            --accent: #818cf8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.5);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        /* Top Header */
        header {
            background: rgba(13, 21, 39, 0.9);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            padding: 12px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .brand-group {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #0284c7, #6366f1);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);
        }

        .brand-title {
            font-size: 16px;
            font-weight: 800;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #f8fafc, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-subtitle {
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .nav-btn {
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .nav-btn:hover {
            background: #334155;
            color: #fff;
            border-color: var(--primary);
        }

        .sound-btn-active {
            background: rgba(16, 185, 129, 0.15);
            border-color: rgba(16, 185, 129, 0.4);
            color: #34d399;
        }

        .sound-btn-muted {
            background: rgba(239, 68, 68, 0.15);
            border-color: rgba(239, 68, 68, 0.4);
            color: #f87171;
        }

        .pulse-live {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 11px;
            font-weight: 700;
            color: #34d399;
            background: rgba(16, 185, 129, 0.15);
            padding: 5px 10px;
            border-radius: 20px;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 10px #10b981;
            animation: pulse-ring 1.5s infinite;
        }

        @keyframes pulse-ring {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        /* Pegonamiento Global Alert Banner */
        .bunching-banner {
            background: linear-gradient(90deg, #991b1b, #dc2626, #b91c1c);
            border-bottom: 1px solid #f87171;
            padding: 10px 28px;
            box-shadow: 0 4px 20px rgba(220, 38, 38, 0.4);
            animation: banner-glow 1.5s infinite alternate;
        }

        @keyframes banner-glow {
            0% { box-shadow: 0 4px 15px rgba(220, 38, 38, 0.3); }
            100% { box-shadow: 0 4px 28px rgba(239, 68, 68, 0.7); }
        }

        .bunching-banner-content {
            max-width: 1600px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }

        .bunching-banner-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .banner-icon {
            font-size: 24px;
            animation: bounce-alert 0.8s infinite alternate;
        }

        .banner-title {
            font-size: 14px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.01em;
        }

        .banner-subtitle {
            font-size: 12px;
            color: #fecaca;
            font-weight: 500;
        }

        .banner-btn {
            background: #ffffff;
            color: #991b1b;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 800;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.2s ease;
        }

        .banner-btn:hover {
            background: #fef2f2;
            transform: scale(1.04);
        }

        /* KPI Top Strip */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            padding: 20px 28px 10px 28px;
            max-width: 1600px;
            margin: 0 auto;
            width: 100%;
        }

        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            position: relative;
            overflow: hidden;
        }

        .kpi-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
        }

        .kpi-bunching::before { background: var(--danger); box-shadow: 0 0 12px var(--danger); }
        .kpi-buses::before { background: var(--primary); }
        .kpi-routes::before { background: var(--accent); }
        .kpi-sync::before { background: var(--success); }

        .kpi-bunching.has-alerts {
            border-color: rgba(239, 68, 68, 0.6);
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.12), #0d1527);
            animation: kpi-alert-pulse 1.2s infinite alternate;
        }

        @keyframes kpi-alert-pulse {
            0% { box-shadow: 0 0 8px rgba(239, 68, 68, 0.2); }
            100% { box-shadow: 0 0 22px rgba(239, 68, 68, 0.6); }
        }

        .kpi-info h4 {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }

        .kpi-value {
            font-size: 26px;
            font-weight: 900;
            letter-spacing: -0.02em;
            display: flex;
            align-items: baseline;
            gap: 6px;
        }

        .kpi-icon {
            font-size: 28px;
            opacity: 0.85;
        }

        /* Main Workspace */
        main {
            flex: 1;
            padding: 14px 28px 40px 28px;
            max-width: 1600px;
            margin: 0 auto;
            width: 100%;
        }

        /* Filter Pills */
        .filter-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
            overflow-x: auto;
            padding-bottom: 6px;
        }

        .filter-pill {
            background: #111a2e;
            border: 1px solid #1e293b;
            color: #94a3b8;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .filter-pill:hover, .filter-pill.active {
            background: #0284c7;
            color: #fff;
            border-color: #38bdf8;
            box-shadow: 0 2px 10px rgba(56, 189, 248, 0.25);
        }

        .filter-pill.bunching-filter.active {
            background: #dc2626;
            border-color: #f87171;
            box-shadow: 0 2px 10px rgba(239, 68, 68, 0.4);
        }

        /* Track Container Cards */
        .route-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px 24px;
            margin-bottom: 22px;
            transition: all 0.25s ease;
            position: relative;
        }

        .route-card:hover {
            border-color: var(--border-glow);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
        }

        .route-card.bunching-card {
            border-color: rgba(239, 68, 68, 0.5);
            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.15);
        }

        .route-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 22px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .route-id-badge {
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
            font-weight: 900;
            font-size: 14px;
            padding: 6px 14px;
            border-radius: 8px;
            letter-spacing: 0.05em;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);
        }

        .route-meta {
            display: flex;
            align-items: center;
            gap: 14px;
            flex-wrap: wrap;
        }

        .route-name {
            font-size: 15px;
            font-weight: 700;
            color: #e2e8f0;
        }

        .route-length {
            font-size: 12px;
            color: var(--text-muted);
            background: #111a2e;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #1e293b;
        }

        .route-status-pill {
            font-size: 11px;
            font-weight: 800;
            padding: 4px 12px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            text-transform: uppercase;
        }

        .pill-bunching {
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.4);
            animation: bunching-flash 1s infinite alternate;
        }

        @keyframes bunching-flash {
            0% { box-shadow: 0 0 4px rgba(239, 68, 68, 0.4); }
            100% { box-shadow: 0 0 16px rgba(239, 68, 68, 0.8); }
        }

        .pill-optimal {
            background: rgba(16, 185, 129, 0.15);
            color: #6ee7b7;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .pill-warning {
            background: rgba(245, 158, 11, 0.15);
            color: #fcd34d;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .pill-empty {
            background: rgba(148, 163, 184, 0.1);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.2);
        }

        /* The Horizontal Track */
        .track-wrapper {
            position: relative;
            padding: 34px 20px 24px 20px;
            margin: 10px 0 20px 0;
            background: #090e1a;
            border-radius: 12px;
            border: 1px solid #162032;
        }

        .terminal-labels {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #64748b;
            font-weight: 700;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .terminal-labels span {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .rail-track {
            position: relative;
            height: 10px;
            background: #1e293b;
            border-radius: 5px;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
        }

        .rail-track-progress {
            position: absolute;
            top: 0; left: 0; height: 100%;
            background: linear-gradient(90deg, #0284c7, #38bdf8);
            border-radius: 5px;
            opacity: 0.7;
        }

        /* Kilometer Ticks */
        .tick-marks {
            position: relative;
            height: 16px;
            margin-top: 6px;
        }

        .tick {
            position: absolute;
            font-size: 9px;
            color: #475569;
            transform: translateX(-50%);
            font-weight: 600;
        }

        .tick::before {
            content: '';
            position: absolute;
            top: -10px;
            left: 50%;
            width: 1px;
            height: 5px;
            background: #334155;
        }

        /* Bus Marker on Track */
        .bus-marker {
            position: absolute;
            top: -20px;
            transform: translateX(-50%);
            display: flex;
            flex-direction: column;
            align-items: center;
            cursor: pointer;
            z-index: 25;
            transition: left 0.6s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s ease;
        }

        .bus-marker:hover {
            transform: translateX(-50%) translateY(-3px) scale(1.12);
            z-index: 50;
        }

        .bus-marker-bubble {
            background: #0284c7;
            color: white;
            padding: 4px 8px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 4px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
            border: 2px solid #38bdf8;
            white-space: nowrap;
            transition: all 0.2s ease;
        }

        .bus-marker:hover .bus-marker-bubble {
            border-color: #ffffff;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.8);
        }

        .bus-marker.bunching .bus-marker-bubble {
            background: #dc2626;
            border-color: #f87171;
            box-shadow: 0 0 16px rgba(239, 68, 68, 0.8);
            animation: bounce-alert 0.8s infinite alternate;
        }

        @keyframes bounce-alert {
            0% { transform: translateY(0); }
            100% { transform: translateY(-4px); }
        }

        .bus-marker-pointer {
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #0284c7;
            margin-top: -1px;
        }

        .bus-marker.bunching .bus-marker-pointer {
            border-top-color: #dc2626;
        }

        /* Headway Connector Bar */
        .headway-segment {
            position: absolute;
            top: -12px;
            height: 4px;
            background: rgba(56, 189, 248, 0.4);
            border-radius: 2px;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10;
        }

        .headway-segment.critical {
            background: rgba(239, 68, 68, 0.7);
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.6);
            height: 6px;
            top: -13px;
        }

        .headway-segment.terminal {
            background: rgba(245, 158, 11, 0.35);
            height: 4px;
            top: -12px;
        }

        .headway-segment.stop_dwell {
            background: rgba(56, 189, 248, 0.45);
            height: 4px;
            top: -12px;
        }

        .headway-badge {
            background: #0f172a;
            border: 1px solid #334155;
            padding: 2px 7px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 700;
            color: #94a3b8;
            white-space: nowrap;
            position: absolute;
            top: -20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
        }

        .headway-badge.terminal {
            background: rgba(120, 53, 15, 0.85);
            border-color: #f59e0b;
            color: #fef3c7;
        }

        .headway-badge.stop_dwell {
            background: rgba(15, 23, 42, 0.95);
            border-color: #38bdf8;
            color: #7dd3fc;
            font-weight: 700;
        }

        .headway-badge.critical {
            background: #7f1d1d;
            border-color: #ef4444;
            color: #fef2f2;
            font-weight: 900;
            animation: pulse-ring 1s infinite;
        }

        /* Bus Details Mini Table */
        .bus-table-box {
            margin-top: 14px;
            overflow-x: auto;
        }

        .bus-mini-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }

        .bus-mini-table th {
            text-align: left;
            color: #64748b;
            font-weight: 600;
            padding: 6px 10px;
            border-bottom: 1px solid #1e293b;
        }

        .bus-mini-table td {
            padding: 9px 10px;
            border-bottom: 1px solid #162032;
            color: #cbd5e1;
            transition: background 0.15s ease;
        }

        .bus-mini-table tr.clickable-row {
            cursor: pointer;
        }

        .bus-mini-table tr.clickable-row:hover td {
            background: rgba(56, 189, 248, 0.08);
            color: #ffffff;
        }

        .bus-mini-table tr.clickable-row.bunching-row:hover td {
            background: rgba(239, 68, 68, 0.12);
        }

        .empty-state {
            text-align: center;
            padding: 30px;
            color: #64748b;
            font-size: 13px;
        }

        /* Bus Inspection Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(4, 8, 16, 0.75);
            backdrop-filter: blur(8px);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            animation: fadeIn 0.2s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .modal-card {
            background: #0d1527;
            border: 1px solid #1e293b;
            border-radius: 18px;
            width: 100%;
            max-width: 580px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(56, 189, 248, 0.15);
            overflow: hidden;
            animation: scaleUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes scaleUp {
            from { transform: scale(0.93) translateY(10px); opacity: 0; }
            to { transform: scale(1) translateY(0); opacity: 1; }
        }

        .modal-header {
            background: #111a2e;
            padding: 16px 22px;
            border-bottom: 1px solid #1e293b;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .modal-title-box {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .modal-bus-icon {
            font-size: 26px;
            background: #0284c7;
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4);
        }

        .modal-header h3 {
            font-size: 17px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.01em;
        }

        .modal-plate-tag {
            font-size: 11px;
            color: #94a3b8;
            font-weight: 600;
        }

        .modal-close-btn {
            background: transparent;
            border: none;
            color: #64748b;
            font-size: 20px;
            cursor: pointer;
            padding: 6px;
            border-radius: 8px;
            line-height: 1;
            transition: all 0.2s ease;
        }

        .modal-close-btn:hover {
            color: #f8fafc;
            background: #1e293b;
        }

        .modal-bunching-alert {
            background: linear-gradient(90deg, rgba(239, 68, 68, 0.2), rgba(185, 28, 28, 0.25));
            border-bottom: 1px solid rgba(239, 68, 68, 0.4);
            padding: 12px 22px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: #fca5a5;
        }

        .modal-alert-icon {
            font-size: 22px;
            animation: bounce-alert 0.8s infinite alternate;
        }

        .modal-bunching-alert strong {
            color: #ffffff;
            font-size: 13px;
            display: block;
            margin-bottom: 2px;
        }

        .modal-bunching-alert span {
            font-size: 12px;
            color: #fecaca;
        }

        .modal-body-grid {
            padding: 20px 22px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            max-height: 55vh;
            overflow-y: auto;
        }

        .modal-metric {
            background: #090e1a;
            border: 1px solid #162032;
            padding: 10px 14px;
            border-radius: 10px;
        }

        .modal-col-2 {
            grid-column: span 2;
        }

        .modal-metric .lbl {
            font-size: 10px;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: block;
            margin-bottom: 3px;
        }

        .modal-metric .val {
            font-size: 13px;
            font-weight: 700;
            color: #e2e8f0;
        }

        .modal-metric .val.highlight {
            color: var(--primary);
            font-size: 15px;
        }

        .modal-footer {
            background: #111a2e;
            padding: 14px 22px;
            border-top: 1px solid #1e293b;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 12px;
        }

        .btn-locate-map {
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #ffffff;
            border: none;
            padding: 9px 18px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
            transition: all 0.2s ease;
        }

        .btn-locate-map:hover {
            background: linear-gradient(135deg, #0369a1, #1d4ed8);
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(37, 99, 235, 0.6);
        }

        .btn-modal-close {
            background: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            padding: 9px 16px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .btn-modal-close:hover {
            color: #ffffff;
            background: #334155;
        }
    </style>
</head>
<body>

    <!-- Header -->
    <header>
        <div class="brand-group">
            <div class="brand-icon">🚌</div>
            <div>
                <div class="brand-title">Poliverso Transit | Control de Frecuencias & Headway</div>
                <div class="brand-subtitle">Monitoreo Lineal de Regularidad y Detección de Pegonamiento (Bunching)</div>
            </div>
        </div>

        <div class="header-actions">
            <div class="pulse-live">
                <div class="pulse-dot"></div>
                <span>EN VIVO (TELEMETRÍA VMT)</span>
            </div>

            <!-- Botón de Control de Alarma Sonora -->
            <button id="btn-sound-toggle" class="nav-btn sound-btn-active" onclick="toggleSoundAlert()" title="Activar/Silenciar Alerta Sonora de Pegonamiento">
                <span id="sound-icon">🔊</span>
                <span id="sound-text">Alarma: ACTIVA</span>
            </button>

            <a href="/map" class="nav-btn">
                <span>🗺️ Radar Satelital</span>
            </a>
            <a href="http://localhost:8069" target="_blank" class="nav-btn">
                <span>⚡ Odoo ERP</span>
            </a>
        </div>
    </header>

    <!-- Banner Global de Alerta de Pegonamiento -->
    <div id="global-bunching-banner" class="bunching-banner" style="display: none;">
        <div class="bunching-banner-content">
            <div class="bunching-banner-left">
                <span class="banner-icon">🚨</span>
                <div>
                    <div class="banner-title">¡ALERTA CRÍTICA: PEGONAMIENTO DE UNIDADES DETECTADO!</div>
                    <div class="banner-subtitle" id="banner-msg">Se registran unidades circulando con separación menor a 800m. Riesgo inminente de canibalización de frecuencias.</div>
                </div>
            </div>
            <button class="banner-btn" onclick="filterByBunchingOnly()">Filtrar Afectados</button>
        </div>
    </div>

    <!-- Top KPI Cards -->
    <section class="kpi-container">
        <div class="kpi-card kpi-bunching" id="kpi-bunching-card">
            <div class="kpi-info">
                <h4>Alertas de Pegonamiento</h4>
                <div class="kpi-value" id="kpi-bunching" style="color: var(--danger);">0</div>
            </div>
            <div class="kpi-icon">🚨</div>
        </div>

        <div class="kpi-card kpi-buses">
            <div class="kpi-info">
                <h4>Buses en Operación</h4>
                <div class="kpi-value" id="kpi-buses" style="color: var(--primary);">0</div>
            </div>
            <div class="kpi-icon">🚍</div>
        </div>

        <div class="kpi-card kpi-routes">
            <div class="kpi-info">
                <h4>Ramales Monitoreados</h4>
                <div class="kpi-value" id="kpi-routes" style="color: var(--accent);">6</div>
            </div>
            <div class="kpi-icon">🛣️</div>
        </div>

        <div class="kpi-card kpi-sync">
            <div class="kpi-info">
                <h4>Última Actualización</h4>
                <div class="kpi-value" id="kpi-time" style="font-size: 18px; color: var(--success);">--:--:--</div>
            </div>
            <div class="kpi-icon">⏱️</div>
        </div>
    </section>

    <!-- Main Content -->
    <main>
        <!-- Filter Tabs -->
        <div class="filter-bar">
            <div class="filter-pill active" onclick="filterRoute('all')">Todos los Ramales</div>
            <div class="filter-pill bunching-filter" id="pill-filter-bunching" onclick="filterRoute('bunching')">🚨 Con Pegonamiento</div>
            <div class="filter-pill" onclick="filterRoute('020c')">Ramal 020C</div>
            <div class="filter-pill" onclick="filterRoute('020d')">Ramal 020D</div>
            <div class="filter-pill" onclick="filterRoute('020e')">Ramal 020E</div>
            <div class="filter-pill" onclick="filterRoute('020f')">Ramal 020F</div>
            <div class="filter-pill" onclick="filterRoute('0210')">Ramal 0210</div>
            <div class="filter-pill" onclick="filterRoute('0211')">Ramal 0211</div>
        </div>

        <!-- Dynamic Tracks Container -->
        <div id="tracks-container">
            <div class="empty-state">Cargando telemetría geoespacial y trazados lineales...</div>
        </div>
    </main>

    <!-- Bus Detail & Telemetry Inspection Modal -->
    <div id="bus-modal" class="modal-overlay" style="display: none;" onclick="closeModalOnBackdrop(event)">
        <div class="modal-card">
            <div class="modal-header">
                <div class="modal-title-box">
                    <span class="modal-bus-icon">🚌</span>
                    <div>
                        <h3 id="modal-bus-id">Coche #00000</h3>
                        <span id="modal-bus-plate" class="modal-plate-tag">COCHE-00000</span>
                    </div>
                </div>
                <button class="modal-close-btn" onclick="closeBusModal()">✕</button>
            </div>

            <!-- Alerta Crítica en Modal si tiene pegonamiento -->
            <div id="modal-bunching-box" class="modal-bunching-alert" style="display: none;">
                <span class="modal-alert-icon">🚨</span>
                <div>
                    <strong>PEGONAMIENTO CRÍTICO ACTIVO</strong>
                    <span id="modal-bunching-desc">Circulando a menos de 800m de la unidad líder.</span>
                </div>
            </div>

            <!-- Grilla de Telemetría -->
            <div class="modal-body-grid">
                <div class="modal-metric">
                    <span class="lbl">Estado Operativo</span>
                    <span class="val" id="modal-state">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Velocidad Actual</span>
                    <span class="val highlight" id="modal-speed">0 km/h</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Ramal Asignado</span>
                    <span class="val" id="modal-route">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Sentido / Trayecto</span>
                    <span class="val" id="modal-direction">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Progreso en Traza</span>
                    <span class="val" id="modal-progress">0%</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Km en Recorrido</span>
                    <span class="val" id="modal-dist">0.0 km</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Desvío de Eje Oficial</span>
                    <span class="val" id="modal-deviation">0 m</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Conductor Asignado</span>
                    <span class="val" id="modal-driver">--</span>
                </div>
                <div class="modal-metric modal-col-2">
                    <span class="lbl">Ubicación / Calle Aproximada</span>
                    <span class="val" id="modal-location">--</span>
                </div>
                <div class="modal-metric modal-col-2">
                    <span class="lbl">Próxima Parada / Hito</span>
                    <span class="val" id="modal-approaching">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Último Ping GPS</span>
                    <span class="val" id="modal-ping">--:--:--</span>
                </div>
                <div class="modal-metric">
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
            </div>

            <!-- Modal Footer con Acción Directa a GPS -->
            <div class="modal-footer">
                <button class="btn-locate-map" onclick="locateSelectedBusOnMap()">
                    <span>🗺️ Ubicar en Radar GPS</span>
                </button>
                <button class="btn-modal-close" onclick="closeBusModal()">Cerrar</button>
            </div>
        </div>
    </div>

    <script>
        let currentFilter = 'all';
        let latestDashboardData = null;
        const busRegistry = {};
        let selectedBusId = null;

        // --- SISTEMA DE ALERTA SONORA (Web Audio API Synthesizer) ---
        let audioCtx = null;
        let soundEnabled = localStorage.getItem('headway_sound_enabled') !== 'false';
        let lastAlertSoundTime = 0;
        const ALERT_SOUND_COOLDOWN_MS = 14000; // Repetir cada 14s si persiste el pegonamiento

        function initAudioContext() {
            if (!audioCtx) {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (AudioContextClass) {
                    audioCtx = new AudioContextClass();
                }
            }
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            return audioCtx;
        }

        // Desbloquear audio automáticamente al hacer clic en cualquier lugar
        document.addEventListener('click', () => {
            initAudioContext();
        }, { once: false });

        function updateSoundButtonUI() {
            const btn = document.getElementById('btn-sound-toggle');
            const icon = document.getElementById('sound-icon');
            const txt = document.getElementById('sound-text');
            if (soundEnabled) {
                btn.className = 'nav-btn sound-btn-active';
                icon.textContent = '🔊';
                txt.textContent = 'Alarma: ACTIVA';
            } else {
                btn.className = 'nav-btn sound-btn-muted';
                icon.textContent = '🔇';
                txt.textContent = 'Alarma: SILENCIADA';
            }
        }

        function toggleSoundAlert() {
            initAudioContext();
            soundEnabled = !soundEnabled;
            localStorage.setItem('headway_sound_enabled', soundEnabled ? 'true' : 'false');
            updateSoundButtonUI();
            if (soundEnabled) {
                playBunchingTone(true); // Test chime
            }
        }

        function playBunchingTone(forceTest = false) {
            if (!soundEnabled && !forceTest) return;
            const ctx = initAudioContext();
            if (!ctx) return;

            try {
                const now = ctx.currentTime;

                // Tono 1: Chime de alerta bitonal agudo (880Hz -> 659Hz -> 880Hz)
                const osc1 = ctx.createOscillator();
                const gain1 = ctx.createGain();
                osc1.type = 'sine';
                osc1.frequency.setValueAtTime(880, now);
                osc1.frequency.setValueAtTime(659, now + 0.16);
                osc1.frequency.setValueAtTime(880, now + 0.32);

                gain1.gain.setValueAtTime(0.0, now);
                gain1.gain.linearRampToValueAtTime(0.28, now + 0.04);
                gain1.gain.setValueAtTime(0.28, now + 0.42);
                gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.85);

                osc1.connect(gain1);
                gain1.connect(ctx.destination);
                osc1.start(now);
                osc1.stop(now + 0.86);

                // Tono 2: Armónico de resonancia (440Hz -> 330Hz -> 440Hz)
                const osc2 = ctx.createOscillator();
                const gain2 = ctx.createGain();
                osc2.type = 'triangle';
                osc2.frequency.setValueAtTime(440, now);
                osc2.frequency.setValueAtTime(330, now + 0.16);
                osc2.frequency.setValueAtTime(440, now + 0.32);

                gain2.gain.setValueAtTime(0.0, now);
                gain2.gain.linearRampToValueAtTime(0.14, now + 0.04);
                gain2.gain.setValueAtTime(0.14, now + 0.42);
                gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.85);

                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.start(now);
                osc2.stop(now + 0.86);
            } catch (err) {
                console.warn("AudioContext error:", err);
            }
        }

        // Inicializar botón de sonido
        updateSoundButtonUI();

        // --- FILTROS DE VISTA ---
        function filterRoute(code) {
            currentFilter = code;
            document.querySelectorAll('.filter-pill').forEach(el => {
                const txt = el.textContent.toLowerCase();
                if (code === 'all' && txt.includes('todos')) {
                    el.classList.add('active');
                } else if (code === 'bunching' && txt.includes('pegonamiento')) {
                    el.classList.add('active');
                } else if (code !== 'all' && code !== 'bunching' && txt.includes(code)) {
                    el.classList.add('active');
                } else {
                    el.classList.remove('active');
                }
            });
            if (latestDashboardData) {
                renderDashboard(latestDashboardData);
            }
        }

        function filterByBunchingOnly() {
            filterRoute('bunching');
        }

        // --- FETCH Y RENDERIZADO DEL DASHBOARD ---
        async function fetchHeadwayData() {
            try {
                const res = await fetch('/api/v1/headway/data');
                const data = await res.json();
                latestDashboardData = data;
                renderDashboard(data);
            } catch (err) {
                console.error("Error al actualizar headway:", err);
            }
        }

        function renderDashboard(data) {
            const bunchingCount = data.total_bunching_alerts || 0;
            document.getElementById('kpi-bunching').textContent = bunchingCount;
            document.getElementById('kpi-buses').textContent = data.total_active_buses || 0;
            const now = new Date();
            document.getElementById('kpi-time').textContent = now.toLocaleTimeString();

            // Gestionar Alerta Sonora y Banner Global
            const bunchingBanner = document.getElementById('global-bunching-banner');
            const kpiCard = document.getElementById('kpi-bunching-card');

            if (bunchingCount > 0) {
                bunchingBanner.style.display = 'block';
                document.getElementById('banner-msg').textContent = `Se detectaron ${bunchingCount} evento(s) de pegonamiento activo entre unidades a menos de 800m.`;
                kpiCard.classList.add('has-alerts');

                // Emitir sonido si ha pasado el cooldown
                const currentTime = Date.now();
                if (currentTime - lastAlertSoundTime > ALERT_SOUND_COOLDOWN_MS) {
                    lastAlertSoundTime = currentTime;
                    playBunchingTone();
                }
            } else {
                bunchingBanner.style.display = 'none';
                kpiCard.classList.remove('has-alerts');
            }

            const container = document.getElementById('tracks-container');
            let filteredRoutes = data.routes || [];

            if (currentFilter === 'bunching') {
                filteredRoutes = filteredRoutes.filter(r => r.bunching_count > 0 || r.status === 'PEGONAMIENTO');
            } else if (currentFilter !== 'all') {
                filteredRoutes = filteredRoutes.filter(r => r.route_id === currentFilter);
            }

            if (filteredRoutes.length === 0) {
                container.innerHTML = '<div class="empty-state">No hay datos para el filtro seleccionado.</div>';
                return;
            }

            // Registrar buses en memoria global para modal
            (data.routes || []).forEach(r => {
                (r.buses || []).forEach(b => {
                    busRegistry[b.bus_id] = b;
                });
            });

            // Mantener el modal sincronizado en tiempo real si está abierto
            if (selectedBusId && busRegistry[selectedBusId]) {
                updateModalContent(busRegistry[selectedBusId]);
            }

            let html = '';
            filteredRoutes.forEach(r => {
                const totalKm = r.distance_km;
                const buses = r.buses || [];
                const headways = r.headways || [];
                const hasBunching = r.status === 'PEGONAMIENTO' || r.bunching_count > 0;

                let statusBadge = '<span class="route-status-pill pill-empty">Sin buses</span>';
                if (hasBunching) {
                    statusBadge = `<span class="route-status-pill pill-bunching">🚨 ${r.bunching_count} Pegonamiento(s)</span>`;
                } else if (r.status === 'ADVERTENCIA') {
                    statusBadge = '<span class="route-status-pill pill-warning">⚠️ Intervalo Corto</span>';
                } else if (r.status === 'OPTIMO') {
                    statusBadge = '<span class="route-status-pill pill-optimal">✓ Intervalo Regular</span>';
                } else if (r.status === 'UN_BUS') {
                    statusBadge = '<span class="route-status-pill pill-optimal">1 Bus en Ruta</span>';
                }

                html += `
                <div class="route-card ${hasBunching ? 'bunching-card' : ''}">
                    <div class="route-header">
                        <div class="route-meta">
                            <span class="route-id-badge">${r.route_id.toUpperCase()}</span>
                            <span class="route-name">${r.name}</span>
                            <span class="route-length">🛣️ ${totalKm} km · Sentido: ${r.direction_label}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            ${r.waze_impact && r.waze_impact.total_delay_minutes > 0 ? `
                                <span class="route-status-pill" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);">
                                    🚦 Waze: +${r.waze_impact.total_delay_minutes} min demora
                                </span>
                            ` : ''}
                            ${statusBadge}
                        </div>
                    </div>

                    <!-- Horizontal Track Visualizer -->
                    <div class="track-wrapper">
                        <div class="terminal-labels">
                            <span>🏁 ${r.origin} (0.0 km)</span>
                            <span>🎯 ${r.destination} (${totalKm} km)</span>
                        </div>

                        <div class="rail-track">
                            <div class="rail-track-progress" style="width: 100%;"></div>

                            <!-- Headway Connecting Segments -->
                            ${headways.map(hw => {
                                const isCrit = hw.severity === 'CRITICAL';
                                const isTerminal = hw.severity === 'TERMINAL_WAIT';
                                const isStopDwell = hw.severity === 'STOP_DWELL';
                                const cls = isCrit ? 'critical' : (isTerminal ? 'terminal' : (isStopDwell ? 'stop_dwell' : (hw.severity === 'WARNING' ? 'warning' : 'optimal')));
                                const badgePrefix = isCrit ? '🚨 Pegonamiento: ' : (isTerminal ? '🟡 Cabecera: ' : (isStopDwell ? '🚏 En Parada: ' : (hw.severity === 'WARNING' ? '⚠️ Corto: ' : '')));
                                return `
                                    <div class="headway-segment ${cls}" style="left: ${hw.left_pct}%; width: ${hw.width_pct}%;">
                                        <div class="headway-badge ${cls}">
                                            ${badgePrefix}Δ ${hw.gap_km} km (${hw.est_minutes} min)
                                        </div>
                                    </div>
                                `;
                            }).join('')}

                            <!-- Bus Markers on Track (Clickable) -->
                            ${buses.map(b => {
                                const isBunch = b.is_bunching;
                                return `
                                    <div class="bus-marker ${isBunch ? 'bunching' : ''}" 
                                         style="left: ${b.progress_percent}%;" 
                                         onclick="openBusModal('${b.bus_id}')"
                                         title="Coche ${b.bus_id} | ${b.speed_kmh} km/h | Clic para ver detalles y ubicar en GPS">
                                        <div class="bus-marker-bubble">
                                            <span>🚌</span>
                                            <span>${b.bus_id}</span>
                                            <span style="font-size: 9px; opacity: 0.85;">(${b.speed_kmh}k)</span>
                                        </div>
                                        <div class="bus-marker-pointer"></div>
                                    </div>
                                `;
                            }).join('')}
                        </div>

                        <!-- Kilometer Ticks -->
                        <div class="tick-marks">
                            <span class="tick" style="left: 0%;">0 km</span>
                            <span class="tick" style="left: 25%;">${(totalKm * 0.25).toFixed(1)} km</span>
                            <span class="tick" style="left: 50%;">${(totalKm * 0.5).toFixed(1)} km</span>
                            <span class="tick" style="left: 75%;">${(totalKm * 0.75).toFixed(1)} km</span>
                            <span class="tick" style="left: 100%;">${totalKm} km</span>
                        </div>
                    </div>

                    <!-- Mini Bus Audit Table (Clickable Rows) -->
                    ${buses.length > 0 ? `
                    <div class="bus-table-box">
                        <table class="bus-mini-table">
                            <thead>
                                <tr>
                                    <th>Coche (Clic para inspeccionar)</th>
                                    <th>Estado</th>
                                    <th>Velocidad</th>
                                    <th>Km en Shape</th>
                                    <th>Progreso</th>
                                    <th>Desvío del Eje</th>
                                    <th>Último Ping</th>
                                    <th>Estado de Intervalo</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${buses.map(b => `
                                    <tr class="clickable-row ${b.is_bunching ? 'bunching-row' : ''}" onclick="openBusModal('${b.bus_id}')" title="Clic para ver ficha completa y ubicar en mapa">
                                        <td><strong>🚌 ${b.bus_id}</strong> (${b.license_plate})</td>
                                        <td><span style="background: rgba(16, 185, 129, 0.15); color: #34d399; padding: 2px 7px; border-radius: 4px; font-weight: 700; font-size: 11px;">${b.state_label || 'En Circulación'}</span></td>
                                        <td>${b.speed_kmh} km/h</td>
                                        <td><strong>${b.distance_traveled_km} km</strong> / ${totalKm} km</td>
                                        <td>
                                            <div style="display: flex; align-items: center; gap: 8px;">
                                                <div style="flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; width: 60px;">
                                                    <div style="width: ${b.progress_percent}%; height: 100%; background: ${b.is_bunching ? '#ef4444' : '#38bdf8'};"></div>
                                                </div>
                                                <span>${b.progress_percent}%</span>
                                            </div>
                                        </td>
                                        <td>${b.deviation_meters} m</td>
                                        <td>${b.last_ping_time ? b.last_ping_time.substring(11, 19) : '--:--'}</td>
                                        <td>
                                            ${b.is_bunching 
                                                ? '<span style="color: #f87171; font-weight: 700;">🚨 PEGONAMIENTO DETECTADO</span>' 
                                                : (b.speed_kmh <= 5.0 && b.state !== 'AT_ORIGIN' && b.state !== 'AT_DESTINATION' && b.state !== 'GPS_FAULT'
                                                    ? '<span style="color: #38bdf8; font-weight: 600;">🚏 En Parada (Operando)</span>' 
                                                    : (b.state === 'AT_ORIGIN' || b.state === 'AT_DESTINATION'
                                                        ? '<span style="color: #fbbf24; font-weight: 600;">🟡 En Terminal / Cabecera</span>'
                                                        : '<span style="color: #34d399;">✓ Intervalo Regular</span>'
                                                      )
                                                  )
                                            }
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                    ` : '<div style="font-size: 12px; color: #64748b; padding-top: 6px;">No hay unidades transmitiendo en este ramal actualmente.</div>'}
                </div>
                `;
            });

            container.innerHTML = html;
        }

        // --- MODAL DE DETALLES Y UBICAR EN MAPA ---
        function updateModalContent(b) {
            if (!b) return;
            document.getElementById('modal-bus-id').textContent = `Coche #${b.bus_id}`;
            document.getElementById('modal-bus-plate').textContent = `${b.license_plate} · Empresa ${b.agency_id}`;
            document.getElementById('modal-state').textContent = b.state_label || 'En Circulación';
            document.getElementById('modal-speed').textContent = `${b.speed_kmh} km/h`;
            document.getElementById('modal-route').textContent = `${(b.route_id || '').toUpperCase()} - ${b.route_name || 'Troncal'}`;
            document.getElementById('modal-direction').textContent = b.direction_label ? `${b.direction_label} (${b.origin || ''} ➔ ${b.destination || ''})` : 'Itinerario Regular';
            document.getElementById('modal-progress').textContent = `${b.progress_percent}%`;
            document.getElementById('modal-dist').textContent = `${b.distance_traveled_km} km de ${b.route_total_km || '--'} km`;
            document.getElementById('modal-deviation').textContent = `${b.deviation_meters} metros`;
            document.getElementById('modal-driver').textContent = b.driver_id || 'Conductor No Asignado';
            document.getElementById('modal-location').textContent = b.street_name || 'En calzada principal de itinerario';
            document.getElementById('modal-approaching').textContent = b.approaching || 'Avanzando en secuencia normal de paradas';
            document.getElementById('modal-ping').textContent = b.last_ping_time ? b.last_ping_time.substring(11, 19) : '--:--:--';
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
            }

            const bunchBox = document.getElementById('modal-bunching-box');
            if (b.is_bunching) {
                bunchBox.style.display = 'flex';
                document.getElementById('modal-bunching-desc').textContent = 
                    `Circulando pegado a coche #${b.bunching_with} a una distancia crítica de ${b.bunching_gap_m} m (~${b.bunching_gap_min} min de separación).`;
            } else {
                bunchBox.style.display = 'none';
            }
        }

        function openBusModal(busId) {
            initAudioContext();
            const b = busRegistry[busId];
            if (!b) return;

            selectedBusId = busId;
            updateModalContent(b);
            document.getElementById('bus-modal').style.display = 'flex';
        }

        function closeBusModal() {
            document.getElementById('bus-modal').style.display = 'none';
            selectedBusId = null;
        }

        function closeModalOnBackdrop(e) {
            if (e.target.id === 'bus-modal') {
                closeBusModal();
            }
        }

        function locateSelectedBusOnMap() {
            if (!selectedBusId) return;
            // Abre o redirige al Radar GPS con el parámetro del bus
            const targetUrl = `/map?bus=${encodeURIComponent(selectedBusId)}`;
            window.open(targetUrl, '_blank');
        }

        // Cierre con tecla Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeBusModal();
        });

        // Refresco automático cada 3 segundos
        fetchHeadwayData();
        setInterval(fetchHeadwayData, 3000);
    </script>
</body>
</html>
"""
