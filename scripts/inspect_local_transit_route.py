# -*- coding: utf-8 -*-
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

cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns 
    WHERE table_name = 'transit_route' 
    ORDER BY ordinal_position;
""")
print("=== COLUMNAS transit_route ===")
for r in cur.fetchall():
    print(f" - {r['column_name']} ({r['data_type']}) default: {r['column_default']}")

cur.execute("""
    SELECT id, code, name, active, direction, origin, destination, distance_km, service_id, concessionaire_id
    FROM transit_route;
""")
print("\n=== FILAS EN transit_route ===")
for r in cur.fetchall():
    print(dict(r))

conn.close()
