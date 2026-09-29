# -*- coding: utf-8 -*-
"""
Microservicio Broker & Ingestor de Telemetría GPS para Flota de Buses (Producción 100%)
Estándar: Resolución GVMT N° 065/2024 (Paraguay)

Características Integrales:
1. Ingesta Multi-Protocolo:
   - HTTP/REST con token seguro (X-Device-Token)
   - MQTT con Mosquitto y autenticación
   - Payloads Protobuf v3 binarios y JSON
2. Motor Geoespacial PostGIS:
   - Shapes de rutas (LineString) con vigencia histórica bi-temporal (valid_from / valid_until)
   - Paradas oficiales y geocercas circulares (WGS84)
   - Cálculo en tiempo real de % recorrido y desviación respecto a la traza oficial
   - Vinculación automática (trigger) de cada ping con su versión de shape
3. Almacenamiento y Caché:
   - Redis para estado de flota de ultra-baja latencia y pub/sub
   - PostgreSQL particionado mensual (telemetry_ping) para histórico masivo
4. Integración ERP Odoo 18:
   - Webhook garantizado con reintentos y Exponential Backoff
5. Radar Web en Vivo (/map):
   - WebSocket de 0ms con fallback de polling
   - Renderizado de trazas de ruta, paradas, desvíos y selector de vigencia histórica
"""

import os
import math
import time
import json
import asyncio
import logging
import threading
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Set

import requests
import psycopg2
from psycopg2.extras import execute_values
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gps_broker")

app = FastAPI(
    title="Broker de Telemetría GPS & PostGIS Shapes (Resolución GVMT 065/2024)",
    description="Servicio integral: Ingesta MQTT/Protobuf, Motor de Geocercas PostGIS, ETA Predictivo por Parada, Cumplimiento VMT (Res. 065/2024), Detector de Pegonamiento y WebSockets",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Configuración de Entorno
# ------------------------------------------------------------------------------
ODOO_URL = os.getenv("ODOO_URL", "http://web:8069")
ODOO_API_TOKEN = os.getenv("ODOO_API_TOKEN", "GPS_SECRET_KEY_2026")
DEVICE_API_TOKEN = os.getenv("DEVICE_API_TOKEN", "GPS_DEVICE_SECRET_2026")
SPEED_LIMIT_KMH = float(os.getenv("SPEED_LIMIT_KMH", "70.0"))
MAX_DEVIATION_METERS = float(os.getenv("MAX_DEVIATION_METERS", "400.0"))

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "gps_device")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "GPS_DEVICE_SECRET_2026")
CARTO_API_KEY = os.getenv("CARTO_API_KEY", "cb1_3skd_1_b01311b843bcb7fb316c4384")

# ------------------------------------------------------------------------------
# Conexión Redis (Estado en Tiempo Real)
# ------------------------------------------------------------------------------
redis_client = None
try:
    import redis
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    redis_client.ping()
    logger.info("Conectado exitosamente a Redis para almacenamiento de estado en tiempo real.")
except Exception as e:
    logger.warning(f"No se pudo conectar a Redis ({REDIS_URL}): {e}. Operando con memoria local de respaldo.")
    redis_client = None

# Inicialización de StreetResolver para contextualización de calles
from street_service import StreetResolver
street_resolver: Optional[StreetResolver] = None
try:
    street_resolver = StreetResolver(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS, redis_client)
except Exception as e:
    logger.warning(f"No se pudo inicializar StreetResolver: {e}")

active_vehicles_memory: Dict[str, Dict[str, Any]] = {}
event_history_memory: List[Dict[str, Any]] = []
routes_cache: List[Dict[str, Any]] = []

def get_vehicle_state(bus_id: str) -> Optional[Dict[str, Any]]:
    if redis_client:
        try:
            data = redis_client.get(f"vehicle:{bus_id}")
            if data:
                res = json.loads(data)
                res["crossed_checkpoints"] = set(res.get("crossed_checkpoints", []))
                return res
        except Exception as e:
            logger.debug(f"Redis get error: {e}")
    return active_vehicles_memory.get(bus_id)

def save_vehicle_state(bus_id: str, state: Dict[str, Any]):
    active_vehicles_memory[bus_id] = state
    if redis_client:
        try:
            serializable = dict(state)
            serializable["crossed_checkpoints"] = list(state.get("crossed_checkpoints", []))
            redis_client.set(f"vehicle:{bus_id}", json.dumps(serializable), ex=86400)
            redis_client.sadd("active_buses_set", bus_id)
        except Exception as e:
            logger.debug(f"Redis set error: {e}")

def format_vehicle_for_client(v: Dict[str, Any]) -> Dict[str, Any]:
    lat = v.get("latitude") if v.get("latitude") is not None else v.get("last_latitude")
    lon = v.get("longitude") if v.get("longitude") is not None else v.get("last_longitude")
    speed = v.get("speed_kmh") if v.get("speed_kmh") is not None else v.get("last_speed_kmh", 0.0)
    state = v.get("state") or v.get("current_state") or "IN_TRANSIT"
    checkpoints = v.get("crossed_checkpoints", [])
    if isinstance(checkpoints, set):
        checkpoints = list(checkpoints)
    return {
        "bus_id": v.get("bus_id"),
        "license_plate": v.get("license_plate") or f"COCHE-{v.get('bus_id')}",
        "agency_id": v.get("agency_id", "004B"),
        "route_id": v.get("route_id", ""),
        "state": state,
        "current_state": state,
        "status_display": v.get("status_display") or ("En Circulación" if state == "IN_TRANSIT" else state),
        "street_name": v.get("street_name", ""),
        "approaching": v.get("approaching", ""),
        "latitude": lat,
        "longitude": lon,
        "last_latitude": lat,
        "last_longitude": lon,
        "speed_kmh": speed,
        "last_speed_kmh": speed,
        "heading_deg": v.get("heading_deg", 0.0),
        "odometer_km": v.get("odometer_km", 0.0),
        "last_ping_time": v.get("last_ping_time", ""),
        "geofence_name": v.get("current_geofence_name", "En Ruta"),
        "current_geofence_name": v.get("current_geofence_name", "En Ruta"),
        "speed_alert": bool(v.get("speed_alert", False)),
        "deviation_alert": bool(v.get("deviation_alert", False)),
        "progress_percent": v.get("progress_percent", 0.0),
        "distance_traveled_km": v.get("distance_traveled_km", 0.0),
        "route_total_km": v.get("route_total_km", 0.0),
        "deviation_meters": v.get("deviation_meters", 0.0),
        "crossed_checkpoints": checkpoints
    }

def get_all_active_vehicles() -> List[Dict[str, Any]]:
    vehicles = []
    if redis_client:
        try:
            bus_ids = redis_client.smembers("active_buses_set")
            for b_id in bus_ids:
                v = get_vehicle_state(b_id)
                if v:
                    vehicles.append(format_vehicle_for_client(v))
            if vehicles:
                return vehicles
        except Exception as e:
            logger.debug(f"Redis smembers error: {e}")
    out = []
    for v in active_vehicles_memory.values():
        out.append(format_vehicle_for_client(v))
    return out

