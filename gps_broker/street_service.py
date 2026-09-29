# -*- coding: utf-8 -*-
"""
Servicio de Localización Contextual de Calles e Intersecciones para Transporte Público.
Resuelve en tiempo real la calle actual y la próxima intersección que el bus está aproximando:
Ejemplo: "Circulando (Av. Mcal. López aproximándose a P. Villamayor)"

Características:
1. Cache en memoria y Redis por cuadrícula geoespacial (~100m) para latencia sub-milisegundo.
2. Indexación en memoria de las 340 paradas oficiales CID sincronizadas en PostGIS.
3. Formateo y abreviatura de calles habituales del Gran Asunción.
"""

import os
import re
import json
import logging
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("street_service")

# Abreviaturas y normalización para el Gran Asunción
ROAD_REPLACEMENTS = [
    (r"\bAvenida Mariscal Francisco Solano L[oó]pez\b", "Av. Mcal. López"),
    (r"\bAvenida Aviadores del Chaco\b", "Av. Aviadores del Chaco"),
    (r"\bAvenida Eusebio Ayala\b", "Av. Eusebio Ayala"),
    (r"\bAvenida España\b", "Av. España"),
    (r"\bAvenida del Agr[oó]nomo\b", "Av. del Agrónomo"),
    (r"\bRuta Nacional Mariscal Estigarribia\b", "Ruta PY02 (Mcal. Estigarribia)"),
    (r"\bF[eé]lix de Azara\b", "Calle Azara"),
    (r"\bAvenida\b", "Av."),
    (r"\bGeneral\b", "Gral."),
    (r"\bCoronel\b", "Cnel."),
    (r"\bMariscal\b", "Mcal."),
]

def clean_road_name(name: str) -> str:
    if not name:
        return "Itinerario Principal"
    cleaned = name.strip()
    for pattern, repl in ROAD_REPLACEMENTS:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(Bus.*?\)", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def clean_cross_street(raw_name: str, current_road: str = "") -> str:
    if not raw_name:
        return ""
    name = raw_name.strip()
    name = re.sub(r"\s*\(Bus.*?\)", "", name, flags=re.IGNORECASE)
    
    # Si es solo una lista de líneas de bus, no es un nombre de calle
    if name.lower().startswith("bus línea") or name.lower().startswith("bus linea") or name.lower().startswith("línea ") or name.lower().startswith("linea "):
        return ""
    if any(c.isdigit() for c in name[:3]) and (',' in name or '-' in name):
        return ""

    if " esq. " in name.lower():
        parts = re.split(r"\s+esq\.?\s+", name, flags=re.IGNORECASE)
        name = parts[1] if len(parts) > 1 else parts[0]
    elif " y " in name.lower():
        parts = re.split(r"\s+y\s+", name, flags=re.IGNORECASE)
        # Si la primera parte coincide con la calle actual, usar la segunda
        if len(parts) > 1:
            name = parts[1]
    elif " casi " in name.lower():
        parts = re.split(r"\s+casi\s+", name, flags=re.IGNORECASE)
        if len(parts) > 1:
            name = parts[1]

    name = clean_road_name(name)
    if not name or len(name) < 3 or name.lower() in ("parada", "parada urbana", "bus_stop", "parada interurbana", "itinerario principal"):
        return ""
    return name

