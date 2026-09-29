#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-evalúa el estado operativo de todos los vehículos activos en Redis según su
progreso real en el trazado shape, desvío y velocidad.
"""

import os
import json
import redis

redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
keys = r.keys('vehicle:*')

print(f"[*] Encontrados {len(keys)} vehículos en Redis para re-evaluación...")

updated = 0
for k in keys:
    val = r.get(k)
    if not val:
        continue
    bus = json.loads(val)
    bus_id = bus.get('bus_id')
    route_id = (bus.get('route_id') or '').lower()
    pct = float(bus.get('progress_percent') or 0.0)
    dist_km = float(bus.get('distance_traveled_km') or 0.0)
    total_km = float(bus.get('route_total_km') or 0.0)
    dev_m = float(bus.get('deviation_meters') or 0.0)
    speed = float(bus.get('last_speed_kmh') or bus.get('speed_kmh') or 0.0)
    
    old_state = bus.get('current_state')
    
    # Evaluación de estado
    if route_id in ('0000', '', 'depot', 'taller'):
        new_state = 'DEPOT'
        geofence = 'En Depósito / Patio'
    elif dev_m > 400.0:
        new_state = 'OFF_ROUTE'
        geofence = f'Desviado ({round(dev_m)}m)'
    elif pct >= 97.5 or (total_km > 0 and (total_km - dist_km) <= 0.35):
        new_state = 'AT_DESTINATION'
        geofence = 'Terminal Llegada'
    elif (pct < 2.5 or dist_km < 0.35) and speed < 5.0:
        new_state = 'AT_ORIGIN'
        geofence = 'En Cabecera (Origen)'
    else:
        new_state = 'IN_TRANSIT'
        geofence = 'En Itinerario'

    bus['current_state'] = new_state
    bus['state'] = new_state
    bus['current_geofence_name'] = geofence
    bus['geofence_name'] = geofence
    
    r.set(k, json.dumps(bus))
    updated += 1
    print(f"  [+] Bus {bus_id} ({route_id}): {old_state} -> {new_state} (Progreso: {pct}% | Dist: {dist_km} km | Vel: {speed} km/h)")

print(f"\n[OK] Se actualizaron {updated} vehículos en Redis.")
