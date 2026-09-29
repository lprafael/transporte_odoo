import os
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host=os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py"),
    port=int(os.getenv("VMT_DB_PORT", 5432)),
    dbname=os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod"),
    user=os.getenv("VMT_DB_USER", "jefe-CID"),
    password=os.getenv("VMT_DB_PASS", "vmtdmt"),
    sslmode="require",
    connect_timeout=15
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== DATABASES ON SERVER ===")
try:
    cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
    for row in cur.fetchall():
        print("DB:", row['datname'])
except Exception as e:
    print("Error listing databases:", e)

print("\n=== SCHEMAS IN bbdd-monitoreo-prod ===")
cur.execute("SELECT schema_name FROM information_schema.schemata;")
for row in cur.fetchall():
    print("Schema:", row['schema_name'])

print("\n=== SEARCHING FOR 'itinerario' OR 'geometria' OR 'shape' IN TABLES ===")
cur.execute("""
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_name ILIKE '%itinerario%' 
       OR table_name ILIKE '%shape%' 
       OR table_name ILIKE '%ruta%'
       OR table_name ILIKE '%recorrido%'
       OR table_schema ILIKE '%geometria%';
""")
for row in cur.fetchall():
    print(f"Found table: [{row['table_schema']}].{row['table_name']}")

cur.close()
conn.close()
