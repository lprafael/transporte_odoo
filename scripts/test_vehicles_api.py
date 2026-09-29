import urllib.request
import json

print("=== CHECKING /api/v1/live ===")
url = 'http://localhost:8088/api/v1/live'
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    vehicles = data.get('vehicles', [])

for v in vehicles:
    print(f"Bus {v.get('bus_id')}: Route={v.get('route_id')} | State={v.get('current_state')} | Geofence={v.get('current_geofence_name')} | Prog={v.get('progress_percent')}% ({v.get('distance_traveled_km')} km) | Vel={v.get('speed_kmh')} km/h")
