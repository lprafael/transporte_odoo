import psycopg2
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

conn_cid = psycopg2.connect(
    host=os.getenv('CID_DB_HOST'),
    port=os.getenv('CID_DB_PORT'),
    dbname=os.getenv('CID_DB_NAME'),
    user=os.getenv('CID_DB_USER'),
    password=os.getenv('CID_DB_PASS')
)
cur = conn_cid.cursor(cursor_factory=RealDictCursor)

tables = [
    'servicio_especial', 
    'ruta_servicio_especial', 
    'adjudicacion_servicio', 
    'bus_adjudicacion', 
    'parametro_monitoreo', 
    'programacion_operativa'
]

for t in tables:
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_schema = 'servicios_especiales' AND table_name = '{t}'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    cur.execute(f"SELECT count(*) as count FROM servicios_especiales.{t}")
    cnt = cur.fetchone()['count']
    print(f"\n=== TABLE: servicios_especiales.{t} (rows: {cnt}) ===")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}) - Nullable: {c['is_nullable']}")

conn_cid.close()
