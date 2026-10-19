#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincronizador de Programación Operativa y Schema servicios_especiales desde CID hacia Odoo (flota_db)
Extrae:
 1. servicios_especiales.servicio_especial
 2. servicios_especiales.ruta_servicio_especial
 3. servicios_especiales.adjudicacion_servicio
 4. servicios_especiales.bus_adjudicacion
 5. servicios_especiales.parametro_monitoreo
 6. servicios_especiales.programacion_operativa (908 registros de cuadro de marcha)
 7. control_metricas.tipo_dia
Y mapea la programación operativa directamente al modelo de Cuadro de Marchas de Odoo (transit_timetable).
"""

import os
import sys
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from dotenv import load_dotenv

load_dotenv()

# Conexión Origen: CID VMT
CID_HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
CID_PORT = int(os.getenv("CID_DB_PORT", "2024"))
CID_NAME = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
CID_USER = os.getenv("CID_DB_USER", "cid_admin_user")
CID_PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

# Conexión Destino: Local flota_db
if os.getenv("RUNNING_IN_DOCKER"):
    PG_HOST = os.getenv("PG_HOST", "db")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
elif sys.platform == 'win32':
    PG_HOST = os.getenv("LOCAL_PG_HOST", "localhost")
    PG_PORT = int(os.getenv("LOCAL_PG_PORT", 5437))
else:
    PG_HOST = os.getenv("PG_HOST", "localhost")
    PG_PORT = int(os.getenv("PG_PORT", 5432))

PG_NAME = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def sync():
    print("=" * 70)
    print("SINCRONIZACIÓN DE PROGRAMACIÓN OPERATIVA (CID -> FLOTA_DB)")
    print("=" * 70)

    print(f"[*] Conectando a CID ({CID_HOST}:{CID_PORT}/{CID_NAME})...")
    cid_conn = psycopg2.connect(
        host=CID_HOST, port=CID_PORT, dbname=CID_NAME, user=CID_USER, password=CID_PASS, connect_timeout=15
    )
    cid_conn.set_client_encoding('UTF8')
    cid_cur = cid_conn.cursor(cursor_factory=RealDictCursor)

    print(f"[*] Conectando a Base Local ({PG_HOST}:{PG_PORT}/{PG_NAME})...")
    local_conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASS, connect_timeout=10
    )
    local_conn.set_client_encoding('UTF8')
    local_cur = local_conn.cursor(cursor_factory=RealDictCursor)

    # -------------------------------------------------------------
    # PASO 1: Creación de Esquemas y Tablas en flota_db
    # -------------------------------------------------------------
    print("\n[+] Paso 1: Verificando esquemas y tablas en flota_db...")
    local_cur.execute("""
        CREATE SCHEMA IF NOT EXISTS servicios_especiales;
        CREATE SCHEMA IF NOT EXISTS control_metricas;

        -- Tabla tipo_dia
        CREATE TABLE IF NOT EXISTS control_metricas.tipo_dia (
            id_tipo_dia INTEGER PRIMARY KEY,
            codigo VARCHAR(50),
            descripcion VARCHAR(255),
            activo BOOLEAN DEFAULT TRUE
        );

        -- Tabla servicio_especial
        CREATE TABLE IF NOT EXISTS servicios_especiales.servicio_especial (
            id_servicio_especial INTEGER PRIMARY KEY,
            codigo VARCHAR(50) NOT NULL,
            nombre VARCHAR(255) NOT NULL,
            descripcion TEXT,
            activo BOOLEAN DEFAULT TRUE,
            fecha_creacion TIMESTAMP,
            fecha_actualizacion TIMESTAMP
        );

        -- Tabla ruta_servicio_especial
        CREATE TABLE IF NOT EXISTS servicios_especiales.ruta_servicio_especial (
            id_ruta_servicio INTEGER PRIMARY KEY,
            id_servicio_especial INTEGER NOT NULL,
            ruta_hex VARCHAR(50) NOT NULL,
            sentido VARCHAR(50) NOT NULL,
            vigente_desde DATE,
            vigente_hasta DATE
        );

        -- Tabla adjudicacion_servicio
        CREATE TABLE IF NOT EXISTS servicios_especiales.adjudicacion_servicio (
            id_adjudicacion INTEGER PRIMARY KEY,
            id_servicio_especial INTEGER NOT NULL,
            id_eot INTEGER NOT NULL,
            fecha_inicio_servicio DATE NOT NULL,
            fecha_fin_servicio DATE,
            observacion TEXT,
            fecha_creacion TIMESTAMP,
            link_dashboard TEXT
        );

        -- Tabla bus_adjudicacion
        CREATE TABLE IF NOT EXISTS servicios_especiales.bus_adjudicacion (
            id_bus_adjudicacion INTEGER PRIMARY KEY,
            id_adjudicacion INTEGER NOT NULL,
            numero_orden INTEGER NOT NULL,
            idsam VARCHAR(50) NOT NULL,
            mean_id VARCHAR(50)
        );

        -- Tabla parametro_monitoreo
        CREATE TABLE IF NOT EXISTS servicios_especiales.parametro_monitoreo (
            id_parametro INTEGER PRIMARY KEY,
            id_servicio_especial INTEGER NOT NULL,
            radio_geocerca_m INTEGER NOT NULL,
            radio_itinerario_m INTEGER NOT NULL,
            rango_cumplimiento_pct INTEGER NOT NULL,
            franja_hora_inicio VARCHAR(50) NOT NULL,
            franja_hora_fin VARCHAR(50) NOT NULL,
            tolerancia_antes_min INTEGER NOT NULL,
            tolerancia_despues_min INTEGER NOT NULL,
            emisor_id INTEGER,
            agency_ids TEXT,
            activo BOOLEAN DEFAULT TRUE,
            fecha_creacion TIMESTAMP,
            fecha_actualizacion TIMESTAMP,
            pasa_al_dia_siguiente BOOLEAN DEFAULT FALSE
        );

        -- Tabla programacion_operativa
        CREATE TABLE IF NOT EXISTS servicios_especiales.programacion_operativa (
            id_programacion INTEGER PRIMARY KEY,
            id_servicio_especial INTEGER NOT NULL,
            fecha_inicio_vigencia DATE NOT NULL,
            fecha_fin_vigencia DATE,
            numero_servicio INTEGER NOT NULL,
            sentido VARCHAR(50) NOT NULL,
            horario_salida TIME NOT NULL,
            horario_llegada TIME,
            tipo_dia INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_prog_op_servicio ON servicios_especiales.programacion_operativa(id_servicio_especial);
        CREATE INDEX IF NOT EXISTS idx_prog_op_tipo_dia ON servicios_especiales.programacion_operativa(tipo_dia);
        CREATE INDEX IF NOT EXISTS idx_prog_op_sentido ON servicios_especiales.programacion_operativa(sentido);
        CREATE INDEX IF NOT EXISTS idx_prog_op_horario ON servicios_especiales.programacion_operativa(horario_salida);

        -- Columnas adicionales en transit_timetable para Odoo
        ALTER TABLE transit_timetable ADD COLUMN IF NOT EXISTS cid_programacion_id INTEGER;
        ALTER TABLE transit_timetable ADD COLUMN IF NOT EXISTS direction VARCHAR;
        ALTER TABLE transit_timetable ADD COLUMN IF NOT EXISTS valid_from DATE;
        ALTER TABLE transit_timetable ADD COLUMN IF NOT EXISTS valid_until DATE;
        ALTER TABLE transit_timetable ADD COLUMN IF NOT EXISTS arrival_time_float DOUBLE PRECISION;
        CREATE INDEX IF NOT EXISTS idx_transit_timetable_cid_id ON transit_timetable(cid_programacion_id);
    """)
    local_conn.commit()
    print("  [OK] Esquemas y tablas base asegurados.")

    # -------------------------------------------------------------
    # PASO 2: Sincronizar Tablas del schema servicios_especiales (SOLO ELÉCTRICOS)
    # -------------------------------------------------------------
    print("\n[+] Paso 2: Importando datos de servicios_especiales (Eléctricos 1, 2, 3) desde CID...")
    ELECTRIC_SERVICE_IDS = [3, 8, 10]

    # 2.1 tipo_dia
    cid_cur.execute("SELECT * FROM control_metricas.tipo_dia;")
    tipo_dias = cid_cur.fetchall()
    for td in tipo_dias:
        local_cur.execute("""
            INSERT INTO control_metricas.tipo_dia (id_tipo_dia, codigo, descripcion, activo)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id_tipo_dia) DO UPDATE SET
                codigo = EXCLUDED.codigo,
                descripcion = EXCLUDED.descripcion,
                activo = EXCLUDED.activo;
        """, (td['id_tipo_dia'], td['codigo'], td['descripcion'], td['activo']))
    print(f"  [OK] control_metricas.tipo_dia: {len(tipo_dias)} registros sincronizados.")

    # 2.2 servicio_especial (Solo Eléctricos)
    cid_cur.execute("SELECT * FROM servicios_especiales.servicio_especial WHERE id_servicio_especial = ANY(%s);", (ELECTRIC_SERVICE_IDS,))
    servicios = cid_cur.fetchall()
    for s in servicios:
        local_cur.execute("""
            INSERT INTO servicios_especiales.servicio_especial 
                (id_servicio_especial, codigo, nombre, descripcion, activo, fecha_creacion, fecha_actualizacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_servicio_especial) DO UPDATE SET
                codigo = EXCLUDED.codigo,
                nombre = EXCLUDED.nombre,
                descripcion = EXCLUDED.descripcion,
                activo = EXCLUDED.activo,
                fecha_creacion = EXCLUDED.fecha_creacion,
                fecha_actualizacion = EXCLUDED.fecha_actualizacion;
        """, (s['id_servicio_especial'], s['codigo'], s['nombre'], s['descripcion'], s['activo'], s['fecha_creacion'], s['fecha_actualizacion']))
    print(f"  [OK] servicios_especiales.servicio_especial (Eléctricos): {len(servicios)} registros sincronizados.")

    # 2.3 ruta_servicio_especial (Solo Eléctricos)
    cid_cur.execute("SELECT * FROM servicios_especiales.ruta_servicio_especial WHERE id_servicio_especial = ANY(%s);", (ELECTRIC_SERVICE_IDS,))
    rutas_se = cid_cur.fetchall()
    for r in rutas_se:
        local_cur.execute("""
            INSERT INTO servicios_especiales.ruta_servicio_especial
                (id_ruta_servicio, id_servicio_especial, ruta_hex, sentido, vigente_desde, vigente_hasta)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_ruta_servicio) DO UPDATE SET
                id_servicio_especial = EXCLUDED.id_servicio_especial,
                ruta_hex = EXCLUDED.ruta_hex,
                sentido = EXCLUDED.sentido,
                vigente_desde = EXCLUDED.vigente_desde,
                vigente_hasta = EXCLUDED.vigente_hasta;
        """, (r['id_ruta_servicio'], r['id_servicio_especial'], r['ruta_hex'], r['sentido'], r['vigente_desde'], r['vigente_hasta']))
    print(f"  [OK] servicios_especiales.ruta_servicio_especial (Eléctricos): {len(rutas_se)} registros sincronizados.")

    # 2.4 adjudicacion_servicio (Solo Eléctricos)
    cid_cur.execute("SELECT * FROM servicios_especiales.adjudicacion_servicio WHERE id_servicio_especial = ANY(%s);", (ELECTRIC_SERVICE_IDS,))
    adjudicaciones = cid_cur.fetchall()
    adj_ids = [a['id_adjudicacion'] for a in adjudicaciones]
    for a in adjudicaciones:
        local_cur.execute("""
            INSERT INTO servicios_especiales.adjudicacion_servicio
                (id_adjudicacion, id_servicio_especial, id_eot, fecha_inicio_servicio, fecha_fin_servicio, observacion, fecha_creacion, link_dashboard)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_adjudicacion) DO UPDATE SET
                id_servicio_especial = EXCLUDED.id_servicio_especial,
                id_eot = EXCLUDED.id_eot,
                fecha_inicio_servicio = EXCLUDED.fecha_inicio_servicio,
                fecha_fin_servicio = EXCLUDED.fecha_fin_servicio,
                observacion = EXCLUDED.observacion,
                fecha_creacion = EXCLUDED.fecha_creacion,
                link_dashboard = EXCLUDED.link_dashboard;
        """, (a['id_adjudicacion'], a['id_servicio_especial'], a['id_eot'], a['fecha_inicio_servicio'], a['fecha_fin_servicio'], a['observacion'], a['fecha_creacion'], a['link_dashboard']))
    print(f"  [OK] servicios_especiales.adjudicacion_servicio: {len(adjudicaciones)} registros sincronizados.")

    # 2.5 bus_adjudicacion (Solo Eléctricos)
    if adj_ids:
        cid_cur.execute("SELECT * FROM servicios_especiales.bus_adjudicacion WHERE id_adjudicacion = ANY(%s);", (adj_ids,))
        buses_adj = cid_cur.fetchall()
        for b in buses_adj:
            local_cur.execute("""
                INSERT INTO servicios_especiales.bus_adjudicacion
                    (id_bus_adjudicacion, id_adjudicacion, numero_orden, idsam, mean_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id_bus_adjudicacion) DO UPDATE SET
                    id_adjudicacion = EXCLUDED.id_adjudicacion,
                    numero_orden = EXCLUDED.numero_orden,
                    idsam = EXCLUDED.idsam,
                    mean_id = EXCLUDED.mean_id;
            """, (b['id_bus_adjudicacion'], b['id_adjudicacion'], b['numero_orden'], b['idsam'], b['mean_id']))
        print(f"  [OK] servicios_especiales.bus_adjudicacion (Eléctricos): {len(buses_adj)} registros sincronizados.")

    # 2.6 parametro_monitoreo (Solo Eléctricos)
    cid_cur.execute("SELECT * FROM servicios_especiales.parametro_monitoreo WHERE id_servicio_especial = ANY(%s);", (ELECTRIC_SERVICE_IDS,))
    params = cid_cur.fetchall()
    for p in params:
        local_cur.execute("""
            INSERT INTO servicios_especiales.parametro_monitoreo
                (id_parametro, id_servicio_especial, radio_geocerca_m, radio_itinerario_m, rango_cumplimiento_pct, 
                 franja_hora_inicio, franja_hora_fin, tolerancia_antes_min, tolerancia_despues_min, 
                 emisor_id, agency_ids, activo, fecha_creacion, fecha_actualizacion, pasa_al_dia_siguiente)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_parametro) DO UPDATE SET
                id_servicio_especial = EXCLUDED.id_servicio_especial,
                radio_geocerca_m = EXCLUDED.radio_geocerca_m,
                radio_itinerario_m = EXCLUDED.radio_itinerario_m,
                rango_cumplimiento_pct = EXCLUDED.rango_cumplimiento_pct,
                franja_hora_inicio = EXCLUDED.franja_hora_inicio,
                franja_hora_fin = EXCLUDED.franja_hora_fin,
                tolerancia_antes_min = EXCLUDED.tolerancia_antes_min,
                tolerancia_despues_min = EXCLUDED.tolerancia_despues_min,
                emisor_id = EXCLUDED.emisor_id,
                agency_ids = EXCLUDED.agency_ids,
                activo = EXCLUDED.activo,
                fecha_creacion = EXCLUDED.fecha_creacion,
                fecha_actualizacion = EXCLUDED.fecha_actualizacion,
                pasa_al_dia_siguiente = EXCLUDED.pasa_al_dia_siguiente;
        """, (p['id_parametro'], p['id_servicio_especial'], p['radio_geocerca_m'], p['radio_itinerario_m'], p['rango_cumplimiento_pct'],
              p['franja_hora_inicio'], p['franja_hora_fin'], p['tolerancia_antes_min'], p['tolerancia_despues_min'],
              p['emisor_id'], p['agency_ids'], p['activo'], p['fecha_creacion'], p['fecha_actualizacion'], p['pasa_al_dia_siguiente']))
    print(f"  [OK] servicios_especiales.parametro_monitoreo (Eléctricos): {len(params)} registros sincronizados.")

    # 2.7 programacion_operativa (Solo Eléctricos: 692 registros)
    cid_cur.execute("""
        SELECT * FROM servicios_especiales.programacion_operativa 
        WHERE id_servicio_especial = ANY(%s) 
        ORDER BY id_programacion;
    """, (ELECTRIC_SERVICE_IDS,))
    progs = cid_cur.fetchall()
    for pr in progs:
        local_cur.execute("""
            INSERT INTO servicios_especiales.programacion_operativa
                (id_programacion, id_servicio_especial, fecha_inicio_vigencia, fecha_fin_vigencia, 
                 numero_servicio, sentido, horario_salida, horario_llegada, tipo_dia)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_programacion) DO UPDATE SET
                id_servicio_especial = EXCLUDED.id_servicio_especial,
                fecha_inicio_vigencia = EXCLUDED.fecha_inicio_vigencia,
                fecha_fin_vigencia = EXCLUDED.fecha_fin_vigencia,
                numero_servicio = EXCLUDED.numero_servicio,
                sentido = EXCLUDED.sentido,
                horario_salida = EXCLUDED.horario_salida,
                horario_llegada = EXCLUDED.horario_llegada,
                tipo_dia = EXCLUDED.tipo_dia;
        """, (pr['id_programacion'], pr['id_servicio_especial'], pr['fecha_inicio_vigencia'], pr['fecha_fin_vigencia'],
              pr['numero_servicio'], pr['sentido'], pr['horario_salida'], pr['horario_llegada'], pr['tipo_dia']))
    local_conn.commit()
    print(f"  [OK] servicios_especiales.programacion_operativa (Eléctricos): {len(progs)} registros sincronizados en flota_db.")

    # -------------------------------------------------------------
    # PASO 3: Asegurar Servicios (transit_service) y Rutas en Odoo (transit_route)
    # -------------------------------------------------------------
    print("\n[+] Paso 3: Asegurando transit_service y catálogo de ramales en transit_route...")
    
    # 3.1 Concesionaria Titular (Consorcio Arapotí)
    local_cur.execute("SELECT id FROM transit_concessionaire WHERE name ILIKE '%Arapot%' OR id = 4 LIMIT 1;")
    conc_row = local_cur.fetchone()
    if not conc_row:
        local_cur.execute("SELECT id FROM transit_concessionaire ORDER BY id ASC LIMIT 1;")
        conc_row = local_cur.fetchone()
    concessionaire_id = conc_row['id'] if conc_row else 4
    print(f"  [+] Concesionaria Titular para Eléctricos: ID {concessionaire_id}")

    # 3.2 Asegurar transit_service para E1, E2, E3
    SERVICES_METADATA = [
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

    service_code_to_id = {}
    route_to_service_id = {}
    for s in SERVICES_METADATA:
        local_cur.execute("SELECT id FROM transit_service WHERE code = %s;", (s['code'],))
        s_row = local_cur.fetchone()
        if s_row:
            s_id = s_row['id']
            local_cur.execute("""
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
            local_cur.execute("""
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
            s_id = local_cur.fetchone()['id']
        service_code_to_id[s['code']] = s_id
        for r_code in s['routes']:
            route_to_service_id[r_code] = s_id

    # 3.3 Catálogo de los 6 Ramales Eléctricos
    ELECTRIC_ROUTES_CATALOG = {
        '020c': {'name': 'Ramal 020C - Eléctrico 1 (San Lorenzo a Asunción)', 'direction': 'inbound', 'origin': 'San Lorenzo', 'destination': 'Asunción Centro', 'km': 19.46},
        '020d': {'name': 'Ramal 020D - Eléctrico 1 (Asunción a San Lorenzo)', 'direction': 'outbound', 'origin': 'Asunción Centro', 'destination': 'San Lorenzo', 'km': 19.78},
        '020e': {'name': 'Ramal 020E - Eléctrico 2 (San Lorenzo a Asunción Variante)', 'direction': 'inbound', 'origin': 'San Lorenzo', 'destination': 'Asunción Centro', 'km': 19.53},
        '020f': {'name': 'Ramal 020F - Eléctrico 2 (Asunción a San Lorenzo Variante)', 'direction': 'outbound', 'origin': 'Asunción Centro', 'destination': 'San Lorenzo', 'km': 19.82},
        '0210': {'name': 'Ramal 0210 - Eléctrico 3 (Luque a Asunción)', 'direction': 'inbound', 'origin': 'Luque (Aeropuerto)', 'destination': 'Asunción Centro', 'km': 18.33},
        '0211': {'name': 'Ramal 0211 - Eléctrico 3 (Asunción a Luque)', 'direction': 'outbound', 'origin': 'Asunción Centro', 'destination': 'Luque (Aeropuerto)', 'km': 18.84},
    }

    route_code_to_id = {}
    for code, info in ELECTRIC_ROUTES_CATALOG.items():
        s_id = route_to_service_id.get(code)
        local_cur.execute("SELECT id FROM transit_route WHERE code = %s;", (code,))
        row = local_cur.fetchone()
        if row:
            route_code_to_id[code] = row['id']
            local_cur.execute("""
                UPDATE transit_route 
                SET name = %s, direction = %s, origin = %s, destination = %s, distance_km = %s,
                    service_id = %s, concessionaire_id = %s
                WHERE id = %s;
            """, (info['name'], info['direction'], info['origin'], info['destination'], info['km'],
                  s_id, concessionaire_id, row['id']))
        else:
            local_cur.execute("""
                INSERT INTO transit_route (code, name, agency_id, direction, origin, destination, distance_km, service_id, concessionaire_id, active)
                VALUES (%s, %s, '004B', %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id;
            """, (code, info['name'], info['direction'], info['origin'], info['destination'], info['km'], s_id, concessionaire_id))
            route_code_to_id[code] = local_cur.fetchone()['id']
            print(f"  [+] Ruta creada en transit_route: {code} -> ID {route_code_to_id[code]}")

    local_conn.commit()
    print("  [OK] transit_service y transit_route perfectamente vinculados.")

    # -------------------------------------------------------------
    # PASO 4: Cargar Horarios Planificados en Odoo (transit_timetable)
    # -------------------------------------------------------------
    print("\n[+] Paso 4: Mapeando e insertando programación operativa de Eléctricos en transit_timetable...")

    # Mapeo de (id_servicio_especial, sentido) -> ruta_hex
    service_direction_to_route = {}
    for r in rutas_se:
        key = (r['id_servicio_especial'], r['sentido'].lower().strip())
        service_direction_to_route[key] = r['ruta_hex'].lower().strip()

    # Mapeo de tipo_dia CID -> day_of_week Odoo
    # 5 -> 'weekday' (Lunes a Viernes)
    # 6 -> '5' (Sábado)
    # 7 -> '6' (Domingo)
    DAY_OF_WEEK_MAP = {
        5: 'weekday',
        6: '5',
        7: '6'
    }

    timetable_inserted = 0
    timetable_updated = 0

    for pr in progs:
        id_prog = pr['id_programacion']
        id_serv = pr['id_servicio_especial']
        sentido = pr['sentido'].lower().strip()
        num_serv = pr['numero_servicio']
        salida = pr['horario_salida']
        llegada = pr['horario_llegada']
        tipo_dia = pr['tipo_dia']
        f_inicio = pr['fecha_inicio_vigencia']
        f_fin = pr['fecha_fin_vigencia']

        # Encontrar ruta_hex
        ruta_hex = service_direction_to_route.get((id_serv, sentido))
        if not ruta_hex or ruta_hex not in route_code_to_id:
            print(f"  [!] Aviso: No se encontró ruta para servicio {id_serv} ({sentido}), id_programacion {id_prog}")
            continue

        route_id = route_code_to_id[ruta_hex]
        parent_service_id = route_to_service_id.get(ruta_hex)

        # Hora salida decimal
        dep_float = salida.hour + (salida.minute / 60.0) + (salida.second / 3600.0)

        # Hora llegada decimal y duración
        arr_float = None
        duration_minutes = 70 # Default

        if llegada:
            arr_float = llegada.hour + (llegada.minute / 60.0) + (llegada.second / 3600.0)
            # Calcular duración
            dep_min = salida.hour * 60 + salida.minute
            arr_min = llegada.hour * 60 + llegada.minute
            if arr_min >= dep_min:
                duration_minutes = arr_min - dep_min
            else:
                # Cruza la medianoche
                duration_minutes = (1440 - dep_min) + arr_min

        day_code = DAY_OF_WEEK_MAP.get(tipo_dia, 'all')
        service_code = f"S{num_serv:02d}"

        # Verificar si ya existe en transit_timetable por cid_programacion_id
        local_cur.execute("SELECT id FROM transit_timetable WHERE cid_programacion_id = %s;", (id_prog,))
        exist = local_cur.fetchone()

        if exist:
            local_cur.execute("""
                UPDATE transit_timetable
                SET route_id = %s,
                    service_id = %s,
                    concessionaire_id = %s,
                    service_code = %s,
                    service_number = %s,
                    departure_time_float = %s,
                    arrival_time_float = %s,
                    scheduled_duration_minutes = %s,
                    tipo_dia = %s,
                    day_of_week = %s,
                    direction = %s,
                    valid_from = %s,
                    valid_until = %s,
                    active = TRUE,
                    write_date = NOW()
                WHERE id = %s;
            """, (route_id, parent_service_id, concessionaire_id, service_code, num_serv, dep_float, arr_float, duration_minutes, str(tipo_dia), day_code, sentido, f_inicio, f_fin, exist['id']))
            timetable_updated += 1
        else:
            local_cur.execute("""
                INSERT INTO transit_timetable
                    (route_id, service_id, concessionaire_id, service_code, service_number,
                     departure_time_float, arrival_time_float, scheduled_duration_minutes,
                     tipo_dia, day_of_week, direction, valid_from, valid_until, cid_programacion_id, active,
                     create_uid, write_uid, create_date, write_date)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, 1, 1, NOW(), NOW());
            """, (route_id, parent_service_id, concessionaire_id, service_code, num_serv, dep_float, arr_float, duration_minutes, str(tipo_dia), day_code, sentido, f_inicio, f_fin, id_prog))
            timetable_inserted += 1

    local_conn.commit()
    print(f"  [OK] transit_timetable completado: {timetable_inserted} insertados, {timetable_updated} actualizados.")

    # -------------------------------------------------------------
    # RESUMEN FINAL
    # -------------------------------------------------------------
    local_cur.execute("SELECT count(*) as total FROM servicios_especiales.programacion_operativa;")
    total_raw = local_cur.fetchone()['total']

    local_cur.execute("SELECT count(*) as total FROM transit_timetable WHERE cid_programacion_id IS NOT NULL;")
    total_timetable = local_cur.fetchone()['total']

    print("\n" + "=" * 70)
    print("RESUMEN DE SINCRONIZACIÓN")
    print("=" * 70)
    print(f"  Total registros en servicios_especiales.programacion_operativa: {total_raw}")
    print(f"  Total horarios en transit_timetable (Odoo):                   {total_timetable}")
    print("=" * 70)

    cid_conn.close()
    local_conn.close()

if __name__ == "__main__":
    sync()
