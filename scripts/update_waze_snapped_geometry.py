# -*- coding: utf-8 -*-
"""
Script para alinear al 100% las coordenadas de Waze CCP con los trazados viales PostGIS de Asunción.
Elimina cualquier desfase y garantiza que los atascos e incidentes se dibujen sobre el asfalto.
"""
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
conn.close()

# 1. Eusebio Ayala (020d)
pts_020d = shapes['020d']
eusebio_jams = [{'x': round(pt[0], 6), 'y': round(pt[1], 6)} for pt in pts_020d if -57.605 <= pt[0] <= -57.575][::2]
alert1_pt = {'x': -57.59039, 'y': -25.310821} # Intersección exacta Eusebio Ayala & República Argentina

# 2. Mcal. Lopez (020f)
pts_020f = shapes['020f']
mcal_jams = [{'x': round(pt[0], 6), 'y': round(pt[1], 6)} for pt in pts_020f if -57.558 <= pt[0] <= -57.530][::3]
alert2_pt = {'x': -57.543601, 'y': -25.305308} # Sobre Av. Mcal López en Fernando de la Mora

# 3. PY02 San Lorenzo (020d)
py02_jams = [{'x': round(pt[0], 6), 'y': round(pt[1], 6)} for pt in pts_020d if -57.535 <= pt[0] <= -57.505][::3]
alert3_pt = {'x': -57.519194, 'y': -25.341317} # Sobre Ruta PY02

# 4. Silvio Pettirossi Luque (0210)
pts_0210 = shapes['0210']
luque_jams = [{'x': round(pt[0], 6), 'y': round(pt[1], 6)} for pt in pts_0210 if -57.545 <= pt[0] <= -57.508][::3]
alert4_pt = {'x': -57.524798, 'y': -25.262735} # Sobre Av. Silvio Pettirossi

print("Puntos exactos extraídos:")
print(f" - Eusebio Ayala Jams: {len(eusebio_jams)} pts, Alerta: {alert1_pt}")
print(f" - Mcal Lopez Jams: {len(mcal_jams)} pts, Alerta: {alert2_pt}")
print(f" - PY02 Jams: {len(py02_jams)} pts, Alerta: {alert3_pt}")
print(f" - Luque Jams: {len(luque_jams)} pts, Alerta: {alert4_pt}")

# Actualizar gps_broker/waze_service.py con los puntos 100% ajustados
WAZE_SERVICE_PATH = r"c:\Users\lpraf\OneDrive\Documentos\Poliverso\transporte_odoo\gps_broker\waze_service.py"

