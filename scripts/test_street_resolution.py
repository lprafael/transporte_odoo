import urllib.request
import json
import redis
import time

import os
redis_host = os.getenv('REDIS_HOST', 'redis')
r = redis.Redis(host=redis_host, port=6379, decode_responses=True)
keys = r.keys('vehicle:*')

print(f"Testing street resolution for {len(keys)} active buses...\n")

headers = {'User-Agent': 'PoliversoTransitOdoo/1.0 (lpraf@poliverso.com)'}

for k in keys:
    val = r.get(k)
    if not val:
        continue
    bus = json.loads(val)
    bus_id = bus.get('bus_id')
    state = bus.get('current_state')
    route_id = bus.get('route_id')
    lat = bus.get('last_latitude')
    lon = bus.get('last_longitude')
    pct = bus.get('progress_percent')
    dist_km = bus.get('distance_traveled_km')
    speed = bus.get('last_speed_kmh')

    if state != 'IN_TRANSIT':
        print(f"Bus {bus_id} ({route_id}): State={state} -> Not in circulation.")
        continue

    # Query Nominatim
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            addr = data.get('address', {})
            road = addr.get('road') or addr.get('pedestrian') or addr.get('highway') or 'Itinerario Principal'
            
            # Check for cross street or suburb/point
            cross = addr.get('highway') if addr.get('highway') != road else None
            if not cross:
                cross = addr.get('junction') or addr.get('suburb') or addr.get('neighbourhood') or 'Próxima Parada'
            
            street_status = f"Circulando ({road} aproximándose a {cross})"
            print(f"Bus {bus_id} ({route_id}) [km {dist_km}, {pct}%]:")
            print(f"   -> {street_status}")
        time.sleep(1.0) # Respect rate limit
    except Exception as e:
        print(f"Error resolving {bus_id}: {e}")
