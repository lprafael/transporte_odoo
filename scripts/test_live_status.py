import urllib.request
import json

req = urllib.request.urlopen('http://localhost:8088/api/v1/live')
data = json.loads(req.read().decode('utf-8'))
print(f"Total vehículos recibidos: {data['count']}")

for v in data['vehicles']:
    b_id = v.get('bus_id')
    if b_id in ('00008', '00011'):
        print(f"[REVISIÓN] Bus {b_id}: Estado={v.get('state')} | FallaGPS={v.get('is_gps_fault')} | Vel={v.get('speed_kmh')} km/h | MinutosSinSeñal={v.get('minutes_since_ping')} | Status={v.get('status_display')}")
    elif b_id in ('00005', '00012'):
        print(f"[ACTIVO]   Bus {b_id}: Estado={v.get('state')} | FallaGPS={v.get('is_gps_fault')} | Vel={v.get('speed_kmh')} km/h | MinutosSinSeñal={v.get('minutes_since_ping')} | Status={v.get('status_display')}")
