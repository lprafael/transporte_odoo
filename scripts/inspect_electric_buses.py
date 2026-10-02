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

print("=== SERVICIOS ESPECIALES ===")
cur.execute("SELECT * FROM servicios_especiales.servicio_especial;")
for s in cur.fetchall():
    print(s)

print("\n=== ALL BUSES IN SERVICIOS ESPECIALES ===")
cur.execute("""
    SELECT se.nombre as servicio, ba.id_bus_adjudicacion, ba.numero_orden, ba.idsam, ba.mean_id,
           ads.id_eot, e.eot_nombre, e.eot_linea
    FROM servicios_especiales.bus_adjudicacion ba
    JOIN servicios_especiales.adjudicacion_servicio ads ON ba.id_adjudicacion = ads.id_adjudicacion
    JOIN servicios_especiales.servicio_especial se ON ads.id_servicio_especial = se.id_servicio_especial
    LEFT JOIN public.eots e ON ads.id_eot = e.eot_id
    ORDER BY se.nombre, ba.numero_orden;
""")
all_buses = cur.fetchall()
print(f"Total buses adjudicados: {len(all_buses)}")
for b in all_buses:
    print(f"[{b['servicio']}] Coche: {b['numero_orden']} | MeanID: {b['mean_id']} | IDSAM (Validador): {b['idsam']} | EOT: {b['eot_nombre']} (Linea {b['eot_linea']})")

# Now let's check if these numero_orden or mean_id exist in registro_habilitacion.buses!
order_nums = [b['numero_orden'] for b in all_buses if 'Eléctrico' in b['servicio']]
print("\nBusca coches electricos en registro_habilitacion.buses con numero_orden in:", order_nums)
cur.execute("""
    SELECT b.*, m.descripcion as marca, mc.descripcion as carroceria
    FROM registro_habilitacion.buses b
    LEFT JOIN registro_habilitacion.marcas m ON b.id_marca = m.id_marca
    LEFT JOIN registro_habilitacion.marcas_carroceria mc ON b.id_marca_carroceria = mc.id_marca_carroceria
    WHERE b.numero_orden IN %s;
""", (tuple(order_nums),))
reg_buses = cur.fetchall()
print(f"Found {len(reg_buses)} matches in registro_habilitacion.buses:")
for rb in reg_buses:
    print(f"Coche {rb['numero_orden']} | Placa: {rb['rua']} | Chasis: {rb['numero_chassis']} | Marca: {rb['marca']} | Carroc: {rb['carroceria']} | Asientos/Cap: {rb['capacidad_pasajeros']} | Rampa: {rb['tiene_rampa']}")

# Also check marcas table in registro_habilitacion for Master Bus or similar
cur.execute("SELECT * FROM registro_habilitacion.marcas WHERE descripcion ILIKE '%master%' OR descripcion ILIKE '%taiwan%' OR descripcion ILIKE '%byd%' OR descripcion ILIKE '%yutong%';")
print("\nMarcas coincidentes:", cur.fetchall())

conn.close()
