import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py"),
    port=int(os.getenv("VMT_DB_PORT", 5432)),
    dbname=os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod"),
    user=os.getenv("VMT_DB_USER", "jefe-CID"),
    password=os.getenv("VMT_DB_PASS", "vmtdmt"),
    sslmode="require",
    connect_timeout=10
)
cur = conn.cursor()
cur.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY schemaname, tablename;")
tables = cur.fetchall()
print(f"Total non-system tables: {len(tables)}")
for s, t in tables:
    print(f" - {s}.{t}")

cur.close()
conn.close()
