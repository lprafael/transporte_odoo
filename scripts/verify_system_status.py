import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=" * 70)
print("AUDITORÍA DE ESTADO: SISTEMA INTEGRAL DE TRANSPORTE ODOO 18")
print("=" * 70)

# 1. Base de datos
conn = psycopg2.connect(host='localhost', port=5434, dbname='flota_db', user='odoo', password='odoo_password')
cur = conn.cursor(cursor_factory=RealDictCursor)

# Module state
cur.execute("SELECT name, state FROM ir_module_module WHERE name = 'transit_operations';")
row = cur.fetchone()
print(f"1. Módulo Odoo transit_operations: {row['state'] if row else 'No encontrado'}")

# Routes
cur.execute("SELECT count(*) as c FROM transit_route;")
print(f"2. Ramales Operativos (transit_route): {cur.fetchone()['c']}")

# Timetables
cur.execute("SELECT count(*) as c FROM transit_timetable;")
print(f"3. Cuadros de Marcha / Despachos Teóricos (transit_timetable): {cur.fetchone()['c']}")

# Shapes PostGIS
cur.execute("SELECT count(*) as c FROM transit_route_shape;")
print(f"4. Trazados Georreferenciados PostGIS (transit_route_shape): {cur.fetchone()['c']}")

# Stops
cur.execute("SELECT count(*) as c FROM transit_stop;")
print(f"5. Paradas Oficiales Indexadas (transit_stop): {cur.fetchone()['c']}")

# Fleet vehicles
cur.execute("SELECT count(*) as c FROM fleet_vehicle;")
print(f"6. Total Unidades en Flota (fleet_vehicle): {cur.fetchone()['c']}")

# Master buses
cur.execute("""
    SELECT count(*) as c 
    FROM fleet_vehicle fv 
    JOIN fleet_vehicle_model_brand fvb ON fv.brand_id = fvb.id 
    WHERE fvb.name ILIKE '%master%';
""")
print(f"7. Flota Master Bus Eléctrica (100% EV): {cur.fetchone()['c']}")

conn.close()

# 2. Servicios Web
print("\n" + "=" * 70)
print("ESTADO DE SERVICIOS Y ENDPOINTS WEB")
print("=" * 70)

endpoints = [
    ("Odoo 18 Core ERP", "http://localhost:8069/web/login"),
    ("Broker GPS - Radar En Vivo (/map)", "http://localhost:8088/map"),
    ("Broker GPS - Tablero Regularidad (/headway)", "http://localhost:8088/headway"),
    ("Broker GPS - Cumplimiento GVMT 065 (/compliance)", "http://localhost:8088/compliance"),
    ("Broker GPS - API Documentación OpenAPI (/docs)", "http://localhost:8088/docs"),
    ("Broker GPS - Healthcheck (/health)", "http://localhost:8088/health"),
]

for name, url in endpoints:
    try:
        r = requests.get(url, timeout=5)
        print(f"  [OK {r.status_code}] {name} -> {url}")
    except Exception as e:
        print(f"  [FAIL] {name} -> {url} ({e})")
