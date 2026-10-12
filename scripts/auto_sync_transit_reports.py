#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincronizador Autónomo y Demonio de Planillas Dinámicas de Tránsito (Excel)
===========================================================================
Detecta de forma automática los servicios concluidos (por Odoo o Telemetría)
e inyecta los datos en tiempo real en los libros oficiales de Excel:
  - Informe_empresa/E1 PLANILLA PRINCIPAL TRANSITO E1 OCTUBRE 2026.xlsx
  - Informe_empresa/E2 PLANILLA PRINCIPAL TRANSITO E2 OCTUBRE 2026.xlsx
  - Informe_empresa/E3 PLANILLA PRINCIPAL TRANSITO E3 OCTUBRE 2026.xlsx

Uso:
  python scripts/auto_sync_transit_reports.py --status
  python scripts/auto_sync_transit_reports.py --once
  python scripts/auto_sync_transit_reports.py --service E1 --date 2026-10-11
  python scripts/auto_sync_transit_reports.py --daemon --interval 30
  python scripts/auto_sync_transit_reports.py --simulate-finish
"""

import os
import sys
import time
import argparse
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# Asegurar codificación UTF-8 en Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Importar el motor central
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_PATH = os.path.join(BASE_DIR, 'custom_addons', 'transit_operations', 'models')
if ADDON_PATH not in sys.path:
    sys.path.insert(0, ADDON_PATH)

from transit_dynamic_report_service import (
    TransitDynamicReportEngine,
    SERVICE_CONFIG,
    find_spreadsheet_path,
    get_informe_directory,
)

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5435))
PG_DB   = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")


def get_db_connection():
    try:
        return psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=5
        )
    except Exception as e:
        print(f"[-] Aviso de conexión a PostgreSQL ({PG_HOST}:{PG_PORT}): {e}")
        return None


def fetch_completed_services_from_db(service_code: str, target_date: datetime.date):
    """
    Consulta en la base de datos local los despachos/servicios completados en la fecha dada.
    """
    conn = get_db_connection()
    if not conn:
        return []

    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT 
            d.id,
            d.name,
            d.date,
            d.state,
            d.actual_departure,
            d.actual_arrival,
            d.scheduled_departure,
            d.scheduled_arrival,
            d.battery_soc_departure,
            d.battery_soc_arrival,
            d.total_passengers,
            d.electronic_validations,
            v.bus_internal_number,
            p.name as driver_name,
            p.driver_code,
            s.code as service_code,
            r.code as route_code,
            r.direction
        FROM transit_dispatch d
        JOIN fleet_vehicle v ON v.id = d.vehicle_id
        LEFT JOIN res_partner p ON p.id = d.driver_id
        JOIN transit_route r ON r.id = d.route_id
        JOIN transit_service s ON s.id = d.service_id OR s.id = r.service_id
        WHERE d.date = %s
          AND s.code = %s
          AND d.state IN ('completed', 'in_transit', 'dispatched')
        ORDER BY d.scheduled_departure ASC, d.id ASC;
    """
    cur.execute(query, (target_date, service_code))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Agrupar por bus para formar redondos (Ida + Vuelta)
    by_bus = {}
    for r in rows:
        b_num = r['bus_internal_number'] or '0'
        by_bus.setdefault(b_num, []).append(r)

    round_trips = []
    for b_num, d_list in by_bus.items():
        i = 0
        while i < len(d_list):
            d1 = d_list[i]
            d2 = d_list[i + 1] if (i + 1) < len(d_list) else None

            driver_c = d1['driver_code'] or (d1['driver_name'][-3:] if d1['driver_name'] and d1['driver_name'][-3:].isdigit() else '001')
            d_name = d1['driver_name'] or 'Chofer Oficial'

            ida_dep = (d1['actual_departure'] or d1['scheduled_departure']).time() if (d1['actual_departure'] or d1['scheduled_departure']) else None
            ida_arr = d1['actual_arrival'].time() if d1['actual_arrival'] else None
            ida_cards = float(d1['electronic_validations'] or d1['total_passengers'] or 0.0)

            reg_dep = None
            reg_arr = None
            reg_cards = 0.0

            if d2:
                reg_dep = (d2['actual_departure'] or d2['scheduled_departure']).time() if (d2['actual_departure'] or d2['scheduled_departure']) else None
                reg_arr = d2['actual_arrival'].time() if d2['actual_arrival'] else None
                reg_cards = float(d2['electronic_validations'] or d2['total_passengers'] or 0.0)
                i += 2
            else:
                i += 1

            bat_s = float(d1['battery_soc_departure'] or 90.0)
            bat_l = float((d2['battery_soc_arrival'] if d2 else d1['battery_soc_arrival']) or 65.0)

            round_trips.append({
                'bus_number': int(b_num) if b_num.isdigit() else b_num,
                'driver_code': driver_c,
                'driver_name': d_name,
                'ida_departure': ida_dep,
                'ida_arrival': ida_arr,
                'ida_cards': ida_cards,
                'reg_departure': reg_dep,
                'reg_arrival': reg_arr,
                'reg_cards': reg_cards,
                'battery_soc_departure': bat_s,
                'battery_soc_arrival': bat_l,
                'date': target_date,
            })

    return round_trips


