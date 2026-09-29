#!/usr/bin/env python3
"""
Sync Telemetry from VMT Monitoring DB (Viceministerio de Transporte - Paraguay)
Target Table: app_monitoreo_mensajeoperativo
Agency Filter: agency_id = '004B'
"""

import sys
import os
import time
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import json
from datetime import datetime

VMT_HOST = os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py")
VMT_PORT = int(os.getenv("VMT_DB_PORT", "5432"))
VMT_NAME = os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod")
VMT_USER = os.getenv("VMT_DB_USER", "jefe-CID")
VMT_PASS = os.getenv("VMT_DB_PASS", "vmtdmt")

BROKER_URL = os.getenv("BROKER_URL", "http://localhost:8088/telemetry/gps")
BROKER_TOKEN = os.getenv("GPS_DEVICE_TOKEN", "GPS_DEVICE_SECRET_2026")

def get_connection(password=VMT_PASS):
    try:
        conn = psycopg2.connect(
            host=VMT_HOST,
            port=VMT_PORT,
            dbname=VMT_NAME,
            user=VMT_USER,
            password=password,
            sslmode="require",
            connect_timeout=10
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"[-] Error de conexión a VMT: {e}")
        return None

def fetch_latest_positions_per_bus(conn, agency_id="004B", sample_size=2000):
    """Obtiene la última posición registrada de cada bus de la agencia de forma ultra-rápida"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT DISTINCT ON (mean_id) 
            id,
            agency_id,
            mean_id,
            route_id,
            driver_id,
            latitude,
            longitude,
            rumbo,
            velocidad,
            fecha_hora
        FROM (
            SELECT 
                id,
                agency_id,
                mean_id,
                route_id,
                driver_id,
                latitude,
                longitude,
                rumbo,
                velocidad,
                fecha_hora
            FROM app_monitoreo_mensajeoperativo
            WHERE agency_id = %s
            ORDER BY id DESC
            LIMIT %s
        ) sub
        ORDER BY mean_id, id DESC;
    """
    cursor.execute(query, (agency_id, sample_size))
    rows = cursor.fetchall()
    cursor.close()
    return rows

def fetch_latest_events(conn, agency_id="004B", limit=25):
    """Obtiene los últimos N registros ordenados cronológicamente"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT 
            id,
            agency_id,
            mean_id,
            route_id,
            driver_id,
            latitude,
            longitude,
            rumbo,
            velocidad,
            fecha_hora
        FROM app_monitoreo_mensajeoperativo
        WHERE agency_id = %s
        ORDER BY fecha_hora DESC
        LIMIT %s;
    """
    cursor.execute(query, (agency_id, limit))
    rows = cursor.fetchall()
    cursor.close()
    return rows

def forward_to_broker(rows, broker_url=BROKER_URL, token=BROKER_TOKEN):
    headers = {
        "Content-Type": "application/json",
        "X-Device-Token": token
    }
    sent = 0
    for row in rows:
        bus_id = f"BUS-{row['mean_id']}"
        rec_time = row['fecha_hora']
        if isinstance(rec_time, datetime):
            rec_time = rec_time.isoformat()

        payload = {
            "agency_id": row["agency_id"],
            "mean_id": row["mean_id"],
            "route_id": row["route_id"],
            "driver_id": row.get("driver_id", ""),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "velocidad": float(row["velocidad"] or 0.0),
            "rumbo": float(row["rumbo"] or 0.0),
            "fecha_hora": rec_time,
            "precision": row.get("precision")
        }
        
        try:
            res = requests.post(broker_url, json=payload, headers=headers, timeout=3)
            if res.status_code in (200, 201):
                sent += 1
            else:
                print(f"[-] Broker devolvió HTTP {res.status_code}: {res.text}")
        except Exception as err:
            print(f"[-] Error enviando {bus_id} al broker: {err}")

    return sent

def main():
    parser = argparse.ArgumentParser(description="VMT Telemetry Sync - Agencia 004B")
    parser.add_argument("--password", "-p", default=VMT_PASS, help="Password para usuario jefe-CID")
    parser.add_argument("--agency", "-a", default="004B", help="ID de agencia (default: 004B)")
    parser.add_argument("--distinct", "-d", action="store_true", default=True, help="Estirar último ping por cada bus distinto")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Límite si no es distinct")
    parser.add_argument("--forward", "-f", action="store_true", help="Reenviar pings hacia el broker local")
    parser.add_argument("--broker-url", default=BROKER_URL, help="URL de ingesta del broker")
    parser.add_argument("--stream", action="store_true", help="Mantener sincronización continua")
    parser.add_argument("--interval", type=int, default=10, help="Intervalo en segundos para el modo stream")
    args = parser.parse_args()

    print(f"[*] Conectando a {VMT_HOST}:{VMT_PORT}/{VMT_NAME}...")
    conn = get_connection(args.password)
    if not conn:
        sys.exit(1)

    print(f"[+] ¡Conexión establecida con la base de datos VMT!")

    def run_sync_cycle(active_conn):
        if args.distinct:
            rows = fetch_latest_positions_per_bus(active_conn, agency_id=args.agency)
        else:
            rows = fetch_latest_events(active_conn, agency_id=args.agency, limit=args.limit)

        print(f"\n=======================================================")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pings recibidos de Agencia {args.agency}: {len(rows)}")
        print(f"=======================================================")
        
        for r in rows:
            hora = r['fecha_hora'].strftime('%H:%M:%S') if isinstance(r['fecha_hora'], datetime) else r['fecha_hora']
            print(f" -> Bus: {r['mean_id']:<6} | Ruta: {r['route_id']:<6} | Coords: ({r['latitude']:>10.6f}, {r['longitude']:>10.6f}) | Vel: {r['velocidad']:>4.1f} km/h | Rumbo: {r['rumbo']:>5.1f}° | Hora: {hora}")

        if args.forward and rows:
            sent = forward_to_broker(rows, broker_url=args.broker_url)
            print(f"[+] Ingestados al Broker / Redis / Postgres: {sent}/{len(rows)}")

    if args.stream:
        print(f"[*] Iniciando sincronización continua cada {args.interval}s (Ctrl+C para detener)...")
        while True:
            try:
                if not conn or conn.closed:
                    print(f"[*] Reconectando a BD VMT ({VMT_HOST})...")
                    conn = get_connection(args.password)
                if conn:
                    run_sync_cycle(conn)
            except Exception as e:
                print(f"[-] Error en ciclo de sincronización VMT: {e}")
                try:
                    if conn:
                        conn.close()
                except Exception:
                    pass
                conn = None
            time.sleep(args.interval)
    else:
        run_sync_cycle(conn)
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
