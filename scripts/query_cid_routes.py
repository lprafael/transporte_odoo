import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
PORT = int(os.getenv("CID_DB_PORT", "2024"))
DBNAME = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
USER = os.getenv("CID_DB_USER", "cid_admin_user")
PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

conn = psycopg2.connect(host=HOST, port=PORT, dbname=DBNAME, user=USER, password=PASS, connect_timeout=10)
cur = conn.cursor(cursor_factory=RealDictCursor)

routes = ['020c', '020d', '020e', '020f', '0210', '0211']
routes_upper = [r.upper() for r in routes]
routes_all = list(set(routes + routes_upper))

print("=== 1. BUSQUEDA EN geometria.historico_itinerario ===")
cur.execute("""
    SELECT 
        id_itinerario, 
        ruta_hex, 
        fecha_inicio_vigencia, 
        fecha_fin_vigencia, 
        vigente, 
        observacion, 
        ST_GeometryType(geom) as geom_type,
        ST_SRID(geom) as srid,
        ST_Length(ST_Transform(geom, 32721)) as length_m,
        ST_NumPoints(geom) as num_points,
        fecha_creacion,
        fecha_actualizacion
    FROM geometria.historico_itinerario
    WHERE UPPER(ruta_hex) = ANY(%s) OR ruta_hex = ANY(%s)
    ORDER BY ruta_hex, fecha_inicio_vigencia DESC;
""", (routes_all, routes_all))

found_hist = cur.fetchall()
print(f"Total registros encontrados en historico_itinerario: {len(found_hist)}")
for r in found_hist:
    km = round(r['length_m'] / 1000.0, 2) if r['length_m'] else 0.0
    print(f" -> Ruta {r['ruta_hex']:<6} | ID: {r['id_itinerario']:<4} | Vigente: {r['vigente']} | Desde: {r['fecha_inicio_vigencia']} | Hasta: {r['fecha_fin_vigencia']} | Km: {km} | Puntos: {r['num_points']} | Obs: {r['observacion']}")

print("\n=== 2. RUTAS DISPONIBLES EN geometria.historico_itinerario (MUESTRA O COINCIDENCIAS LIKE '020%') ===")
cur.execute("""
    SELECT DISTINCT ruta_hex, vigente, count(*) as count
    FROM geometria.historico_itinerario
    WHERE ruta_hex ILIKE '020%' OR ruta_hex ILIKE '021%'
    GROUP BY ruta_hex, vigente
    ORDER BY ruta_hex;
""")
for r in cur.fetchall():
    print(r)

print("\n=== 3. BUSQUEDA EN public.itinerarios_oficiales (LINEA 20 / 020) ===")
cur.execute("""
    SELECT id, linea, empresa, nombre_iti, longitud_m, descripcion, validado
    FROM public.itinerarios_oficiales
    WHERE linea ILIKE '%20%' OR nombre_iti ILIKE '%020%' OR nombre_iti ILIKE '%021%'
    LIMIT 20;
""")
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
