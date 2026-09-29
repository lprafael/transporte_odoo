import psycopg2
from psycopg2.extras import RealDictCursor

conn_local = psycopg2.connect(
    host='localhost',
    port=5434,
    dbname='flota_db',
    user='odoo',
    password='odoo_password'
)
cur = conn_local.cursor(cursor_factory=RealDictCursor)

print('=== LOCAL ROUTES ===')
cur.execute('SELECT id, name, code, active FROM transit_route;')
for r in cur.fetchall():
    print(r)

print('\n=== TABLE COLUMNS: transit_timetable ===')
cur.execute('''
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'transit_timetable'
    ORDER BY ordinal_position;
''')
for r in cur.fetchall():
    print(f"{r['column_name']}: {r['data_type']}")

print('\n=== LOCAL TIMETABLE COUNT ===')
cur.execute('SELECT count(*) FROM transit_timetable;')
print('Count:', cur.fetchone())

cur.execute('SELECT * FROM transit_timetable LIMIT 5;')
for r in cur.fetchall():
    print(r)

conn_local.close()
