#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincronizador de Shapes Oficiales desde CID (VMT) hacia Odoo (flota_db)
Extrae los shapes del schema geometria.historico_itinerario para los ramales:
020c, 020d, 020e, 020f, 0210, 0211
e inserta en transit_route y transit_route_shape con fechas de vigencia históricas.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Conexión origen: BD CID
CID_HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
CID_PORT = int(os.getenv("CID_DB_PORT", "2024"))
CID_NAME = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
CID_USER = os.getenv("CID_DB_USER", "cid_admin_user")
CID_PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

# Conexión destino: Local flota_db
PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_NAME = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

ROUTES = ['020c', '020d', '020e', '020f', '0210', '0211']

def sync_shapes():
    print(f"[*] Conectando a BD CID ({CID_HOST}:{CID_PORT}/{CID_NAME})...")
    cid_conn = psycopg2.connect(
        host=CID_HOST, port=CID_PORT, dbname=CID_NAME, user=CID_USER, password=CID_PASS, connect_timeout=10
    )
    cid_cur = cid_conn.cursor(cursor_factory=RealDictCursor)

    print(f"[*] Conectando a Base Local ({PG_HOST}:{PG_PORT}/{PG_NAME})...")
    local_conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASS, connect_timeout=10
    )
    local_cur = local_conn.cursor(cursor_factory=RealDictCursor)

    # 1. Asegurar que las rutas existan y tengan nombres oficiales en transit_route
    ROUTE_DETAILS = {
        '020c': {'name': 'Ramal 020C - San Lorenzo a Asunción', 'direction': 'inbound', 'origin': 'San Lorenzo (Azara)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.28},
        '020d': {'name': 'Ramal 020D - Asunción a San Lorenzo', 'direction': 'outbound', 'origin': 'Asunción Centro (Puerto)', 'destination': 'San Lorenzo (Azara)', 'km': 18.02},
        '020e': {'name': 'Ramal 020E - San Lorenzo a Asunción (Variante)', 'direction': 'inbound', 'origin': 'San Lorenzo (Azara)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.92},
        '020f': {'name': 'Ramal 020F - Asunción a San Lorenzo (Variante)', 'direction': 'outbound', 'origin': 'Asunción Centro (Puerto)', 'destination': 'San Lorenzo (Azara)', 'km': 18.91},
        '0210': {'name': 'Ramal 0210 - Luque (Aeropuerto) a Asunción', 'direction': 'inbound', 'origin': 'Luque (Rotonda Aeropuerto)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.33},
        '0211': {'name': 'Ramal 0211 - Asunción a Luque (Aeropuerto)', 'direction': 'outbound', 'origin': 'Asunción Centro (Puerto)', 'destination': 'Luque (Rotonda Aeropuerto)', 'km': 18.84},
    }

    route_map = {} # code -> route_id
    for code in ROUTES:
        det = ROUTE_DETAILS[code]
        local_cur.execute("SELECT id FROM transit_route WHERE code = %s;", (code,))
        row = local_cur.fetchone()
        if not row:
            local_cur.execute("""
                INSERT INTO transit_route (code, name, agency_id, direction, origin, destination, distance_km)
                VALUES (%s, %s, '004B', %s, %s, %s, %s)
                RETURNING id;
            """, (code, det['name'], det['direction'], det['origin'], det['destination'], det['km']))
            route_map[code] = local_cur.fetchone()['id']
            print(f"[+] Ruta creada en transit_route: {code} (ID: {route_map[code]})")
        else:
            route_map[code] = row['id']
            local_cur.execute("""
                UPDATE transit_route 
                SET name = %s, direction = %s, origin = %s, destination = %s, distance_km = %s
                WHERE id = %s;
            """, (det['name'], det['direction'], det['origin'], det['destination'], det['km'], route_map[code]))
            print(f"[*] Ruta actualizada en transit_route: {code} (ID: {route_map[code]})")

    local_conn.commit()

    # 2. Consultar shapes de CID con ST_AsText(ST_LineMerge(geom))
    print("\n[*] Extrayendo shapes oficiales de CID...")
    cid_cur.execute("""
        SELECT 
            id_itinerario,
            ruta_hex,
            fecha_inicio_vigencia,
            fecha_fin_vigencia,
            vigente,
            observacion,
            ROUND((ST_Length(ST_Transform(geom, 32721)) / 1000.0)::numeric, 2) as total_km,
            ST_AsText(ST_LineMerge(geom)) as wkt_geom
        FROM geometria.historico_itinerario
        WHERE ruta_hex = ANY(%s)
        ORDER BY ruta_hex, fecha_inicio_vigencia ASC, id_itinerario ASC;
    """, (ROUTES,))

    cid_shapes = cid_cur.fetchall()
    print(f"[+] Se obtuvieron {len(cid_shapes)} shapes desde CID.")

    # 3. Limpiar shapes anteriores para las rutas sincronizadas
    for code, r_id in route_map.items():
        # Antes de borrar, desvincular referencias temporales de telemetry_ping si apuntan a shapes viejos
        local_cur.execute("UPDATE telemetry_ping SET route_shape_id = NULL WHERE route_shape_id IN (SELECT id FROM transit_route_shape WHERE route_id = %s);", (r_id,))
        local_cur.execute("DELETE FROM transit_route_shape WHERE route_id = %s;", (r_id,))

    local_conn.commit()

    # 4. Insertar shapes con versionado incremental
    counts = {c: 0 for c in ROUTES}
    version_counters = {c: 1 for c in ROUTES}

    for s in cid_shapes:
        code = s['ruta_hex']
        r_id = route_map[code]
        ver = version_counters[code]
        version_counters[code] += 1

        v_from = s['fecha_inicio_vigencia']
        v_until = s['fecha_fin_vigencia']
        km = float(s['total_km']) if s['total_km'] else 18.0
        obs = s['observacion'] or ('Trazado Oficial Vigente' if s['vigente'] else 'Trazado Especial / Desvío')
        source = f"CID_VMT_ID_{s['id_itinerario']}"

        # Ajuste de consistencia para valid_until > valid_from
        if v_until and v_until <= v_from:
            # Si coinciden el mismo día, sumar 1 día para satisfacer el check constraint
            local_cur.execute("""
                INSERT INTO transit_route_shape 
                    (route_id, version, valid_from, valid_until, geom, total_km, shape_source, notes, created_by)
                VALUES (%s, %s, %s, %s + INTERVAL '1 day', ST_GeomFromText(%s, 4326), %s, %s, %s, 'CID_SYNC')
                RETURNING id;
            """, (r_id, ver, v_from, v_until, s['wkt_geom'], km, source, obs))
        else:
            local_cur.execute("""
                INSERT INTO transit_route_shape 
                    (route_id, version, valid_from, valid_until, geom, total_km, shape_source, notes, created_by)
                VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, 'CID_SYNC')
                RETURNING id;
            """, (r_id, ver, v_from, v_until, s['wkt_geom'], km, source, obs))

        counts[code] += 1

        # Si este shape es el vigente actual, actualizar distance_km en transit_route
        if s['vigente']:
            local_cur.execute("UPDATE transit_route SET distance_km = %s WHERE id = %s;", (km, r_id))

    local_conn.commit()

    print("\n=======================================================")
    print("      RESUMEN DE SINCRONIZACIÓN DE SHAPES CID          ")
    print("=======================================================")
    for code, qty in counts.items():
        local_cur.execute("SELECT distance_km FROM transit_route WHERE id = %s;", (route_map[code],))
        dist = local_cur.fetchone()['distance_km']
        print(f" -> Ramal {code.upper()}: {qty} versiones importadas (Longitud actual: {dist} km)")

    cid_cur.close()
    cid_conn.close()
    local_cur.close()
    local_conn.close()
    print("\n[+] ¡Sincronización de shapes finalizada con éxito!")

if __name__ == "__main__":
    sync_shapes()
    try:
        from sync_cid_stops_to_flota import sync_stops
        print("\n[*] Sincronizando paradas oficiales e hitos de intersección de los ramales...")
        sync_stops()
    except Exception as e:
        print(f"[!] Aviso: No se pudieron sincronizar las paradas automáticamente: {e}")

