# -*- coding: utf-8 -*-
import psycopg2
import json
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    port=5434,
    dbname='flota_db',
    user='odoo',
    password='odoo_password'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT r.code, ST_AsGeoJSON(ST_LineMerge(s.geom)) as geom_json 
    FROM transit_route_shape s 
    JOIN transit_route r ON s.route_id = r.id 
    WHERE s.valid_until IS NULL OR s.valid_until > CURRENT_DATE;
""")
shapes = {r['code']: json.loads(r['geom_json'])['coordinates'] for r in cur.fetchall()}

# 1. Eusebio Ayala en 020d
pts_020d = shapes['020d']
# Filtrar puntos en Av. Eusebio Ayala entre Kubitschek (-57.605) y Calle Ultima (-57.575)
eusebio_jams = [pt for pt in pts_020d if -57.605 <= pt[0] <= -57.575]
print("Eusebio Ayala pts:", len(eusebio_jams))
# Punto medio de Eusebio Ayala (cerca de Republica Argentina)
mid_eusebio = [pt for pt in eusebio_jams if -57.592 <= pt[0] <= -57.589]
alert_eusebio = mid_eusebio[len(mid_eusebio)//2] if mid_eusebio else eusebio_jams[len(eusebio_jams)//2]
print("Accident point on Eusebio Ayala:", alert_eusebio)

# 2. Mcal. Lopez en 020f
pts_020f = shapes['020f']
mcal_jams = [pt for pt in pts_020f if -57.558 <= pt[0] <= -57.530]
print("Mcal Lopez pts:", len(mcal_jams))
alert_mcal = mcal_jams[len(mcal_jams)//2]
print("Obras point on Mcal Lopez:", alert_mcal)

# 3. PY02 San Lorenzo en 020d
py02_jams = [pt for pt in pts_020d if -57.535 <= pt[0] <= -57.505]
print("PY02 pts:", len(py02_jams))
alert_py02 = py02_jams[len(py02_jams)//2]
print("Peligro point on PY02:", alert_py02)

# 4. Silvio Pettirossi en 0210
pts_0210 = shapes['0210']
pettirossi_jams = [pt for pt in pts_0210 if -57.545 <= pt[0] <= -57.508]
print("Silvio Pettirossi pts:", len(pettirossi_jams))
alert_pettirossi = pettirossi_jams[len(pettirossi_jams)//2]
print("Congestion point on Pettirossi:", alert_pettirossi)

conn.close()