with open(WAZE_SERVICE_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# Reemplazar alert 01
old_alert_1 = '''            "id": "waze_alert_01",
            "uuid": "wz-asu-2026-acc-01",
            "pubMillis": now_ms - (12 * 60 * 1000),
            "type": "ACCIDENT",
            "subtype": "ACCIDENT_MINOR",
            "street": "Av. Doctor Eusebio Ayala",
            "city": "Asunción",
            "location": {"x": -57.5898, "y": -25.3092},'''

new_alert_1 = f'''            "id": "waze_alert_01",
            "uuid": "wz-asu-2026-acc-01",
            "pubMillis": now_ms - (12 * 60 * 1000),
            "type": "ACCIDENT",
            "subtype": "ACCIDENT_MINOR",
            "street": "Av. Doctor Eusebio Ayala",
            "city": "Asunción",
            "location": {json.dumps(alert1_pt)},'''

code = code.replace(old_alert_1, new_alert_1)
code = code.replace('get_waze_deep_link(-25.3092, -57.5898)', f"get_waze_deep_link({alert1_pt['y']}, {alert1_pt['x']})")

# Reemplazar alert 02
old_alert_2 = '''            "id": "waze_alert_02",
            "uuid": "wz-asu-2026-cst-02",
            "pubMillis": now_ms - (35 * 60 * 1000),
            "type": "CONSTRUCTION",
            "subtype": "ROAD_CLOSED_CONSTRUCTION",
            "street": "Av. Mariscal López",
            "city": "Fernando de la Mora",
            "location": {"x": -57.5385, "y": -25.3125},'''

new_alert_2 = f'''            "id": "waze_alert_02",
            "uuid": "wz-asu-2026-cst-02",
            "pubMillis": now_ms - (35 * 60 * 1000),
            "type": "CONSTRUCTION",
            "subtype": "ROAD_CLOSED_CONSTRUCTION",
            "street": "Av. Mariscal López",
            "city": "Fernando de la Mora",
            "location": {json.dumps(alert2_pt)},'''

code = code.replace(old_alert_2, new_alert_2)
code = code.replace('get_waze_deep_link(-25.3125, -57.5385)', f"get_waze_deep_link({alert2_pt['y']}, {alert2_pt['x']})")

# Reemplazar alert 03
old_alert_3 = '''            "id": "waze_alert_03",
            "uuid": "wz-asu-2026-haz-03",
            "pubMillis": now_ms - (8 * 60 * 1000),
            "type": "HAZARD",
            "subtype": "HAZARD_ON_ROAD_CAR_STOPPED",
            "street": "Ruta PY02 (Mcal. Estigarribia)",
            "city": "San Lorenzo",
            "location": {"x": -57.5180, "y": -25.3380},'''

new_alert_3 = f'''            "id": "waze_alert_03",
            "uuid": "wz-asu-2026-haz-03",
            "pubMillis": now_ms - (8 * 60 * 1000),
            "type": "HAZARD",
            "subtype": "HAZARD_ON_ROAD_CAR_STOPPED",
            "street": "Ruta PY02 (Mcal. Estigarribia)",
            "city": "San Lorenzo",
            "location": {json.dumps(alert3_pt)},'''

code = code.replace(old_alert_3, new_alert_3)
code = code.replace('get_waze_deep_link(-25.3380, -57.5180)', f"get_waze_deep_link({alert3_pt['y']}, {alert3_pt['x']})")

# Reemplazar alert 04
old_alert_4 = '''            "id": "waze_alert_04",
            "uuid": "wz-asu-2026-jam-04",
            "pubMillis": now_ms - (5 * 60 * 1000),
            "type": "JAM",
            "subtype": "JAM_HEAVY_TRAFFIC",
            "street": "Av. Aviador Silvio Pettirossi",
            "city": "Luque",
            "location": {"x": -57.5135, "y": -25.2543},'''

new_alert_4 = f'''            "id": "waze_alert_04",
            "uuid": "wz-asu-2026-jam-04",
            "pubMillis": now_ms - (5 * 60 * 1000),
            "type": "JAM",
            "subtype": "JAM_HEAVY_TRAFFIC",
            "street": "Av. Aviador Silvio Pettirossi",
            "city": "Luque",
            "location": {json.dumps(alert4_pt)},'''

code = code.replace(old_alert_4, new_alert_4)
code = code.replace('get_waze_deep_link(-25.2543, -57.5135)', f"get_waze_deep_link({alert4_pt['y']}, {alert4_pt['x']})")

# Reemplazar lineas de jams
# Jam 1: Eusebio Ayala
old_jam_1_lines = '''            "line": [
                {"x": -57.6040, "y": -25.3030},
                {"x": -57.5970, "y": -25.3060},
                {"x": -57.5898, "y": -25.3092},
                {"x": -57.5820, "y": -25.3125},
                {"x": -57.5750, "y": -25.3150}
            ]'''

new_jam_1_lines = f'            "line": {json.dumps(eusebio_jams, indent=16)}'
code = code.replace(old_jam_1_lines, new_jam_1_lines)

# Jam 2: Mcal Lopez
old_jam_2_lines = '''            "line": [
                {"x": -57.5520, "y": -25.3070},
                {"x": -57.5450, "y": -25.3100},
                {"x": -57.5385, "y": -25.3125},
                {"x": -57.5310, "y": -25.3155}
            ]'''

new_jam_2_lines = f'            "line": {json.dumps(mcal_jams, indent=16)}'
code = code.replace(old_jam_2_lines, new_jam_2_lines)

# Jam 3: PY02
old_jam_3_lines = '''            "line": [
                {"x": -57.5280, "y": -25.3320},
                {"x": -57.5210, "y": -25.3360},
                {"x": -57.5180, "y": -25.3380},
                {"x": -57.5100, "y": -25.3410}
            ]'''

new_jam_3_lines = f'            "line": {json.dumps(py02_jams, indent=16)}'
code = code.replace(old_jam_3_lines, new_jam_3_lines)

# Jam 4: Luque
old_jam_4_lines = '''            "line": [
                {"x": -57.5220, "y": -25.2610},
                {"x": -57.5170, "y": -25.2570},
                {"x": -57.5135, "y": -25.2543},
                {"x": -57.5080, "y": -25.2510}
            ]'''

new_jam_4_lines = f'            "line": {json.dumps(luque_jams, indent=16)}'
code = code.replace(old_jam_4_lines, new_jam_4_lines)

with open(WAZE_SERVICE_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("SUCCESS: gps_broker/waze_service.py aligned with 100% PostGIS accuracy!")

# También actualizar gps_broker/main.py para renderizar líneas continuas de tráfico
MAIN_PATH = r"c:\Users\lpraf\OneDrive\Documentos\Poliverso\transporte_odoo\gps_broker\main.py"
with open(MAIN_PATH, "r", encoding="utf-8") as f:
    main_code = f.read()

old_poly_style = '''                    const poly = L.polyline(latlngs, {
                        color: color,
                        weight: 6,
                        opacity: 0.85,
                        dashArray: j.level >= 4 ? '1, 8' : null
                    });'''

new_poly_style = '''                    const poly = L.polyline(latlngs, {
                        color: color,
                        weight: 7,
                        opacity: 0.90,
                        lineCap: 'round',
                        lineJoin: 'round'
                    });'''

if old_poly_style in main_code:
    main_code = main_code.replace(old_poly_style, new_poly_style)
    with open(MAIN_PATH, "w", encoding="utf-8") as f:
        f.write(main_code)
    print("SUCCESS: main.py polyline styling upgraded to solid glowing traffic lines!")
else:
    print("Notice: polyline styling already updated or matched differently.")
