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
    WHERE table_name ILIKE '%ruta%' OR table_name ILIKE '%itinerario%' OR table_name ILIKE '%servicio%'
    ORDER BY table_schema, table_name;
""")
print("=== TABLAS EN CID ===")
for r in cur.fetchall():
    print(f" - {r['table_schema']}.{r['table_name']}")

# Ver catálogo de rutas si existe
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'catalogo_rutas'
    ORDER BY ordinal_position;
""")
cols = cur.fetchall()
if cols:
    print("\n=== COLUMNAS catalogo_rutas ===")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']})")

    cur.execute("SELECT * FROM public.catalogo_rutas LIMIT 10;")
    print("\n=== MUESTRA catalogo_rutas ===")
    for r in cur.fetchall():
        print(dict(r))

conn.close()