def record_event_history(event: Dict[str, Any]):
    event_history_memory.append(event)
    if len(event_history_memory) > 100:
        event_history_memory.pop(0)
    if redis_client:
        try:
            redis_client.lpush("transit_events_log", json.dumps(event))
            redis_client.ltrim("transit_events_log", 0, 49)
        except Exception as e:
            logger.debug(f"Redis event log error: {e}")

# ------------------------------------------------------------------------------
# Gestor de WebSockets (Radar en Vivo)
# ------------------------------------------------------------------------------
class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Nuevo cliente WebSocket conectado. Total activos: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"Cliente WebSocket desconectado. Total activos: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        dead_connections = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead_connections.add(conn)
        for dead in dead_connections:
            self.active_connections.discard(dead)

ws_manager = WebSocketManager()

# ------------------------------------------------------------------------------
# Modelos de Datos
# ------------------------------------------------------------------------------
class TelemetryPing(BaseModel):
    bus_id: Optional[str] = Field(None, example="104")
    mean_id: Optional[str] = Field(None, example="00016")
    agency_id: Optional[str] = Field(None, example="004B")
    route_id: Optional[str] = Field(None, example="020f")
    driver_id: Optional[str] = Field(None, example="")
    license_plate: Optional[str] = Field(None, example="ABC 123")
    latitude: float = Field(..., example=-25.3148)
    longitude: float = Field(..., example=-57.5932)
    altitud: Optional[float] = Field(0.0)
    precision: Optional[int] = Field(None)
    speed_kmh: Optional[float] = Field(None, example=35.5)
    velocidad: Optional[float] = Field(None, example=35.5)
    heading_deg: Optional[float] = Field(None, example=95.0)
    rumbo: Optional[float] = Field(None, example=95.0)
    odometer_km: Optional[float] = Field(0.0)
    timestamp: Optional[str] = Field(None)
    fecha_hora: Optional[str] = Field(None)
    type: Optional[int] = Field(None)
    usuario_broker: Optional[str] = Field(None)

    @property
    def effective_bus_id(self) -> str:
        return str(self.mean_id or self.bus_id or "BUS-UNKNOWN")

    @property
    def effective_license_plate(self) -> str:
        if self.license_plate:
            return self.license_plate
        return f"COCHE-{self.effective_bus_id}"

    @property
    def effective_speed(self) -> float:
        if self.velocidad is not None:
            return float(self.velocidad)
        if self.speed_kmh is not None:
            return float(self.speed_kmh)
        return 0.0

    @property
    def effective_heading(self) -> float:
        if self.rumbo is not None:
            return float(self.rumbo)
        if self.heading_deg is not None:
            return float(self.heading_deg)
        return 0.0

    @property
    def effective_timestamp(self) -> str:
        return self.fecha_hora or self.timestamp or datetime.now(timezone.utc).isoformat()

# ------------------------------------------------------------------------------
# Motor Geodésico Espacial (Haversine & PostGIS)
# ------------------------------------------------------------------------------
def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def calculate_shape_progress(lat: float, lon: float, route_code: str, agency_id: str = "004B") -> Optional[Dict[str, Any]]:
    """Calcula con PostGIS el porcentaje del recorrido completado y la distancia al trazado oficial."""
    if not route_code:
        return None
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=1
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT progress_percent, distance_traveled_km, total_km, deviation_meters FROM get_bus_route_progress(%s, %s, %s, %s)",
            (lat, lon, route_code, agency_id)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "progress_percent": float(row[0]) if row[0] is not None else 0.0,
                "distance_traveled_km": float(row[1]) if row[1] is not None else 0.0,
                "total_km": float(row[2]) if row[2] is not None else 0.0,
                "deviation_meters": float(row[3]) if row[3] is not None else 0.0,
            }
    except Exception as e:
        logger.debug(f"Aviso PostGIS progress: {e}")
    return None

def insert_telemetry_to_pg(ping: TelemetryPing):
    """Guarda el ping en PostgreSQL. El trigger asigna automáticamente geometría y shape_id vigente."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        recorded_at = ping.effective_timestamp
        op_type = ping.type if ping.type is not None else 2
        acc = ping.precision
        alt = ping.altitud or 0.0
        heading = ping.effective_heading
        cur.execute(
            """
            INSERT INTO telemetry_ping 
                (bus_internal_code, license_plate, recorded_at, latitude, longitude, speed_kmh, heading_degrees, odometer_km, agency_id, route_id, driver_id, precision, operation_type, accuracy_m, altitude_m, heading_deg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ping.effective_bus_id,
                ping.effective_license_plate,
                recorded_at,
                ping.latitude,
                ping.longitude,
                ping.effective_speed,
                heading,
                ping.odometer_km or 0.0,
                ping.agency_id or "004B",
                ping.route_id or "",
                ping.driver_id or "",
                acc,
                op_type,
                acc,
                alt,
                heading
            )
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.debug(f"Aviso: Inserción en PostgreSQL diferida: {e}")

# ------------------------------------------------------------------------------
# Consultas GeoJSON de Shapes y Paradas con Vigencia
# ------------------------------------------------------------------------------
def get_active_shapes_geojson() -> Dict[str, Any]:
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(ST_AsGeoJSON(t.*)::json), '[]'::json)
            )
            FROM (
                SELECT 
                    s.id AS shape_id,
                    r.code AS route_code,
                    r.name AS route_name,
                    r.agency_id,
                    r.direction,
                    s.version,
                    s.valid_from::TEXT,
                    s.valid_until::TEXT,
                    s.total_km,
                    s.geom
                FROM transit_route r
                JOIN transit_route_shape s ON s.route_id = r.id
                WHERE s.valid_from <= CURRENT_DATE
                  AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
            ) t;
            """
        )
        geojson = cur.fetchone()[0]
        cur.close()
        conn.close()
        return geojson
    except Exception as e:
        logger.error(f"Error cargando active shapes GeoJSON: {e}")
        return {"type": "FeatureCollection", "features": []}

def get_historical_shape_geojson(route_code: str, agency_id: str, target_date: str) -> Dict[str, Any]:
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(ST_AsGeoJSON(t.*)::json), '[]'::json)
            )
            FROM (
                SELECT 
                    shape_id,
                    route_code,
                    route_name,
                    valid_from::TEXT,
                    valid_until::TEXT,
                    total_km,
                    geom
                FROM get_route_shape_at_date(%s, %s, %s::DATE)
            ) t;
            """,
            (route_code, agency_id, target_date)
        )
        geojson = cur.fetchone()[0]
        cur.close()
        conn.close()
        return geojson
    except Exception as e:
        logger.error(f"Error cargando historical shape GeoJSON: {e}")
        return {"type": "FeatureCollection", "features": []}