def print_status(target_date: datetime.date):
    """Muestra el estado actual de las planillas de tránsito en vivo"""
    print("=" * 80)
    print(f"ESTADO DE PLANILLAS DINÁMICAS DE TRÁNSITO - FECHA: {target_date} (DÍA {target_date.day})")
    print("=" * 80)

    for code in ['E1', 'E2', 'E3']:
        engine = TransitDynamicReportEngine(code, target_date)
        status = engine.get_day_sheet_status(target_date)
        print(f"\n[LÍNEA {code}] {SERVICE_CONFIG[code]['name']}")
        print(f"  Archivo: {status.get('file_path')}")
        print(f"  Estado Hoja '{target_date.day}': {'Encontrada' if status.get('exists') else 'No existe'}")
        print(f"  Redondos Concluidos: {status.get('completed_trips', 0)} / {status.get('scheduled_trips', 0)}")
        print(f"  Total Pasajeros:     {status.get('total_passengers', 0)}")
        print(f"  Kilometraje Total:   {status.get('total_km', 0.0)} km")
        print(f"  IPK Calculado:       {status.get('ipk', 0.0)}")


def sync_service(service_code: str, target_date: datetime.date):
    """Ejecuta la sincronización para un servicio específico"""
    code = service_code.upper()
    print(f"[*] Sincronizando Línea {code} para la fecha {target_date}...")

    # 1. Obtener redondos desde base de datos
    round_trips = fetch_completed_services_from_db(code, target_date)
    engine = TransitDynamicReportEngine(code, target_date)

    if round_trips:
        cnt, saved_path = engine.sync_concluded_round_trips(round_trips, target_date)
        print(f"[✓] {cnt} servicios sincronizados desde la BD en {saved_path}")
    else:
        # Si no hay nuevos registros en la BD pero el archivo existe, validar estado
        status = engine.get_day_sheet_status(target_date)
        print(f"[i] No hay nuevos despachos en BD para {code}. Estado actual en Excel: {status.get('completed_trips')} redondos concluidos.")


