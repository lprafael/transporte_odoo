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

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'registro_habilitacion' AND table_name = 'marcas';
""")
print("Marcas columns:", cur.fetchall())

cur.execute("SELECT * FROM registro_habilitacion.marcas LIMIT 20;")
print("Marcas sample:", cur.fetchall())

# Check eot_id for CONSORCIO ARAPOTI
cur.execute("SELECT * FROM public.eots WHERE eot_nombre ILIKE '%arapoti%' OR eot_linea ILIKE '%E1%';")
arapoti = cur.fetchall()
print("\nArapoti EOT:", json.dumps(arapoti, default=str, indent=2))
eot_id = arapoti[0]['eot_id'] if arapoti else None

# Check bus_empresa for Arapoti
if eot_id:
    cur.execute(f"SELECT * FROM registro_habilitacion.bus_empresa WHERE id_eot = '{eot_id}';")
    print(f"\nBus empresa for Arapoti ({eot_id}):", cur.fetchall())

# Check all electric buses in bus_adjudicacion (distinct)
cur.execute("""
    SELECT DISTINCT ba.numero_orden, ba.mean_id, ba.idsam
    FROM servicios_especiales.bus_adjudicacion ba
    JOIN servicios_especiales.adjudicacion_servicio ads ON ba.id_adjudicacion = ads.id_adjudicacion
    JOIN servicios_especiales.servicio_especial se ON ads.id_servicio_especial = se.id_servicio_especial
    WHERE se.nombre ILIKE '%eléctrico%' or se.nombre ILIKE '%electrico%'
    ORDER BY ba.numero_orden;
""")
ebuses = cur.fetchall()
print(f"\nTotal distinct electric buses: {len(ebuses)}")
for eb in ebuses:
    print(eb)

conn.close()
