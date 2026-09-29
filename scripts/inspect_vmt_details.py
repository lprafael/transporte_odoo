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

print("=== 1. ORGANIZACIONES / AGENCIAS / EMISORES ===")
cur.execute("SELECT * FROM app_eps_emisormensajeoperativo LIMIT 10;")
print("Emisores:", json.dumps(cur.fetchall(), default=str, indent=2))

cur.execute("SELECT * FROM app_organizaciones_organizacion LIMIT 10;")
print("Organizaciones:", json.dumps(cur.fetchall(), default=str, indent=2))

print("\n=== 2. VEHÍCULOS (mean_id) Y RUTAS PARA AGENCIA 004B ===")
cur.execute("""
    SELECT mean_id, count(*) as total_pings, 
           max(fecha_hora) as ultima_transmision,
           array_agg(DISTINCT route_id) as rutas_detectadas
    FROM (
        SELECT mean_id, route_id, fecha_hora 
        FROM app_monitoreo_mensajeoperativo 
        WHERE agency_id = '004B' 
        ORDER BY id DESC 
        LIMIT 5000
    ) sub
    GROUP BY mean_id
    ORDER BY ultima_transmision DESC;
""")
print("Buses activos 004B:", json.dumps(cur.fetchall(), default=str, indent=2))

print("\n=== 3. VALORES DE TYPE EN MENSAJES OPERATIVOS ===")
cur.execute("""
    SELECT type, count(*) 
    FROM (
        SELECT type FROM app_monitoreo_mensajeoperativo ORDER BY id DESC LIMIT 5000
    ) sub 
    GROUP BY type;
""")
print("Tipos de mensaje:", json.dumps(cur.fetchall(), default=str, indent=2))

print("\n=== 4. ÍNDICES DE app_monitoreo_mensajeoperativo ===")
cur.execute("""
    SELECT indexname, indexdef 
    FROM pg_indexes 
    WHERE tablename = 'app_monitoreo_mensajeoperativo';
""")
print("Índices:", json.dumps(cur.fetchall(), default=str, indent=2))

cur.close()
conn.close()