def simulate_service_conclusions(target_date: datetime.date):
    """
    Simulación de Demostración:
    Concluye en vivo los servicios que se encuentran actualmente pendientes en la hoja 11
    (por ejemplo, las salidas de las 18:40 y 19:40 de E1, E2 y E3)
    demostrando la detección automática e inserción instantánea en Excel.
    """
    print("=" * 80)
    print(f"SIMULACIÓN EN VIVO: DETECCIÓN AUTOMÁTICA DE SERVICIOS CONCLUIDOS")
    print(f"Fecha: {target_date} | Hoja: '{target_date.day}'")
    print("=" * 80)

    # 1. Para E1: completar salidas de la tarde/noche (Bus 4 y Bus 12)
    sim_e1 = [
        {
            'bus_number': 4,
            'driver_code': '034',
            'driver_name': 'Rodrigo Patiño 034',
            'ida_departure': datetime.time(18, 40),
            'ida_arrival': datetime.time(19, 28),
            'ida_cards': 8.0,
            'reg_departure': datetime.time(19, 30),
            'reg_arrival': datetime.time(20, 18),
            'reg_cards': 4.0,
            'battery_soc_departure': 92.0,
            'battery_soc_arrival': 63.0,
            'date': target_date,
        },
        {
            'bus_number': 12,
            'driver_code': '048',
            'driver_name': 'Fany Sosa 048',
            'ida_departure': datetime.time(19, 40),
            'ida_arrival': datetime.time(20, 25),
            'ida_cards': 6.0,
            'reg_departure': datetime.time(20, 30),
            'reg_arrival': datetime.time(21, 15),
            'reg_cards': 3.0,
            'battery_soc_departure': 90.0,
            'battery_soc_arrival': 62.0,
            'date': target_date,
        }
    ]

    # 2. Para E2: completar salida pendiente de la tarde (Bus 18 y Bus 11)
    sim_e2 = [
        {
            'bus_number': 18,
            'driver_code': '017',
            'driver_name': 'Ignacio Coronel 017',
            'ida_departure': datetime.time(16, 40),
            'ida_arrival': datetime.time(17, 35),
            'ida_cards': 14.0,
            'reg_departure': datetime.time(17, 36),
            'reg_arrival': datetime.time(18, 29),
            'reg_cards': 11.0,
            'battery_soc_departure': 91.0,
            'battery_soc_arrival': 58.0,
            'date': target_date,
        },
        {
            'bus_number': 11,
            'driver_code': '001',
            'driver_name': 'Idalina Peralta 001',
            'ida_departure': datetime.time(18, 40),
            'ida_arrival': datetime.time(19, 32),
            'ida_cards': 19.0,
            'reg_departure': datetime.time(19, 32),
            'reg_arrival': datetime.time(20, 25),
            'reg_cards': 15.0,
            'battery_soc_departure': 90.0,
            'battery_soc_arrival': 59.0,
            'date': target_date,
        }
    ]

    # 3. Para E3: completar salida pendiente (Bus 30 y Bus 23)
    sim_e3 = [
        {
            'bus_number': 30,
            'driver_code': '043',
            'driver_name': 'Eulalio Burgos 043',
            'ida_departure': datetime.time(18, 40),
            'ida_arrival': datetime.time(19, 30),
            'ida_cards': 6.0,
            'reg_departure': datetime.time(19, 32),
            'reg_arrival': datetime.time(20, 20),
            'reg_cards': 8.0,
            'battery_soc_departure': 86.0,
            'battery_soc_arrival': 58.0,
            'date': target_date,
        },
        {
            'bus_number': 23,
            'driver_code': '045',
            'driver_name': 'Nathalia Peralta 045',
            'ida_departure': datetime.time(19, 40),
            'ida_arrival': datetime.time(20, 28),
            'ida_cards': 7.0,
            'reg_departure': datetime.time(20, 30),
            'reg_arrival': datetime.time(21, 18),
            'reg_cards': 5.0,
            'battery_soc_departure': 85.0,
            'battery_soc_arrival': 55.0,
            'date': target_date,
        }
    ]

    for code, trips in [('E1', sim_e1), ('E2', sim_e2), ('E3', sim_e3)]:
        print(f"\n[+] Inyectando servicios concluidos en Planilla {code}...")
        engine = TransitDynamicReportEngine(code, target_date)
        cnt, saved = engine.sync_concluded_round_trips(trips, target_date)
        status = engine.get_day_sheet_status(target_date)
        print(f"  ✓ {cnt} redondos concluidos actualizados en {os.path.basename(saved)}.")
        print(f"  ✓ Nuevos totales: {status['completed_trips']} redondos completados | Pasajeros: {status['total_passengers']} | IPK: {status['ipk']}")

    print("\n" + "=" * 80)
    print("✅ SIMULACIÓN EXITOSA: TODAS LAS PLANILLAS ACTUALIZADAS EN VIVO")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Sincronizador Dinámico de Planillas de Tránsito (Excel)")
    parser.add_argument("--service", choices=['E1', 'E2', 'E3', 'all'], default='all', help="Servicio a sincronizar")
    parser.add_argument("--date", default=None, help="Fecha objetivo en formato YYYY-MM-DD (por defecto hoy)")
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola sincronización y salir")
    parser.add_argument("--status", action="store_true", help="Mostrar el estado actual de las planillas")
    parser.add_argument("--simulate-finish", action="store_true", help="Simular la culminación de servicios activos")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar como demonio en segundo plano")
    parser.add_argument("--interval", type=int, default=30, help="Intervalo en segundos para modo demonio")

    args = parser.parse_args()

    # Resolver fecha objetivo
    if args.date:
        target_date = datetime.datetime.strptime(args.date, '%Y-%m-%d').date()
    else:
        # Si hoy es posterior a octubre 2026 o en desarrollo, usar la fecha actual del sistema
        target_date = datetime.date.today()

    if args.status:
        print_status(target_date)
        return

    if args.simulate_finish:
        simulate_service_conclusions(target_date)
        return

    services = ['E1', 'E2', 'E3'] if args.service == 'all' else [args.service.upper()]

    if args.daemon:
        print(f"[*] Iniciando Demonio de Sincronización Automática de Planillas (intervalo: {args.interval}s)...")
        try:
            while True:
                today = datetime.date.today()
                for s in services:
                    sync_service(s, today)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[!] Demonio detenido por el usuario.")
    else:
        for s in services:
            sync_service(s, target_date)


if __name__ == '__main__':
    main()