def get_active_stops_geojson() -> Dict[str, Any]:
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(ST_AsGeoJSON(t.*)::json), '[]'::json)
            )
            FROM (
                SELECT 
                    id,
                    stop_code,
                    name,
                    stop_type,
                    agency_id,
                    radius_meters,
                    address,
                    geom
                FROM transit_stop
                WHERE valid_from <= CURRENT_DATE
                  AND (valid_until IS NULL OR valid_until > CURRENT_DATE)
            ) t;
            """
        )
        geojson = cur.fetchone()[0]
        cur.close()
        conn.close()
        return geojson
    except Exception as e:
        logger.error(f"Error cargando active stops GeoJSON: {e}")
        return {"type": "FeatureCollection", "features": []}

# ------------------------------------------------------------------------------
# Cola de Reintentos con Exponential Backoff para Odoo Webhook
# ------------------------------------------------------------------------------
def dispatch_odoo_webhook_with_retry(event_payload: Dict[str, Any], max_retries: int = 3):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ODOO_API_TOKEN}"
    }
    url = f"{ODOO_URL}/api/v1/transit/events"
    
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(url, json=event_payload, headers=headers, timeout=5.0)
            if res.status_code == 200:
                logger.info(f"Webhook entregado a Odoo [200]: {event_payload.get('event_type')} para Bus #{event_payload.get('internal_number')}")
                return True
        except Exception as e:
            logger.debug(f"Aviso Odoo Webhook (Intento {attempt}/{max_retries}): {e}")
        
        if attempt < max_retries:
            time.sleep(2 ** attempt)
            
    return False

# ------------------------------------------------------------------------------
# Sincronización de Geocercas (PostGIS & Odoo)
# ------------------------------------------------------------------------------
def sync_geofences_from_postgis():
    global routes_cache
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 
                r.id AS route_id, r.code, r.name,
                r.origin AS origin_name, r.destination AS destination_name,
                COALESCE(r.origin_latitude, ST_Y(ST_StartPoint(sh.geom))) as orig_lat,
                COALESCE(r.origin_longitude, ST_X(ST_StartPoint(sh.geom))) as orig_lon,
                COALESCE(r.destination_latitude, ST_Y(ST_EndPoint(sh.geom))) as dest_lat,
                COALESCE(r.destination_longitude, ST_X(ST_EndPoint(sh.geom))) as dest_lon
            FROM transit_route r
            JOIN transit_route_shape sh ON sh.route_id = r.id AND (sh.valid_until IS NULL OR sh.valid_until > CURRENT_DATE)
            WHERE r.active = TRUE OR r.active IS NULL
            ORDER BY r.code;
            """
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if rows:
            loaded_routes = []
            for r_id, code, name, orig_name, dest_name, o_lat, o_lon, d_lat, d_lon in rows:
                orig = {
                    "name": orig_name or "Cabecera Origen",
                    "latitude": float(o_lat) if o_lat is not None else None,
                    "longitude": float(o_lon) if o_lon is not None else None,
                    "radius_meters": 400
                }
                dest = {
                    "name": dest_name or "Terminal Destino",
                    "latitude": float(d_lat) if d_lat is not None else None,
                    "longitude": float(d_lon) if d_lon is not None else None,
                    "radius_meters": 400
                }
                loaded_routes.append({
                    "id": r_id,
                    "code": code,
                    "name": name,
                    "origin": orig,
                    "destination": dest,
                    "checkpoints": [orig, dest]
                })
            routes_cache = loaded_routes
            logger.info(f"Cargadas {len(routes_cache)} rutas con paradas directamente desde PostGIS.")
            return True
    except Exception as e:
        logger.warning(f"No se pudieron cargar geocercas desde PostGIS: {e}")
    return False

