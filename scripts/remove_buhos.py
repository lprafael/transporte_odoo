import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost', port=5434, dbname='flota_db', user='odoo', password='odoo_password'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== ELIMINANDO BÚHOS Y RUTAS NO ELÉCTRICAS ===")

# 1. Identificar rutas a eliminar
codes_to_remove = ['01eb', '01ec', '020a', '020b', '01ef', '01f0', '0206', '0207', '006a', '006b']
cur.execute("SELECT id, code, name FROM transit_route WHERE code = ANY(%s);", (codes_to_remove,))
routes_to_del = cur.fetchall()
route_ids = [r['id'] for r in routes_to_del]
print(f"Rutas identificadas ({len(route_ids)}): {[r['code'] for r in routes_to_del]}")

# 2. Eliminar de transit_timetable
if route_ids:
    cur.execute("DELETE FROM transit_timetable WHERE route_id = ANY(%s);", (route_ids,))
    print(f"Horarios eliminados de transit_timetable: {cur.rowcount}")

    # 3. Eliminar de transit_route
    cur.execute("DELETE FROM transit_route WHERE id = ANY(%s);", (route_ids,))
    print(f"Rutas eliminadas de transit_route: {cur.rowcount}")

# 4. En schema servicios_especiales, dejar SOLO Eléctricos (id_servicio_especial IN (3, 8, 10))
ELECTRIC_SERVICE_IDS = [3, 8, 10]

# programacion_operativa
cur.execute("DELETE FROM servicios_especiales.programacion_operativa WHERE id_servicio_especial != ALL(%s);", (ELECTRIC_SERVICE_IDS,))
print(f"Despachos eliminados de servicios_especiales.programacion_operativa: {cur.rowcount}")

# ruta_servicio_especial
cur.execute("DELETE FROM servicios_especiales.ruta_servicio_especial WHERE id_servicio_especial != ALL(%s);", (ELECTRIC_SERVICE_IDS,))
print(f"Rutas eliminadas de servicios_especiales.ruta_servicio_especial: {cur.rowcount}")

# bus_adjudicacion & adjudicacion_servicio
cur.execute("""
    DELETE FROM servicios_especiales.bus_adjudicacion 
    WHERE id_adjudicacion IN (
        SELECT id_adjudicacion FROM servicios_especiales.adjudicacion_servicio 
        WHERE id_servicio_especial != ALL(%s)
    );
""", (ELECTRIC_SERVICE_IDS,))
print(f"Buses eliminados de servicios_especiales.bus_adjudicacion: {cur.rowcount}")

cur.execute("DELETE FROM servicios_especiales.adjudicacion_servicio WHERE id_servicio_especial != ALL(%s);", (ELECTRIC_SERVICE_IDS,))
print(f"Adjudicaciones eliminadas de servicios_especiales.adjudicacion_servicio: {cur.rowcount}")

# parametro_monitoreo
cur.execute("DELETE FROM servicios_especiales.parametro_monitoreo WHERE id_servicio_especial != ALL(%s);", (ELECTRIC_SERVICE_IDS,))
print(f"Parámetros eliminados de servicios_especiales.parametro_monitoreo: {cur.rowcount}")

# servicio_especial
cur.execute("DELETE FROM servicios_especiales.servicio_especial WHERE id_servicio_especial != ALL(%s);", (ELECTRIC_SERVICE_IDS,))
print(f"Servicios eliminados de servicios_especiales.servicio_especial: {cur.rowcount}")

conn.commit()

# Verificaciones
print("\n=== VERIFICACIÓN FINAL ===")
cur.execute("SELECT count(*) as total FROM servicios_especiales.programacion_operativa;")
print(f"Total en servicios_especiales.programacion_operativa: {cur.fetchone()['total']}")

cur.execute("SELECT count(*) as total FROM transit_timetable WHERE cid_programacion_id IS NOT NULL;")
print(f"Total en transit_timetable (CID): {cur.fetchone()['total']}")

cur.execute("SELECT id, code, name FROM transit_route ORDER BY id;")
print("Rutas activas en transit_route:")
for r in cur.fetchall():
    print(f"  ID {r['id']}: [{r['code']}] {r['name']}")

cur.execute("""
    SELECT r.code, r.name, count(s.id) as total_shapes
    FROM transit_route r
    JOIN transit_route_shape s ON s.route_id = r.id
    GROUP BY r.code, r.name
    ORDER BY r.code;
""")
print("\nShapes activos por ruta:")
for s in cur.fetchall():
    print(f"  [{s['code']}]: {s['total_shapes']} shapes | {s['name']}")

conn.close()
