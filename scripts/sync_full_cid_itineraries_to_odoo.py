# -*- coding: utf-8 -*-
"""
Sincronización Completa de Itinerarios, Shapes y Geocercas desde CID a Odoo (flota_db).
Garantiza que todos los ramales y sus paradas queden 100% activos y visibles en Odoo (transit.route).
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

LOCAL_HOST = "localhost" if os.name == "nt" or not os.path.exists("/.dockerenv") else os.getenv("PG_HOST", "db")
LOCAL_PORT = int(os.getenv("POSTGRES_PORT", "5434")) if LOCAL_HOST == "localhost" else int(os.getenv("PG_PORT", "5432"))
LOCAL_NAME = os.getenv("PG_DB", "flota_db")
LOCAL_USER = os.getenv("PG_USER", "odoo")
LOCAL_PASS = os.getenv("PG_PASS", "odoo_password")

ROUTES_CONFIG = {
    '020c': {
        'name': 'Ramal 020C - Eléctrico 1 (San Lorenzo a Asunción)',
        'direction': 'inbound',
        'origin': 'San Lorenzo (Azara)',
        'destination': 'Asunción Centro (Puerto)',
        'distance_km': 19.46,
        'duration_min': 65,
        'fare': 3400.0,
        'service_id': 1,
        'cid_itinerario': 2171
    },
    '020d': {
        'name': 'Ramal 020D - Eléctrico 1 (Asunción a San Lorenzo)',
        'direction': 'outbound',
        'origin': 'Asunción Centro (Puerto)',
        'destination': 'San Lorenzo (Azara)',
        'distance_km': 19.78,
        'duration_min': 65,
        'fare': 3400.0,
        'service_id': 1,
        'cid_itinerario': 2172
    },
    '020e': {
        'name': 'Ramal 020E - Eléctrico 2 (San Lorenzo a Asunción Variante)',
        'direction': 'inbound',
        'origin': 'San Lorenzo (Azara)',
        'destination': 'Asunción Centro (Puerto)',
        'distance_km': 19.53,
        'duration_min': 65,
        'fare': 3400.0,
        'service_id': 2,
        'cid_itinerario': 2190
    },
    '020f': {
        'name': 'Ramal 020F - Eléctrico 2 (Asunción a San Lorenzo Variante)',
        'direction': 'outbound',
        'origin': 'Asunción Centro (Puerto)',
        'destination': 'San Lorenzo (Azara)',
        'distance_km': 19.82,
        'duration_min': 65,
        'fare': 3400.0,
        'service_id': 2,
        'cid_itinerario': 2191
    },
    '0210': {
        'name': 'Ramal 0210 - Eléctrico 3 (Luque a Asunción)',
        'direction': 'inbound',
        'origin': 'Luque (Aeropuerto)',
        'destination': 'Asunción Centro (Puerto)',
        'distance_km': 18.33,
        'duration_min': 60,
        'fare': 3400.0,
        'service_id': 3,
        'cid_itinerario': 2192
    },
    '0211': {
        'name': 'Ramal 0211 - Eléctrico 3 (Asunción a Luque)',
        'direction': 'outbound',
        'origin': 'Asunción Centro (Puerto)',
        'destination': 'Luque (Aeropuerto)',
        'distance_km': 18.84,
        'duration_min': 60,
        'fare': 3400.0,
        'service_id': 3,
        'cid_itinerario': 2201
    }
}

def clean_stop_name(raw_name: str) -> str:
    if not raw_name:
        return "Parada Oficial"
    name = raw_name.strip()
    if name.lower().startswith("línea ") or name.lower().startswith("linea "):
        return "Parada Urbana Interdistrital"
    if any(c.isdigit() for c in name[:3]) and (',' in name or '-' in name):
        return "Parada Interurbana"
    if name.lower() == "bus_stop":
        return "Parada de Ómnibus"
    if " (bus" in name.lower():
        idx = name.lower().index(" (bus")
        name = name[:idx].strip()
    return name

def sync_full_itineraries():
    print(f"[*] Conectando a CID ({CID_HOST}:{CID_PORT}/{CID_NAME})...")
    cid_conn = psycopg2.connect(host=CID_HOST, port=CID_PORT, dbname=CID_NAME, user=CID_USER, password=CID_PASS, connect_timeout=10)
    cid_cur = cid_conn.cursor(cursor_factory=RealDictCursor)

    print(f"[*] Conectando a Base Local Odoo ({LOCAL_HOST}:{LOCAL_PORT}/{LOCAL_NAME})...")
    local_conn = psycopg2.connect(host=LOCAL_HOST, port=LOCAL_PORT, dbname=LOCAL_NAME, user=LOCAL_USER, password=LOCAL_PASS, connect_timeout=10)
    local_conn.set_client_encoding('UTF8')
    local_cur = local_conn.cursor(cursor_factory=RealDictCursor)

    # 1. Asegurar Concesionaria 004B en transit_concessionaire
    local_cur.execute("SELECT id FROM transit_concessionaire WHERE code = '004B';")
    con_row = local_cur.fetchone()
    if con_row:
        concessionaire_id = con_row['id']
    else:
        local_cur.execute("""
            INSERT INTO transit_concessionaire (name, code, active)
            VALUES ('Consorcio Arapoti (Línea 20 Eléctricos)', '004B', TRUE)
            RETURNING id;
        """)
        concessionaire_id = local_cur.fetchone()['id']
    print(f"[+] Concesionaria activa: ID {concessionaire_id}")

    # 2. Actualizar / Crear Rutas en transit_route y poner active = TRUE
    route_db_ids = {}
    for code, cfg in ROUTES_CONFIG.items():
        local_cur.execute("SELECT id FROM transit_route WHERE code = %s;", (code,))
        r_row = local_cur.fetchone()

        if r_row:
            r_id = r_row['id']
            local_cur.execute("""
                UPDATE transit_route
                SET name = %s,
                    direction = %s,
                    origin = %s,
                    destination = %s,
                    distance_km = %s,
                    standard_duration_minutes = %s,
                    standard_fare = %s,
                    concessionaire_id = %s,
                    service_id = %s,
                    active = TRUE
                WHERE id = %s;
            """, (cfg['name'], cfg['direction'], cfg['origin'], cfg['destination'], cfg['distance_km'], cfg['duration_min'], cfg['fare'], concessionaire_id, cfg['service_id'], r_id))
            print(f"[*] Ruta actualizada y activada: {code} (ID: {r_id})")
        else:
            local_cur.execute("""
                INSERT INTO transit_route 
                    (name, code, direction, origin, destination, distance_km, standard_duration_minutes, standard_fare, concessionaire_id, service_id, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id;
            """, (cfg['name'], code, cfg['direction'], cfg['origin'], cfg['destination'], cfg['distance_km'], cfg['duration_min'], cfg['fare'], concessionaire_id, cfg['service_id']))
            r_id = local_cur.fetchone()['id']
            print(f"[+] Nueva ruta creada y activada: {code} (ID: {r_id})")

        route_db_ids[code] = r_id

    local_conn.commit()

    # 3. Extraer y Sincronizar Checkpoints / Geocercas desde CID (geometria.itinerario_parada)
    print("\n[*] Extrayendo puntos de control y geocercas desde CID...")
    total_checkpoints = 0

    for code, cfg in ROUTES_CONFIG.items():
        r_id = route_db_ids[code]
        id_itinerario = cfg['cid_itinerario']

        cid_cur.execute("""
            SELECT 
                ip.orden,
                p.id as parada_id,
                p.source_name,
                ST_Y(p.geom) as lat,
                ST_X(p.geom) as lon
            FROM geometria.itinerario_parada ip
            JOIN geometria.paradas_oficiales p ON ip.id_parada = p.id
            WHERE ip.id_itinerario = %s
            ORDER BY ip.orden ASC;
        """, (id_itinerario,))
        stops = cid_cur.fetchall()
        print(f"[*] Ramal {code}: {len(stops)} paradas encontradas en CID.")

        if not stops:
            continue

        # Limpiar checkpoints previos de esta ruta
        local_cur.execute("DELETE FROM transit_route_checkpoint WHERE route_id = %s;", (r_id,))

        n_stops = len(stops)
        for idx, s in enumerate(stops):
            seq = (idx + 1) * 10
            clean_name = clean_stop_name(s['source_name'])
            lat = float(s['lat'])
            lon = float(s['lon'])

            if idx == 0:
                cp_type = 'origin'
                radius = 100
                offset = 0
                # Actualizar coordenadas de origen en transit_route
                local_cur.execute("""
                    UPDATE transit_route 
                    SET origin_latitude = %s, origin_longitude = %s, origin_radius_meters = 100
                    WHERE id = %s;
                """, (lat, lon, r_id))
            elif idx == n_stops - 1:
                cp_type = 'destination'
                radius = 100
                offset = cfg['duration_min']
                # Actualizar coordenadas de destino en transit_route
                local_cur.execute("""
                    UPDATE transit_route 
                    SET destination_latitude = %s, destination_longitude = %s, destination_radius_meters = 100
                    WHERE id = %s;
                """, (lat, lon, r_id))
            else:
                cp_type = 'stop'
                radius = 60
                offset = int((idx / (n_stops - 1)) * cfg['duration_min'])

            # Detección del punto de retorno al 80%
            if idx == int(n_stops * 0.8):
                local_cur.execute("""
                    UPDATE transit_route 
                    SET return_80_latitude = %s, return_80_longitude = %s, return_80_radius_meters = 150
                    WHERE id = %s;
                """, (lat, lon, r_id))

            local_cur.execute("""
                INSERT INTO transit_route_checkpoint
                    (route_id, sequence, name, checkpoint_type, latitude, longitude, radius_meters, offset_minutes, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE);
            """, (r_id, seq, clean_name, cp_type, lat, lon, radius, offset))
            total_checkpoints += 1

    local_conn.commit()
    print(f"\n[+] Total puntos de control (checkpoints) sincronizados en Odoo: {total_checkpoints}")

    # 4. Resumen Final de Odoo transit.route
    local_cur.execute("""
        SELECT 
            r.code, 
            r.name, 
            r.active, 
            r.distance_km,
            (SELECT COUNT(*) FROM transit_route_shape s WHERE s.route_id = r.id) as cant_shapes,
            (SELECT COUNT(*) FROM transit_timetable t WHERE t.route_id = r.id) as cant_horarios,
            (SELECT COUNT(*) FROM transit_route_checkpoint c WHERE c.route_id = r.id) as cant_geocercas
        FROM transit_route r
        WHERE r.code IN %s
        ORDER BY r.code;
    """, (tuple(ROUTES_CONFIG.keys()),))

    print("\n=======================================================")
    print(" ESTADO DEFINITIVO DE RUTAS E ITINERARIOS EN ODOO ERP")
    print("=======================================================")
    for row in local_cur.fetchall():
        print(f"[{row['code'].upper()}] {row['name']}")
        print(f"   - Activo en Odoo: {row['active']} | Distancia: {row['distance_km']} km")
        print(f"   - Shapes (Vigencias CID): {row['cant_shapes']} trazados")
        print(f"   - Cuadro de Marcha CID: {row['cant_horarios']} salidas programadas")
        print(f"   - Geocercas de Paradas: {row['cant_geocercas']} puntos de control")
        print("-------------------------------------------------------")

    cid_conn.close()
    local_conn.close()

if __name__ == "__main__":
    sync_full_itineraries()
