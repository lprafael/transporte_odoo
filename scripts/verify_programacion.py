import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost', port=5434, dbname='flota_db', user='odoo', password='odoo_password'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print('=== TOTAL EN SERVICIOS_ESPECIALES.PROGRAMACION_OPERATIVA ===')
cur.execute('SELECT count(*) as total FROM servicios_especiales.programacion_operativa;')
print("Total en servicios_especiales.programacion_operativa:", cur.fetchone()['total'])

print('\n=== TOTAL EN TRANSIT_TIMETABLE ===')
cur.execute('SELECT count(*) as total FROM transit_timetable;')
print("Total en transit_timetable:", cur.fetchone()['total'])

print('\n=== HORARIOS POR RUTA EN TRANSIT_TIMETABLE ===')
cur.execute('''
    SELECT r.code, r.name, t.day_of_week, t.direction, count(*) as salidas,
           min(t.departure_time_float) as primer_salida,
           max(t.departure_time_float) as ultima_salida
    FROM transit_timetable t
    JOIN transit_route r ON r.id = t.route_id
    GROUP BY r.code, r.name, t.day_of_week, t.direction
    ORDER BY r.code, t.direction, t.day_of_week;
''')
for row in cur.fetchall():
    h_min = int(row['primer_salida'] or 0)
    m_min = int(((row['primer_salida'] or 0) - h_min) * 60)
    h_max = int(row['ultima_salida'] or 0)
    m_max = int(((row['ultima_salida'] or 0) - h_max) * 60)
    direction_str = (row['direction'] or 'N/A').upper()
    print(f"[{row['code']}] {direction_str:6s} ({row['day_of_week']:7s}): {row['salidas']:2d} salidas | 1ra: {h_min:02d}:{m_min:02d} | Ult: {h_max:02d}:{m_max:02d} | {row['name']}")

conn.close()
