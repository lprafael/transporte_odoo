import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

HOST = os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py")
PORT = int(os.getenv("VMT_DB_PORT", "5432"))
DBNAME = os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod")
USER = os.getenv("VMT_DB_USER", "jefe-CID")
PASSWORD = os.getenv("VMT_DB_PASS", "vmtdmt")

conn = psycopg2.connect(
    host=HOST, port=PORT, dbname=DBNAME, user=USER, password=PASSWORD, sslmode="require", connect_timeout=15
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== COLUMNAS DE app_monitoreo_mensajeoperativofallido ===")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'app_monitoreo_mensajeoperativofallido' 
    ORDER BY ordinal_position;
""")
for c in cur.fetchall():
    print(f" - {c['column_name']}: {c['data_type']}")

print("\n=== MUESTRA DE MENSAJE OPERATIVO FALLIDO (ÚLTIMO) ===")
cur.execute("SELECT * FROM app_monitoreo_mensajeoperativofallido ORDER BY id DESC LIMIT 1;")
sample_fallido = cur.fetchall()
print(json.dumps(sample_fallido, default=str, indent=2))

print("\n=== USUARIOS BROKER (app_monitoreo_usuariobroker) ===")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'app_monitoreo_usuariobroker' 
    ORDER BY ordinal_position;
""")
for c in cur.fetchall():
    print(f" - {c['column_name']}: {c['data_type']}")

cur.execute("SELECT * FROM app_monitoreo_usuariobroker LIMIT 5;")
print(json.dumps(cur.fetchall(), default=str, indent=2))

cur.close()
conn.close()
