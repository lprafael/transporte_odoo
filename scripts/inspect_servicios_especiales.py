import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('CID_DB_HOST', '168.90.177.232'),
    port=int(os.getenv('CID_DB_PORT', '2024')),
    dbname=os.getenv('CID_DB_NAME', 'bbdd-monitoreo-cid'),
    user=os.getenv('CID_DB_USER', 'cid_admin_user'),
    password=os.getenv('CID_DB_PASS', 'vmtdmtcidccm'),
    connect_timeout=10
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== TABLAS EN SCHEMA servicios_especiales ===")
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'servicios_especiales'
    ORDER BY table_name;
""")
tables = [t['table_name'] for t in cur.fetchall()]
print(tables)

for t in tables:
    cur.execute(f"SELECT count(*) as cant FROM servicios_especiales.{t};")
    print(f"Table {t}: {cur.fetchone()['cant']} rows")
    cur.execute(f"SELECT * FROM servicios_especiales.{t} LIMIT 3;")
    print(f"Sample {t}:", [dict(x) for x in cur.fetchall()])
    print("---")

conn.close()
