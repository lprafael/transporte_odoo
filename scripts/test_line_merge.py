import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("CID_DB_HOST", "168.90.177.232"),
    port=int(os.getenv("CID_DB_PORT", "2024")),
    dbname=os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid"),
    user=os.getenv("CID_DB_USER", "cid_admin_user"),
    password=os.getenv("CID_DB_PASS", "vmtdmtcidccm"),
    connect_timeout=10
)
cur = conn.cursor()
cur.execute("""
    SELECT DISTINCT ST_GeometryType(ST_LineMerge(geom)) 
    FROM geometria.historico_itinerario 
    WHERE ruta_hex IN ('020c', '020d', '020e', '020f', '0210', '0211');
""")
print("LineMerge geom types in CID:", cur.fetchall())
cur.close()
conn.close()
