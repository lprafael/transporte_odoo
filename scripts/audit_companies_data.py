# -*- coding: utf-8 -*-
"""
Auditoría exhaustiva de empresas, flota, rutas, geocercas y servicios en flota_db.
Identifica qué pertenece a Consorcio Arapotí (004B) y qué pertenece a otras empresas.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    port=5434,
    dbname='flota_db',
    user='odoo',
    password='odoo_password'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=================================================================")
print(" 1. CONCESIONARIAS / EMPRESAS (transit_concessionaire)")
print("=================================================================")
cur.execute("SELECT id, name, code, active FROM transit_concessionaire ORDER BY id;")
concessionaires = cur.fetchall()
for c in concessionaires:
    print(dict(c))

print("\n=================================================================")
print(" 2. FLOTA DE VEHÍCULOS (fleet_vehicle)")
print("=================================================================")
cur.execute("""
    SELECT v.id, v.license_plate, v.model_id, v.concessionaire_id, v.active,
           c.name as concesionaria, c.code as cod_concesionaria
    FROM fleet_vehicle v
    LEFT JOIN transit_concessionaire c ON v.concessionaire_id = c.id
    ORDER BY v.id;
""")
vehicles = cur.fetchall()
print(f"Total vehículos en fleet_vehicle: {len(vehicles)}")
by_con = {}
for v in vehicles:
    key = f"{v['concessionaire_id']} ({v['concesionaria'] or 'SIN CONCESIONARIA'})"
    by_con.setdefault(key, []).append(v['license_plate'])

for k, plates in by_con.items():
    print(f" - {k}: {len(plates)} buses (Ej: {plates[:5]})")

print("\n=================================================================")
print(" 3. RUTAS / ITINERARIOS (transit_route)")
print("=================================================================")
cur.execute("""
    SELECT r.id, r.code, r.name, r.agency_id, r.concessionaire_id, r.active,
           c.name as concesionaria
    FROM transit_route r
    LEFT JOIN transit_concessionaire c ON r.concessionaire_id = c.id
    ORDER BY r.id;
""")
routes = cur.fetchall()
for r in routes:
    print(dict(r))

print("\n=================================================================")
print(" 4. SERVICIOS OPERATIVOS (transit_service)")
print("=================================================================")
cur.execute("""
    SELECT s.id, s.name, s.code, s.concessionaire_id, s.active,
           c.name as concesionaria
    FROM transit_service s
    LEFT JOIN transit_concessionaire c ON s.concessionaire_id = c.id
    ORDER BY s.id;
""")
services = cur.fetchall()
for s in services:
    print(dict(s))

print("\n=================================================================")
print(" 5. CHECKPOINTS Y GEOCERCAS (transit_route_checkpoint)")
print("=================================================================")
cur.execute("""
    SELECT r.code, r.name, COUNT(cp.id) as cant_checkpoints
    FROM transit_route r
    LEFT JOIN transit_route_checkpoint cp ON cp.route_id = r.id
    GROUP BY r.id, r.code, r.name
    ORDER BY r.code;
""")
for r in cur.fetchall():
    print(dict(r))

print("\n=================================================================")
print(" 6. CUADRO DE HORARIOS / TIMETABLE (transit_timetable)")
print("=================================================================")
cur.execute("""
    SELECT r.code, r.name, COUNT(tt.id) as cant_horarios
    FROM transit_route r
    LEFT JOIN transit_timetable tt ON tt.route_id = r.id
    GROUP BY r.id, r.code, r.name
    ORDER BY r.code;
""")
for r in cur.fetchall():
    print(dict(r))

print("\n=================================================================")
print(" 7. TRAZADOS Y SHAPES (transit_route_shape)")
print("=================================================================")
cur.execute("""
    SELECT r.code, r.name, COUNT(sh.id) as cant_shapes
    FROM transit_route r
    LEFT JOIN transit_route_shape sh ON sh.route_id = r.id
    GROUP BY r.id, r.code, r.name
    ORDER BY r.code;
""")
for r in cur.fetchall():
    print(dict(r))

conn.close()
