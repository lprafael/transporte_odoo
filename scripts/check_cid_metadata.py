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

# Let's search all tables in public or geometria for '020c' or '020d'
cur.execute("""
SELECT table_schema, table_name, column_name
FROM information_schema.columns
WHERE data_type IN ('text', 'character varying')
  AND table_schema IN ('public', 'geometria', 'gestion_uf');
""")
cols = cur.fetchall()

for c in cols:
    sch = c['table_schema']
    tbl = c['table_name']
    col = c['column_name']
    try:
        cur.execute(f'SELECT DISTINCT "{col}" FROM "{sch}"."{tbl}" WHERE "{col}" ILIKE %s LIMIT 3;', ('%020c%',))
        rows = cur.fetchall()
        if rows:
            print(f"Match in {sch}.{tbl}.{col}:", [r[col] for r in rows])
    except Exception as e:
        conn.rollback()
