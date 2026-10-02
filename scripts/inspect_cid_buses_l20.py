import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
PORT = int(os.getenv("CID_DB_PORT", "2024"))
DBNAME = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
USER = os.getenv("CID_DB_USER", "cid_admin_user")
PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

conn = psycopg2.connect(
    host=HOST, port=PORT, dbname=DBNAME, user=USER, password=PASS, connect_timeout=15
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# 1. Total buses in registro_habilitacion.buses
cur.execute("SELECT count(*) FROM registro_habilitacion.buses;")
print("Total buses in registro_habilitacion.buses:", cur.fetchone())

# 2. Total bus_empresa
cur.execute("SELECT count(*) FROM registro_habilitacion.bus_empresa;")
print("Total bus_empresa:", cur.fetchone())

# 3. Check sample buses in registro_habilitacion.buses
cur.execute("SELECT * FROM registro_habilitacion.buses LIMIT 5;")
print("\nSample buses:")
for r in cur.fetchall():
    print(json.dumps(r, default=str, indent=2))

# 4. Check distinct id_eot in bus_empresa
cur.execute("""
    SELECT id_eot, count(*) as cnt 
    FROM registro_habilitacion.bus_empresa 
    GROUP BY id_eot 
    ORDER BY cnt DESC 
    LIMIT 20;
""")
print("\nTop id_eot in bus_empresa:")
print(json.dumps(cur.fetchall(), default=str, indent=2))

# 5. Check eots table for id_eot mapping
cur.execute("SELECT eot_id, eot_nombre, eot_linea, cod_catalogo, id_eot_vmt_hex FROM public.eots WHERE eot_linea = '20' OR eot_nombre ILIKE '%20%' LIMIT 5;")
print("\nEOT Linea 20:", json.dumps(cur.fetchall(), default=str, indent=2))

# 6. Check servicios_especiales.adjudicacion_servicio and bus_adjudicacion
cur.execute("SELECT * FROM servicios_especiales.adjudicacion_servicio;")
print("\nservicios_especiales.adjudicacion_servicio:")
print(json.dumps(cur.fetchall(), default=str, indent=2))

cur.execute("""
    SELECT ba.*, se.nombre as servicio_nombre
    FROM servicios_especiales.bus_adjudicacion ba
    JOIN servicios_especiales.adjudicacion_servicio ads ON ba.id_adjudicacion = ads.id_adjudicacion
    JOIN servicios_especiales.servicio_especial se ON ads.id_servicio_especial = se.id_servicio_especial
    LIMIT 25;
""")
print("\nbus_adjudicacion with servicio_especial:")
print(json.dumps(cur.fetchall(), default=str, indent=2))

# 7. Check ITV and Seguros in registro_habilitacion
cur.execute("SELECT count(*) FROM registro_habilitacion.itv_bus;")
print("\nTotal itv_bus:", cur.fetchone())
cur.execute("SELECT * FROM registro_habilitacion.itv_bus LIMIT 2;")
print("Sample itv_bus:", json.dumps(cur.fetchall(), default=str, indent=2))

cur.execute("SELECT count(*) FROM registro_habilitacion.seguros_bus;")
print("\nTotal seguros_bus:", cur.fetchone())
cur.execute("SELECT * FROM registro_habilitacion.seguros_bus LIMIT 2;")
print("Sample seguros_bus:", json.dumps(cur.fetchall(), default=str, indent=2))

conn.close()
