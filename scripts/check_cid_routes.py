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

routes = ['01eb', '01ec', '020a', '020b', '01ef', '01f0', '0206', '0207', '020c', '020d', '020e', '020f', '0210', '0211']

cur.execute("""
    SELECT DISTINCT ruta_hex, observacion, vigente, fecha_inicio_vigencia, fecha_fin_vigencia
    FROM geometria.historico_itinerario
    WHERE ruta_hex = ANY(%s)
    ORDER BY ruta_hex;
""", (routes,))

for r in cur.fetchall():
    print(r)

conn_cid.close()
