import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py"),
    port=int(os.getenv("VMT_DB_PORT", 5432)),
    dbname=os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod"),
    user=os.getenv("VMT_DB_USER", "jefe-CID"),
    password=os.getenv("VMT_DB_PASS", "vmtdmt"),
    sslmode="require",
    connect_timeout=15
)
cur = conn.cursor()
cur.execute("SELECT reltuples::bigint AS estimate FROM pg_class WHERE relname = 'app_monitoreo_mensajeoperativo';")
print("Estimado total filas:", cur.fetchone()[0])
cur.execute("SELECT max(id) FROM app_monitoreo_mensajeoperativo;")
print("Max ID:", cur.fetchone()[0])
cur.close()
conn.close()
