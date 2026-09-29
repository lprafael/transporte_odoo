#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enriquece todos los vehículos en Redis con su calle e intersección actual ("Circulando (Calle X aproximándose a Calle Y)").
"""

import os
import sys
import json
import redis

sys.path.append("/app")
from street_service import StreetResolver

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
resolver = StreetResolver(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS, r)

keys = r.keys("vehicle:*")
print(f"[*] Enriqueciendo {len(keys)} vehículos en Redis con calles e intersecciones...")

for k in keys:
    val = r.get(k)
    if not val:
        continue
    bus = json.loads(val)
    bus_id = bus.get("bus_id")
    route_id = bus.get("route_id", "")
    state = bus.get("current_state", "IN_TRANSIT")
    lat = bus.get("last_latitude", 0.0)
    lon = bus.get("last_longitude", 0.0)
    dist_km = float(bus.get("distance_traveled_km") or 0.0)
    speed = float(bus.get("last_speed_kmh") or 0.0)
    dev_m = float(bus.get("deviation_meters") or 0.0)

    st_info = resolver.format_bus_status(
        current_state=state,
        route_code=route_id,
        lat=lat,
        lon=lon,
        distance_km=dist_km,
        speed_kmh=speed,
        deviation_meters=dev_m
    )

    bus["status_display"] = st_info["status_display"]
    bus["street_name"] = st_info["street_name"]
    bus["approaching"] = st_info["approaching"]

    r.set(k, json.dumps(bus), ex=86400)
    print(f"  [+] Bus {bus_id} ({route_id}) -> {st_info['status_display']}")

print("\n[OK] Vehículos enriquecidos exitosamente.")