class StreetResolver:
    def __init__(self, pg_host: str, pg_port: int, pg_db: str, pg_user: str, pg_pass: str, redis_client=None):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_db = pg_db
        self.pg_user = pg_user
        self.pg_pass = pg_pass
        self.redis = redis_client
        self.memory_grid_cache: Dict[str, str] = {}
        self.route_stops_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.load_route_stops()

    def load_route_stops(self):
        """Carga en memoria las paradas oficiales de cada ramal ordenadas por km."""
        try:
            conn = psycopg2.connect(
                host=self.pg_host, port=self.pg_port, dbname=self.pg_db,
                user=self.pg_user, password=self.pg_pass, connect_timeout=3
            )
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT 
                    r.code as route_code,
                    s.name as stop_name,
                    rs.sequence,
                    rs.distance_from_origin_km as km,
                    ST_Y(s.geom) as lat,
                    ST_X(s.geom) as lon
                FROM transit_route_stop rs
                JOIN transit_stop s ON rs.stop_id = s.id
                JOIN transit_route_shape sh ON rs.route_shape_id = sh.id
                JOIN transit_route r ON sh.route_id = r.id
                WHERE sh.valid_until IS NULL OR sh.valid_until > CURRENT_DATE
                ORDER BY r.code, rs.distance_from_origin_km ASC;
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            new_cache = {}
            for r in rows:
                code = (r['route_code'] or '').lower()
                if code not in new_cache:
                    new_cache[code] = []
                new_cache[code].append({
                    'name': r['stop_name'],
                    'sequence': r['sequence'],
                    'km': float(r['km'] or 0.0),
                    'lat': r['lat'],
                    'lon': r['lon']
                })
            self.route_stops_cache = new_cache
            logger.info(f"Cargadas {len(rows)} paradas oficiales en memoria para {len(self.route_stops_cache)} ramales.")
        except Exception as e:
            logger.warning(f"Error cargando paradas en street_service: {e}")

    def get_road_name(self, lat: float, lon: float) -> str:
        """Obtiene el nombre de la calle con caché por cuadrícula (~100m)."""
        grid_key = f"{round(lat, 3)}:{round(lon, 3)}"
        
        # 1. Caché en memoria
        if grid_key in self.memory_grid_cache:
            return self.memory_grid_cache[grid_key]

        # 2. Caché en Redis
        redis_key = f"street_grid:{grid_key}"
        if self.redis:
            try:
                cached = self.redis.get(redis_key)
                if cached:
                    self.memory_grid_cache[grid_key] = cached
                    return cached
            except Exception:
                pass

        # 3. Geocodificación inversa vía Nominatim
        road_name = "Itinerario Principal"
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'PoliversoTransitOdoo/1.0 (info@poliverso.com)'})
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                addr = data.get('address', {})
                raw_road = addr.get('road') or addr.get('pedestrian') or addr.get('highway') or 'Itinerario Principal'
                road_name = clean_road_name(raw_road)
        except Exception as e:
            logger.debug(f"Aviso geocoding {grid_key}: {e}")

        # Guardar en cachés
        self.memory_grid_cache[grid_key] = road_name
        if self.redis:
            try:
                self.redis.setex(redis_key, 86400 * 30, road_name) # 30 días TTL
            except Exception:
                pass

        return road_name

    def get_approaching_street(self, route_code: str, distance_km: float, current_road: str = "") -> str:
        """Encuentra la próxima intersección o parada oficial por delante del bus."""
        code = (route_code or '').lower()
        stops = self.route_stops_cache.get(code, [])
        if not stops:
            return "Próxima Parada"

        # Buscar la primera parada nombrada que esté por delante
        for s in stops:
            if s['km'] >= (distance_km - 0.02):
                cleaned = clean_cross_street(s['name'], current_road)
                if cleaned and cleaned != current_road:
                    return cleaned

        return "Cabecera Final"

    def format_bus_status(
        self,
        current_state: str,
        route_code: str,
        lat: float,
        lon: float,
        distance_km: float,
        speed_kmh: float,
        deviation_meters: float = 0.0,
        origin_name: str = "Cabecera Origen",
        dest_name: str = "Terminal Destino"
    ) -> Dict[str, str]:
        """
        Retorna el estado operativo enriquecido con calle e intersección.
        """
        if current_state == "AT_ORIGIN":
            return {
                "state": "AT_ORIGIN",
                "state_short": "En Cabecera",
                "street_name": origin_name,
                "approaching": "",
                "status_display": f"En Cabecera ({origin_name})"
            }

        if current_state == "AT_DESTINATION":
            return {
                "state": "AT_DESTINATION",
                "state_short": "En Destino",
                "street_name": dest_name,
                "approaching": "",
                "status_display": f"En Destino ({dest_name})"
            }

        if current_state == "DEPOT":
            return {
                "state": "DEPOT",
                "state_short": "En Depósito",
                "street_name": "Patio de Maniobras",
                "approaching": "",
                "status_display": "En Depósito / Taller"
            }

        if current_state == "OFF_ROUTE":
            return {
                "state": "OFF_ROUTE",
                "state_short": "Desviado",
                "street_name": "Fuera de Itinerario",
                "approaching": "",
                "status_display": f"Desviado ({round(deviation_meters)}m fuera de trazado)"
            }

        # Estado IN_TRANSIT (En Circulación)
        road = self.get_road_name(lat, lon)
        approaching = self.get_approaching_street(route_code, distance_km, road)

        status_display = f"Circulando ({road} aproximándose a {approaching})"

        return {
            "state": "IN_TRANSIT",
            "state_short": "En Circulación",
            "street_name": road,
            "approaching": approaching,
            "status_display": status_display
        }
