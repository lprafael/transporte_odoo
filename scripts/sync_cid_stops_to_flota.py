#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincroniza las 340 paradas oficiales del CID (geometria.paradas_oficiales e itinerario_parada)
hacia la base local (transit_stop y transit_route_stop) para los 6 ramales de la Línea 20 (004B).
Calcula la distancia exacta en km a lo largo del shape oficial (distance_from_origin_km).
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

CID_HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
CID_PORT = int(os.getenv("CID_DB_PORT", "2024"))
CID_NAME = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
CID_USER = os.getenv("CID_DB_USER", "cid_admin_user")
CID_PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

LOCAL_HOST = os.getenv("PG_HOST", "localhost")
LOCAL_PORT = int(os.getenv("PG_PORT", "5434" if os.getenv("PG_HOST") != "db" else "5432"))
LOCAL_NAME = os.getenv("PG_DB", "flota_db")
LOCAL_USER = os.getenv("PG_USER", "odoo")
LOCAL_PASS = os.getenv("PG_PASS", "odoo_password")

ROUTES_MAP = {
    '020c': 2171,
    '020d': 2172,
    '020e': 2190,
    '020f': 2191,
    '0210': 2192,
    '0211': 2201
}

def clean_stop_name(raw_name: str) -> str:
    if not raw_name:
        return "Parada Oficial"
    name = raw_name.strip()
    # Limpiar prefijos de líneas ej: "Línea 14, 19, 20..." o "9.3, 9.4..."
    if name.lower().startswith("línea ") or name.lower().startswith("linea "):
        return "Parada Urbana Interdistrital"
    if any(c.isdigit() for c in name[:3]) and (',' in name or '-' in name):
        return "Parada Interurbana"
    if name.lower() == "bus_stop":
        return "Parada de Ómnibus"
    # Quitar sufijos de líneas ej: " (Bus Línea 12, 13...)"
    if " (bus" in name.lower():
        idx = name.lower().index(" (bus")
        name = name[:idx].strip()
    return name

def sync_stops():
    print(f"[*] Conectando a BD CID ({CID_HOST}:{CID_PORT}/{CID_NAME})...")
    cid_conn = psycopg2.connect(host=CID_HOST, port=CID_PORT, dbname=CID_NAME, user=CID_USER, password=CID_PASS)
    cid_cur = cid_conn.cursor(cursor_factory=RealDictCursor)

    print(f"[*] Conectando a BD Local ({LOCAL_HOST}:{LOCAL_PORT}/{LOCAL_NAME})...")
    local_conn = psycopg2.connect(host=LOCAL_HOST, port=LOCAL_PORT, dbname=LOCAL_NAME, user=LOCAL_USER, password=LOCAL_PASS)
    local_conn.set_client_encoding('UTF8')
    local_cur = local_conn.cursor(cursor_factory=RealDictCursor)

    # 1. Obtener shapes vigentes en flota_db
    local_cur.execute("""
        SELECT s.id as shape_id, r.code as route_code, s.total_km
        FROM transit_route_shape s
        JOIN transit_route r ON s.route_id = r.id
        WHERE s.valid_until IS NULL OR s.valid_until > CURRENT_DATE;
    """)
    active_shapes = {row['route_code']: row for row in local_cur.fetchall()}
    print(f"[+] Shapes activos locales encontrados: {list(active_shapes.keys())}")

    # Limpiar transit_route_stop anterior
    local_cur.execute("DELETE FROM transit_route_stop;")
    local_conn.commit()

    total_synced_stops = 0

    for route_code, id_itinerario in ROUTES_MAP.items():
        if route_code not in active_shapes:
            continue
        
        shape_info = active_shapes[route_code]
        shape_id = shape_info['shape_id']
        total_km = float(shape_info['total_km'])

        # Consultar paradas en CID
        cid_cur.execute("""
            SELECT 
                ip.orden,
                p.id as parada_id,
                p.source_name,
                ST_AsText(p.geom) as wkt_geom,
                ST_Y(p.geom) as lat,
                ST_X(p.geom) as lon
            FROM geometria.itinerario_parada ip
            JOIN geometria.paradas_oficiales p ON ip.id_parada = p.id
            WHERE ip.id_itinerario = %s
            ORDER BY ip.orden ASC;
        """, (id_itinerario,))
        cid_stops = cid_cur.fetchall()
        print(f"[*] Ramal {route_code} (Itinerario CID {id_itinerario}): {len(cid_stops)} paradas oficiales encontradas.")

        seq = 1
        for s in cid_stops:
            p_id = s['parada_id']
            clean_name = clean_stop_name(s['source_name'])
            stop_code = f"CID-P{p_id}"
            wkt = s['wkt_geom']

            # Insertar parada en transit_stop si no existe
            local_cur.execute("""
                INSERT INTO transit_stop (stop_code, name, stop_type, agency_id, valid_from, geom, radius_meters, address)
                VALUES (%s, %s, 'stop', '004B', '2024-01-01', ST_GeomFromText(%s, 4326), 40, %s)
                ON CONFLICT (stop_code) DO UPDATE 
                SET name = EXCLUDED.name, geom = EXCLUDED.geom
                RETURNING id;
            """, (stop_code, clean_name, wkt, s['source_name']))
            local_stop_id = local_cur.fetchone()['id']

            # Calcular distancia lineal a lo largo del shape
            local_cur.execute("""
                SELECT ROUND((ST_LineLocatePoint(s.geom, ST_GeomFromText(%s, 4326)) * %s)::numeric, 2) as dist_km
                FROM transit_route_shape s
                WHERE s.id = %s;
            """, (wkt, total_km, shape_id))
            dist_km = float(local_cur.fetchone()['dist_km'] or 0.0)

            # Insertar en transit_route_stop
            local_cur.execute("""
                INSERT INTO transit_route_stop (route_shape_id, stop_id, sequence, distance_from_origin_km)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (route_shape_id, sequence) DO UPDATE
                SET stop_id = EXCLUDED.stop_id, distance_from_origin_km = EXCLUDED.distance_from_origin_km;
            """, (shape_id, local_stop_id, seq, dist_km))

            seq += 1
            total_synced_stops += 1

        local_conn.commit()
        print(f"  [+] Sincronizadas {seq-1} paradas para el Ramal {route_code}")

    print(f"\n[OK] Sincronización exitosa: {total_synced_stops} paradas oficiales vinculadas a los shapes en flota_db.")
    cid_cur.close()
    cid_conn.close()
    local_cur.close()
    local_conn.close()

if __name__ == '__main__':
    sync_stops()
