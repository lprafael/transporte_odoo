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

# 1. Ver qué empresas / EOTs existen en catalogo_rutas
cur.execute("""
    SELECT DISTINCT c.id_eot_catalogo, COUNT(*) as cant_rutas
    FROM public.catalogo_rutas c
    GROUP BY c.id_eot_catalogo
    ORDER BY cant_rutas DESC;
""")
print("=== EOTs en public.catalogo_rutas ===")
for r in cur.fetchall():
    print(r)

# 2. Ver todas las rutas de EOT 7 y EOT 75 (Línea 27 y Línea 20 Eléctricos)
cur.execute("""
    SELECT ruta_hex, id_eot_catalogo, sentido, ramal, origen, destino, identificacion, identificador_troncal, estado
    FROM public.catalogo_rutas
    ORDER BY id_eot_catalogo, ruta_hex;
""")
all_cat = cur.fetchall()
print(f"\nTotal rutas en catalogo_rutas: {len(all_cat)}")

# 3. Ver qué rutas tienen shapes en geometria.historico_itinerario
cur.execute("""
    SELECT DISTINCT ruta_hex, COUNT(*) as cant_shapes
    FROM geometria.historico_itinerario
    GROUP BY ruta_hex
    ORDER BY cant_shapes DESC;
""")
all_shapes = cur.fetchall()
print(f"\nTotal rutas con shapes en geometria.historico_itinerario: {len(all_shapes)}")

conn.close()
