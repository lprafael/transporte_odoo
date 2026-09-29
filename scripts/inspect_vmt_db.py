import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

HOST = os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py")
PORT = int(os.getenv("VMT_DB_PORT", "5432"))
DBNAME = os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod")
USER = os.getenv("VMT_DB_USER", "jefe-CID")
PASSWORD = os.getenv("VMT_DB_PASS", "vmtdmt")

print(f"Connecting to {HOST}:{PORT}/{DBNAME} as {USER}...")

try:
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=DBNAME,
        user=USER,
        password=PASSWORD,
        sslmode="require",
        connect_timeout=15
    )
    print("SUCCESS: Connected to VMT database!")

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. List all tables in public schema
    cur.execute("""
        SELECT table_schema, table_name 
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name;
    """)
    tables = cur.fetchall()
    print("\n--- TABLES FOUND ---")
    for t in tables:
        print(f"[{t['table_schema']}] {t['table_name']}")

    # 2. Inspect app_monitoreo_mensajeoperativo columns
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'app_monitoreo_mensajeoperativo'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    print("\n--- COLUMNS of app_monitoreo_mensajeoperativo ---")
    for col in columns:
        print(f" - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']}, default: {col['column_default']})")

    # 3. Sample rows from app_monitoreo_mensajeoperativo
    cur.execute("""
        SELECT *
        FROM app_monitoreo_mensajeoperativo
        ORDER BY id DESC
        LIMIT 2;
    """)
    samples = cur.fetchall()
    print("\n--- SAMPLE ROWS (LATEST 2) ---")
    for s in samples:
        print(json.dumps(s, default=str, indent=2))

    # 4. Check agency filter 004B sample
    cur.execute("""
        SELECT *
        FROM app_monitoreo_mensajeoperativo
        WHERE agency_id = '004B'
        ORDER BY id DESC
        LIMIT 2;
    """)
    agency_samples = cur.fetchall()
    print("\n--- SAMPLE ROWS FOR AGENCY 004B ---")
    for s in agency_samples:
        print(json.dumps(s, default=str, indent=2))

    cur.close()
    conn.close()

except Exception as e:
    print(f"ERROR: {e}")
