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
            SELECT code, name, direction, origin, destination, distance_km
            FROM transit_route
            WHERE code IN ('020c', '020d', '020e', '020f', '0210', '0211')
            ORDER BY code;
        """)
        for r in cur.fetchall():
            routes_dict[r['code']] = {
                "route_id": r['code'],
                "name": r['name'],
                "direction": r['direction'],
                "direction_label": "Ida" if r['direction'] == 'inbound' else ("Vuelta" if r['direction'] == 'outbound' else "Circular"),
                "origin": r['origin'] or "Cabecera Origen",
                "destination": r['destination'] or "Cabecera Destino",
                "distance_km": float(r['distance_km']) if r['distance_km'] else 18.5,
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
                    active_buses.append(data)
        except Exception as e:
            logger.debug(f"Error Redis headway: {e}")

    if not active_buses and active_vehicles_memory:
        active_buses = list(active_vehicles_memory.values())

    total_active_buses = 0
    total_bunching_alerts = 0

    # 3. Asignar buses a sus ramales
    for b in active_buses:
        r_code = (b.get("route_id") or "").lower()
        if r_code in routes_dict:
            total_active_buses += 1
            total_km = routes_dict[r_code]["distance_km"]
            dist_km = float(b.get("distance_traveled_km") or 0.0)
            
            # Calcular porcentaje lineal
            if total_km > 0:
                pct = min(100.0, max(0.0, round((dist_km / total_km) * 100.0, 1)))
            else:
                pct = float(b.get("progress_percent") or 0.0)

            state = b.get("state") or b.get("current_state") or "IN_TRANSIT"
            state_label = b.get("status_display") or ("En Circulación" if state == "IN_TRANSIT" else ("En Cabecera" if state == "AT_ORIGIN" else ("En Destino" if state == "AT_DESTINATION" else ("Desviado" if state == "OFF_ROUTE" else "En Depósito"))))

            bus_entry = {
                "bus_id": b.get("bus_id"),
                "license_plate": b.get("license_plate") or f"COCHE-{b.get('bus_id')}",
                "state": state,
                "state_label": state_label,
                "speed_kmh": float(b.get("last_speed_kmh") or 0.0),
                "distance_traveled_km": round(dist_km, 2),
                "progress_percent": pct,
                "deviation_meters": float(b.get("deviation_meters") or 0.0),
                "last_ping_time": b.get("last_ping_time"),
                "is_bunching": False
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

            # Clasificación de Pegonamiento (Bunching Threshold < 0.8 km u 800m)
            if gap_km < 0.8:
                severity = "CRITICAL" # 🚨 Pegonamiento
                b_leader["is_bunching"] = True
                b_trailer["is_bunching"] = True
                r_data["bunching_count"] += 1
                total_bunching_alerts += 1
                r_data["status"] = "PEGONAMIENTO"
            elif gap_km <= 1.5:
                severity = "WARNING"  # ⚠️ Intervalo corto
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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #060b14;
            --bg-card: #0d1527;
            --bg-card-hover: #131d36;
            --border: #1e293b;
            --border-glow: rgba(56, 189, 248, 0.3);
            --primary: #38bdf8;
            --accent: #818cf8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
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
            background: rgba(13, 21, 39, 0.85);
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
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, #0284c7, #6366f1);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
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
            gap: 16px;
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
            transition: all 0.2s ease;
        }

        .nav-btn:hover {
            background: #334155;
            color: #fff;
            border-color: var(--primary);
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
            opacity: 0.8;
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
            z-index: 20;
            transition: left 0.6s cubic-bezier(0.4, 0, 0.2, 1);
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
            padding: 8px 10px;
            border-bottom: 1px solid #162032;
            color: #cbd5e1;
        }

        .bus-mini-table tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .empty-state {
            text-align: center;
            padding: 30px;
            color: #64748b;
            font-size: 13px;
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
            <a href="/map" class="nav-btn">
                <span>🗺️ Radar Satelital</span>
            </a>
            <a href="http://localhost:8069" target="_blank" class="nav-btn">
                <span>⚡ Odoo ERP</span>
            </a>
        </div>
    </header>

    <!-- Top KPI Cards -->
    <section class="kpi-container">
        <div class="kpi-card kpi-bunching">
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

    <script>
        let currentFilter = 'all';

        function filterRoute(code) {
            currentFilter = code;
            document.querySelectorAll('.filter-pill').forEach(el => {
                if (el.textContent.toLowerCase().includes(code) || (code === 'all' && el.textContent.includes('Todos'))) {
                    el.classList.add('active');
                } else {
                    el.classList.remove('active');
                }
            });
            fetchHeadwayData();
        }

        async function fetchHeadwayData() {
            try {
                const res = await fetch('/api/v1/headway/data');
                const data = await res.json();
                renderDashboard(data);
            } catch (err) {
                console.error("Error al actualizar headway:", err);
            }
        }

        function renderDashboard(data) {
            // Update KPIs
            document.getElementById('kpi-bunching').textContent = data.total_bunching_alerts;
            document.getElementById('kpi-buses').textContent = data.total_active_buses;
            const now = new Date();
            document.getElementById('kpi-time').textContent = now.toLocaleTimeString();

            const container = document.getElementById('tracks-container');
            const filteredRoutes = data.routes.filter(r => currentFilter === 'all' || r.route_id === currentFilter);

            if (filteredRoutes.length === 0) {
                container.innerHTML = '<div class="empty-state">No hay datos para el ramal seleccionado.</div>';
                return;
            }

            let html = '';
            filteredRoutes.forEach(r => {
                const totalKm = r.distance_km;
                const buses = r.buses;
                const headways = r.headways;

                let statusBadge = '<span class="route-status-pill pill-empty">Sin buses</span>';
                if (r.status === 'PEGONAMIENTO') {
                    statusBadge = `<span class="route-status-pill pill-bunching">🚨 ${r.bunching_count} Pegonamiento(s)</span>`;
                } else if (r.status === 'ADVERTENCIA') {
                    statusBadge = '<span class="route-status-pill pill-warning">⚠️ Intervalo Corto</span>';
                } else if (r.status === 'OPTIMO') {
                    statusBadge = '<span class="route-status-pill pill-optimal">✓ Intervalo Regular</span>';
                } else if (r.status === 'UN_BUS') {
                    statusBadge = '<span class="route-status-pill pill-optimal">1 Bus en Ruta</span>';
                }

                html += `
                <div class="route-card">
                    <div class="route-header">
                        <div class="route-meta">
                            <span class="route-id-badge">${r.route_id.toUpperCase()}</span>
                            <span class="route-name">${r.name}</span>
                            <span class="route-length">🛣️ ${totalKm} km · Sentido: ${r.direction_label}</span>
                        </div>
                        <div>
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
                                const cls = isCrit ? 'critical' : (hw.severity === 'WARNING' ? 'warning' : 'optimal');
                                return `
                                    <div class="headway-segment ${cls}" style="left: ${hw.left_pct}%; width: ${hw.width_pct}%;">
                                        <div class="headway-badge ${cls}">
                                            ${isCrit ? '⚠️ ' : ''}Δ ${hw.gap_km} km (${hw.est_minutes} min)
                                        </div>
                                    </div>
                                `;
                            }).join('')}

                            <!-- Bus Markers on Track -->
                            ${buses.map(b => {
                                const isBunch = b.is_bunching;
                                return `
                                    <div class="bus-marker ${isBunch ? 'bunching' : ''}" style="left: ${b.progress_percent}%;" title="Bus ${b.bus_id} | ${b.speed_kmh} km/h | km ${b.distance_traveled_km}">
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

                    <!-- Mini Bus Audit Table -->
                    ${buses.length > 0 ? `
                    <div class="bus-table-box">
                        <table class="bus-mini-table">
                            <thead>
                                <tr>
                                    <th>Coche</th>
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
                                    <tr>
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
                                                : '<span style="color: #34d399;">✓ Intervalo Regular</span>'
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

        // Refresco automático cada 3 segundos
        fetchHeadwayData();
        setInterval(fetchHeadwayData, 3000);
    </script>
</body>
</html>
"""
