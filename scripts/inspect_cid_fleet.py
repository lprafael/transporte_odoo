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

def inspect_table(schema, table, limit=5, where=""):
    print(f"\n=================== {schema}.{table} ===================")
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = '{schema}' AND table_name = '{table}'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    print("Columns:", [f"{c['column_name']} ({c['data_type']})" for c in cols])
    
    query = f"SELECT * FROM {schema}.{table} {where} LIMIT {limit};"
    cur.execute(query)
    rows = cur.fetchall()
    print(f"Sample data ({len(rows)} rows):")
    for r in rows:
        print(json.dumps(r, default=str, indent=2))

inspect_table("registro_habilitacion", "buses", limit=3)
inspect_table("registro_habilitacion", "bus_empresa", limit=3)
inspect_table("registro_habilitacion", "marcas", limit=10)
inspect_table("public", "buses_declarados", limit=3)
inspect_table("public", "empresas", limit=10)
inspect_table("public", "eots", limit=10)

# Check specifically for Empresa Línea 20 or agency 004B or similar
cur.execute("""
    SELECT * FROM public.empresas WHERE descripcion ILIKE '%20%' OR descripcion ILIKE '%asuncion%' OR descripcion ILIKE '%ciudad%';
""")
print("\n=== Linea 20 / Empresas matching ===")
print(json.dumps(cur.fetchall(), default=str, indent=2))

conn.close()
