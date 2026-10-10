#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador de Tráfico en Vivo para la Flota Completa (Línea 20)
Mueve continuamente las 27 unidades eléctricas a lo largo de sus itinerarios
reales en PostGIS, emitiendo telemetría GPS segundo a segundo al Broker.
Permite visualizar movimiento fluido y dinámico en /headway y /map.
"""

import sys
import os
import time
import math
import random
import json
import argparse
from datetime import datetime, timezone
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BROKER_URL = os.getenv("BROKER_URL", "http://localhost:8088/telemetry/gps")
BROKER_TOKEN = os.getenv("GPS_DEVICE_TOKEN", "GPS_DEVICE_SECRET_2026")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5434))
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )

def load_simulation_state():
    """Carga los buses y sus posiciones actuales relativas."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Obtener longitud de cada shape
    cur.execute("""
        SELECT r.code, s.total_km, ST_AsGeoJSON(s.geom) as geom_json
        FROM transit_route_shape s
        JOIN transit_route r ON s.route_id = r.id
        WHERE s.valid_until IS NULL OR s.valid_until > CURRENT_DATE;
    """)
    shapes = {}
    for row in cur.fetchall():
        geom = json.loads(row['geom_json'])
        shapes[row['code'].lower()] = {
            'total_km': float(row['total_km']),
            'coords': geom['coordinates']  # [[lon, lat], ...]
        }

    # 2. Obtener estado de los 27 buses
    cur.execute("""
        SELECT DISTINCT ON (bus_internal_code)
            bus_internal_code as bus_id,
            license_plate,
            route_id,
            agency_id,
            latitude,
            longitude,
            speed_kmh as speed,
            odometer_km,
            recorded_at
        FROM telemetry_ping
        WHERE route_id IN ('020c', '020d', '020e', '020f', '0210', '0211')
        ORDER BY bus_internal_code, recorded_at DESC;
    """)
    buses = []
    for r in cur.fetchall():
        r_code = (r['route_id'] or '020f').lower()
        shape = shapes.get(r_code)
        if not shape:
            continue
        
        # Calcular porcentaje inicial aproximado
        buses.append({
            'bus_id': str(r['bus_id']),
            'license_plate': r['license_plate'] or f"COCHE-{r['bus_id']}",
            'route_id': r_code,
            'agency_id': r['agency_id'] or '004B',
            'speed': max(15.0, float(r['speed'] or 25.0)),
            'odometer_km': float(r['odometer_km'] or 120000.0),
            'progress_fraction': random.uniform(0.05, 0.90),
            'shape': shape
        })
    cur.close()
    conn.close()
    return buses

def interpolate_coords(coords, fraction):
    """Interpola linealmente lat/lon en el LineString."""
    fraction = max(0.0, min(1.0, fraction))
    n = len(coords)
    if n == 0:
        return -25.30, -57.55
    if n == 1 or fraction == 0.0:
        return coords[0][1], coords[0][0]
    if fraction == 1.0:
        return coords[-1][1], coords[-1][0]

    # Posición métrica aproximada por índice de segmentos
    target_idx = fraction * (n - 1)
    i = int(math.floor(target_idx))
    rem = target_idx - i

    if i >= n - 1:
        return coords[-1][1], coords[-1][0]

    p1 = coords[i]
    p2 = coords[i + 1]

    lon = p1[0] + (p2[0] - p1[0]) * rem
    lat = p1[1] + (p2[1] - p1[1]) * rem
    return lat, lon

def run_simulation(cycles=50, interval=3.0, stream=False):
    print("=" * 70)
    print("🚦 INICIANDO SIMULADOR DE MOVIMIENTO EN VIVO - FLOTA LÍNEA 20")
    print(f"📡 Destino Broker: {BROKER_URL}")
    print(f"⏱️  Intervalo: {interval}s entre ciclos de telemetría")
    print("=" * 70)

    buses = load_simulation_state()
    print(f"[*] Cargados {len(buses)} buses con sus trazados oficiales.")

    headers = {
        "Content-Type": "application/json",
        "X-Device-Token": BROKER_TOKEN
    }

    cycle = 1
    while stream or cycle <= cycles:
        now_iso = datetime.now(timezone.utc).isoformat()
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Ciclo {cycle} -> Actualizando telemetría de {len(buses)} unidades...")

        sent_ok = 0
        for b in buses:
            # Variar velocidad de tráfico urbano (entre 18 y 48 km/h)
            speed = round(max(0.0, b['speed'] + random.uniform(-4.0, 4.0)), 1)
            b['speed'] = speed

            # Distancia recorrida en este intervalo (km)
            km_advanced = (speed / 3600.0) * interval
            b['odometer_km'] += km_advanced

            total_km = b['shape']['total_km']
            if total_km > 0:
                frac_step = km_advanced / total_km
                b['progress_fraction'] += frac_step

                # Si llega al final del ramal (100%), vuelve a salir de cabecera (0%)
                if b['progress_fraction'] >= 1.0:
                    b['progress_fraction'] = 0.0
                    b['speed'] = random.uniform(0.0, 10.0)

            lat, lon = interpolate_coords(b['shape']['coords'], b['progress_fraction'])

            payload = {
                "agency_id": b["agency_id"],
                "mean_id": b["bus_id"],
                "route_id": b["route_id"],
                "latitude": lat,
                "longitude": lon,
                "velocidad": speed,
                "odometer_km": round(b['odometer_km'], 1),
                "rumbo": 90.0,
                "fecha_hora": now_iso
            }

            try:
                res = requests.post(BROKER_URL, json=payload, headers=headers, timeout=2.0)
                if res.status_code == 200:
                    sent_ok += 1
            except Exception as e:
                pass

        print(f"  ✓ {sent_ok}/{len(buses)} pings emitidos al Broker GPS.")
        time.sleep(interval)
        cycle += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulador de Movimiento de Flota Línea 20")
    parser.add_argument("--cycles", type=int, default=10, help="Número de ciclos de simulación (default: 10)")
    parser.add_argument("--interval", type=float, default=3.0, help="Segundos entre pings (default: 3.0)")
    parser.add_argument("--stream", action="store_true", help="Ejecutar en bucle continuo infinito")
    args = parser.parse_args()

    run_simulation(cycles=args.cycles, interval=args.interval, stream=args.stream)
