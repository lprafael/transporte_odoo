import os
import psycopg2
from psycopg2.extras import RealDictCursor

HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
PORT = int(os.getenv("CID_DB_PORT", "2024"))
DBNAME = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
USER = os.getenv("CID_DB_USER", "cid_admin_user")
PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

conn = psycopg2.connect(host=HOST, port=PORT, dbname=DBNAME, user=USER, password=PASS, connect_timeout=10)
cur = conn.cursor(cursor_factory=RealDictCursor)

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
        ROUND((ST_Length(ST_Transform(geom, 32721)) / 1000.0)::numeric, 2) as total_km,
        ST_NPoints(geom) as num_points,
        ST_AsText(ST_StartPoint(ST_GeometryN(geom, 1))) as start_pt,
        ST_AsText(ST_EndPoint(ST_GeometryN(geom, 1))) as end_pt
    FROM geometria.historico_itinerario
    WHERE ruta_hex IN ('020c', '020d', '020e', '020f', '0210', '0211')
    ORDER BY ruta_hex, fecha_inicio_vigencia ASC;
""")

rows = cur.fetchall()
print(f"Total registros: {len(rows)}")
for r in rows:
    print(f"Ruta: {r['ruta_hex']} | ID: {r['id_itinerario']} | Vigente: {r['vigente']} | Vigencia: [{r['fecha_inicio_vigencia']} -> {r['fecha_fin_vigencia']}] | Km: {r['total_km']} | Puntos: {r['num_points']} | Obs: {r['observacion']}")

cur.close()
conn.close()