def sync_geofences_from_odoo():
    global routes_cache
    url = f"{ODOO_URL}/api/v1/transit/active_routes_geofences"
    headers = {"Authorization": f"Bearer {ODOO_API_TOKEN}"}
    try:
        res = requests.get(url, headers=headers, timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            routes = data.get("routes", [])
            if routes:
                routes_cache = routes
                logger.info(f"Sincronizadas {len(routes_cache)} rutas con geocercas desde Odoo.")
                return True
    except Exception as e:
        logger.debug(f"Aviso Odoo geocercas sync: {e}")
    return sync_geofences_from_postgis()

@app.on_event("startup")
def startup_event():
    logger.info("🚀 Iniciando Broker GPS con Redis, PostgreSQL, PostGIS y WebSockets...")
    sync_geofences_from_postgis()

    # Iniciar Consumidor Mosquitto MQTT en hilo desacoplado
    try:
        from mqtt_consumer import start_consumer_thread
        start_consumer_thread()
        logger.info("✅ Consumidor MQTT Mosquitto iniciado en background.")
    except Exception as e:
        logger.warning(f"No se pudo iniciar el consumidor MQTT: {e}")

# ------------------------------------------------------------------------------
# Endpoints de Telemetría (Ingesta HTTP & MQTT)
# ------------------------------------------------------------------------------
@app.post("/api/v1/telemetry")
@app.post("/telemetry/gps")
@app.post("/api/v1/vmt/telemetry")
async def receive_telemetry(
    ping: TelemetryPing, 
    background_tasks: BackgroundTasks,
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token")
):
    bus_key = ping.effective_bus_id
    now_iso = ping.effective_timestamp
    speed = ping.effective_speed
    heading = ping.effective_heading
    plate = ping.effective_license_plate

    # 1. Validación de Token
    if DEVICE_API_TOKEN and x_device_token != DEVICE_API_TOKEN:
        raise HTTPException(status_code=401, detail="Dispositivo no autorizado. Provea X-Device-Token válido.")

    # 1.1 Validación de Coordenadas Geográficas (Res. GVMT 065/2024 Sección 5.1)
    if (abs(ping.latitude) < 1e-6 and abs(ping.longitude) < 1e-6) or not (-90.0 <= ping.latitude <= 90.0) or not (-180.0 <= ping.longitude <= 180.0):
        logger.warning(f"Coordenadas descartadas (inválidas o 0,0): ({ping.latitude}, {ping.longitude}) para móvil {bus_key}")
        return {"status": "ignored", "reason": "invalid_coordinates", "bus_id": bus_key}

    # Bandera de baja precisión GPS (>50m según Res. GVMT 065/2024 Sección 5.1)
    is_low_accuracy = bool(ping.precision and ping.precision > 50)

    # 2. Recuperar o Inicializar Estado
    v_state = get_vehicle_state(bus_key)
    if not v_state:
        v_state = {
            "bus_id": bus_key,
            "license_plate": plate,
            "agency_id": ping.agency_id or "004B",
            "route_id": ping.route_id or "020f",
            "current_state": "AT_ORIGIN",
            "crossed_checkpoints": set(),
            "last_latitude": ping.latitude,
            "last_longitude": ping.longitude,
            "last_speed_kmh": speed,
            "heading_deg": heading,
            "odometer_km": ping.odometer_km or 0.0,
            "last_ping_time": now_iso,
            "speed_alert": False,
            "deviation_alert": False,
            "current_geofence_name": "Terminal Origen",
            "progress_percent": 0.0,
            "distance_traveled_km": 0.0,
            "route_total_km": 0.0,
            "deviation_meters": 0.0,
        }

    v_state["last_latitude"] = ping.latitude
    v_state["last_longitude"] = ping.longitude
    v_state["last_speed_kmh"] = speed
    v_state["heading_deg"] = heading
    if ping.route_id:
        v_state["route_id"] = ping.route_id
    if ping.agency_id:
        v_state["agency_id"] = ping.agency_id
    if ping.odometer_km:
        v_state["odometer_km"] = ping.odometer_km
    v_state["last_ping_time"] = now_iso

    # 3. Guardado Asíncrono en PostgreSQL
    background_tasks.add_task(insert_telemetry_to_pg, ping)

    # 4. Cálculo PostGIS de Progreso en Ruta y Desvío Exacto
    progress = calculate_shape_progress(
        ping.latitude, ping.longitude, v_state.get("route_id", "020f"), v_state.get("agency_id", "004B")
    )
    
    old_state = v_state.get("current_state", "IN_TRANSIT")
    route_code = (v_state.get("route_id") or "").lower()

    if progress:
        pct = progress["progress_percent"]
        dist_km = progress["distance_traveled_km"]
        total_km = progress["total_km"]
        dev_m = progress["deviation_meters"]

        v_state["progress_percent"] = pct
        v_state["distance_traveled_km"] = dist_km
        v_state["route_total_km"] = total_km
        v_state["deviation_meters"] = dev_m

        # Alerta por desvío de la traza de ruta (> MAX_DEVIATION_METERS)
        if dev_m > MAX_DEVIATION_METERS:
            if not v_state.get("deviation_alert"):
                v_state["deviation_alert"] = True
                event_data = {
                    "license_plate": plate,
                    "internal_number": bus_key,
                    "event_type": "deviation_alert",
                    "timestamp": now_iso,
                    "location": {"latitude": ping.latitude, "longitude": ping.longitude},
                    "telemetry": {"deviation_meters": dev_m}
                }
                background_tasks.add_task(dispatch_odoo_webhook_with_retry, event_data)
                record_event_history({"time": now_iso, "bus": bus_key, "type": "deviation", "desc": f"Desvío de trazado ({round(dev_m)}m)"})
        else:
            v_state["deviation_alert"] = False

        # --- DETERMINACIÓN DEL ESTADO OPERATIVO INTELIGENTE ---
        if route_code in ("0000", "", "depot", "taller"):
            v_state["current_state"] = "DEPOT"
            v_state["current_geofence_name"] = "En Depósito / Patio"

        elif dev_m > MAX_DEVIATION_METERS:
            v_state["current_state"] = "OFF_ROUTE"
            v_state["current_geofence_name"] = f"Desviado ({round(dev_m)}m)"

        elif ping.type == 1 or pct >= 97.5 or (total_km > 0 and (total_km - dist_km) <= 0.35):
            # Llegada a terminal destino
            v_state["current_state"] = "AT_DESTINATION"
            v_state["current_geofence_name"] = "Terminal Llegada"

        elif (pct < 2.5 or dist_km < 0.35) and speed < 5.0 and ping.type != 0:
            # En cabecera de origen esperando salida
            v_state["current_state"] = "AT_ORIGIN"
            v_state["current_geofence_name"] = "En Cabecera (Origen)"

        else:
            # En circulación activa a lo largo del itinerario
            v_state["current_state"] = "IN_TRANSIT"
            v_state["current_geofence_name"] = "En Itinerario"

    # Notificaciones automáticas de transición de estado hacia Odoo
    if old_state == "AT_ORIGIN" and v_state["current_state"] == "IN_TRANSIT":
        event_data = {
            "license_plate": plate,
            "internal_number": bus_key,
            "event_type": "departure",
            "timestamp": now_iso,
            "location": {"checkpoint_name": "Salida a Itinerario", "latitude": ping.latitude, "longitude": ping.longitude},
            "telemetry": {"odometer_km": v_state["odometer_km"], "speed_kmh": speed}
        }
        background_tasks.add_task(dispatch_odoo_webhook_with_retry, event_data)
        record_event_history({"time": now_iso, "bus": bus_key, "type": "departure", "desc": f"Salida de cabecera a circulación (km {round(v_state.get('distance_traveled_km', 0.0), 1)})"})

    elif old_state == "IN_TRANSIT" and v_state["current_state"] == "AT_DESTINATION":
        event_data = {
            "license_plate": plate,
            "internal_number": bus_key,
            "event_type": "arrival",
            "timestamp": now_iso,
            "location": {"checkpoint_name": "Llegada a Destino", "latitude": ping.latitude, "longitude": ping.longitude},
            "telemetry": {"odometer_km": v_state["odometer_km"], "speed_kmh": speed}
        }
        background_tasks.add_task(dispatch_odoo_webhook_with_retry, event_data)
        record_event_history({"time": now_iso, "bus": bus_key, "type": "arrival", "desc": f"Llegada a terminal destino (km {round(v_state.get('distance_traveled_km', 0.0), 1)})"})

    # Alerta por Velocidad
    if speed > SPEED_LIMIT_KMH and not v_state["speed_alert"]:
        v_state["speed_alert"] = True
        event_data = {
            "license_plate": plate,
            "internal_number": bus_key,
            "event_type": "speeding_alert",
            "timestamp": now_iso,
            "location": {"latitude": ping.latitude, "longitude": ping.longitude},
            "telemetry": {"speed_kmh": speed}
        }
        background_tasks.add_task(dispatch_odoo_webhook_with_retry, event_data)
        record_event_history({"time": now_iso, "bus": bus_key, "type": "speeding", "desc": f"Exceso de velocidad: {speed} km/h"})
    # 5.5 Resolución Contextual de Calles e Intersección ("Circulando (Calle X aprox. a Calle Y)")
    if street_resolver:
        try:
            st_info = street_resolver.format_bus_status(
                current_state=v_state["current_state"],
                route_code=route_code,
                lat=ping.latitude,
                lon=ping.longitude,
                distance_km=v_state.get("distance_traveled_km", 0.0),
                speed_kmh=speed,
                deviation_meters=v_state.get("deviation_meters", 0.0)
            )
            v_state["status_display"] = st_info["status_display"]
            v_state["street_name"] = st_info["street_name"]
            v_state["approaching"] = st_info["approaching"]
        except Exception as e:
            logger.debug(f"Error resolviendo calle para {bus_key}: {e}")
            v_state["status_display"] = "En Circulación" if v_state["current_state"] == "IN_TRANSIT" else v_state["current_state"]
    else:
        v_state["status_display"] = "En Circulación" if v_state["current_state"] == "IN_TRANSIT" else v_state["current_state"]

    # 6. Guardar Estado en Redis
    save_vehicle_state(bus_key, v_state)

    # 7. Difusión WebSocket
    ws_payload = {
        "type": "vehicle_update",
        "vehicle": format_vehicle_for_client(v_state)
    }
    background_tasks.add_task(ws_manager.broadcast, ws_payload)

    return {
        "status": "success",
        "bus_id": bus_key,
        "current_state": v_state["current_state"],
        "progress_percent": v_state.get("progress_percent", 0.0),
        "deviation_meters": v_state.get("deviation_meters", 0.0),
        "geofence": v_state["current_geofence_name"],
        "timestamp": now_iso
    }

# ------------------------------------------------------------------------------
# Endpoints REST de Shapes, Paradas y Rutas
# ------------------------------------------------------------------------------
@app.get("/api/v1/shapes/active")
async def api_get_active_shapes():
    """Retorna las geometrías (LineString) de todas las rutas vigentes hoy en formato GeoJSON."""
    return get_active_shapes_geojson()

@app.get("/api/v1/shapes/history")
async def api_get_historical_shape(
    route_code: str = Query("020f", description="Código del ramal (ej: 020f)"),
    agency_id: str = Query("004B", description="Código de empresa (ej: 004B)"),
    date: str = Query(..., description="Fecha histórica de consulta (YYYY-MM-DD)")
):
    """Retorna el trazado GeoJSON que estaba vigente en una fecha histórica específica."""
    return get_historical_shape_geojson(route_code, agency_id, date)

@app.get("/api/v1/stops/active")
async def api_get_active_stops():
    """Retorna todas las paradas y cabeceras activas en formato GeoJSON."""
    return get_active_stops_geojson()

@app.get("/api/v1/routes")
async def api_get_routes():
    """Catálogo maestro de líneas y ramales."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.id, r.code, r.name, r.agency_id, r.direction, r.origin, r.destination,
                   s.version AS active_version, s.valid_from, s.valid_until, s.total_km
            FROM transit_route r
            LEFT JOIN transit_route_shape s ON s.route_id = r.id 
                 AND s.valid_from <= CURRENT_DATE 
                 AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
            ORDER BY r.code;
            """
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "id": r[0], "code": r[1], "name": r[2], "agency_id": r[3], "direction": r[4],
                "origin": r[5], "destination": r[6], "active_version": r[7],
                "valid_from": str(r[8]) if r[8] else None,
                "valid_until": str(r[9]) if r[9] else "Actualidad",
                "total_km": float(r[10]) if r[10] else None
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/v1/test_mqtt_ping")
async def test_mqtt_ping(
    agency_id: str = "004B",
    bus_id: str = "00016",
    route_id: str = "020f",
    lat: float = -25.3210,
    lon: float = -57.5520,
    speed: float = 38.0
):
    """Publica un payload binario Protobuf v3 en Mosquitto para probar el flujo de punta a punta."""
    try:
        import paho.mqtt.publish as publish
        from proto.decoder import encode_test_operation

        payload = encode_test_operation(
            agency_id=agency_id,
            mean_id=bus_id,
            route_id=route_id,
            latitude=lat,
            longitude=lon,
            speed=speed,
            bearing=95.0
        )
        topic = f"transporte/flota/{agency_id}/operacion"
        auth = {"username": MQTT_USERNAME, "password": MQTT_PASSWORD}
        publish.single(
            topic,
            payload=payload,
            hostname=MQTT_BROKER_HOST,
            port=MQTT_BROKER_PORT,
            auth=auth
        )
        return {
            "status": "published",
            "topic": topic,
            "bytes_sent": len(payload),
            "protocol": "Protobuf v3 (Res. GVMT 065/2024)",
            "bus": bus_id
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Fallo al publicar en MQTT: {e}"})

# ------------------------------------------------------------------------------
# WebSocket y Radar Dashboard
# ------------------------------------------------------------------------------
@app.websocket("/ws/live")
async def websocket_live_radar(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        initial_data = {
            "type": "init",
            "vehicles": get_all_active_vehicles(),
            "events": event_history_memory[-10:],
            "shapes": get_active_shapes_geojson(),
            "stops": get_active_stops_geojson()
        }
        await websocket.send_json(initial_data)

        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket client error: {e}")
        ws_manager.disconnect(websocket)

@app.get("/api/v1/live")
async def get_live_fleet():
    vehicles = get_all_active_vehicles()
    return {
        "status": "success",
        "count": len(vehicles),
        "vehicles": vehicles,
        "events": event_history_memory[-10:],
        "shapes": get_active_shapes_geojson(),
        "stops": get_active_stops_geojson()
    }

@app.get("/health")
async def health_check():
    redis_ok = False
    if redis_client:
        try:
            redis_ok = redis_client.ping()
        except Exception:
            redis_ok = False

    active_v = get_all_active_vehicles()
    return {
        "status": "healthy",
        "service": "gps_broker",
        "version": "3.0.0",
        "redis_connected": redis_ok,
        "mqtt_broker": f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}",
        "active_vehicles": len(active_v),
        "ws_clients": len(ws_manager.active_connections),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "features": {
            "eta_predictivo": True,
            "cumplimiento_vmt": True,
            "detector_pegonamiento": True,
            "radar_mapa": True,
            "tablero_lineal": True,
        },
        "endpoints": {
            "mapa_en_vivo": "/map",
            "tablero_lineal": "/headway",
            "cumplimiento_vmt": "/compliance",
            "parada_eta": "/parada/{stop_code}",
            "api_eta": "/api/v1/eta/{stop_code}",
            "api_bunching": "/api/v1/bunching/alerts",
            "api_compliance": "/api/v1/compliance/today",
        }
    }

# ------------------------------------------------------------------------------
# Tablero Lineal de Frecuencias & Detector de Pegonamiento (Headway Monitoring)
# ------------------------------------------------------------------------------
from headway_service import get_headway_data, get_headway_html

@app.get("/api/v1/headway/data")
async def api_headway_data():
    return get_headway_data(redis_client=redis_client, active_vehicles_memory=active_vehicles_memory)

@app.get("/headway", response_class=HTMLResponse)
async def headway_dashboard_view():
    return get_headway_html()

@app.get("/api/v1/bunching/alerts")
async def api_bunching_alerts():
    """
    Retorna solo las alertas activas de pegonamiento (bunching) de todos los ramales.
    Ideal para integraciones MQTT, Odoo webhooks o paneles de control rápidos.
    """
    hw_data = get_headway_data(redis_client=redis_client, active_vehicles_memory=active_vehicles_memory)
    alerts = []
    for route in hw_data.get("routes", []):
        if route.get("status") in ("PEGONAMIENTO", "ADVERTENCIA"):
            for hw in route.get("headways", []):
                if hw.get("severity") in ("CRITICAL", "WARNING"):
                    alerts.append({
                        "route_code": route["route_code"],
                        "route_name": route.get("name", ""),
                        "severity": hw["severity"],
                        "trailer_id": hw["trailer_id"],
                        "leader_id": hw["leader_id"],
                        "gap_km": hw["gap_km"],
                        "gap_meters": hw["gap_meters"],
                        "est_minutes": hw["est_minutes"],
                        "alert_label": (
                            f"Pegonamiento critico: buses {hw['trailer_id']} y {hw['leader_id']} "
                            f"a {hw['gap_meters']}m de separacion en {route['route_code'].upper()}"
                        ) if hw["severity"] == "CRITICAL" else (
                            f"Intervalo corto: {hw['gap_km']} km entre buses {hw['trailer_id']} y {hw['leader_id']}"
                        )
                    })
    return {
        "timestamp": hw_data.get("timestamp"),
        "total_bunching_alerts": hw_data.get("total_bunching_alerts", 0),
        "alerts": alerts
    }

# ------------------------------------------------------------------------------
# ETA Predictivo por Parada (Tiempo de Espera en Tiempo Real)
# ------------------------------------------------------------------------------
from eta_service import compute_eta_for_stop, get_all_stop_etas, get_stop_page_html

@app.get("/api/v1/eta/{stop_code}")
async def api_eta_stop(stop_code: str):
    """
    Retorna el tiempo de espera estimado para los proximos buses electricos
    que se aproximan a la parada indicada, calculado con PostGIS en tiempo real.
    """
    vehicles = get_all_active_vehicles()
    return compute_eta_for_stop(stop_code, vehicles, redis_client)

@app.get("/api/v1/eta/all")
async def api_eta_all():
    """Retorna ETAs calculados para todas las paradas activas de los Electricos."""
    vehicles = get_all_active_vehicles()
    results = get_all_stop_etas(vehicles, redis_client)
    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "total_stops": len(results),
        "stops": results
    }

@app.get("/parada/{stop_code}", response_class=HTMLResponse)
async def stop_page(stop_code: str, request: Request):
    """
    Pagina movil-first para pasajeros con ETA en tiempo real,
    QR embebido para compartir, auto-refresh cada 15 segundos.
    Accesible escaneando el QR en la parada fisica.
    """
    host_url = str(request.base_url).rstrip("/")
    return get_stop_page_html(stop_code, host_url)

# ------------------------------------------------------------------------------
# Dashboard de Cumplimiento VMT (Res. GVMT 065/2024)
# ------------------------------------------------------------------------------
from compliance_service import get_today_compliance, get_compliance_alerts, get_compliance_html

@app.get("/compliance", response_class=HTMLResponse)
async def compliance_dashboard():
    """
    Dashboard interactivo de cumplimiento de la cuota diaria de 692 despachos
    exigida por la Resolucion GVMT 065/2024 para la Linea 20 Electrica.
    Muestra cumplimiento actual, proyeccion al cierre, detalle por ramal e historial.
    """
    return get_compliance_html()

@app.get("/api/v1/compliance/today")
async def api_compliance_today():
    """
    Datos JSON de cumplimiento del dia actual.
    Incluye: despachos ejecutados, programados, % cumplimiento, proyeccion y alertas.
    """
    return get_today_compliance(redis_client)

@app.get("/api/v1/compliance/alerts")
async def api_compliance_alerts():
    """
    Lista de alertas activas de deficit de cumplimiento.
    Se integra con notificaciones Odoo y MQTT.
    """
    alerts = get_compliance_alerts(redis_client)
    return {
        "total": len(alerts),
        "has_alerts": len(alerts) > 0,
        "alerts": alerts
    }

@app.get("/api/v1/compliance/history")
async def api_compliance_history():
    """Historial de cumplimiento de los ultimos 30 dias."""
    data = get_today_compliance(redis_client)
    return {
        "daily_quota": data.get("daily_quota", 692),
        "history": data.get("history_30d", [])
    }

# ------------------------------------------------------------------------------
# Dashboard Radar Web en Vivo con PostGIS Shapes y Visor Histórico
# ------------------------------------------------------------------------------
@app.get("/map", response_class=HTMLResponse)
async def live_map_view():
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poliverso Transit | Radar Integral con Trazados Históricos</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background-color: #0b1120; color: #f8fafc; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        header { background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px); padding: 10px 24px; border-bottom: 1px solid #1e293b; display: flex; align-items: center; justify-content: space-between; z-index: 1000; }
        .logo-group { display: flex; align-items: center; gap: 12px; }
        .badge { padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display: inline-flex; align-items: center; gap: 5px; }
        .badge-ws { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
        .badge-poll { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
        .badge-info { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); }
        .controls-bar { display: flex; align-items: center; gap: 14px; }
        .date-picker-box { display: flex; align-items: center; gap: 8px; font-size: 12px; background: #1e293b; padding: 5px 12px; border-radius: 8px; border: 1px solid #334155; }
        .date-picker-box input { background: #0f172a; border: 1px solid #475569; color: #f8fafc; padding: 3px 6px; border-radius: 4px; font-size: 12px; }
        .btn-hist { background: #0284c7; color: white; border: none; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; }
        .btn-hist:hover { background: #0369a1; }
        .metrics-bar { display: flex; gap: 12px; }
        .metric-card { background: #1e293b; padding: 5px 12px; border-radius: 8px; border: 1px solid #334155; font-size: 12px; }
        .metric-card strong { color: #38bdf8; font-size: 15px; margin-left: 4px; }
        #app-layout { display: flex; flex: 1; position: relative; overflow: hidden; }
        #map { flex: 1; height: 100%; z-index: 1; }
        #sidebar { width: 380px; background: #111827; border-left: 1px solid #1f2937; display: flex; flex-direction: column; z-index: 10; }
        .sidebar-header { padding: 12px 16px; border-bottom: 1px solid #1f2937; font-weight: 700; font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; display: flex; justify-content: space-between; align-items: center; }
        .bus-list { flex: 1; overflow-y: auto; padding: 12px; }
        .bus-card { background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 14px; margin-bottom: 10px; transition: all 0.2s ease; }
        .bus-card:hover { border-color: #38bdf8; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15); }
        .bus-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .bus-title { font-weight: 700; font-size: 14px; color: #f9fafb; }
        .status-pill { font-size: 10px; padding: 2px 8px; border-radius: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
        .status-transit { background: #059669; color: #fff; }
        .status-origin { background: #2563eb; color: #fff; }
        .status-dest { background: #9333ea; color: #fff; }
        .status-offroute { background: #dc2626; color: #fff; }
        .status-depot { background: #4b5563; color: #fff; }
        .progress-container { margin: 8px 0; }
        .progress-labels { display: flex; justify-content: space-between; font-size: 11px; color: #9ca3af; margin-bottom: 3px; }
        .progress-bar-bg { width: 100%; height: 6px; background: #374151; border-radius: 3px; overflow: hidden; }
        .progress-bar-fill { height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8); border-radius: 3px; transition: width 0.4s ease; }
        .bus-meta { font-size: 12px; color: #9ca3af; line-height: 1.5; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 6px; }
        .alert-box { background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; padding: 5px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; margin-top: 8px; }
        .event-feed { height: 160px; background: #0b1120; border-top: 1px solid #1f2937; overflow-y: auto; padding: 12px; font-size: 11px; }
        .event-item { margin-bottom: 6px; border-left: 3px solid #38bdf8; padding-left: 8px; }
        .event-time { color: #6b7280; font-size: 10px; }
        .legend-box { position: absolute; bottom: 20px; left: 20px; background: rgba(17, 24, 39, 0.92); border: 1px solid #374151; padding: 12px 16px; border-radius: 8px; z-index: 1000; font-size: 11px; backdrop-filter: blur(8px); }
        .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
        .legend-line { width: 22px; height: 4px; border-radius: 2px; }
    </style>
</head>
<body>
    <header>
        <div class="logo-group">
            <h2 style="font-size: 16px; font-weight: 800; letter-spacing: -0.02em;">🚍 Poliverso Transit Radar</h2>
            <span id="conn-badge" class="badge badge-poll">Iniciando...</span>
            <span class="badge badge-info">MQTT + Protobuf GVMT N°065</span>
        </div>
        <div class="controls-bar">
            <div class="date-picker-box">
                <span>📅 Vigencia Histórica:</span>
                <input type="date" id="hist-date" value="2026-09-25">
                <button class="btn-hist" onclick="loadHistoricalShape()">Consultar</button>
                <button class="btn-hist" style="background:#475569;" onclick="resetToActiveShapes()">Hoy</button>
            </div>
            <div class="metrics-bar">
                <div class="metric-card">Flota: <strong id="m-buses">0</strong></div>
                <div class="metric-card">En Ruta: <strong id="m-transit">0</strong></div>
                <div class="metric-card">Alertas: <strong id="m-alerts" style="color: #ef4444;">0</strong></div>
            </div>
            <a href="/headway" style="background: linear-gradient(135deg, #0284c7, #6366f1); color: #fff; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 800; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);">📊 Tablero Lineal</a>
        </div>
    </header>

    <div id="app-layout">
        <div id="map"></div>
        <div class="legend-box" id="legend">
            <strong style="color: #e5e7eb; display:block; margin-bottom: 6px;">Trazados de Rutas (PostGIS)</strong>
            <div class="legend-item"><div class="legend-line" style="background: #38bdf8;"></div><span>Ramal 020F (Asunción - San Lorenzo)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #a855f7;"></div><span>Ramal 020C (San Lorenzo - Asunción)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #f59e0b;"></div><span>Ramal 020D (Asunción - San Lorenzo)</span></div>
            <div class="legend-item"><div class="legend-line" style="background: #ef4444; border-top: 2px dashed #fff;"></div><span id="hist-label">Histórico Anterior</span></div>
        </div>
        <div id="sidebar">
            <div class="sidebar-header">
                <span>Unidades en Operación</span>
                <span id="route-count" style="font-size: 11px; color: #38bdf8;">Línea 20 (004B)</span>
            </div>
            <div class="bus-list" id="bus-list"></div>
            <div class="sidebar-header" style="border-top: 1px solid #1f2937;">Eventos y Geocercas en Vivo</div>
            <div class="event-feed" id="event-feed"></div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const map = L.map('map').setView([-25.3250, -57.5300], 12);
        const cartoKey = 'cb1_3skd_1_b01311b843bcb7fb316c4384';
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=' + cartoKey, {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions" target="_blank">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);

        const markers = {};
        const activeVehicles = {};
        let shapeLayers = [];
        let stopLayers = [];
        let eventHistory = [];
        let ws = null;
        let pollingInterval = null;

        const routeColors = {
            '020f': '#38bdf8',
            '020c': '#a855f7',
            '020d': '#f59e0b',
            '0210': '#10b981',
            'default': '#64748b'
        };

        function renderShapesGeoJSON(geojson, isHistorical = false) {
            shapeLayers.forEach(l => map.removeLayer(l));
            shapeLayers = [];

            if (!geojson || !geojson.features) return;

            const layer = L.geoJSON(geojson, {
                style: (feature) => {
                    const code = (feature.properties.route_code || '').toLowerCase();
                    const color = isHistorical ? '#ef4444' : (routeColors[code] || routeColors['default']);
                    return {
                        color: color,
                        weight: isHistorical ? 5 : 4,
                        opacity: 0.85,
                        dashArray: isHistorical ? '6, 6' : null
                    };
                },
                onEachFeature: (feature, layer) => {
                    const p = feature.properties;
                    layer.bindPopup(`
                        <b>${p.route_name || p.route_code}</b><br>
                        Ramal: ${p.route_code} | v${p.version || '?'}<br>
                        Longitud: ${p.total_km} km<br>
                        Vigencia: ${p.valid_from} al ${p.valid_until || 'Actualidad'}
                    `);
                }
            }).addTo(map);
            shapeLayers.push(layer);
        }

        function renderStopsGeoJSON(geojson) {
            stopLayers.forEach(l => map.removeLayer(l));
            stopLayers = [];

            if (!geojson || !geojson.features) return;

            const layer = L.geoJSON(geojson, {
                pointToLayer: (feature, latlng) => {
                    const p = feature.properties;
                    const isTerminal = p.stop_type === 'origin' || p.stop_type === 'destination';
                    const marker = L.circleMarker(latlng, {
                        radius: isTerminal ? 7 : 5,
                        fillColor: isTerminal ? '#f43f5e' : '#38bdf8',
                        color: '#ffffff',
                        weight: 1.5,
                        opacity: 1,
                        fillOpacity: 0.8
                    });

                    // Círculo de geocerca
                    const fence = L.circle(latlng, {
                        radius: p.radius_meters || 70,
                        color: isTerminal ? '#f43f5e' : '#38bdf8',
                        weight: 1,
                        fillOpacity: 0.08
                    });
                    stopLayers.push(fence.addTo(map));

                    return marker;
                },
                onEachFeature: (feature, layer) => {
                    const p = feature.properties;
                    layer.bindPopup(`
                        <b>🚏 ${p.name}</b><br>
                        Código: ${p.stop_code} (${p.stop_type})<br>
                        Radio Geocerca: ${p.radius_meters}m<br>
                        ${p.address || ''}
                    `);
                }
            }).addTo(map);
            stopLayers.push(layer);
        }

        async function loadHistoricalShape() {
            const dateVal = document.getElementById('hist-date').value;
            if (!dateVal) return;
            try {
                const res = await fetch(`/api/v1/shapes/history?route_code=020f&agency_id=004B&date=${dateVal}`);
                const data = await res.json();
                renderShapesGeoJSON(data, true);
                document.getElementById('hist-label').textContent = `Vigente al ${dateVal}`;
            } catch (err) {
                console.error("Error cargando histórico:", err);
            }
        }

        async function resetToActiveShapes() {
            try {
                const res = await fetch('/api/v1/shapes/active');
                const data = await res.json();
                renderShapesGeoJSON(data, false);
                document.getElementById('hist-label').textContent = `Histórico Anterior`;
            } catch (err) {
                console.error("Error reseteando shapes:", err);
            }
        }

        function updateUI() {
            const vehicles = Object.values(activeVehicles);
            document.getElementById('m-buses').textContent = vehicles.length;
            document.getElementById('m-transit').textContent = vehicles.filter(v => (v.state === 'IN_TRANSIT' || v.current_state === 'IN_TRANSIT')).length;
            const alertsCount = vehicles.filter(v => v.speed_alert || v.deviation_alert).length;
            document.getElementById('m-alerts').textContent = alertsCount;

            const stateLabels = {
                'IN_TRANSIT': 'En Circulación',
                'AT_ORIGIN': 'En Cabecera',
                'AT_DESTINATION': 'En Destino',
                'OFF_ROUTE': 'Desviado',
                'DEPOT': 'En Depósito'
            };

            vehicles.forEach(v => {
                const lat = (v.latitude !== undefined && v.latitude !== null) ? v.latitude : v.last_latitude;
                const lon = (v.longitude !== undefined && v.longitude !== null) ? v.longitude : v.last_longitude;
                if (lat === undefined || lon === undefined || lat === null || lon === null || isNaN(lat) || isNaN(lon)) {
                    return;
                }
                const latlng = [lat, lon];
                const state = v.state || v.current_state || 'IN_TRANSIT';
                const estadoEsp = v.status_display || (stateLabels[state] || state);
                const speed = (v.speed_kmh !== undefined && v.speed_kmh !== null) ? v.speed_kmh : (v.last_speed_kmh || 0);

                const popupText = `
                    <b>🚍 Coche #${v.bus_id} (${v.license_plate})</b><br>
                    Ramal: <b>${v.route_id}</b> (${v.agency_id})<br>
                    Estado: <b style="color: #38bdf8;">${estadoEsp}</b><br>
                    Progreso: <b>${v.progress_percent || 0}%</b> (${v.distance_traveled_km || 0} / ${v.route_total_km || 0} km)<br>
                    Desvío Traza: <b>${Math.round(v.deviation_meters || 0)}m</b><br>
                    Velocidad: <b>${speed} km/h</b>
                `;

                if (!markers[v.bus_id]) {
                    const icon = L.divIcon({
                        className: 'custom-bus-icon',
                        html: `<div style="background: #38bdf8; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 13px; box-shadow: 0 0 12px #38bdf8;">🚌</div>`,
                        iconSize: [28, 28]
                    });
                    markers[v.bus_id] = L.marker(latlng, { icon: icon }).addTo(map).bindPopup(popupText);
                } else {
                    markers[v.bus_id].setLatLng(latlng).setPopupContent(popupText);
                }
            });

            const listEl = document.getElementById('bus-list');
            listEl.innerHTML = vehicles.map(v => {
                const state = v.state || v.current_state || 'IN_TRANSIT';
                const estadoEsp = v.status_display || (stateLabels[state] || state);
                const pillClass = state === 'IN_TRANSIT' ? 'status-transit' : (state === 'AT_ORIGIN' ? 'status-origin' : (state === 'OFF_ROUTE' ? 'status-offroute' : (state === 'DEPOT' ? 'status-depot' : 'status-dest')));
                const speed = (v.speed_kmh !== undefined && v.speed_kmh !== null) ? v.speed_kmh : (v.last_speed_kmh || 0);
                return `
                <div class="bus-card">
                    <div class="bus-header">
                        <span class="bus-title">🚍 Coche #${v.bus_id} (${v.license_plate})</span>
                        <span class="status-pill ${pillClass}">${stateLabels[state] || state}</span>
                    </div>
                    <div style="font-size: 11px; color: #38bdf8; margin: 4px 0 6px 0; font-weight: 500; display: flex; align-items: center; gap: 4px;">
                        <span>📍</span>
                        <span>${estadoEsp}</span>
                    </div>
                    <div class="progress-container">
                        <div class="progress-labels">
                            <span>Progreso Itinerario</span>
                            <span><strong>${v.progress_percent || 0}%</strong> (${v.distance_traveled_km || 0} km)</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" style="width: ${Math.min(v.progress_percent || 0, 100)}%;"></div>
                        </div>
                    </div>
                    <div class="bus-meta">
                        <div>Ramal: <strong style="color:#f8fafc;">${v.route_id || '--'}</strong></div>
                        <div>Velocidad: <strong style="color:#f8fafc;">${speed} km/h</strong></div>
                        <div>Desvío Traza: <strong style="color:${v.deviation_alert ? '#ef4444':'#34d399'};">${Math.round(v.deviation_meters || 0)}m</strong></div>
                        <div>Último Ping: <strong style="color:#f8fafc;">${v.last_ping_time ? v.last_ping_time.slice(11, 19) : '--'}</strong></div>
                    </div>
                    ${v.speed_alert ? '<div class="alert-box">⚠️ ¡EXCESO DE VELOCIDAD (&gt;70 km/h)!</div>' : ''}
                    ${v.deviation_alert ? '<div class="alert-box">⚠️ ¡DESVÍO DE TRAZADO OFICIAL (&gt;400m)!</div>' : ''}
                </div>
            `;
            }).join('');

            const feedEl = document.getElementById('event-feed');
            feedEl.innerHTML = eventHistory.slice(-15).map(e => `
                <div class="event-item">
                    <span class="event-time">${e.time ? e.time.slice(11, 19) : ''}</span> [Bus #${e.bus}] <strong>${e.desc}</strong>
                </div>
            `).reverse().join('');
        }

        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/live`;
            const badge = document.getElementById('conn-badge');

            try {
                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    badge.className = 'badge badge-ws';
                    badge.innerHTML = '● WebSocket en Vivo (0ms)';
                    if (pollingInterval) {
                        clearInterval(pollingInterval);
                        pollingInterval = null;
                    }
                };

                ws.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'init') {
                            if (msg.shapes) renderShapesGeoJSON(msg.shapes);
                            if (msg.stops) renderStopsGeoJSON(msg.stops);
                            (msg.vehicles || []).forEach(v => activeVehicles[v.bus_id] = v);
                            eventHistory = msg.events || [];
                            updateUI();
                        } else if (msg.type === 'vehicle_update' && msg.vehicle) {
                            activeVehicles[msg.vehicle.bus_id] = msg.vehicle;
                            updateUI();
                        }
                    } catch (e) {
                        console.error("Error parseando WebSocket:", e);
                    }
                };

                ws.onclose = () => {
                    badge.className = 'badge badge-poll';
                    badge.innerHTML = '▲ Polling de Respaldo (Reconectando...)';
                    startPollingFallback();
                    setTimeout(initWebSocket, 4000);
                };

                ws.onerror = () => ws.close();
            } catch (err) {
                startPollingFallback();
            }
        }

        async function fetchHttpLive() {
            try {
                const res = await fetch('/api/v1/live');
                const data = await res.json();
                if (data.shapes && shapeLayers.length === 0) renderShapesGeoJSON(data.shapes);
                if (data.stops && stopLayers.length === 0) renderStopsGeoJSON(data.stops);
                (data.vehicles || []).forEach(v => activeVehicles[v.bus_id] = v);
                eventHistory = data.events || [];
                updateUI();
            } catch (err) {
                console.debug("HTTP fallback error:", err);
            }
        }

        function startPollingFallback() {
            if (!pollingInterval) {
                pollingInterval = setInterval(fetchHttpLive, 3000);
                fetchHttpLive();
            }
        }

        initWebSocket();
    </script>
</body>
</html>
"""
