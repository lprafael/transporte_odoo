#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("LOCAL_PG_HOST") or ("localhost" if os.name == 'nt' else "db")
PG_PORT = int(os.getenv("LOCAL_PG_PORT") or ("5434" if os.name == 'nt' else "5432"))
PG_NAME = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def main():
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASS
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("[*] Asegurando Concesionaria ID 1 (Línea 20)...")
    cur.execute("SELECT id FROM transit_concessionaire WHERE id = 1;")
    conc = cur.fetchone()
    concessionaire_id = conc['id'] if conc else 1

    # 1. Servicios E1, E2, E3
    services_data = [
        {
            'cid_id': 3,
            'code': 'E1',
            'name': 'Línea 20 Eléctrico 1 (San Lorenzo - Asunción)',
            'description': 'Servicio de Buses Eléctricos que van por Eusebio Ayala (San Lorenzo - Asunción)',
            'daily_target': 220,
            'geofence_r': 150,
            'buffer': 50,
            'comp_pct': 70.0,
            'incomp_pct': 80.0,
            'tol_early': 5,
            'tol_late': 10,
            'routes': ['020c', '020d']
        },
        {
            'cid_id': 8,
            'code': 'E2',
            'name': 'Línea 20 Eléctrico 2 (San Lorenzo - Asunción Variante)',
            'description': 'Servicio de Buses Eléctricos Variante (San Lorenzo - Asunción)',
            'daily_target': 300,
            'geofence_r': 150,
            'buffer': 50,
            'comp_pct': 80.0,
            'incomp_pct': 80.0,
            'tol_early': 5,
            'tol_late': 10,
            'routes': ['020e', '020f']
        },
        {
            'cid_id': 10,
            'code': 'E3',
            'name': 'Línea 20 Eléctrico 3 (Luque - Asunción)',
            'description': 'Servicio de Buses Eléctricos por Mcal López y Aviadores (Luque - Asunción)',
            'daily_target': 172,
            'geofence_r': 100,
            'buffer': 50,
            'comp_pct': 60.0,
            'incomp_pct': 80.0,
            'tol_early': 5,
            'tol_late': 10,
            'routes': ['0210', '0211']
        }
    ]

    service_map = {}
    for s in services_data:
        cur.execute("SELECT id FROM transit_service WHERE code = %s;", (s['code'],))
        row = cur.fetchone()
        if row:
            s_id = row['id']
            cur.execute("""
                UPDATE transit_service
                SET name = %s, description = %s, concessionaire_id = %s, cid_service_id = %s,
                    daily_target_departures = %s, geofence_radius_m = %s, itinerary_buffer_m = %s,
                    compliance_threshold_pct = %s, incomplete_threshold_pct = %s,
                    tolerance_early_min = %s, tolerance_late_min = %s, agency_vmt_id = '004B',
                    active = TRUE, write_date = NOW()
                WHERE id = %s;
            """, (s['name'], s['description'], concessionaire_id, s['cid_id'],
                  s['daily_target'], s['geofence_r'], s['buffer'], s['comp_pct'], s['incomp_pct'],
                  s['tol_early'], s['tol_late'], s_id))
        else:
            cur.execute("""
                INSERT INTO transit_service
                    (name, code, description, concessionaire_id, cid_service_id,
                     daily_target_departures, geofence_radius_m, itinerary_buffer_m,
                     compliance_threshold_pct, incomplete_threshold_pct,
                     tolerance_early_min, tolerance_late_min, agency_vmt_id,
                     operating_window_start, operating_window_end, spans_next_day,
                     active, create_uid, write_uid, create_date, write_date)
                VALUES
                    (%s, %s, %s, %s, %s,
                     %s, %s, %s,
                     %s, %s,
                     %s, %s, '004B',
                     '04:00:00', '03:30:59', TRUE,
                     TRUE, 1, 1, NOW(), NOW())
                RETURNING id;
            """, (s['name'], s['code'], s['description'], concessionaire_id, s['cid_id'],
                  s['daily_target'], s['geofence_r'], s['buffer'], s['comp_pct'], s['incomp_pct'],
                  s['tol_early'], s['tol_late']))
            s_id = cur.fetchone()['id']
            print(f"[+] transit_service creado: {s['code']} -> ID {s_id}")
        service_map[s['code']] = s_id

        # Vincular rutas
        for r_code in s['routes']:
            cur.execute("""
                UPDATE transit_route
                SET service_id = %s, concessionaire_id = %s
                WHERE code = %s;
            """, (s_id, concessionaire_id, r_code))
            print(f"  [+] Ruta {r_code} vinculada a servicio {s['code']} (ID {s_id})")

    # 2. Actualizar transit_timetable con service_id, tipo_dia corregido y service_number
    print("\n[*] Actualizando transit_timetable con service_id y tipo_dia...")
    cur.execute("""
        UPDATE transit_timetable tt
        SET service_id = r.service_id,
            concessionaire_id = r.concessionaire_id
        FROM transit_route r
        WHERE tt.route_id = r.id AND r.service_id IS NOT NULL;
    """)
    print(f"  [+] {cur.rowcount} registros actualizados con service_id en transit_timetable.")

    # Corregir tipo_dia en transit_timetable desde servicios_especiales.programacion_operativa
    cur.execute("""
        UPDATE transit_timetable tt
        SET tipo_dia = p.tipo_dia::text,
            service_number = p.numero_servicio
        FROM servicios_especiales.programacion_operativa p
        WHERE tt.cid_programacion_id = p.id_programacion;
    """)
    print(f"  [+] {cur.rowcount} registros corregidos con tipo_dia y numero_servicio en transit_timetable.")

    conn.commit()

    # Verificación
    print("\n=== RESUMEN VERIFICACIÓN ===")
    cur.execute("""
        SELECT s.code as servicio, s.name, count(tt.id) as salidas,
               count(CASE WHEN tt.tipo_dia = '5' THEN 1 END) as laboral,
               count(CASE WHEN tt.tipo_dia = '6' THEN 1 END) as sabado,
               count(CASE WHEN tt.tipo_dia = '7' THEN 1 END) as dom_fer
        FROM transit_service s
        JOIN transit_timetable tt ON tt.service_id = s.id
        GROUP BY s.code, s.name
        ORDER BY s.code;
    """)
    for row in cur.fetchall():
        print(f"[{row['servicio']}] {row['name']}: {row['salidas']} salidas (L-V: {row['laboral']}, Sab: {row['sabado']}, Dom/Fer: {row['dom_fer']})")

    conn.close()
    print("\n[OK] Completado exitosamente.")

if __name__ == '__main__':
    main()
