import urllib.request
import json

url = 'http://localhost:8088/api/v1/headway/data'
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))

print("Total Active Buses:", data.get('total_active_buses'))
print("Total Bunching Alerts:", data.get('total_bunching_alerts'))
print("\n--- Routes in Headway Dashboard ---")
for r in data.get('routes', []):
    print(f"[{r['route_id'].upper()}] {r['name']}")
    print(f"    Sentido: {r['direction_label']} ({r['direction']})")
    print(f"    0.0 km:  {r['origin']}")
    print(f"    {r['distance_km']} km: {r['destination']}")
    print(f"    Buses:   {len(r['buses'])}")
    for b in r.get('buses', []):
        print(f"      -> 🚌 {b['bus_id']}: {b.get('state_label')} (km {b['distance_traveled_km']})")
    print()
