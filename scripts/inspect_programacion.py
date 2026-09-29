import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('CID_DB_HOST', '168.90.177.232'),
    port=int(os.getenv('CID_DB_PORT', '2024')),
    dbname=os.getenv('CID_DB_NAME', 'bbdd-monitoreo-cid'),
    user=os.getenv('CID_DB_USER', 'cid_admin_user'),
    password=os.getenv('CID_DB_PASS', 'vmtdmtcidccm'),
    connect_timeout=10
)
cur = conn.cursor(cursor_factory=RealDictCursor)

ITINERARIOS_LINEA_20 = [2171, 2172, 2190, 2191, 2192, 2201]

# 1. Buscar por id_itinerario
cur.execute("""
    SELECT id_itinerario, count(*) as cant, min(fecha_desde) as f_min, max(fecha_hasta) as f_max
    FROM servicios_especiales.programacion_operativa
    WHERE id_itinerario = ANY(%s)
    GROUP BY id_itinerario
    ORDER BY id_itinerario;
""", (ITINERARIOS_LINEA_20,))
rows_itin = cur.fetchall()
print("=== COINCIDENCIAS POR ID_ITINERARIO ===")
for r in rows_itin:
    print(r)

# 2. Si no hay por esos IDs exactos, averiguar qué id_linea o empresa corresponde a Línea 20 (004B)
cur.execute("""
    SELECT DISTINCT p.id_linea, count(*) as cant
    FROM servicios_especiales.programacion_operativa p
    GROUP BY p.id_linea
    ORDER BY cant DESC
    LIMIT 20;
""")
print("=== TOP 20 ID_LINEA EN PROGRAMACION_OPERATIVA ===")
for r in cur.fetchall():
    print(r)

# 3. Consultar tablas de líneas/empresas en CID para saber el id_linea de la Empresa La Limpeña / Línea 20
cur.execute("""
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_name ILIKE '%linea%' OR table_name ILIKE '%empresa%' OR table_name ILIKE '%agencia%'
    ORDER BY table_schema, table_name;
""")
print("=== TABLAS DE LINEAS/EMPRESAS EN CID ===")
for r in cur.fetchall():
    print(r['table_schema'], '.', r['table_name'])

conn.close()
