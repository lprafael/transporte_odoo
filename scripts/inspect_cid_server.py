import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
PORT = int(os.getenv("CID_DB_PORT", "2024"))
DBNAME = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
USER = os.getenv("CID_DB_USER", "cid_admin_user")
PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

print(f"Connecting to CID: {HOST}:{PORT}/{DBNAME} as {USER}...")
try:
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=DBNAME,
        user=USER,
        password=PASS,
        connect_timeout=10
    )
    print("SUCCESS: Connected to CID DB!")

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Schemas
    cur.execute("SELECT schema_name FROM information_schema.schemata;")
    print("Schemas:", [r['schema_name'] for r in cur.fetchall()])

    # 2. Tables in geometrias or matching itinerario
    cur.execute("""
        SELECT table_schema, table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'geometrias' 
           OR table_name ILIKE '%itinerario%'
           OR table_name ILIKE '%historico%';
    """)
    rows = cur.fetchall()
    print("Matching tables:", [f"{r['table_schema']}.{r['table_name']}" for r in rows])

    # 3. Columns of the target table
    # Check if there is geometrias.historico:itinerario or similar
    cur.execute("""
        SELECT table_schema, table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'geometrias' OR table_name ILIKE '%itinerario%'
        ORDER BY table_schema, table_name, ordinal_position;
    """)
    cols = cur.fetchall()
    print(f"\nFound {len(cols)} columns across matched tables:")
    for c in cols:
        print(f" - [{c['table_schema']}].{c['table_name']} -> {c['column_name']} ({c['data_type']})")

    cur.close()
    conn.close()
except Exception as e:
    print("ERROR connecting to CID:", e)
