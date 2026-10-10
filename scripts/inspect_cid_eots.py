# -*- coding: utf-8 -*-
import psycopg2
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('CID_DB_HOST'),
    port=os.getenv('CID_DB_PORT'),
    dbname=os.getenv('CID_DB_NAME'),
    user=os.getenv('CID_DB_USER'),
    password=os.getenv('CID_DB_PASS')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_name ILIKE '%eot%' OR table_name ILIKE '%empresa%'
    ORDER BY table_schema, table_name;
""")
print("=== TABLAS EOT ===")
for r in cur.fetchall():
    print(r)

# Si existe public.eot
cur.execute("""
    SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('eot', 'empresas', 'concesionarias');
""")
print("Tablas encontradas:", [r['table_name'] for r in cur.fetchall()])

# Ver registros de EOT si existe
try:
    cur.execute("SELECT * FROM public.eot WHERE id_eot IN (7, 75);")
    for r in cur.fetchall():
        print(dict(r))
except Exception as e:
    print("Error querying public.eot:", e)

conn.close()
