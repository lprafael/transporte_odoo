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
import urllib.parse
import asyncio
import logging
import threading
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

import requests
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auth import (
    get_current_user_from_request,
    require_authenticated_user,
    authenticate_odoo_user,
    invalidate_session,
    render_login_page,
    is_device_or_internal_token,
    validate_odoo_session,
)

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gps_broker")

app = FastAPI(
    title="Broker de Telemetría GPS & PostGIS Shapes",
    description="Servicio integral: Ingesta MQTT/Protobuf, Motor de Geocercas PostGIS, ETA Predictivo por Parada, Cumplimiento Operativo, Detector de Pegonamiento y WebSockets",
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

_last_agencies_cache_time = 0.0
_cached_valid_agencies: Set[str] = {"004B"}

def get_valid_agencies() -> Set[str]:
    """Recupera la lista de agencias/concesionarias registradas activas en PostgreSQL con cache de 60s."""
    global _last_agencies_cache_time, _cached_valid_agencies
    now = time.time()
    if now - _last_agencies_cache_time < 60.0 and _cached_valid_agencies:
        return _cached_valid_agencies

    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=3
        )
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(agency_id, code) FROM transit_concessionaire WHERE active = TRUE;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        agencies = {r[0].strip() for r in rows if r and r[0]}
        if not agencies:
            agencies = {"004B"}
        _cached_valid_agencies = agencies
        _last_agencies_cache_time = now
    except Exception as e:
        logger.debug(f"Error consultando agencias en BD: {e}")
        if not _cached_valid_agencies:
            _cached_valid_agencies = {"004B"}
    return _cached_valid_agencies

# Pares de ramales opuestos (Ida <-> Vuelta) para detección de IDRuta invertido
OPPOSITE_ROUTE_PAIRS: Dict[str, str] = {
    # Automotores Guaraní - Línea 15
    "004a": "004b", "004b": "004a",
    "004c": "004d", "004d": "004c",
    "004e": "004f", "004f": "004e",
    "0050": "0051", "0051": "0050",
    "01a0": "01a1", "01a1": "01a0",
    "01ef": "01f0", "01f0": "01ef",
    # Automotores Guaraní - Línea 47
    "0052": "0053", "0053": "0052",
    "0054": "0055", "0055": "0054",
    "0056": "0057", "0057": "0056",
    "0058": "0059", "0059": "0058",
    "0185": "0186", "0186": "0185",
    "01a2": "01a3", "01a3": "01a2",
    # Consorcio Arapotí - Línea 20
    "020c": "020d", "020d": "020c",
    "020e": "020f", "020f": "020e",
    "0210": "0211", "0211": "0210",
    # San José Obrero - Línea 187
    "0138": "0139", "0139": "0138",
    "013a": "013b", "013b": "013a",
}

def get_opposite_route_code(route_code: str, agency_id: Optional[str] = None) -> Optional[str]:
    if not route_code:
        return None
    clean = route_code.strip().lower()
    return OPPOSITE_ROUTE_PAIRS.get(clean)

def get_route_line_name(route_code: str) -> str:
    clean = (route_code or "").strip().lower()
    for r in routes_cache:
        if str(r.get("code", "")).lower() == clean and r.get("line_name"):
            return r["line_name"]
    # Fallback según códigos conocidos
    if clean in ('0052', '0053', '0054', '0055', '0056', '0057', '0058', '0059', '0185', '0186', '01a2', '01a3'):
        return "Línea 47"
    if clean in ('004a', '004b', '004c', '004d', '004e', '004f', '0050', '0051', '01a0', '01a1', '01ef', '01f0'):
        return "Línea 15"
    if clean.startswith("020") or clean.startswith("021") or clean == "0000":
        return "Línea 20"
    if clean in ('0138', '0139', '013a', '013b'):
        return "Línea 187"
    return "Línea General"

def get_vehicle_state(bus_id: str, agency_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    keys_to_try = []
    if agency_id:
        keys_to_try.append(f"vehicle:{agency_id}:{bus_id}")
    else:
        for ag in ("004B", "002A", "0008"):
            keys_to_try.append(f"vehicle:{ag}:{bus_id}")
        keys_to_try.append(f"vehicle:{bus_id}")

    if redis_client:
        try:
            for k in keys_to_try:
                data = redis_client.get(k)
                if data:
                    res = json.loads(data)
                    res["crossed_checkpoints"] = set(res.get("crossed_checkpoints", []))
                    return res
        except Exception as e:
            logger.debug(f"Redis get error: {e}")

    for k in keys_to_try:
        if k in active_vehicles_memory:
            return active_vehicles_memory[k]
    return active_vehicles_memory.get(bus_id)

def save_vehicle_state(bus_id: str, state: Dict[str, Any], agency_id: Optional[str] = None):
    agency = agency_id or state.get("agency_id") or "004B"
    state["agency_id"] = agency
    key = f"vehicle:{agency}:{bus_id}"
    active_vehicles_memory[key] = state
    if redis_client:
        try:
            serializable = dict(state)
            serializable["crossed_checkpoints"] = list(state.get("crossed_checkpoints", []))
            redis_client.set(key, json.dumps(serializable))
            redis_client.sadd(f"active_buses_{agency}", bus_id)
            redis_client.sadd("active_buses_all", f"{agency}:{bus_id}")
        except Exception as e:
            logger.debug(f"Redis set error: {e}")

def format_vehicle_for_client(v: Dict[str, Any]) -> Dict[str, Any]:
    lat = v.get("last_latitude") if v.get("last_latitude") is not None else v.get("latitude")
    lon = v.get("last_longitude") if v.get("last_longitude") is not None else v.get("longitude")
    raw_speed = v.get("speed_kmh") if v.get("speed_kmh") is not None else v.get("last_speed_kmh", 0.0)

    last_ping = v.get("last_ping_time", "")
    minutes_ago = None
    is_gps_fault = False
    if last_ping:
        try:
            clean_ts = str(last_ping).replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            minutes_ago = max(0.0, round((datetime.now(timezone.utc) - dt).total_seconds() / 60.0, 1))
            if minutes_ago > 30.0:
                is_gps_fault = True
            else:
                is_gps_fault = False
        except Exception:
            pass
    else:
        is_gps_fault = True
        minutes_ago = 999.0

    if is_gps_fault:
        state = "GPS_FAULT"
        speed = 0.0
        status_disp = f"Falla de GPS ({int(minutes_ago or 30)}m sin reporte)"
        geofence_name = f"Falla GPS (Sin señal >30m)"
    else:
        # Recuperar estado operativo real sin quedar atrapado en GPS_FAULT
        state = v.get("current_state") or v.get("state") or "IN_TRANSIT"
        if state == "GPS_FAULT":
            state = "IN_TRANSIT"
        speed = raw_speed
        status_disp = v.get("status_display") or ("En Circulación" if state == "IN_TRANSIT" else state)
        if status_disp.startswith("Falla de GPS"):
            status_disp = "En Circulación" if state == "IN_TRANSIT" else ("En Cabecera" if state in ("AT_ORIGIN", "AT_DESTINATION") else state)
        geofence_name = v.get("current_geofence_name", "En Ruta")

    checkpoints = v.get("crossed_checkpoints", [])
    if isinstance(checkpoints, set):
        checkpoints = list(checkpoints)
    return {
        "vehicle_key": f"{v.get('agency_id', '004B')}_{v.get('bus_id')}",
        "bus_id": v.get("bus_id"),
        "license_plate": v.get("license_plate") or f"COCHE-{v.get('bus_id')}",
        "agency_id": v.get("agency_id", "004B"),
        "route_id": v.get("route_id", ""),
        "state": state,
        "current_state": state,
        "status_display": status_disp,
        "street_name": v.get("street_name", ""),
        "approaching": v.get("approaching", ""),
        "latitude": lat,
        "longitude": lon,
        "last_latitude": lat,
        "last_longitude": lon,
        "speed_kmh": speed,
        "last_speed_kmh": speed,
        "calculated_speed_kmh": v.get("calculated_speed_kmh"),
        "is_gps_fault": is_gps_fault,
        "minutes_since_ping": minutes_ago,
        "gps_status": "GPS_FAULT" if is_gps_fault else "ONLINE",
        "heading_deg": v.get("heading_deg", 0.0),
        "odometer_km": v.get("odometer_km", 0.0),
        "last_ping_time": v.get("last_ping_time", ""),
        "geofence_name": geofence_name,
        "current_geofence_name": geofence_name,
        "speed_alert": bool(v.get("speed_alert", False)),
        "deviation_alert": bool(v.get("deviation_alert", False)),
        "wrong_direction_alert": bool(v.get("wrong_direction_alert", False)),
        "wrong_direction_reason": v.get("wrong_direction_reason", ""),
        "suggested_opposite_route": v.get("suggested_opposite_route") or (get_opposite_route_code(v.get("route_id", "")) if v.get("wrong_direction_alert") else ""),
        "heading_diff_deg": v.get("heading_diff_deg"),
        "route_bearing_deg": v.get("route_bearing_deg"),
        "line_name": v.get("line_name") or get_route_line_name(v.get("route_id", "")),
        "progress_percent": v.get("progress_percent", 0.0),
        "distance_traveled_km": v.get("distance_traveled_km", 0.0),
        "route_total_km": v.get("route_total_km", 0.0),
        "deviation_meters": v.get("deviation_meters", 0.0),
        "crossed_checkpoints": checkpoints
    }

def get_all_active_vehicles(agency_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    vehicles = []
    valid_agencies = get_valid_agencies()
    target_agencies = {agency_filter.strip()} if agency_filter else valid_agencies

    if redis_client:
        try:
            if agency_filter:
                bus_ids = redis_client.smembers(f"active_buses_{agency_filter.strip()}")
                for b_id in bus_ids:
                    v = get_vehicle_state(b_id, agency_id=agency_filter.strip())
                    if v:
                        vehicles.append(format_vehicle_for_client(v))
            else:
                entries = redis_client.smembers("active_buses_all")
                for entry in entries:
                    if ":" in entry:
                        ag, b_id = entry.split(":", 1)
                        if ag in target_agencies:
                            v = get_vehicle_state(b_id, agency_id=ag)
                            if v:
                                vehicles.append(format_vehicle_for_client(v))
            if vehicles:
                return vehicles
        except Exception as e:
            logger.debug(f"Redis get_all_active_vehicles error: {e}")

    out = []
    for k, v in active_vehicles_memory.items():
        if ":" in k:
            ag = v.get("agency_id")
            if ag in target_agencies:
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
        self.active_connections: Dict[WebSocket, Optional[str]] = {}

    async def connect(self, websocket: WebSocket, agency_filter: Optional[str] = None):
        await websocket.accept()
        self.active_connections[websocket] = agency_filter
        logger.info(f"Nuevo cliente WebSocket conectado (filtro: {agency_filter}). Total activos: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)
        logger.info(f"Cliente WebSocket desconectado. Total activos: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        dead_connections = set()
        vehicle_agency = None
        if message.get("type") == "vehicle_update" and message.get("vehicle"):
            vehicle_agency = message["vehicle"].get("agency_id")

        for conn, agency_filter in list(self.active_connections.items()):
            if agency_filter and vehicle_agency and agency_filter != vehicle_agency:
                continue
            try:
                await conn.send_json(message)
            except Exception:
                dead_connections.add(conn)
        for dead in dead_connections:
            self.active_connections.pop(dead, None)

    def broadcast_sync(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        global main_event_loop
        if main_event_loop and main_event_loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.broadcast(message), main_event_loop)
            except Exception as e:
                logger.debug(f"broadcast_sync error: {e}")

ws_manager = WebSocketManager()
main_event_loop = None

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
    fecha_hora_procesamiento: Optional[str] = Field(None)
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
        # Priorizar la estampa GPS original emitida por el satélite / módem a bordo
        return self.fecha_hora or self.fecha_hora_procesamiento or self.timestamp or datetime.now(timezone.utc).isoformat()

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

def calculate_bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula el rumbo geodésico inicial (azimut en grados 0.0 - 359.9) entre dos coordenadas geográficas."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.degrees(math.atan2(y, x))
    return round((bearing + 360.0) % 360.0, 1)

_pg_thread_local = threading.local()

def _get_thread_pg_conn():
    conn = getattr(_pg_thread_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        conn.autocommit = True
        _pg_thread_local.conn = conn
    return conn

def get_bus_active_dispatch(bus_id: str, agency_id: str = None) -> Optional[Dict[str, Any]]:
    """Consulta si el vehículo tiene un despacho activo en Odoo hoy para fijar su ramal oficial."""
    if not bus_id:
        return None
    clean_id = str(bus_id).strip()
    candidates = [clean_id, clean_id.lstrip("0")]
    try:
        dec_num = str(int(clean_id, 16))
        if dec_num not in candidates:
            candidates.append(dec_num)
    except Exception:
        pass

    cache_key = f"dispatch:route:{agency_id or 'all'}:{clean_id}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    try:
        conn = _get_thread_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                d.id AS dispatch_id,
                r.code AS route_code,
                r.name AS route_name,
                d.state,
                r.agency_id
            FROM transit_dispatch d
            JOIN fleet_vehicle v ON d.vehicle_id = v.id
            JOIN transit_route r ON d.route_id = r.id
            WHERE (v.bus_internal_number = ANY(%s) OR v.license_plate = ANY(%s))
              AND d.state IN ('draft', 'inspected', 'dispatched', 'in_transit')
              AND d.date = CURRENT_DATE
            ORDER BY d.actual_departure DESC NULLS LAST, d.scheduled_departure DESC
            LIMIT 1;
        """, (candidates, candidates))
        row = cur.fetchone()
        cur.close()
        if row:
            res = {
                "dispatch_id": row[0],
                "route_code": str(row[1]).lower(),
                "route_name": row[2],
                "state": row[3],
                "agency_id": row[4],
            }
            if redis_client:
                try:
                    redis_client.setex(cache_key, 60, json.dumps(res))
                except Exception:
                    pass
            return res
    except Exception as e:
        logger.debug(f"Aviso get_bus_active_dispatch: {e}")
    return None

def calculate_shape_progress(lat: float, lon: float, route_code: str, agency_id: str = "004B", bus_id: str = None) -> Optional[Dict[str, Any]]:
    """Calcula con PostGIS el porcentaje del recorrido completado y la distancia al trazado oficial.
    Respeta bloqueos manuales en Redis y despachos activos en Odoo antes de buscar shapes alternativos.
    """
    try:
        conn = _get_thread_pg_conn()
        cur = conn.cursor()
        row = None
        clean_route = (route_code or "").strip().lower()

        # 1. Comprobar bloqueo manual de ramal en Redis (fijado por operador)
        if bus_id and redis_client:
            try:
                locked = redis_client.get(f"vehicle_route_lock:{agency_id}:{bus_id}") or redis_client.get(f"vehicle_route_lock:{bus_id}")
                if locked:
                    clean_route = (locked.decode("utf-8") if isinstance(locked, bytes) else str(locked)).strip().lower()
            except Exception:
                pass

        # 2. Si no tiene ruta o es 0000/depot, consultar despacho activo en Odoo
        if (not clean_route or clean_route in ("0000", "none", "depot", "taller")) and bus_id:
            disp = get_bus_active_dispatch(bus_id, agency_id=agency_id)
            if disp and disp.get("route_code"):
                clean_route = disp["route_code"]

        if clean_route and clean_route not in ("0000", "none", "depot", "taller"):
            cur.execute(
                "SELECT progress_percent, distance_traveled_km, total_km, deviation_meters, route_bearing_deg FROM get_bus_route_progress(%s, %s, %s, %s)",
                (lat, lon, clean_route, agency_id)
            )
            row = cur.fetchone()

        # 3. Comprobar si la ruta está bloqueada manualmente
        is_locked = False
        if bus_id and redis_client:
            try:
                is_locked = bool(redis_client.exists(f"vehicle_route_lock:{agency_id}:{bus_id}") or redis_client.exists(f"vehicle_route_lock:{bus_id}"))
            except Exception:
                pass

        # Si el bus reporta ruta 0000 o está sobre otro ramal (>400m del código reportado) y NO está bloqueado manualmente:
        if not is_locked and (not row or row[0] is None or (row[3] is not None and float(row[3]) > MAX_DEVIATION_METERS)):
            cur.execute(
                """
                SELECT
                    r.code,
                    ROUND((ST_LineLocatePoint(s.geom, pt.v_pt) * 100.0)::NUMERIC, 1) AS progress_percent,
                    ROUND((ST_LineLocatePoint(s.geom, pt.v_pt) * COALESCE(s.total_km, ST_Length(s.geom::geography)/1000.0))::NUMERIC, 2) AS distance_traveled_km,
                    ROUND(COALESCE(s.total_km, ST_Length(s.geom::geography)/1000.0)::NUMERIC, 2) AS total_km,
                    ROUND(ST_Distance(pt.v_pt::geography, s.geom::geography)::NUMERIC, 0) AS deviation_meters,
                    ROUND(CASE WHEN ST_LineLocatePoint(s.geom, pt.v_pt) < 0.999 THEN
                        DEGREES(ST_Azimuth(
                            ST_LineInterpolatePoint(s.geom, ST_LineLocatePoint(s.geom, pt.v_pt)),
                            ST_LineInterpolatePoint(s.geom, LEAST(1.0, ST_LineLocatePoint(s.geom, pt.v_pt) + 0.005))
                        ))
                    ELSE
                        DEGREES(ST_Azimuth(
                            ST_LineInterpolatePoint(s.geom, GREATEST(0.0, ST_LineLocatePoint(s.geom, pt.v_pt) - 0.005)),
                            ST_LineInterpolatePoint(s.geom, ST_LineLocatePoint(s.geom, pt.v_pt))
                        ))
                    END::NUMERIC, 1) AS route_bearing_deg
                FROM transit_route r
                JOIN transit_route_shape s ON s.route_id = r.id
                CROSS JOIN (SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326) AS v_pt) pt
                WHERE (r.agency_id = %s OR r.concessionaire_id IN (SELECT id FROM transit_concessionaire WHERE agency_id = %s))
                  AND s.valid_from <= CURRENT_DATE
                  AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
                ORDER BY s.geom <-> pt.v_pt
                LIMIT 1;
                """,
                (lon, lat, agency_id, agency_id)
            )
            best = cur.fetchone()
            if best and best[0] is not None:
                best_dev = float(best[4]) if best[4] is not None else 9999.0
                orig_dev = float(row[3]) if (row and row[3] is not None) else 9999.0
                if not row or row[0] is None or best_dev < orig_dev:
                    cur.close()
                    return {
                        "matched_route_code": str(best[0]).lower(),
                        "progress_percent": float(best[1]) if best[1] is not None else 0.0,
                        "distance_traveled_km": float(best[2]) if best[2] is not None else 0.0,
                        "total_km": float(best[3]) if best[3] is not None else 0.0,
                        "deviation_meters": best_dev,
                        "route_bearing_deg": float(best[5]) if len(best) > 5 and best[5] is not None else None,
                    }

        cur.close()
        if row and row[0] is not None:
            return {
                "matched_route_code": clean_route,
                "progress_percent": float(row[0]) if row[0] is not None else 0.0,
                "distance_traveled_km": float(row[1]) if row[1] is not None else 0.0,
                "total_km": float(row[2]) if row[2] is not None else 0.0,
                "deviation_meters": float(row[3]) if row[3] is not None else 0.0,
                "route_bearing_deg": float(row[4]) if len(row) > 4 and row[4] is not None else None,
            }
    except Exception as e:
        logger.debug(f"Aviso PostGIS progress: {e}")
        try:
            _pg_thread_local.conn = None
        except Exception:
            pass
    return None

def insert_telemetry_to_pg(ping: TelemetryPing):
    """Guarda el ping en PostgreSQL. El trigger asigna automáticamente geometría y shape_id vigente."""
    try:
        conn = _get_thread_pg_conn()
        cur = conn.cursor()
        recorded_at = ping.effective_timestamp
        op_type = ping.type if ping.type is not None else 2
        acc = ping.precision
        alt = ping.altitud or 0.0
        heading = ping.heading_deg if (ping.heading_deg is not None and ping.heading_deg > 0) else ping.effective_heading
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
        cur.close()
    except Exception as e:
        logger.debug(f"Aviso: Inserción en PostgreSQL diferida: {e}")
        try:
            _pg_thread_local.conn = None
        except Exception:
            pass

# ------------------------------------------------------------------------------
# Consultas GeoJSON de Shapes y Paradas con Vigencia
# ------------------------------------------------------------------------------
def get_active_shapes_geojson(agency_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        query = """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(ST_AsGeoJSON(t.*)::json), '[]'::json)
            )
            FROM (
                SELECT 
                    s.id AS shape_id,
                    r.code AS route_code,
                    r.code AS route_id,
                    r.name AS route_name,
                    r.name AS name,
                    r.agency_id,
                    r.direction,
                    COALESCE(r.line_name, 'Línea General') AS line_name,
                    s.version,
                    s.valid_from::TEXT,
                    s.valid_until::TEXT,
                    s.total_km,
                    s.geom
                FROM transit_route r
                JOIN transit_route_shape s ON s.route_id = r.id
                WHERE s.valid_from <= CURRENT_DATE
                  AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
        """
        params = []
        if agency_id:
            query += " AND (r.agency_id = %s OR r.concessionaire_id IN (SELECT id FROM transit_concessionaire WHERE agency_id = %s))"
            params.extend([agency_id, agency_id])
        query += " ) t;"
        cur.execute(query, params)
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

def get_active_stops_geojson(agency_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        query = """
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
        """
        params = []
        if agency_id:
            query += " AND (agency_id = %s OR agency_id IS NULL)"
            params.append(agency_id)
        query += " ) t;"
        cur.execute(query, params)
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
                COALESCE(r.destination_longitude, ST_X(ST_EndPoint(sh.geom))) as dest_lon,
                r.direction,
                COALESCE(r.line_name, 'Línea General') as line_name
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
            for r_id, code, name, orig_name, dest_name, o_lat, o_lon, d_lat, d_lon, direction, l_name in rows:
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
                    "direction": direction,
                    "line_name": l_name,
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

def hydrate_active_fleet_from_postgis(force: bool = False) -> int:
    """
    Restaura el estado de la flota activa desde PostgreSQL (telemetry_ping)
    hacia Redis y la memoria interna si Redis está vacío o si se fuerza la hidratación.
    Garantiza que al reiniciar el broker o el contenedor, los buses sigan apareciendo
    inmediatamente en /headway, /map, /compliance y demás dashboards.
    """
    global active_vehicles_memory
    if not force and redis_client:
        try:
            keys = redis_client.keys("vehicle:*")
            if len(keys) > 0:
                logger.info(f"Redis ya contiene {len(keys)} vehículos activos en caché.")
                return len(keys)
        except Exception as e:
            logger.debug(f"Aviso consultando Redis en hidratación: {e}")

    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=3
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if redis_client:
            try:
                old_ids = list(redis_client.smembers("active_buses_set"))
                valid_ags = get_valid_agencies()
                for old_id in old_ids:
                    st = get_vehicle_state(old_id)
                    if st and st.get("agency_id") and st.get("agency_id") not in valid_ags:
                        redis_client.delete(f"vehicle:{old_id}")
                        redis_client.srem("active_buses_set", old_id)
            except Exception as e:
                logger.debug(f"Redis cleanup error: {e}")

        valid_agencies_list = list(get_valid_agencies())
        cur.execute("""
            SELECT DISTINCT ON (agency_id, bus_internal_code)
                bus_internal_code as mean_id,
                license_plate,
                route_id,
                agency_id,
                latitude,
                longitude,
                speed_kmh as velocidad,
                heading_deg as rumbo,
                odometer_km,
                recorded_at as fecha_hora
            FROM telemetry_ping
            WHERE (agency_id = ANY(%s) OR agency_id IS NOT NULL)
            ORDER BY agency_id, bus_internal_code, recorded_at DESC;
        """, (valid_agencies_list,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        count = 0
        now_utc = datetime.now(timezone.utc)
        for r in rows:
            bus_key = str(r["mean_id"])
            route_code = (r["route_id"] or "020f").lower()
            plate = r["license_plate"] or f"COCHE-{bus_key}"
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            raw_speed = float(r["velocidad"] or 0.0)
            heading = float(r["rumbo"] or 0.0)
            rec_time = r["fecha_hora"].isoformat() if hasattr(r["fecha_hora"], "isoformat") else str(r["fecha_hora"])

            # Comprobar antigüedad del ping (>30 min => Falla GPS)
            minutes_old = 0.0
            is_stale = False
            try:
                dt_p = r["fecha_hora"]
                if not hasattr(dt_p, "tzinfo") or dt_p.tzinfo is None:
                    dt_p = dt_p.replace(tzinfo=timezone.utc)
                minutes_old = round((now_utc - dt_p).total_seconds() / 60.0, 1)
                if minutes_old > 30.0:
                    is_stale = True
            except Exception:
                pass

            agency_val = r["agency_id"] or "004B"
            progress = calculate_shape_progress(lat, lon, route_code, agency_val, bus_id=bus_key)
            if progress and progress.get("matched_route_code"):
                matched_c = progress["matched_route_code"]
                if route_code in ("0000", "", "none", "depot", "taller"):
                    route_code = matched_c
            pct = progress["progress_percent"] if progress else 0.0
            dist_km = progress["distance_traveled_km"] if progress else 0.0
            total_km = progress["total_km"] if progress else 0.0
            dev_m = progress["deviation_meters"] if progress else 0.0

            if is_stale:
                curr_state = "GPS_FAULT"
                geofence = f"Falla GPS (Sin señal hace {int(minutes_old)}m)"
                speed = 0.0
            elif route_code in ("0000", "", "depot", "taller") and raw_speed < 5.0:
                curr_state = "DEPOT"
                geofence = "En Depósito / Patio"
                speed = raw_speed
            elif pct >= 97.5 or (total_km > 0 and (total_km - dist_km) <= 0.35 and raw_speed < 5.0):
                curr_state = "AT_DESTINATION"
                geofence = "Terminal Llegada"
                speed = raw_speed
            elif (pct < 2.5 or dist_km < 0.35) and raw_speed < 5.0:
                curr_state = "AT_ORIGIN"
                geofence = "En Cabecera (Origen)"
                speed = raw_speed
            else:
                curr_state = "IN_TRANSIT"
                geofence = "En Itinerario"
                speed = raw_speed

            v_state = {
                "bus_id": bus_key,
                "license_plate": plate,
                "agency_id": r["agency_id"] or "004B",
                "route_id": route_code,
                "current_state": curr_state,
                "state": curr_state,
                "crossed_checkpoints": set(),
                "latitude": lat,
                "longitude": lon,
                "last_latitude": lat,
                "last_longitude": lon,
                "speed_kmh": speed,
                "last_speed_kmh": speed,
                "is_gps_fault": is_stale,
                "minutes_since_ping": minutes_old,
                "heading_deg": heading,
                "odometer_km": float(r["odometer_km"] or 0.0),
                "last_ping_time": rec_time,
                "speed_alert": False,
                "deviation_alert": (dev_m > MAX_DEVIATION_METERS) if not is_stale else False,
                "current_geofence_name": geofence,
                "progress_percent": pct,
                "distance_traveled_km": dist_km,
                "route_total_km": total_km,
                "deviation_meters": dev_m,
            }

            if is_stale:
                v_state["status_display"] = f"Falla de GPS ({int(minutes_old)}m sin reporte)"
            elif street_resolver:
                try:
                    st_info = street_resolver.format_bus_status(
                        current_state=curr_state,
                        route_code=route_code,
                        lat=lat,
                        lon=lon,
                        distance_km=dist_km,
                        speed_kmh=speed,
                        deviation_meters=dev_m
                    )
                    v_state["status_display"] = st_info["status_display"]
                    v_state["street_name"] = st_info["street_name"]
                    v_state["approaching"] = st_info["approaching"]
                except Exception:
                    v_state["status_display"] = "En Circulación" if curr_state == "IN_TRANSIT" else curr_state
            else:
                v_state["status_display"] = "En Circulación" if curr_state == "IN_TRANSIT" else curr_state

            save_vehicle_state(bus_key, v_state, agency_id=r["agency_id"] or "004B")
            count += 1

        logger.info(f"✅ Hidratados {count} vehículos activos desde PostgreSQL a Redis / Memoria.")
        return count
    except Exception as e:
        logger.error(f"Error hidratando flota desde PostgreSQL: {e}")
        return 0

# ------------------------------------------------------------------------------
# Hilo Continuo de Sincronización Directa contra VMT Monitoreo Central (.env L49-L55)
# Permite consultar la flota Arapotí en tiempo real mientras el broker no reciba directo
# ------------------------------------------------------------------------------
VMT_DB_HOST = os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py")
VMT_DB_PORT = int(os.getenv("VMT_DB_PORT", "5432"))
VMT_DB_NAME = os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod")
VMT_DB_USER = os.getenv("VMT_DB_USER", "jefe-CID")
VMT_DB_PASS = os.getenv("VMT_DB_PASS", "vmtdmt")
VMT_AGENCY_ID = os.getenv("VMT_AGENCY_ID", "004B")

def process_telemetry_ping_internal(ping: TelemetryPing, background_tasks: Optional[BackgroundTasks] = None) -> Dict[str, Any]:
    bus_key = ping.effective_bus_id
    now_iso = ping.effective_timestamp
    speed = ping.effective_speed
    heading = ping.effective_heading
    plate = ping.effective_license_plate

    # Filtrar por empresas registradas en la plataforma
    agency = (ping.agency_id or VMT_AGENCY_ID).strip()
    valid_agencies = get_valid_agencies()
    if agency not in valid_agencies and agency not in (VMT_AGENCY_ID, "004B"):
        return {"status": "ignored", "reason": "agency_mismatch", "bus_id": bus_key, "agency_id": agency}

    # Validación de desfase de reloj del GPS (desfase severo >24 horas => alinear a tiempo real actual)
    now_dt = datetime.now(timezone.utc)
    try:
        clean_ts = str(now_iso).replace("Z", "+00:00")
        dt_ping = datetime.fromisoformat(clean_ts)
        if dt_ping.tzinfo is None:
            dt_ping = dt_ping.replace(tzinfo=timezone.utc)
        diff_hours = abs((now_dt - dt_ping).total_seconds()) / 3600.0
        if diff_hours > 24.0:
            now_iso = now_dt.isoformat()
    except Exception:
        pass

    # Validación de Coordenadas Geográficas (Res. GVMT 065/2024 Sección 5.1)
    if (abs(ping.latitude) < 1e-6 and abs(ping.longitude) < 1e-6) or not (-90.0 <= ping.latitude <= 90.0) or not (-180.0 <= ping.longitude <= 180.0):
        logger.warning(f"Coordenadas descartadas (inválidas o 0,0): ({ping.latitude}, {ping.longitude}) para móvil {bus_key}")
        return {"status": "ignored", "reason": "invalid_coordinates", "bus_id": bus_key}

    # 2. Recuperar o Inicializar Estado (aislado por empresa)
    v_state = get_vehicle_state(bus_key, agency_id=agency)
    raw_ping_time = str(ping.fecha_hora or ping.fecha_hora_procesamiento or ping.timestamp or now_iso).strip()
    is_new_vehicle = v_state is None

    prev_lat = v_state.get("last_latitude") if v_state else None
    prev_lon = v_state.get("last_longitude") if v_state else None
    prev_time = v_state.get("last_ping_time") if v_state else None
    prev_raw_time = v_state.get("raw_ping_time") if v_state else None
    prev_heading = v_state.get("heading_deg") if v_state else None

    if not v_state:
        v_state = {
            "bus_id": bus_key,
            "license_plate": plate,
            "agency_id": agency,
            "route_id": ping.route_id or "020f",
            "current_state": "IN_TRANSIT",
            "state": "IN_TRANSIT",
            "crossed_checkpoints": set(),
            "latitude": ping.latitude,
            "longitude": ping.longitude,
            "last_latitude": ping.latitude,
            "last_longitude": ping.longitude,
            "last_speed_kmh": speed,
            "speed_kmh": speed,
            "heading_deg": heading,
            "odometer_km": ping.odometer_km or 0.0,
            "last_ping_time": now_iso,
            "raw_ping_time": raw_ping_time,
            "speed_alert": False,
            "deviation_alert": False,
            "current_geofence_name": "En Itinerario",
            "progress_percent": 0.0,
            "distance_traveled_km": 0.0,
            "route_total_km": 0.0,
            "deviation_meters": 0.0,
        }

    # 2.0 Monotonicidad Temporal y Deduplicación Estricta:
    # Evita que pings rezagados o duplicados hagan retroceder o saltar la posición del bus (efecto elástico)
    if not is_new_vehicle:
        if prev_lat is not None and prev_lon is not None:
            is_same_coords = (
                abs(float(prev_lat) - float(ping.latitude)) < 1e-7 and
                abs(float(prev_lon) - float(ping.longitude)) < 1e-7
            )
            is_same_time = (
                (prev_raw_time is not None and str(prev_raw_time) == raw_ping_time) or
                (prev_time is not None and str(prev_time) == str(now_iso))
            )
            if is_same_coords and is_same_time:
                return {
                    "status": "ignored",
                    "reason": "duplicate_ping",
                    "bus_id": bus_key,
                    "timestamp": now_iso
                }

        # Descartar paquetes fuera de orden (estampa satelital más antigua que la última procesada)
        if prev_time and now_iso:
            try:
                curr_dt_chk = datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
                prev_dt_chk = datetime.fromisoformat(str(prev_time).replace("Z", "+00:00"))
                if curr_dt_chk.tzinfo is None:
                    curr_dt_chk = curr_dt_chk.replace(tzinfo=timezone.utc)
                if prev_dt_chk.tzinfo is None:
                    prev_dt_chk = prev_dt_chk.replace(tzinfo=timezone.utc)
                if curr_dt_chk < prev_dt_chk:
                    return {
                        "status": "ignored",
                        "reason": "out_of_order_ping",
                        "bus_id": bus_key,
                        "timestamp": now_iso
                    }
            except Exception:
                pass

    # 2.1 Velocidad y Rumbo Cinemático Geodésico Exacto (0.0° - 359.9°)
    # VMT app_monitoreo_mensajeoperativo entrega rumbos truncados/plegados a [0, 180]°,
    # lo cual invierte el ángulo cuando los buses viajan hacia el Oeste (~280°-320° en dirección Asunción).
    # Calculamos el rumbo exacto a partir del vector cinemático real de desplazamiento.
    if speed is None or speed < 0:
        speed = 0.0

    kinematic_heading = None
    if prev_lat is not None and prev_lon is not None:
        try:
            d_moved = haversine_meters(float(prev_lat), float(prev_lon), float(ping.latitude), float(ping.longitude))
            # Con desplazamiento físico >= 5m y velocidad >= 2 km/h, el rumbo geodésico atan2 es exacto al 100%
            if d_moved >= 5.0 and speed >= 2.0:
                kinematic_heading = calculate_bearing_degrees(float(prev_lat), float(prev_lon), float(ping.latitude), float(ping.longitude))
        except Exception as e:
            logger.debug(f"Error cálculo rumbo cinemático: {e}")

    if kinematic_heading is not None:
        heading = kinematic_heading
    elif speed < 2.0 and prev_heading is not None and float(prev_heading) > 0:
        # Si el vehículo está detenido o en semáforo, conservar el último rumbo válido para no rotar la flecha
        heading = float(prev_heading)
    elif prev_heading is not None and float(prev_heading) > 0:
        heading = float(prev_heading)
    else:
        # Primer reporte sin historial previo: tomar el valor del módem
        heading = float(ping.effective_heading or 0.0)

    ping.heading_deg = heading

    v_state["prev_latitude"] = prev_lat
    v_state["prev_longitude"] = prev_lon
    v_state["prev_ping_time"] = prev_time
    v_state["calculated_speed_kmh"] = speed
    v_state["latitude"] = ping.latitude
    v_state["longitude"] = ping.longitude
    v_state["last_latitude"] = ping.latitude
    v_state["last_longitude"] = ping.longitude
    v_state["last_speed_kmh"] = speed
    v_state["speed_kmh"] = speed
    v_state["heading_deg"] = heading
    v_state["is_gps_fault"] = False
    v_state["minutes_since_ping"] = 0.0
    if ping.route_id:
        v_state["route_id"] = ping.route_id
    if ping.agency_id:
        v_state["agency_id"] = ping.agency_id
    if ping.odometer_km:
        v_state["odometer_km"] = ping.odometer_km
    v_state["last_ping_time"] = now_iso
    v_state["raw_ping_time"] = raw_ping_time

    # 3. Guardado en PostgreSQL (reutilizando conexión thread-local en worker o vía BackgroundTasks en HTTP)
    if background_tasks:
        background_tasks.add_task(insert_telemetry_to_pg, ping)
    else:
        insert_telemetry_to_pg(ping)

    # 4. Cálculo PostGIS de Progreso en Ruta y Desvío Exacto
    bus_key = str(v_state.get("bus_id") or ping.bus_internal_code or "").strip()
    agency_key = str(v_state.get("agency_id") or ping.agency_id or "004B").strip()

    progress = calculate_shape_progress(
        ping.latitude, ping.longitude, v_state.get("route_id", "020f"), agency_key, bus_id=bus_key
    )
    
    old_state = v_state.get("current_state", "IN_TRANSIT")
    route_code = (v_state.get("route_id") or "").lower()

    if progress:
        pct = progress["progress_percent"]
        dist_km = progress["distance_traveled_km"]
        total_km = progress["total_km"]
        dev_m = progress["deviation_meters"]
        matched_route = progress.get("matched_route_code")
        route_bearing = progress.get("route_bearing_deg")

        # Si aún no tenemos rumbo cinemático previo y el módem envió rumbo plegado [0, 180],
        # desambiguar con la dirección oficial del trazado en ese punto
        if kinematic_heading is None and prev_heading is None and route_bearing is not None and heading > 0.0:
            cand1 = heading
            cand2 = (heading + 180.0) % 360.0
            diff1 = min(abs(cand1 - route_bearing), 360.0 - abs(cand1 - route_bearing))
            diff2 = min(abs(cand2 - route_bearing), 360.0 - abs(cand2 - route_bearing))
            if diff2 < diff1 and diff1 > 90.0:
                heading = cand2
                ping.heading_deg = heading
                v_state["heading_deg"] = heading

        if matched_route and route_code in ("0000", "", "none", "depot", "taller"):
            v_state["route_id"] = matched_route
            route_code = matched_route.lower()

        v_state["progress_percent"] = pct
        v_state["distance_traveled_km"] = dist_km
        v_state["route_total_km"] = total_km
        v_state["deviation_meters"] = dev_m

        if dev_m > MAX_DEVIATION_METERS:
            v_state["deviation_alert"] = True
        else:
            v_state["deviation_alert"] = False

        # Detección de proximidad física a Cabecera Origen y Terminal Destino
        is_at_origin_geofence = False
        is_at_dest_geofence = False
        for r_meta in routes_cache:
            if str(r_meta.get("code", "")).lower() == route_code:
                orig = r_meta.get("origin")
                if orig and orig.get("latitude") is not None and orig.get("longitude") is not None:
                    dist_to_orig = haversine_meters(ping.latitude, ping.longitude, float(orig["latitude"]), float(orig["longitude"]))
                    if dist_to_orig <= float(orig.get("radius_meters", 400.0)):
                        is_at_origin_geofence = True
                dest = r_meta.get("destination")
                if dest and dest.get("latitude") is not None and dest.get("longitude") is not None:
                    dist_to_dest = haversine_meters(ping.latitude, ping.longitude, float(dest["latitude"]), float(dest["longitude"]))
                    if dist_to_dest <= float(dest.get("radius_meters", 400.0)):
                        is_at_dest_geofence = True
                break

        if route_code in ("0000", "", "depot", "taller") and speed < 5.0:
            v_state["current_state"] = "DEPOT"
            v_state["current_geofence_name"] = "En Depósito / Patio"
        elif (ping.type == 1 or pct >= 98.5 or (total_km > 0 and (total_km - dist_km) <= 0.25) or is_at_dest_geofence) and speed < 5.0:
            v_state["current_state"] = "AT_DESTINATION"
            v_state["current_geofence_name"] = "Terminal Llegada"
            if is_at_dest_geofence:
                v_state["progress_percent"] = 100.0
                v_state["distance_traveled_km"] = total_km
        elif ((pct < 1.5 or dist_km < 0.25) or is_at_origin_geofence) and speed < 5.0:
            v_state["current_state"] = "AT_ORIGIN"
            v_state["current_geofence_name"] = "En Cabecera (Origen)"
            if is_at_origin_geofence:
                v_state["progress_percent"] = 0.0
                v_state["distance_traveled_km"] = 0.0
        elif dev_m > MAX_DEVIATION_METERS and not is_at_origin_geofence and not is_at_dest_geofence:
            v_state["current_state"] = "IN_TRANSIT"
            v_state["current_geofence_name"] = f"En Circulación (Desvío {round(dev_m)}m)"
        else:
            v_state["current_state"] = "IN_TRANSIT"
            v_state["current_geofence_name"] = "En Itinerario"

    v_state["state"] = v_state["current_state"]

    # 4.5 Detección de Contrasentido / IDRuta Invertido (Ticket REQ-2026-0002)
    v_state["line_name"] = get_route_line_name(route_code)
    route_bearing = progress.get("route_bearing_deg") if progress else None
    prev_dist_km = v_state.get("prev_distance_traveled_km") or 0.0
    v_state["prev_distance_traveled_km"] = v_state.get("distance_traveled_km", 0.0)

    is_wrong_direction = False
    wrong_dir_reason = ""
    heading_diff = None

    if route_code not in ("0000", "", "none", "depot", "taller") and route_bearing is not None and speed >= 7.0 and dev_m <= 400.0:
        bus_h = v_state.get("heading_deg") or heading

        if bus_h is not None and bus_h > 0.0:
            diff = abs(bus_h - route_bearing) % 360.0
            if diff > 180.0:
                diff = 360.0 - diff
            heading_diff = round(diff, 1)

            # Si el ángulo es >= 105°, el vehículo se desplaza en sentido opuesto al trazado oficial
            if diff >= 105.0:
                is_wrong_direction = True
                wrong_dir_reason = f"Desplazamiento en contrasentido (Rumbo bus {round(bus_h)}° vs Ruta {round(route_bearing)}°, desfase {heading_diff}°)"

        # Comprobación de retroceso continuo de kilometraje en shape a velocidad de circulación
        if prev_dist_km > 0.5 and v_state.get("distance_traveled_km", 0.0) > 0:
            delta_dist = v_state["distance_traveled_km"] - prev_dist_km
            if delta_dist < -0.15 and speed >= 10.0:
                is_wrong_direction = True
                wrong_dir_reason = f"Retroceso continuo de km sobre el trazado ({round(delta_dist, 2)} km a {round(speed)} km/h)"

    if is_wrong_direction:
        v_state["wrong_direction_consecutive"] = v_state.get("wrong_direction_consecutive", 0) + 1
        if v_state["wrong_direction_consecutive"] >= 2:
            v_state["wrong_direction_alert"] = True
            v_state["wrong_direction_reason"] = wrong_dir_reason
            v_state["heading_diff_deg"] = heading_diff
            v_state["route_bearing_deg"] = round(route_bearing, 1) if route_bearing is not None else None
            v_state["suggested_opposite_route"] = get_opposite_route_code(route_code)
    else:
        if (heading_diff is not None and heading_diff < 80.0) or (speed < 5.0 and v_state.get("current_state") in ("AT_ORIGIN", "AT_DESTINATION", "DEPOT")):
            v_state["wrong_direction_consecutive"] = 0
            v_state["wrong_direction_alert"] = False
            v_state["wrong_direction_reason"] = ""
            v_state["suggested_opposite_route"] = None

    # 5. Detección de Eventos Operativos para Odoo (Res. GVMT 065/2024 & Monitoreo VMT)
    new_state = v_state["current_state"]
    if old_state != new_state:
        event_type = None
        if old_state in ("AT_ORIGIN", "DEPOT") and new_state == "IN_TRANSIT":
            event_type = "departure"
        elif old_state == "IN_TRANSIT" and new_state == "AT_DESTINATION":
            event_type = "arrival"
        elif new_state == "OFF_ROUTE" and old_state != "OFF_ROUTE":
            event_type = "deviation"

        if event_type:
            event_payload = {
                "event_type": event_type,
                "internal_number": bus_key,
                "license_plate": plate,
                "agency_id": agency,
                "route_code": v_state.get("route_id"),
                "latitude": ping.latitude,
                "longitude": ping.longitude,
                "speed_kmh": speed,
                "timestamp": now_iso,
                "progress_percent": v_state.get("progress_percent", 0.0),
                "distance_km": v_state.get("distance_traveled_km", 0.0),
                "deviation_meters": v_state.get("deviation_meters", 0.0),
            }
            logger.info(f"⚡ Disparando evento '{event_type}' hacia Odoo para Bus #{bus_key} (estado: {old_state} -> {new_state})")
            if background_tasks:
                background_tasks.add_task(dispatch_odoo_webhook_with_retry, event_payload)
            else:
                threading.Thread(target=dispatch_odoo_webhook_with_retry, args=(event_payload,), daemon=True).start()

    # Alerta por Velocidad
    if speed > SPEED_LIMIT_KMH and not v_state.get("speed_alert"):
        v_state["speed_alert"] = True
    elif speed <= SPEED_LIMIT_KMH:
        v_state["speed_alert"] = False

    # 5.5 Resolución Contextual de Calles e Intersección
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

    if v_state.get("wrong_direction_alert"):
        base_status = v_state.get("status_display") or "En Circulación"
        if not base_status.startswith("⚠️"):
            v_state["status_display"] = f"⚠️ Contrasentido ({base_status})"

    # 6. Guardar Estado en Redis (con aislamiento por agencia)
    save_vehicle_state(bus_key, v_state, agency_id=agency)

    # 7. Difusión WebSocket
    ws_payload = {
        "type": "vehicle_update",
        "vehicle": format_vehicle_for_client(v_state)
    }
    if background_tasks:
        background_tasks.add_task(ws_manager.broadcast, ws_payload)
    else:
        ws_manager.broadcast_sync(ws_payload)

    return {
        "status": "success",
        "bus_id": bus_key,
        "current_state": v_state["current_state"],
        "progress_percent": v_state.get("progress_percent", 0.0),
        "deviation_meters": v_state.get("deviation_meters", 0.0),
        "geofence": v_state["current_geofence_name"],
        "timestamp": now_iso
    }

_last_seen_vmt_pings: Dict[str, Tuple[Any, float, float, str]] = {}

def vmt_continuous_sync_worker():
    """Hilo continuo que consulta la BD del Viceministerio de Transporte (VMT) según .env"""
    logger.info(f"🔄 Iniciando sincronización continua con VMT ({VMT_DB_HOST}:{VMT_DB_PORT}/{VMT_DB_NAME}) para Agencia {VMT_AGENCY_ID}...")
    conn = None
    initial_load = True
    while True:
        try:
            if not conn or conn.closed:
                conn = psycopg2.connect(
                    host=VMT_DB_HOST,
                    port=VMT_DB_PORT,
                    dbname=VMT_DB_NAME,
                    user=VMT_DB_USER,
                    password=VMT_DB_PASS,
                    sslmode="require",
                    connect_timeout=10
                )
                logger.info(f"✅ Conexión establecida con VMT Monitoreo Central ({VMT_DB_HOST}). Flota en sincronía.")

            target_agencies = list(get_valid_agencies())
            if not target_agencies:
                target_agencies = ["004B", "002A", "0008"]

            cur = conn.cursor(cursor_factory=RealDictCursor)
            if initial_load:
                query = """
                    SELECT DISTINCT ON (agency_id, mean_id) 
                        id,
                        agency_id,
                        mean_id,
                        route_id,
                        driver_id,
                        latitude,
                        longitude,
                        rumbo,
                        velocidad,
                        fecha_hora,
                        fecha_hora_procesamiento
                    FROM app_monitoreo_mensajeoperativo
                    WHERE agency_id = ANY(%s)
                      AND fecha_hora_procesamiento >= NOW() - INTERVAL '12 hours'
                    ORDER BY agency_id, mean_id, id DESC;
                """
            else:
                query = """
                    SELECT DISTINCT ON (agency_id, mean_id) 
                        id,
                        agency_id,
                        mean_id,
                        route_id,
                        driver_id,
                        latitude,
                        longitude,
                        rumbo,
                        velocidad,
                        fecha_hora,
                        fecha_hora_procesamiento
                    FROM app_monitoreo_mensajeoperativo
                    WHERE agency_id = ANY(%s)
                      AND fecha_hora_procesamiento >= NOW() - INTERVAL '30 minutes'
                    ORDER BY agency_id, mean_id, id DESC;
                """
            cur.execute(query, (target_agencies,))
            rows = cur.fetchall()
            cur.close()
            if initial_load and rows:
                logger.info(f"📡 Carga inicial VMT completada: {len(rows)} buses detectados para agencias {target_agencies}.")
                initial_load = False

            for r in rows:
                bus_key = str(r["mean_id"]).strip()
                if not bus_key:
                    continue
                # Estampas temporales: satelital GPS original emitida por el módem vs llegada al servidor VMT
                gps_dt = r.get("fecha_hora")
                proc_dt = r.get("fecha_hora_procesamiento")
                gps_iso = gps_dt.isoformat() if hasattr(gps_dt, "isoformat") else str(gps_dt) if gps_dt else None
                proc_iso = proc_dt.isoformat() if hasattr(proc_dt, "isoformat") else str(proc_dt) if proc_dt else None
                rec_iso = gps_iso or proc_iso or datetime.now(timezone.utc).isoformat()
                lat = float(r["latitude"])
                lon = float(r["longitude"])
                row_id = r.get("id")

                ping_agency = r.get("agency_id") or VMT_AGENCY_ID

                # Punto 1: Deduplicación incremental en memoria por agencia y bus
                cache_key = f"{ping_agency}_{bus_key}"
                cache_sig = (row_id, round(lat, 6), round(lon, 6), gps_iso or proc_iso)
                if _last_seen_vmt_pings.get(cache_key) == cache_sig:
                    continue
                _last_seen_vmt_pings[cache_key] = cache_sig

                ping_agency = r.get("agency_id") or VMT_AGENCY_ID
                ping_route = r.get("route_id")
                if not ping_route or ping_route == "None":
                    if ping_agency == "002A":
                        ping_route = "0138"
                    elif ping_agency == "0008":
                        ping_route = "004a"
                    else:
                        ping_route = "020f"

                ping_obj = TelemetryPing(
                    bus_id=bus_key,
                    mean_id=bus_key,
                    agency_id=ping_agency,
                    route_id=ping_route,
                    driver_id=r.get("driver_id") or "",
                    latitude=lat,
                    longitude=lon,
                    velocidad=float(r["velocidad"] or 0.0),
                    rumbo=float(r["rumbo"] or 0.0),
                    fecha_hora=gps_iso or rec_iso,
                    fecha_hora_procesamiento=proc_iso or rec_iso
                )

                process_telemetry_ping_internal(ping_obj)

        except Exception as e:
            logger.warning(f"Aviso en sincronización continua VMT: {e}")
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
            conn = None

        time.sleep(5)

def start_vmt_poller_thread():
    t = threading.Thread(target=vmt_continuous_sync_worker, daemon=True, name="VMT-Continuous-Poller")
    t.start()

def start_billetaje_poller_thread():
    """Inicia el worker periódico para sincronizar ramales de validadores y pasajes de Jaha."""
    def _run():
        import time
        from billetaje_service import sync_billetaje_all
        logger.info("💳 Iniciando sincronizador de Billetaje Electrónico Jaha (EPAS)...")
        # Primera sincronización tras 10s de arranque
        time.sleep(10)
        try:
            sync_billetaje_all(redis_client)
        except Exception as e:
            logger.debug(f"Aviso sync inicial Billetaje: {e}")

        while True:
            try:
                time.sleep(60)
                sync_billetaje_all(redis_client)
            except Exception as e:
                logger.debug(f"Aviso en loop Billetaje: {e}")
                time.sleep(30)

    t = threading.Thread(target=_run, name="billetaje_poller", daemon=True)
    t.start()
    logger.info("✅ Sincronizador de Billetaje Electrónico Jaha iniciado en background.")

@app.on_event("startup")
def startup_event():
    global main_event_loop
    try:
        main_event_loop = asyncio.get_running_loop()
    except Exception:
        pass
    logger.info("🚀 Iniciando Broker GPS con Redis, PostgreSQL, PostGIS y WebSockets...")
    sync_geofences_from_postgis()
    hydrate_active_fleet_from_postgis()

    # Iniciar Consumidor Mosquitto MQTT en hilo desacoplado
    try:
        from mqtt_consumer import start_consumer_thread
        start_consumer_thread()
        logger.info("✅ Consumidor MQTT Mosquitto iniciado en background.")
    except Exception as e:
        logger.warning(f"No se pudo iniciar el consumidor MQTT: {e}")

    # Iniciar Sincronizador Continuo directo a BD Monitoreo VMT (.env: VMT_DB_HOST, VMT_AGENCY_ID)
    start_vmt_poller_thread()

    # Iniciar Sincronizador de Billetaje Electrónico Jaha (Validadores y Pasajeros)
    start_billetaje_poller_thread()

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
    if DEVICE_API_TOKEN and x_device_token != DEVICE_API_TOKEN:
        raise HTTPException(status_code=401, detail="Dispositivo no autorizado. Provea X-Device-Token válido.")
    return process_telemetry_ping_internal(ping, background_tasks=background_tasks)

# ------------------------------------------------------------------------------
# Endpoints REST de Shapes, Paradas y Rutas
# ------------------------------------------------------------------------------
@app.get("/api/v1/shapes/active")
async def api_get_active_shapes(request: Request, agency_id: Optional[str] = Query(None)):
    """Retorna las geometrías (LineString) de las rutas vigentes hoy en formato GeoJSON, filtradas por empresa."""
    user = get_current_user_from_request(request)
    target_agency = agency_id
    if user and not user.get("is_admin") and user.get("agency_id"):
        target_agency = user.get("agency_id")
    return get_active_shapes_geojson(agency_id=target_agency)

@app.get("/api/v1/shapes/history")
async def api_get_historical_shape(
    route_code: str = Query("020f", description="Código del ramal (ej: 020f)"),
    agency_id: str = Query("004B", description="Código de empresa (ej: 004B)"),
    date: str = Query(..., description="Fecha histórica de consulta (YYYY-MM-DD)")
):
    """Retorna el trazado GeoJSON que estaba vigente en una fecha histórica específica."""
    return get_historical_shape_geojson(route_code, agency_id, date)

@app.get("/api/v1/stops/active")
async def api_get_active_stops(request: Request, agency_id: Optional[str] = Query(None)):
    """Retorna todas las paradas y cabeceras activas en formato GeoJSON, filtradas por empresa."""
    user = get_current_user_from_request(request)
    target_agency = agency_id
    if user and not user.get("is_admin") and user.get("agency_id"):
        target_agency = user.get("agency_id")
    return get_active_stops_geojson(agency_id=target_agency)


@app.get("/api/v1/routes")
async def api_get_routes(request: Request, agency_id: Optional[str] = Query(None)):
    """Catálogo maestro de líneas y ramales filtrado por empresa / concesionaria."""
    user = get_current_user_from_request(request)
    target_agency = agency_id
    if user and not user.get("is_admin") and user.get("agency_id"):
        target_agency = user.get("agency_id")
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor()
        query = """
            SELECT r.id, r.code, r.name, r.agency_id, r.direction, r.origin, r.destination,
                   s.version AS active_version, s.valid_from, s.valid_until, s.total_km,
                   COALESCE(r.line_name, 'Línea General') AS line_name
            FROM transit_route r
            LEFT JOIN transit_route_shape s ON s.route_id = r.id 
                 AND s.valid_from <= CURRENT_DATE 
                 AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
        """
        params = []
        if target_agency:
            query += " WHERE (r.agency_id = %s OR r.concessionaire_id IN (SELECT id FROM transit_concessionaire WHERE agency_id = %s))"
            params.extend([target_agency, target_agency])
        query += " ORDER BY r.code;"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "id": r[0], "code": r[1], "route_id": r[1], "name": r[2], "agency_id": r[3], "direction": r[4],
                "origin": r[5], "destination": r[6], "active_version": r[7],
                "valid_from": str(r[8]) if r[8] else None,
                "valid_until": str(r[9]) if r[9] else "Actualidad",
                "total_km": float(r[10]) if r[10] else None,
                "line_name": r[11] or get_route_line_name(r[1])
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
    session_id = websocket.cookies.get("session_id") or websocket.query_params.get("session_id")
    user = validate_odoo_session(session_id) if session_id else None
    agency_filter = user.get("agency_id") if (user and not user.get("is_admin")) else websocket.query_params.get("agency_id")
    await ws_manager.connect(websocket, agency_filter=agency_filter)
    try:
        initial_data = {
            "type": "init",
            "vehicles": get_all_active_vehicles(agency_filter=agency_filter),
            "events": event_history_memory[-10:],
            "shapes": get_active_shapes_geojson(agency_id=agency_filter),
            "stops": get_active_stops_geojson(agency_id=agency_filter)
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
async def get_live_fleet(request: Request):
    user = get_current_user_from_request(request)
    agency_filter = user.get("agency_id") if (user and not user.get("is_admin")) else request.query_params.get("agency_id")
    vehicles = get_all_active_vehicles(agency_filter=agency_filter)
    if not vehicles:
        hydrate_active_fleet_from_postgis(force=True)
        vehicles = get_all_active_vehicles(agency_filter=agency_filter)
    return {
        "status": "success",
        "count": len(vehicles),
        "vehicles": vehicles,
        "events": event_history_memory[-10:],
        "shapes": get_active_shapes_geojson(agency_id=agency_filter),
        "stops": get_active_stops_geojson(agency_id=agency_filter)
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

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/.well-known/appspecific/{path:path}", include_in_schema=False)
async def devtools_probe(path: str):
    return Response(status_code=204)

# ------------------------------------------------------------------------------
# Autenticación y Sesión Unificada Odoo ERP (flota_db)
# ------------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_view(request: Request, redirect: str = "/headway"):
    user = get_current_user_from_request(request)
    if user:
        return RedirectResponse(url=redirect or "/headway", status_code=303)
    return HTMLResponse(render_login_page(redirect_url=redirect))

@app.post("/login")
async def login_submit(request: Request):
    login = ""
    password = ""
    redirect_url = "/headway"
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            login = str(body.get("login", "")).strip()
            password = str(body.get("password", "")).strip()
            redirect_url = str(body.get("redirect", "/headway") or "/headway").strip()
        else:
            raw_body = (await request.body()).decode("utf-8")
            parsed = urllib.parse.parse_qs(raw_body)
            login = parsed.get("login", [""])[0].strip()
            password = parsed.get("password", [""])[0].strip()
            redirect_url = parsed.get("redirect", ["/headway"])[0].strip() or "/headway"
    except Exception as e:
        logger.warning(f"Error parseando login submit: {e}")
    
    success, session_id, user_dict, err_msg = authenticate_odoo_user(login, password)
    if not success or not session_id:
        return HTMLResponse(
            render_login_page(error_msg=err_msg or "Credenciales incorrectas en Odoo ERP.", redirect_url=redirect_url),
            status_code=401
        )
    
    resp = RedirectResponse(url=redirect_url, status_code=303)
    resp.set_cookie(
        key="session_id",
        value=session_id,
        max_age=86400 * 7,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return resp

@app.get("/logout")
async def logout_view(request: Request):
    session_id = request.cookies.get("session_id")
    invalidate_session(session_id)
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key="session_id", path="/")
    return resp

# ------------------------------------------------------------------------------
# Informe y Diccionario de Datos de la Base de Datos (flota_db)
# ------------------------------------------------------------------------------
from db_report_service import get_db_schema_html

@app.get("/db-schema", response_class=HTMLResponse)
@app.get("/database", response_class=HTMLResponse)
async def db_schema_view(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?redirect=/db-schema", status_code=303)
    return HTMLResponse(get_db_schema_html())

# ------------------------------------------------------------------------------
# Tablero Lineal de Frecuencias & Detector de Pegonamiento (Headway Monitoring)
# ------------------------------------------------------------------------------
from headway_service import get_headway_data, get_headway_html

@app.post("/api/v1/fleet/hydrate")
async def api_hydrate_fleet(force: bool = Query(True, description="Forzar recarga completa desde PostgreSQL")):
    """Recarga el estado de los buses activos desde PostgreSQL hacia Redis y memoria."""
    count = hydrate_active_fleet_from_postgis(force=force)
    return {"status": "success", "hydrated_buses": count}

@app.get("/api/v1/headway/data")
async def api_headway_data(request: Request):
    user = get_current_user_from_request(request)
    if not user and not is_device_or_internal_token(request):
        raise HTTPException(status_code=401, detail="Sesión no iniciada. Inicie sesión en Odoo ERP.")

    agency_id = user.get("agency_id") if (user and not user.get("is_admin")) else request.query_params.get("agency_id")
    hw_data = get_headway_data(redis_client=redis_client, active_vehicles_memory=active_vehicles_memory, agency_id=agency_id)
    if hw_data.get("total_active_buses", 0) == 0:
        logger.info("Headway solicitó datos pero encontró 0 buses. Ejecutando auto-hidratación desde PostgreSQL...")
        hydrate_active_fleet_from_postgis(force=True)
        hw_data = get_headway_data(redis_client=redis_client, active_vehicles_memory=active_vehicles_memory, agency_id=agency_id)
    return hw_data

class RouteReassignPayload(BaseModel):
    bus_id: str
    new_route_code: str
    agency_id: Optional[str] = "0008"

@app.post("/api/v1/headway/reassign_route")
async def api_headway_reassign_route(payload: RouteReassignPayload, request: Request):
    """Permite al operador reasignar de inmediato un bus al ramal correcto desde el tablero.
    Fija el bloqueo en Redis y actualiza el despacho en Odoo (transit_dispatch).
    """
    bus_id = str(payload.bus_id).strip()
    agency_id = str(payload.agency_id or "0008").strip()
    new_route_code = str(payload.new_route_code).strip().lower()

    if not bus_id or not new_route_code:
        raise HTTPException(status_code=400, detail="bus_id y new_route_code son requeridos")

    # 1. Obtener datos de la nueva ruta
    route_name = new_route_code.upper()
    try:
        conn = _get_thread_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name FROM transit_route WHERE LOWER(code) = %s LIMIT 1", (new_route_code,))
        r_db = cur.fetchone()
        cur.close()
        if r_db and r_db[2]:
            route_name = r_db[2]
    except Exception as e:
        logger.debug(f"Aviso consultando ruta: {e}")

    # 2. Bloquear en Redis durante 4 horas (14400s) para evitar que vuelva a cambiar
    if redis_client:
        try:
            redis_client.setex(f"vehicle_route_lock:{agency_id}:{bus_id}", 14400, new_route_code)
            redis_client.setex(f"vehicle_route_lock:{bus_id}", 14400, new_route_code)
        except Exception as e:
            logger.debug(f"Aviso bloqueo Redis: {e}")

    # 3. Actualizar estado del bus en Redis / memoria inmediatamente
    v_state = get_vehicle_state(bus_id, agency_id=agency_id)
    if v_state:
        v_state["route_id"] = new_route_code
        v_state["route_locked"] = True
        lat = v_state.get("latitude")
        lon = v_state.get("longitude")
        if lat and lon:
            prog = calculate_shape_progress(lat, lon, new_route_code, agency_id=agency_id, bus_id=bus_id)
            if prog:
                v_state["progress_percent"] = prog["progress_percent"]
                v_state["distance_traveled_km"] = prog["distance_traveled_km"]
                v_state["route_total_km"] = prog["total_km"]
                v_state["deviation_meters"] = prog["deviation_meters"]
        save_vehicle_state(bus_id, v_state, agency_id=agency_id)

    # 4. Actualizar despacho activo en Odoo (transit_dispatch)
    candidates = [bus_id, bus_id.lstrip("0")]
    try:
        dec_num = str(int(bus_id, 16))
        if dec_num not in candidates:
            candidates.append(dec_num)
    except Exception:
        pass

    try:
        conn = _get_thread_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE transit_dispatch
            SET route_id = (SELECT id FROM transit_route WHERE LOWER(code) = %s LIMIT 1),
                write_date = NOW()
            WHERE id = (
                SELECT d.id
                FROM transit_dispatch d
                JOIN fleet_vehicle v ON d.vehicle_id = v.id
                WHERE (v.bus_internal_number = ANY(%s) OR v.license_plate = ANY(%s))
                  AND d.state IN ('draft', 'inspected', 'dispatched', 'in_transit')
                  AND d.date = CURRENT_DATE
                ORDER BY d.actual_departure DESC NULLS LAST, d.scheduled_departure DESC
                LIMIT 1
            );
        """, (new_route_code, candidates, candidates))
        cur.close()
    except Exception as e:
        logger.debug(f"Aviso actualizando transit_dispatch: {e}")

    return {
        "success": True,
        "message": f"Coche #{bus_id} reasignado al ramal {new_route_code.upper()} ({route_name})",
        "bus_id": bus_id,
        "route_code": new_route_code,
        "route_name": route_name
    }

@app.get("/api/v1/headway/routes_for_agency")
async def api_headway_routes_for_agency(agency_id: Optional[str] = "0008"):
    """Retorna los ramales disponibles para el selector de reasignación manual."""
    try:
        conn = _get_thread_pg_conn()
        cur = conn.cursor()
        if agency_id:
            cur.execute("""
                SELECT code, name, direction, COALESCE(distance_km, 0), COALESCE(line_name, 'Línea General')
                FROM transit_route
                WHERE agency_id = %s AND active = TRUE
                ORDER BY line_name ASC, code ASC;
            """, (agency_id,))
        else:
            cur.execute("""
                SELECT code, name, direction, COALESCE(distance_km, 0), COALESCE(line_name, 'Línea General')
                FROM transit_route
                WHERE active = TRUE
                ORDER BY line_name ASC, code ASC;
            """)
        rows = cur.fetchall()
        cur.close()
        routes = [{"code": r[0], "name": r[1], "direction": r[2], "distance_km": float(r[3]), "line_name": r[4] or get_route_line_name(r[0])} for r in rows]
        return {"agency_id": agency_id, "routes": routes}
    except Exception as e:
        logger.error(f"Error cargando rutas por agencia: {e}")
        return {"agency_id": agency_id, "routes": []}

# ------------------------------------------------------------------------------
# Endpoints de Billetaje Electrónico Jaha (EPAS S.A.)
# ------------------------------------------------------------------------------
from billetaje_service import sync_billetaje_all, get_cached_financial_summary

@app.get("/api/v1/billetaje/summary")
async def api_billetaje_summary(agency_id: str = "0008"):
    """Retorna el resumen financiero y operacional diario de Billetaje Jaha."""
    fin = get_cached_financial_summary(redis_client, agency_id=agency_id)
    if not fin:
        try:
            res = sync_billetaje_all(redis_client, agency_id=agency_id)
            fin = res.get("financial_summary", {})
        except Exception as e:
            logger.error(f"Error sincronizando billetaje summary: {e}")
    return {"agency_id": agency_id, "summary": fin}

@app.post("/api/v1/billetaje/sync_now")
async def api_billetaje_sync_now(agency_id: str = "0008"):
    """Dispara una sincronización inmediata con la plataforma de Billetaje Jaha."""
    try:
        res = sync_billetaje_all(redis_client, agency_id=agency_id)
        return res
    except Exception as e:
        logger.error(f"Error forzando sync billetaje: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/headway", response_class=HTMLResponse)
async def headway_dashboard_view(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?redirect=/headway", status_code=303)
    return get_headway_html(user=user)

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
from compliance_service import get_today_compliance, get_compliance_alerts, get_compliance_html, get_available_services, get_available_companies

@app.get("/compliance", response_class=HTMLResponse)
async def compliance_dashboard(request: Request):
    """
    Dashboard interactivo de cumplimiento regulatorio (Res. GVMT 065/2024 & Dec. 710/2023)
    con soporte multilínea (Línea 20 E1, E2, E3, Línea 187, Línea 15/47, etc.),
    control de CBD, ICCBDM, IFO y cálculo de cuotas de despacho.
    """
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?redirect=/compliance", status_code=303)
    is_admin = bool(user.get("is_admin"))
    user_agency = user.get("agency_id") or "004B"
    user_company = user.get("company_name") or "Consorcio Arapotí"
    return HTMLResponse(get_compliance_html(default_agency=user_agency, default_company=user_company, is_admin=is_admin))

@app.get("/api/v1/compliance/companies")
async def api_compliance_companies(request: Request):
    """Lista de empresas/concesionarias registradas en el sistema."""
    user = get_current_user_from_request(request)
    companies = get_available_companies()
    if user and not user.get("is_admin") and user.get("agency_id"):
        companies = [c for c in companies if c.get("agency_id") == user.get("agency_id")]
    return companies

@app.get("/api/v1/compliance/services")
async def api_compliance_services(request: Request, agency_id: Optional[str] = Query(None)):
    """Lista de servicios operativos activos parametrizados en el sistema."""
    user = get_current_user_from_request(request)
    if not user and not is_device_or_internal_token(request):
        raise HTTPException(status_code=401, detail="Sesión no iniciada. Inicie sesión en Odoo ERP.")
    target_agency = agency_id
    if user and not user.get("is_admin") and user.get("agency_id"):
        target_agency = user.get("agency_id")
    return get_available_services(agency_id=target_agency)

@app.get("/api/v1/compliance/today")
async def api_compliance_today(
    request: Request,
    service: Optional[str] = Query(None, description="Filtrar por código de servicio (ej: ALL, E1, E2, E3, 187-R1)"),
    date: Optional[str] = Query(None, description="Fecha de evaluación (YYYY-MM-DD)"),
    agency_id: Optional[str] = Query(None, description="Código de empresa (ej: 004B, 0008, 002A)")
):
    """
    Datos JSON de cumplimiento del día actual o fecha evaluada.
    Incluye: CBD en itinerario, CBD_hora, CBD_franja, ICCBDM (0.7/0.3), IFO hora y franja,
    CBD objetivo (100% IFO), despachos ejecutados, auditoría de 4 semanas históricas y 5 estados.
    """
    user = get_current_user_from_request(request)
    if not user and not is_device_or_internal_token(request):
        raise HTTPException(status_code=401, detail="Sesión no iniciada. Inicie sesión en Odoo ERP.")
    target_agency = agency_id
    if user and not user.get("is_admin") and user.get("agency_id"):
        target_agency = user.get("agency_id")
    return get_today_compliance(redis_client, service_code=service, target_date=date, agency_id=target_agency)

@app.get("/api/v1/compliance/alerts")
async def api_compliance_alerts(
    request: Request,
    service: Optional[str] = Query(None, description="Filtrar alertas por código de servicio"),
    agency_id: Optional[str] = Query(None, description="Código de empresa")
):
    """
    Lista de alertas activas de déficit de cumplimiento.
    Se integra con notificaciones Odoo y MQTT.
    """
    user = get_current_user_from_request(request)
    target_agency = agency_id
    if user and not user.get("is_admin") and user.get("agency_id"):
        target_agency = user.get("agency_id")
    alerts = get_compliance_alerts(redis_client, service_code=service, agency_id=target_agency)
    return {
        "total": len(alerts),
        "has_alerts": len(alerts) > 0,
        "alerts": alerts
    }

@app.get("/api/v1/compliance/history")
async def api_compliance_history(
    request: Request,
    service: Optional[str] = Query(None, description="Filtrar historial por código de servicio"),
    agency_id: Optional[str] = Query(None, description="Código de empresa")
):
    """Historial de cumplimiento de los últimos 30 días."""
    user = get_current_user_from_request(request)
    target_agency = agency_id
    if user and not user.get("is_admin") and user.get("agency_id"):
        target_agency = user.get("agency_id")
    data = get_today_compliance(redis_client, service_code=service, agency_id=target_agency)
    return {
        "daily_quota": data.get("daily_quota", 692),
        "history": data.get("history_30d", [])
    }


# ------------------------------------------------------------------------------
# Hojas de Ruta y Encadenamiento Diario de Buses (Vehicle Duty API)
# ------------------------------------------------------------------------------
def get_daily_bus_schedules(target_date: Optional[str] = None, vehicle_code: Optional[str] = None) -> List[Dict[str, Any]]:
    d = target_date or datetime.now().date().isoformat()
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASS, connect_timeout=3
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                s.id AS schedule_id,
                s.name AS schedule_name,
                s.date::text AS date,
                s.state AS schedule_state,
                COALESCE(v.bus_internal_number, v.license_plate, 'Bus') AS bus_code,
                v.license_plate,
                COALESCE(c.name, 'Concesionaria') AS concessionaire,
                COALESCE(p.name, 'Sin Chofer') AS driver_name,
                l.id AS leg_id,
                l.sequence,
                l.leg_number,
                r.code AS route_code,
                r.name AS route_name,
                r.direction,
                r.origin,
                r.destination,
                r.distance_km,
                l.departure_time_str,
                l.duration_minutes,
                l.arrival_time_str,
                l.rest_minutes,
                l.suggested_next_departure_str,
                l.state AS leg_state
            FROM transit_bus_schedule s
            JOIN fleet_vehicle v ON v.id = s.vehicle_id
            LEFT JOIN transit_concessionaire c ON c.id = s.concessionaire_id
            LEFT JOIN res_partner p ON p.id = s.driver_id
            LEFT JOIN transit_bus_schedule_line l ON l.schedule_id = s.id
            LEFT JOIN transit_route r ON r.id = l.route_id
            WHERE s.date = %s
        """
        params = [d]
        if vehicle_code:
            query += " AND (v.bus_internal_number = %s OR v.license_plate = %s)"
            params.extend([vehicle_code, vehicle_code])
        query += " ORDER BY v.bus_internal_number ASC, l.sequence ASC"

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        grouped: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            b_code = r["bus_code"]
            if b_code not in grouped:
                grouped[b_code] = {
                    "schedule_id": r["schedule_id"],
                    "schedule_name": r["schedule_name"],
                    "date": r["date"],
                    "state": r["schedule_state"],
                    "bus_code": b_code,
                    "license_plate": r["license_plate"],
                    "concessionaire": r["concessionaire"],
                    "driver_name": r["driver_name"],
                    "legs": []
                }
            if r.get("leg_id"):
                grouped[b_code]["legs"].append({
                    "leg_number": r["leg_number"],
                    "sequence": r["sequence"],
                    "route_code": r["route_code"],
                    "route_name": r["route_name"],
                    "direction": r["direction"],
                    "origin": r["origin"],
                    "destination": r["destination"],
                    "distance_km": r["distance_km"],
                    "departure_time": r["departure_time_str"],
                    "duration_minutes": r["duration_minutes"],
                    "arrival_time": r["arrival_time_str"],
                    "rest_minutes": r["rest_minutes"],
                    "next_departure_suggested": r["suggested_next_departure_str"],
                    "state": r["leg_state"]
                })
        return list(grouped.values())
    except Exception as e:
        logger.debug(f"Aviso al consultar transit_bus_schedule: {e}")
        return []

@app.get("/api/v1/schedules/today")
async def api_schedules_today(
    date: Optional[str] = Query(None, description="Fecha YYYY-MM-DD (por defecto hoy)"),
    bus: Optional[str] = Query(None, description="Filtrar por número de interno o matrícula de bus")
):
    """
    Retorna la programación diaria de hojas de ruta y secuencias de itinerarios por bus.
    Muestra el encadenamiento de viajes (ida, retorno, rotación) con horas exactas y descansos.
    """
    data = get_daily_bus_schedules(target_date=date, vehicle_code=bus)
    return {
        "date": date or datetime.now().date().isoformat(),
        "total_vehicles_scheduled": len(data),
        "schedules": data
    }

# ------------------------------------------------------------------------------
# Conexión e Integración Waze for Cities (Connected Citizens Program - CCP)
# ------------------------------------------------------------------------------
from waze_service import fetch_waze_ccp_feed, correlate_waze_with_transit, get_waze_deep_link

@app.get("/api/v1/waze/traffic")
async def api_waze_traffic(refresh: bool = Query(False, description="Forzar refresco del feed Waze")):
    """
    Retorna el feed de tráfico en tiempo real de Waze for Cities (CCP):
    Incidentes (accidentes, obras, peligros) y congestiones viales (jams con nivel y retraso).
    """
    return fetch_waze_ccp_feed(force_refresh=refresh)

@app.get("/api/v1/waze/corridor-impacts")
async def api_waze_corridor_impacts():
    """
    Cruza los incidentes y atascos de Waze con los 6 corredores de transporte de la flota.
    Calcula demoras inducidas y lista coches afectados en cada ramal.
    """
    waze_data = fetch_waze_ccp_feed()
    hw_data = get_headway_data(redis_client=redis_client, active_vehicles_memory=active_vehicles_memory)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "waze_source": waze_data.get("source"),
        "total_alerts": waze_data.get("total_alerts", 0),
        "total_jams": waze_data.get("total_jams", 0),
        "corridor_impacts": correlate_waze_with_transit(waze_data, hw_data.get("routes", []))
    }

# ------------------------------------------------------------------------------
# Dashboard Radar Web en Vivo con PostGIS Shapes y Visor Histórico
# ------------------------------------------------------------------------------
@app.get("/map", response_class=HTMLResponse)
async def live_map_view(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?redirect=/map", status_code=303)
    user_agency = user.get("agency_id") or ""
    user_company = user.get("concessionaire_name") or ("Todas las Empresas (Administrador General)" if user.get("is_admin") else "Consorcio Arapotí")
    company_badge = f"{user_company} ({user_agency})" if user_agency else user_company
    html = """<!DOCTYPE html>

<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poliverso Transit | Radar Integral con Geocercas y Estado de Flota</title>
    <link rel="icon" href="data:,">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background-color: #0b1120; color: #f8fafc; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        header { background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px); padding: 8px 20px; border-bottom: 1px solid #1e293b; display: flex; align-items: center; justify-content: space-between; z-index: 1000; }
        .logo-group { display: flex; align-items: center; gap: 12px; }
        .badge { padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display: inline-flex; align-items: center; gap: 5px; }
        .badge-ws { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
        .badge-poll { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
        .badge-info { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); }
        .controls-bar { display: flex; align-items: center; gap: 12px; }
        .date-picker-box { display: flex; align-items: center; gap: 8px; font-size: 11px; background: #1e293b; padding: 4px 10px; border-radius: 8px; border: 1px solid #334155; }
        .date-picker-box input { background: #0f172a; border: 1px solid #475569; color: #f8fafc; padding: 3px 6px; border-radius: 4px; font-size: 11px; }
        .btn-hist { background: #0284c7; color: white; border: none; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; }
        .btn-hist:hover { background: #0369a1; }
        .metrics-bar { display: flex; gap: 8px; }
        .metric-card { background: #1e293b; padding: 4px 10px; border-radius: 8px; border: 1px solid #334155; font-size: 11px; }
        .metric-card strong { color: #38bdf8; font-size: 14px; margin-left: 4px; }
        
        /* Barra de Control de Geocercas Configurables */
        .geofence-toolbar { background: #0f172a; padding: 6px 20px; border-bottom: 1px solid #1e293b; display: flex; align-items: center; justify-content: space-between; gap: 14px; font-size: 11px; z-index: 999; flex-wrap: wrap; }
        .geofence-ctrl-group { display: flex; align-items: center; gap: 6px; background: #1e293b; padding: 3px 10px; border-radius: 6px; border: 1px solid #334155; }
        .val-badge { font-weight: 800; padding: 1px 6px; border-radius: 4px; font-size: 11px; min-width: 42px; text-align: center; }
        
        #app-layout { display: flex; flex: 1; position: relative; overflow: hidden; }
        #map { flex: 1; height: 100%; z-index: 1; background: #ffffff; }
        #sidebar { width: 380px; background: #111827; border-left: 1px solid #1f2937; display: flex; flex-direction: column; z-index: 10; }
        .sidebar-header { padding: 10px 16px; border-bottom: 1px solid #1f2937; font-weight: 700; font-size: 11px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; display: flex; justify-content: space-between; align-items: center; }
        
        /* Controles de Filtros en Sidebar */
        .sidebar-filters { padding: 10px 14px; background: #0f172a; border-bottom: 1px solid #1f2937; display: flex; flex-direction: column; gap: 8px; }
        .btn-quick-filter { background: #0284c7; color: white; border: none; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; cursor: pointer; transition: background 0.15s; }
        .btn-quick-filter:hover { background: #0369a1; }
        
        .bus-list { flex: 1; overflow-y: auto; padding: 10px; }
        .bus-card { background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 12px; margin-bottom: 8px; transition: all 0.2s ease; cursor: pointer; }
        .bus-card:hover { border-color: #38bdf8; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15); }
        .bus-card.card-fault { border-color: rgba(239, 68, 68, 0.6); background: rgba(31, 41, 55, 0.9); }
        .bus-card.card-fault:hover { border-color: #ef4444; box-shadow: 0 4px 12px rgba(239, 68, 68, 0.25); }
        .bus-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .bus-title { font-weight: 700; font-size: 13px; color: #f9fafb; }
        .status-pill { font-size: 10px; padding: 2px 8px; border-radius: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
        .status-transit { background: #10b981; color: #fff; }
        .status-origin { background: #f59e0b; color: #fff; }
        .status-dest { background: #f59e0b; color: #fff; }
        .status-offroute { background: #ef4444; color: #fff; }
        .status-depot { background: #4b5563; color: #fff; }
        .status-gpsfault { background: #475569; color: #fca5a5; border: 1px solid #ef4444; }
        .progress-container { margin: 6px 0; }
        .progress-labels { display: flex; justify-content: space-between; font-size: 11px; color: #9ca3af; margin-bottom: 2px; }
        .progress-bar-bg { width: 100%; height: 5px; background: #374151; border-radius: 3px; overflow: hidden; }
        .progress-bar-fill { height: 100%; background: linear-gradient(90deg, #10b981, #38bdf8); border-radius: 3px; transition: width 0.4s ease; }
        .bus-meta { font-size: 11px; color: #9ca3af; line-height: 1.5; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 5px; }
        .alert-box { background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; margin-top: 6px; }
        .event-feed { height: 140px; background: #0b1120; border-top: 1px solid #1f2937; overflow-y: auto; padding: 10px; font-size: 11px; }
        .event-item { margin-bottom: 5px; border-left: 3px solid #38bdf8; padding-left: 8px; }
        .event-time { color: #6b7280; font-size: 10px; }
        .legend-box { position: absolute; bottom: 20px; left: 20px; background: rgba(17, 24, 39, 0.94); border: 1px solid #374151; padding: 12px 14px; border-radius: 8px; z-index: 1000; font-size: 11px; backdrop-filter: blur(8px); }
        .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
        .legend-line { width: 20px; height: 4px; border-radius: 2px; }

        /* Estilos de Marcadores Direccionales SVG con Badge de Velocidad */
        .bus-marker-wrap {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            user-select: none;
            pointer-events: auto;
        }
        .bus-speed-badge {
            background: rgba(15, 23, 42, 0.95);
            color: #38bdf8;
            border: 1px solid #38bdf8;
            border-radius: 8px;
            font-size: 10px;
            font-weight: 800;
            padding: 1px 6px;
            white-space: nowrap;
            box-shadow: 0 2px 6px rgba(0,0,0,0.5);
            margin-bottom: 2px;
            transition: all 0.2s ease;
        }
        .bus-speed-badge.stopped {
            color: #94a3b8;
            border-color: #475569;
        }
        .bus-speed-badge.overspeed {
            color: #f87171;
            border-color: #ef4444;
        }
        .bus-arrow-circle {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            border: 2px solid #ffffff;
            box-shadow: 0 0 10px rgba(0,0,0,0.6);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .bus-number-badge {
            background: #0f172a;
            color: #ffffff;
            border: 1px solid #475569;
            border-radius: 5px;
            font-size: 9px;
            font-weight: 700;
            padding: 1px 4px;
            margin-top: 2px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.5);
        }
        .bus-speed-badge.wrong-dir {
            background: #d97706;
            color: #ffffff;
            border-color: #fbbf24;
            animation: bounce-alert 0.8s infinite alternate;
        }
        .bus-marker-wrap.wrong-dir .bus-arrow-circle {
            background: #d97706 !important;
            box-shadow: 0 0 15px #f59e0b !important;
            border-color: #fef08a !important;
        }
        .bus-card.card-wrong-dir {
            border-left: 4px solid #f59e0b !important;
            background: rgba(40, 25, 10, 0.7);
        }
        .bus-line-badge {
            background: #1e3a8a;
            color: #93c5fd;
            border: 1px solid #3b82f6;
            font-size: 9px;
            padding: 1px 5px;
            border-radius: 4px;
            font-weight: 700;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-group">
            <h2 style="font-size: 16px; font-weight: 800; letter-spacing: -0.02em;">🚍 Poliverso Transit Radar</h2>
            <span id="conn-badge" class="badge badge-poll">Iniciando...</span>
            <span class="badge badge-info" id="company-badge">__COMPANY_BADGE__</span>
        </div>
        <div class="controls-bar">
            <div class="date-picker-box">
                <span>📅 Vigencia:</span>
                <input type="date" id="hist-date" value="2026-09-25">
                <button class="btn-hist" onclick="loadHistoricalShape()">Consultar</button>
                <button class="btn-hist" style="background:#475569;" onclick="resetToActiveShapes()">Hoy</button>
            </div>
            <div class="metrics-bar">
                <div class="metric-card">Flota: <strong id="m-buses">0</strong></div>
                <div class="metric-card">En Ruta: <strong id="m-transit" style="color: #10b981;">0</strong></div>
                <div class="metric-card">Cabeceras: <strong id="m-terminals" style="color: #f59e0b;">0</strong></div>
                <div class="metric-card">Falla GPS: <strong id="m-faults" style="color: #ef4444;">0</strong></div>
                <div class="metric-card" id="m-card-wrong-dir" style="background: rgba(245, 158, 11, 0.2); border-color: #f59e0b; display: none;">
                    <span>⚠️ Contrasentido: </span><strong id="m-wrong-dir" style="color: #fbbf24;">0</strong>
                </div>
                <div class="metric-card" style="background: rgba(2, 132, 199, 0.15); border-color: rgba(56, 189, 248, 0.4);">
                    <span>🚦 Waze: </span><strong id="m-waze" style="color: #38bdf8;">--</strong>
                </div>
            </div>
            <a href="/headway" style="background: linear-gradient(135deg, #0284c7, #6366f1); color: #fff; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 800; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);">📊 Tablero Lineal</a>
            <a href="/web#action=transit_operations.action_transit_requirement" target="_blank" style="background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #34d399; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 800; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;" title="Enviar requerimiento o sugerencia de ajuste técnico">🛠️ Solicitar Ajuste</a>
        </div>
    </header>

    <!-- Barra de Configuración Dinámica de Geocercas y Filtro GPS -->
    <div class="geofence-toolbar">
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <div class="geofence-ctrl-group">
                <span style="color: #10b981; font-weight: 700;">🟢 Geocerca Itinerario:</span>
                <input type="range" id="range-itin-geofence" min="30" max="250" step="10" value="70" oninput="updateGeofenceRadii()" style="width: 80px; accent-color: #10b981; cursor: pointer;">
                <span id="lbl-itin-geofence" class="val-badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);">70m</span>
            </div>
            <div class="geofence-ctrl-group">
                <span style="color: #f59e0b; font-weight: 700;">🟡 Geocerca Cabeceras:</span>
                <input type="range" id="range-term-geofence" min="100" max="800" step="50" value="400" oninput="updateGeofenceRadii()" style="width: 80px; accent-color: #f59e0b; cursor: pointer;">
                <span id="lbl-term-geofence" class="val-badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);">400m</span>
            </div>
            <div class="geofence-ctrl-group">
                <span style="color: #94a3b8; font-weight: 600;">⏱️ Filtro Sin Señal GPS:</span>
                <select id="sel-gps-timeout" onchange="updateGpsTimeout()" style="background: #0f172a; border: 1px solid #475569; color: #f8fafc; padding: 2px 6px; border-radius: 4px; font-size: 11px;">
                    <option value="15">15 min</option>
                    <option value="30" selected>30 min (Regla Operativa)</option>
                    <option value="60">60 min</option>
                </select>
            </div>
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; color: #cbd5e1; font-size: 11px;">
                <input type="checkbox" id="chk-show-faults" checked onchange="applyRouteAndVisibilityFilters()">
                <span>⚠️ Mostrar coches con Falla GPS</span>
            </label>
        </div>
        <div style="display: flex; align-items: center; gap: 8px; font-size: 11px; color: #94a3b8;">
            <span>⚡ Velocidad: <b>Diferencial (2 últimos pings)</b></span>
        </div>
    </div>

    <div id="app-layout">
        <div id="map"></div>
        <div class="legend-box" id="legend">
            <strong style="color: #e5e7eb; display:block; margin-bottom: 6px;">Trazados & Geocercas (PostGIS)</strong>
            <div id="legend-routes-list" style="max-height: 140px; overflow-y: auto; margin-bottom: 4px;"></div>
            <div class="legend-item"><div class="legend-line" style="background: #ef4444; border-top: 2px dashed #fff;"></div><span id="hist-label">Histórico Anterior</span></div>
            <div style="border-top: 1px solid #374151; margin-top: 6px; padding-top: 6px;">
                <div class="legend-item"><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#10b981; box-shadow:0 0 6px #10b981;"></span><span>En Itinerario (Verde + Flecha SVG)</span></div>
                <div class="legend-item"><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#f59e0b; box-shadow:0 0 6px #f59e0b;"></span><span>En Cabecera (Amarillo + Flecha SVG)</span></div>
                <div class="legend-item"><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#ef4444; box-shadow:0 0 6px #ef4444;"></span><span>Fuera de Itinerario (Rojo)</span></div>
                <div class="legend-item"><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#475569; border:1px solid #ef4444;"></span><span>Falla GPS (&gt;30 min sin señal)</span></div>
            </div>
        </div>

        <!-- Capas Waze for Cities (CCP) -->
        <div class="legend-box" style="bottom: 230px; left: 20px; border-color: rgba(56, 189, 248, 0.4);">
            <strong style="color: #38bdf8; display:flex; align-items:center; gap:6px; margin-bottom: 6px;">
                <span>🚗 Waze for Cities (CCP)</span>
            </strong>
            <label style="display:flex; align-items:center; gap:6px; font-size:11px; margin-bottom:5px; cursor:pointer;">
                <input type="checkbox" id="chk-waze-jams" checked onchange="toggleWazeLayers()">
                <span>🚦 Tráfico / Jams (Colores)</span>
            </label>
            <label style="display:flex; align-items:center; gap:6px; font-size:11px; cursor:pointer;">
                <input type="checkbox" id="chk-waze-alerts" checked onchange="toggleWazeLayers()">
                <span>⚠️ Incidentes & Obras</span>
            </label>
        </div>

        <div id="sidebar">
            <div class="sidebar-header">
                <span>Flota <span id="sidebar-company-name">__COMPANY_NAME__</span></span>
                <span id="route-count" style="font-size: 11px; color: #38bdf8;">__AGENCY_ID__</span>
            </div>

            <!-- Controles de Filtro de Ramal y Visibilidad Rápida -->
            <div class="sidebar-filters">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Ramal:</span>
                    <select id="sel-route-filter" onchange="onRouteFilterChange()" style="background: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; outline: none; cursor: pointer; flex: 1; max-width: 240px;">
                        <option value="ALL">Todos los Ramales</option>
                    </select>
                </div>

                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 11px; color: #cbd5e1;">Buses: <strong id="lbl-visible-count" style="color: #38bdf8;">0</strong> / <span id="lbl-total-count">0</span></span>
                    <div style="display: flex; gap: 4px;">
                        <button type="button" class="btn-quick-filter" id="btn-quick-wrong-dir" style="background: #d97706; display: none;" onclick="filterOnlyWrongDir()" title="Filtrar buses con IDRuta en contrasentido">⚠️ Contrasentido (<span id="lbl-wrong-dir-count">0</span>)</button>
                        <button type="button" class="btn-quick-filter" onclick="setAllBusesVisibility(true)">Todos</button>
                        <button type="button" class="btn-quick-filter" style="background: #334155;" onclick="setAllBusesVisibility(false)">Ninguno</button>
                    </div>
                </div>
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
        
        // Capa predeterminada: Fondo Blanco / Claro (CartoDB Positron)
        const lightTileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=' + cartoKey, {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions" target="_blank">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);

        const osmTileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
            maxZoom: 19
        });

        const darkTileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=' + cartoKey, {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions" target="_blank">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        });

        const esriSatLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: '&copy; <a href="https://www.esri.com/" target="_blank">Esri</a>',
            maxZoom: 19
        });

        const baseMaps = {
            "🗺️ Mapa Claro (Blanco)": lightTileLayer,
            "🌐 OpenStreetMap": osmTileLayer,
            "🛰️ Satelital Esri": esriSatLayer,
            "🌙 Modo Oscuro": darkTileLayer
        };
        L.control.layers(baseMaps, null, { position: 'topright' }).addTo(map);

        const markers = {};
        const busCircles = {};
        const activeVehicles = {};
        const busVisibility = {};
        const markerAnimations = {};
        let shapeLayers = [];
        let stopLayers = [];
        let wazeJamLayers = [];
        let wazeAlertLayers = [];
        let eventHistory = [];
        let ws = null;
        let pollingInterval = null;

        const CURRENT_AGENCY = "__CURRENT_AGENCY__";
        let hasFittedMap = false;

        const routeColors = {
            '020f': '#38bdf8',
            '020c': '#a855f7',
            '020d': '#f59e0b',
            '020e': '#14b8a6',
            '0210': '#10b981',
            '0211': '#ec4899',
            '0138': '#10b981',
            '0139': '#06b6d4',
            '013a': '#f59e0b',
            '013b': '#ec4899',
            '004a': '#3b82f6',
            '004b': '#6366f1',
            '004c': '#8b5cf6',
            '004d': '#a855f7',
            '004e': '#d946ef',
            '004f': '#ec4899',
            '0050': '#f43f5e',
            '0051': '#f97316',
            '0052': '#eab308',
            '0053': '#84cc16',
            'default': '#64748b'
        };

        function getRouteColor(code) {
            if (!code) return '#64748b';
            const c = code.toLowerCase();
            if (routeColors[c]) return routeColors[c];
            let hash = 0;
            for (let i = 0; i < c.length; i++) hash = c.charCodeAt(i) + ((hash << 5) - hash);
            const h = Math.abs(hash % 360);
            return `hsl(${h}, 85%, 55%)`;
        }

        function filterOnlyWrongDir() {
            const sel = document.getElementById('sel-route-filter');
            if (sel) {
                if (sel.value === 'WRONG_DIR') {
                    sel.value = 'ALL';
                } else {
                    let opt = sel.querySelector('option[value="WRONG_DIR"]');
                    if (!opt) {
                        opt = document.createElement('option');
                        opt.value = 'WRONG_DIR';
                        opt.textContent = '⚠️ Solo Buses en Contrasentido';
                        sel.insertBefore(opt, sel.children[1]);
                    }
                    sel.value = 'WRONG_DIR';
                }
                applyRouteAndVisibilityFilters();
            }
        }

        function populateRouteDropdown(features) {
            const sel = document.getElementById('sel-route-filter');
            if (!sel || !features) return;
            const currentVal = sel.value;
            sel.innerHTML = '<option value="ALL">Todos los Ramales</option>';
            
            // Agrupar features por línea comercial (line_name)
            const byLine = {};
            const seen = new Set();
            features.forEach(f => {
                const code = f.properties.route_code;
                const name = f.properties.route_name || code;
                const lineName = f.properties.line_name || 'Línea Regular';
                if (code && !seen.has(code.toLowerCase())) {
                    seen.add(code.toLowerCase());
                    if (!byLine[lineName]) byLine[lineName] = [];
                    byLine[lineName].push({ code: code.toUpperCase(), name: name });
                }
            });

            // Si hay más de una línea comercial, agregar opción para filtrar toda la línea
            const lineNames = Object.keys(byLine);
            if (lineNames.length > 1) {
                const groupFilter = document.createElement('optgroup');
                groupFilter.label = '⚡ Filtrar Línea Completa';
                lineNames.forEach(ln => {
                    const opt = document.createElement('option');
                    opt.value = 'LINE:' + ln;
                    opt.textContent = `🚍 Toda la ${ln} (${byLine[ln].length} ramales)`;
                    groupFilter.appendChild(opt);
                });
                sel.appendChild(groupFilter);
            }

            // Ramales organizados por grupos de línea
            lineNames.forEach(ln => {
                const optGroup = document.createElement('optgroup');
                optGroup.label = `🚍 ${ln}`;
                byLine[ln].forEach(item => {
                    const opt = document.createElement('option');
                    opt.value = item.code;
                    opt.textContent = `${item.code} - ${item.name}`;
                    optGroup.appendChild(opt);
                });
                sel.appendChild(optGroup);
            });

            if (currentVal) {
                sel.value = currentVal;
            }
        }

        function updateLegendRoutes(features) {
            const leg = document.getElementById('legend-routes-list');
            if (!leg || !features) return;
            leg.innerHTML = '';
            const seen = new Set();
            features.forEach(f => {
                const p = f.properties;
                const code = (p.route_code || '').toLowerCase();
                if (code && !seen.has(code)) {
                    seen.add(code);
                    const color = getRouteColor(code);
                    const item = document.createElement('div');
                    item.className = 'legend-item';
                    item.innerHTML = `<div class="legend-line" style="background: ${color};"></div><span>${p.route_name || p.route_code}</span>`;
                    leg.appendChild(item);
                }
            });
        }

        function updateGeofenceRadii() {
            const itinR = parseInt(document.getElementById('range-itin-geofence').value, 10);
            const termR = parseInt(document.getElementById('range-term-geofence').value, 10);
            document.getElementById('lbl-itin-geofence').textContent = itinR + 'm';
            document.getElementById('lbl-term-geofence').textContent = termR + 'm';
            applyRouteAndVisibilityFilters();
        }

        function updateGpsTimeout() {
            applyRouteAndVisibilityFilters();
        }

        function renderShapesGeoJSON(geojson, isHistorical = false) {
            shapeLayers.forEach(l => map.removeLayer(l));
            shapeLayers = [];

            if (!geojson || !geojson.features) return;

            const layer = L.geoJSON(geojson, {
                style: (feature) => {
                    const code = (feature.properties.route_code || '').toLowerCase();
                    const color = isHistorical ? '#ef4444' : getRouteColor(code);
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

            if (!isHistorical && geojson.features.length > 0) {
                populateRouteDropdown(geojson.features);
                updateLegendRoutes(geojson.features);
                if (!hasFittedMap) {
                    try {
                        map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 14 });
                        hasFittedMap = true;
                    } catch (e) {}
                }
            }
        }

        function renderStopsGeoJSON(geojson) {
            stopLayers.forEach(l => map.removeLayer(l));
            stopLayers = [];

            if (!geojson || !geojson.features) return;

            const termR = parseInt(document.getElementById('range-term-geofence')?.value || 400, 10);

            const layer = L.geoJSON(geojson, {
                pointToLayer: (feature, latlng) => {
                    const p = feature.properties;
                    const isTerminal = p.stop_type === 'origin' || p.stop_type === 'destination';
                    const marker = L.circleMarker(latlng, {
                        radius: isTerminal ? 7 : 5,
                        fillColor: isTerminal ? '#f59e0b' : '#38bdf8',
                        color: '#ffffff',
                        weight: 1.5,
                        opacity: 1,
                        fillOpacity: 0.8
                    });

                    const fence = L.circle(latlng, {
                        radius: isTerminal ? termR : (p.radius_meters || 70),
                        color: isTerminal ? '#f59e0b' : '#38bdf8',
                        weight: 1,
                        fillOpacity: isTerminal ? 0.08 : 0.05
                    });
                    stopLayers.push(fence.addTo(map));

                    return marker;
                },
                onEachFeature: (feature, layer) => {
                    const p = feature.properties;
                    const isTerminal = p.stop_type === 'origin' || p.stop_type === 'destination';
                    layer.bindPopup(`
                        <b>🚏 ${p.name}</b><br>
                        Código: ${p.stop_code} (${p.stop_type})<br>
                        Radio Geocerca: ${isTerminal ? termR : (p.radius_meters || 70)}m<br>
                        ${p.address || ''}
                    `);
                }
            }).addTo(map);
            stopLayers.push(layer);
        }

        async function loadHistoricalShape() {
            const dateVal = document.getElementById('hist-date').value;
            if (!dateVal) return;
            const selRoute = document.getElementById('sel-route-filter').value;
            const rCode = (selRoute && selRoute !== 'ALL') ? selRoute.toLowerCase() : (window.firstRouteCode || '0138');
            const agId = CURRENT_AGENCY || '002A';
            try {
                const res = await fetch(`/api/v1/shapes/history?route_code=${rCode}&agency_id=${agId}&date=${dateVal}`);
                const data = await res.json();
                renderShapesGeoJSON(data, true);
                document.getElementById('hist-label').textContent = `Vigente al ${dateVal} (${rCode.toUpperCase()})`;
            } catch (err) {
                console.error("Error cargando histórico:", err);
            }
        }

        async function resetToActiveShapes() {
            try {
                const url = CURRENT_AGENCY ? `/api/v1/shapes/active?agency_id=${CURRENT_AGENCY}` : '/api/v1/shapes/active';
                const res = await fetch(url);
                const data = await res.json();
                renderShapesGeoJSON(data, false);
                document.getElementById('hist-label').textContent = `Histórico Anterior`;
            } catch (err) {
                console.error("Error reseteando shapes:", err);
            }
        }


        /* -------------------------------------------------------------
           Cálculo de Rumbo Cinemático Geodésico según Vector de Movimiento
        ------------------------------------------------------------- */
        function getMovementBearing(startLat, startLng, endLat, endLng) {
            const dLng = (endLng - startLng) * Math.PI / 180;
            const lat1 = startLat * Math.PI / 180;
            const lat2 = endLat * Math.PI / 180;
            const y = Math.sin(dLng) * Math.cos(lat2);
            const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
            const brng = Math.atan2(y, x) * 180 / Math.PI;
            return Math.round((brng + 360) % 360);
        }

        /* -------------------------------------------------------------
           Punto 3: Icono SVG Direccional Rotativo + Badge de Velocidad
        ------------------------------------------------------------- */
        function createBusDivIcon(v, markerColor, heading, speed) {
            const isFault = v._isFault;
            const isStopped = speed < 1.0;
            const isOverSpeed = speed > 70.0;
            const isWrongDir = !!v.wrong_direction_alert;
            const headingDeg = Math.round(heading || 0);

            const iconHtml = `
                <div class="bus-marker-wrap ${isWrongDir ? 'wrong-dir' : ''}">
                    <div class="bus-speed-badge ${isWrongDir ? 'wrong-dir' : (isStopped ? 'stopped' : (isOverSpeed ? 'overspeed' : ''))}">
                        ${isWrongDir ? '⚠️ CONTRASENTIDO' : (isFault ? 'SIN SEÑAL' : Math.round(speed) + ' km/h')}
                    </div>
                    <div class="bus-arrow-circle" style="background: ${isWrongDir ? '#d97706' : markerColor}; box-shadow: 0 0 10px ${isWrongDir ? '#f59e0b' : markerColor};">
                        ${isFault ? '<span style="font-size:14px;">📡</span>' : `
                        <svg viewBox="0 0 24 24" width="18" height="18" style="transform: rotate(${headingDeg}deg); transform-origin: 50% 50%; display:block;">
                            <path fill="#ffffff" d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
                        </svg>
                        `}
                    </div>
                    <div class="bus-number-badge">${isWrongDir ? '⚠️ #' : '#'}${v.bus_id}</div>
                </div>
            `;
            return L.divIcon({
                className: 'custom-bus-icon' + (isWrongDir ? ' wrong-dir-marker' : ''),
                html: iconHtml,
                iconSize: [46, 58],
                iconAnchor: [23, 29]
            });
        }

        function getBusKey(v) {
            if (!v) return '';
            return v.vehicle_key || `${v.agency_id || '004B'}_${v.bus_id}`;
        }

        /* -------------------------------------------------------------
           Punto 3: Interpolación Cinemática Suave a 60 FPS (animateMarker)
        ------------------------------------------------------------- */
        function animateMarker(busKey, marker, startLatLng, endLatLng, durationMs = 15000) {
            if (markerAnimations[busKey]) {
                cancelAnimationFrame(markerAnimations[busKey]);
                delete markerAnimations[busKey];
            }

            const startLat = startLatLng.lat !== undefined ? startLatLng.lat : startLatLng[0];
            const startLng = startLatLng.lng !== undefined ? startLatLng.lng : startLatLng[1];
            const endLat = endLatLng.lat !== undefined ? endLatLng.lat : endLatLng[0];
            const endLng = endLatLng.lng !== undefined ? endLatLng.lng : endLatLng[1];

            const dLat = endLat - startLat;
            const dLng = endLng - startLng;

            // Si el salto es mayor a 2 km (~0.02 grados) o infinitesimal, ajustar de inmediato sin animar trazos erráticos
            if (Math.abs(dLat) > 0.02 || Math.abs(dLng) > 0.02 || (Math.abs(dLat) < 0.000005 && Math.abs(dLng) < 0.000005)) {
                marker.setLatLng([endLat, endLng]);
                if (busCircles[busKey]) busCircles[busKey].setLatLng([endLat, endLng]);
                return;
            }

            const startTime = performance.now();

            function step(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / durationMs, 1.0);
                const ease = progress; // Desplazamiento lineal uniforme a lo largo de los 15 segundos

                const curLat = startLat + dLat * ease;
                const curLng = startLng + dLng * ease;
                const curPos = [curLat, curLng];

                marker.setLatLng(curPos);
                if (busCircles[busKey]) busCircles[busKey].setLatLng(curPos);

                if (progress < 1.0) {
                    markerAnimations[busKey] = requestAnimationFrame(step);
                } else {
                    marker.setLatLng([endLat, endLng]);
                    if (busCircles[busKey]) busCircles[busKey].setLatLng([endLat, endLng]);
                    delete markerAnimations[busKey];
                }
            }

            markerAnimations[busKey] = requestAnimationFrame(step);
        }

        /* -------------------------------------------------------------
           Punto 4: Verificación de Visibilidad por Filtro de Ramal y Checkbox
        ------------------------------------------------------------- */
        function isBusVisibleByFilter(v) {
            const selectedRoute = document.getElementById('sel-route-filter')?.value || 'ALL';
            const showFaults = document.getElementById('chk-show-faults')?.checked ?? true;
            if (v._isFault && !showFaults) return false;

            if (selectedRoute !== 'ALL') {
                if (selectedRoute.startsWith('LINE:')) {
                    const targetLine = selectedRoute.substring(5).toUpperCase();
                    const busLine = (v.line_name || '').toUpperCase();
                    if (!busLine.includes(targetLine)) return false;
                } else if (selectedRoute === 'WRONG_DIR') {
                    if (!v.wrong_direction_alert) return false;
                } else {
                    const busRoute = (v.route_id || '').toUpperCase();
                    if (!busRoute.includes(selectedRoute.toUpperCase())) return false;
                }
            }

            const busKey = getBusKey(v);
            if (busVisibility[busKey] === false) return false;

            return true;
        }

        /* -------------------------------------------------------------
           Punto 3: Actualización Reactiva de Marcador en Mapa
        ------------------------------------------------------------- */
        function renderOrUpdateVehicleMarker(v, animate = true) {
            const busKey = getBusKey(v);
            const lat = (v.last_latitude !== undefined && v.last_latitude !== null) ? v.last_latitude : v.latitude;
            const lon = (v.last_longitude !== undefined && v.last_longitude !== null) ? v.last_longitude : v.longitude;
            if (lat === undefined || lon === undefined || lat === null || lon === null || isNaN(lat) || isNaN(lon)) {
                return;
            }
            const newLatLng = [lat, lon];
            const isVisible = isBusVisibleByFilter(v);

            if (!isVisible) {
                if (markers[busKey]) map.removeLayer(markers[busKey]);
                if (busCircles[busKey]) map.removeLayer(busCircles[busKey]);
                return;
            }

            const itinR = parseInt(document.getElementById('range-itin-geofence')?.value || 70, 10);
            const termR = parseInt(document.getElementById('range-term-geofence')?.value || 400, 10);
            const isFault = v._isFault;
            const state = isFault ? 'GPS_FAULT' : (v.state || v.current_state || 'IN_TRANSIT');
            let markerColor = '#10b981';
            let circleColor = '#10b981';
            let circleRadius = itinR;
            let circleDash = null;

            if (isFault) {
                markerColor = '#475569';
                circleColor = '#ef4444';
                circleRadius = 50;
                circleDash = '4, 4';
            } else if (state === 'OFF_ROUTE' || v.deviation_alert) {
                markerColor = '#ef4444';
                circleColor = '#ef4444';
                circleRadius = itinR;
            } else if (state === 'AT_ORIGIN' || state === 'AT_DESTINATION') {
                markerColor = '#f59e0b';
                circleColor = '#f59e0b';
                circleRadius = termR;
            } else if (state === 'DEPOT') {
                markerColor = '#64748b';
                circleColor = '#64748b';
                circleRadius = 60;
            } else {
                markerColor = '#10b981';
                circleColor = '#10b981';
                circleRadius = itinR;
            }

            const stateLabels = {
                'IN_TRANSIT': 'En Circulación',
                'AT_ORIGIN': 'En Cabecera',
                'AT_DESTINATION': 'En Destino',
                'OFF_ROUTE': 'Desviado',
                'DEPOT': 'En Depósito',
                'GPS_FAULT': 'Falla de GPS'
            };

            const estadoEsp = isFault ? `Falla GPS (${Math.round(v._minsAgo)}m sin señal)` : (v.status_display || (stateLabels[state] || state));
            // Rumbo cinemático geodésico exacto (0.0° - 359.9°) calculado por el backend y velocidad
            let heading = isFault ? 0.0 : (v.heading_deg !== undefined && v.heading_deg !== null ? Number(v.heading_deg) : (v.heading_degrees || v.rumbo || 0.0));
            let speed = isFault ? 0.0 : ((v.speed_kmh !== undefined && v.speed_kmh !== null) ? Number(v.speed_kmh) : ((v.last_speed_kmh !== undefined && v.last_speed_kmh !== null) ? Number(v.last_speed_kmh) : ((v.velocidad !== undefined && v.velocidad !== null) ? Number(v.velocidad) : 0.0)));
            if (isNaN(speed)) speed = 0.0;

            // Si el móvil está detenido (< 1.5 km/h) y ya tenía un rumbo previo, preservarlo para no rotar la flecha
            if (speed < 1.5 && markers[busKey] && markers[busKey]._lastHeading !== undefined) {
                heading = markers[busKey]._lastHeading;
            }

            let popupContent = '';
            if (isFault) {
                popupContent = `
                    <div style="min-width: 220px;">
                        <div style="background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #fca5a5; padding: 6px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-bottom: 6px; display:flex; align-items:center; gap:6px;">
                            <span>📡⚠️</span>
                            <span>COMUNICAR FALLA DE GPS</span>
                        </div>
                        <b>🚍 Coche #${v.bus_id} (${v.license_plate})</b><br>
                        Ramal: <b>${v.route_id || '--'}</b> (${v.agency_id || '004B'})<br>
                        Estado: <b style="color: #ef4444;">Sin señal GPS hace ${Math.round(v._minsAgo)} min</b><br>
                        Velocidad: <b>0.0 km/h (Detenido / Sin transmisión)</b><br>
                        Última posición: <b>${lat.toFixed(5)}, ${lon.toFixed(5)}</b><br>
                        Último ping registrado: <b style="color:#cbd5e1;">${v.last_ping_time ? v.last_ping_time.replace('T', ' ').slice(0, 19) : '--'}</b>
                    </div>
                `;
            } else {
                const geofenceLabel = state === 'IN_TRANSIT' ? `Itinerario (${itinR}m)` : (state.includes('AT_') ? `Cabecera (${termR}m)` : `Fuera de Ruta`);
                const wrongDirBanner = v.wrong_direction_alert ? `
                    <div style="background: rgba(245, 158, 11, 0.2); border: 1px solid #f59e0b; color: #fde047; padding: 6px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-bottom: 6px;">
                        ⚠️ ALERTA: IDRUTA EN CONTRASENTIDO<br>
                        <span style="font-weight: 500; font-size: 10px; color: #e2e8f0;">
                            ${v.wrong_direction_reason || 'Circulando en sentido opuesto a la ruta.'}
                            ${v.suggested_opposite_route ? '<br><b>Sugerido:</b> Ramal ' + v.suggested_opposite_route.toUpperCase() : ''}
                        </span>
                    </div>
                ` : '';
                popupContent = `
                    <div style="min-width: 210px;">
                        ${wrongDirBanner}
                        <b>🚍 Coche #${v.bus_id} (${v.license_plate})</b><br>
                        ${v.line_name ? `Línea: <b style="color: #38bdf8;">${v.line_name}</b><br>` : ''}
                        Ramal: <b>${v.route_id}</b> (${v.agency_id})<br>
                        Estado: <b style="color: ${v.wrong_direction_alert ? '#f59e0b' : markerColor};">${v.wrong_direction_alert ? '⚠️ En Contrasentido' : estadoEsp}</b><br>
                        Rumbo: <b>${Math.round(heading)}°</b> | Velocidad: <b>${speed.toFixed(1)} km/h</b><br>
                        Progreso: <b>${v.progress_percent || 0}%</b> (${v.distance_traveled_km || 0} / ${v.route_total_km || 0} km)<br>
                        Desvío Traza: <b>${Math.round(v.deviation_meters || 0)}m</b><br>
                        Geocerca Activa: <b style="color: ${circleColor};">${geofenceLabel}</b>
                    </div>
                `;
            }

            const icon = createBusDivIcon(v, markerColor, heading, speed);

            if (!markers[busKey]) {
                markers[busKey] = L.marker(newLatLng, { icon: icon }).addTo(map).bindPopup(popupContent);
                markers[busKey]._lastHeading = heading;
                busCircles[busKey] = L.circle(newLatLng, {
                    radius: circleRadius,
                    color: circleColor,
                    fillColor: circleColor,
                    fillOpacity: isFault ? 0.05 : 0.12,
                    weight: 1.5,
                    dashArray: circleDash
                }).addTo(map);
            } else {
                const marker = markers[busKey];
                if (!map.hasLayer(marker)) marker.addTo(map);
                if (busCircles[busKey] && !map.hasLayer(busCircles[busKey])) busCircles[busKey].addTo(map);

                marker.setIcon(icon).setPopupContent(popupContent);
                marker._lastHeading = heading;

                if (animate) {
                    const oldLatLng = marker.getLatLng();
                    animateMarker(busKey, marker, oldLatLng, newLatLng, 15000);
                } else {
                    marker.setLatLng(newLatLng);
                    if (busCircles[busKey]) busCircles[busKey].setLatLng(newLatLng);
                }

                if (busCircles[busKey]) {
                    busCircles[busKey].setRadius(circleRadius);
                    busCircles[busKey].setStyle({
                        color: circleColor,
                        fillColor: circleColor,
                        fillOpacity: isFault ? 0.05 : 0.12,
                        dashArray: circleDash
                    });
                }
            }
        }

        /* -------------------------------------------------------------
           Punto 4: Actualización Reactiva de Tarjetas en Sidebar
        ------------------------------------------------------------- */
        function updateVehicleCardInSidebar(v) {
            const busKey = getBusKey(v);
            const card = document.getElementById(`card-bus-${busKey}`);
            if (!card) {
                renderFullSidebarList();
                return;
            }

            const isVisible = isBusVisibleByFilter(v);
            card.style.display = isVisible ? 'block' : 'none';

            const isChecked = busVisibility[busKey] !== false;
            const chk = document.getElementById(`chk-bus-${busKey}`);
            if (chk) chk.checked = isChecked;
            card.style.opacity = isChecked ? '1' : '0.5';

            const isFault = v._isFault;
            const state = isFault ? 'GPS_FAULT' : (v.state || v.current_state || 'IN_TRANSIT');
            const stateLabels = {
                'IN_TRANSIT': 'En Circulación',
                'AT_ORIGIN': 'En Cabecera',
                'AT_DESTINATION': 'En Destino',
                'OFF_ROUTE': 'Desviado',
                'DEPOT': 'En Depósito',
                'GPS_FAULT': 'Falla de GPS'
            };
            const estadoEsp = isFault ? `Falla GPS (${Math.round(v._minsAgo)}m sin señal)` : (v.status_display || (stateLabels[state] || state));
            const speed = isFault ? 0.0 : ((v.speed_kmh !== undefined && v.speed_kmh !== null) ? v.speed_kmh : (v.last_speed_kmh || 0));

            const statusEl = document.getElementById(`card-status-text-${busKey}`);
            if (statusEl) statusEl.textContent = estadoEsp;

            const speedEl = document.getElementById(`card-speed-${busKey}`);
            if (speedEl) speedEl.textContent = `${speed} km/h`;

            const devEl = document.getElementById(`card-dev-${busKey}`);
            if (devEl) {
                devEl.textContent = `${Math.round(v.deviation_meters || 0)}m`;
                devEl.style.color = v.deviation_alert ? '#ef4444' : '#34d399';
            }

            const pingEl = document.getElementById(`card-ping-${busKey}`);
            if (pingEl) pingEl.textContent = v.last_ping_time ? v.last_ping_time.slice(11, 19) : '--';

            const progPctEl = document.getElementById(`card-prog-pct-${busKey}`);
            if (progPctEl) progPctEl.textContent = `${v.progress_percent || 0}%`;

            const progKmEl = document.getElementById(`card-prog-km-${busKey}`);
            if (progKmEl) progKmEl.textContent = `${v.distance_traveled_km || 0}`;

            const progBarEl = document.getElementById(`card-prog-bar-${busKey}`);
            if (progBarEl) progBarEl.style.width = `${Math.min(v.progress_percent || 0, 100)}%`;

            if (v.wrong_direction_alert) {
                card.classList.add('card-wrong-dir');
            } else {
                card.classList.remove('card-wrong-dir');
            }
        }

        function renderFullSidebarList() {
            const listEl = document.getElementById('bus-list');
            const vehicles = Object.values(activeVehicles).sort((a, b) => {
                const numA = parseInt(a.bus_id, 10) || 0;
                const numB = parseInt(b.bus_id, 10) || 0;
                return numA - numB;
            });

            const stateLabels = {
                'IN_TRANSIT': 'En Circulación',
                'AT_ORIGIN': 'En Cabecera',
                'AT_DESTINATION': 'En Destino',
                'OFF_ROUTE': 'Desviado',
                'DEPOT': 'En Depósito',
                'GPS_FAULT': 'Falla de GPS'
            };
            const gpsTimeoutMin = parseInt(document.getElementById('sel-gps-timeout')?.value || 30, 10);

            listEl.innerHTML = vehicles.map(v => {
                const busKey = getBusKey(v);
                const isFault = v._isFault;
                const isWrongDir = !!v.wrong_direction_alert;
                const state = isFault ? 'GPS_FAULT' : (v.state || v.current_state || 'IN_TRANSIT');
                const estadoEsp = isFault ? `Falla GPS (${Math.round(v._minsAgo)}m sin señal)` : (isWrongDir ? '⚠️ En Contrasentido' : (v.status_display || (stateLabels[state] || state)));
                const pillClass = isFault ? 'status-gpsfault' : (state === 'IN_TRANSIT' ? 'status-transit' : (state === 'OFF_ROUTE' ? 'status-offroute' : (state === 'DEPOT' ? 'status-depot' : 'status-origin')));
                const pillLabel = isFault ? 'Falla GPS' : (isWrongDir ? 'Contrasentido' : (stateLabels[state] || state));
                const speed = isFault ? 0.0 : ((v.speed_kmh !== undefined && v.speed_kmh !== null) ? v.speed_kmh : (v.last_speed_kmh || 0));
                const isVisible = isBusVisibleByFilter(v);
                const isChecked = busVisibility[busKey] !== false;
                const cardClass = isFault ? 'card-fault' : (isWrongDir ? 'card-wrong-dir' : '');
                const lineBadge = v.line_name ? `<span class="bus-line-badge">${v.line_name}</span>` : '';

                return `
                    <div class="bus-card ${cardClass}" id="card-bus-${busKey}" style="display: ${isVisible ? 'block' : 'none'}; opacity: ${isChecked ? '1' : '0.5'};" onclick="focusBus('${busKey}')" title="Clic para centrar en radar">
                        <div class="bus-header">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <input type="checkbox" id="chk-bus-${busKey}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation(); toggleBusVisibility('${busKey}')" style="cursor: pointer; accent-color: #38bdf8; width: 14px; height: 14px;">
                                <span class="bus-title">${isWrongDir ? '⚠️ ' : ''}🚍 Coche #${v.bus_id} (${v.license_plate})</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 6px;">
                                ${lineBadge}
                                <span class="status-pill ${pillClass}">${pillLabel}</span>
                            </div>
                        </div>
                        <div style="font-size: 11px; color: ${isFault ? '#ef4444' : (isWrongDir ? '#fbbf24' : '#38bdf8')}; margin: 4px 0 6px 0; font-weight: 500; display: flex; align-items: center; gap: 4px;">
                            <span>${isFault ? '📡' : (isWrongDir ? '⚠️' : '📍')}</span>
                            <span id="card-status-text-${busKey}">${estadoEsp}</span>
                        </div>
                        ${!isFault ? `
                        <div class="progress-container">
                            <div class="progress-labels">
                                <span>Progreso Itinerario</span>
                                <span><strong id="card-prog-pct-${busKey}">${v.progress_percent || 0}%</strong> (<span id="card-prog-km-${busKey}">${v.distance_traveled_km || 0}</span> km)</span>
                            </div>
                            <div class="progress-bar-bg">
                                <div class="progress-bar-fill" id="card-prog-bar-${busKey}" style="width: ${Math.min(v.progress_percent || 0, 100)}%; background: ${isWrongDir ? '#f59e0b' : 'linear-gradient(90deg, #10b981, #38bdf8)'};"></div>
                            </div>
                        </div>
                        ` : ''}
                        <div class="bus-meta">
                            <div>Ramal: <strong style="color:#f8fafc;" id="card-route-${busKey}">${v.route_id || '--'}</strong></div>
                            <div>Velocidad: <strong style="color:${isFault ? '#ef4444' : '#f8fafc'};" id="card-speed-${busKey}">${speed} km/h</strong></div>
                            <div>Desvío Traza: <strong style="color:${v.deviation_alert ? '#ef4444':'#34d399'};" id="card-dev-${busKey}">${Math.round(v.deviation_meters || 0)}m</strong></div>
                            <div>Último Ping: <strong style="color:${isFault ? '#ef4444' : '#f8fafc'};" id="card-ping-${busKey}">${v.last_ping_time ? v.last_ping_time.slice(11, 19) : '--'}</strong></div>
                        </div>
                        ${isFault ? `<div class="alert-box">📡 Alerta: Sin reporte GPS hace ${Math.round(v._minsAgo)} min (> ${gpsTimeoutMin}m)</div>` : ''}
                        ${isWrongDir ? `
                            <div class="alert-box" style="background: rgba(245, 158, 11, 0.2); border-color: #f59e0b; color: #fbbf24;">
                                ⚠️ <b>IDRUTA EN CONTRASENTIDO:</b> Rumbo opuesto (${Math.round(v.heading_diff_deg || 180)}°).
                                ${v.suggested_opposite_route ? `<br><b>Sugerido:</b> Asignar a Ramal ${v.suggested_opposite_route.toUpperCase()}` : ''}
                            </div>
                        ` : ''}
                        ${v.speed_alert && !isFault ? '<div class="alert-box">⚠️ ¡EXCESO DE VELOCIDAD (>70 km/h)!</div>' : ''}
                        ${v.deviation_alert && !isFault ? '<div class="alert-box">⚠️ ¡DESVÍO DE TRAZADO OFICIAL (>400m)!</div>' : ''}
                    </div>
                `;
            }).join('');
        }

        /* -------------------------------------------------------------
            Punto 4: Manejo de Visibilidad, Checkboxes y Botones Rápidos
        ------------------------------------------------------------- */
        function toggleBusVisibility(busKey) {
            busVisibility[busKey] = busVisibility[busKey] === false ? true : false;
            const v = activeVehicles[busKey];
            if (v) renderOrUpdateVehicleMarker(v, false);
            const card = document.getElementById(`card-bus-${busKey}`);
            if (card) {
                card.style.opacity = busVisibility[busKey] !== false ? '1' : '0.5';
            }
            updateHeaderMetrics();
        }

        function setAllBusesVisibility(val) {
            const selectedRoute = document.getElementById('sel-route-filter')?.value || 'ALL';
            Object.values(activeVehicles).forEach(v => {
                let matches = false;
                if (selectedRoute === 'ALL') {
                    matches = true;
                } else if (selectedRoute.startsWith('LINE:')) {
                    const targetLine = selectedRoute.substring(5).toUpperCase();
                    matches = (v.line_name || '').toUpperCase().includes(targetLine);
                } else if (selectedRoute === 'WRONG_DIR') {
                    matches = !!v.wrong_direction_alert;
                } else {
                    matches = (v.route_id || '').toUpperCase().includes(selectedRoute.toUpperCase());
                }
                if (matches) {
                    busVisibility[getBusKey(v)] = val;
                }
            });
            applyRouteAndVisibilityFilters();
        }

        function onRouteFilterChange() {
            applyRouteAndVisibilityFilters();
        }

        function applyRouteAndVisibilityFilters() {
            Object.values(activeVehicles).forEach(v => {
                renderOrUpdateVehicleMarker(v, false);
                updateVehicleCardInSidebar(v);
            });
            updateHeaderMetrics();
        }

        function updateHeaderMetrics() {
            const vehicles = Object.values(activeVehicles);
            const gpsTimeoutMin = parseInt(document.getElementById('sel-gps-timeout')?.value || 30, 10);

            let inTransitCount = 0;
            let inTerminalsCount = 0;
            let faultsCount = 0;
            let visibleCount = 0;
            let wrongDirCount = 0;

            vehicles.forEach(v => {
                let minsAgo = v.minutes_since_ping;
                if (minsAgo === undefined || minsAgo === null) {
                    if (v.last_ping_time) {
                        const pDate = new Date(v.last_ping_time);
                        minsAgo = Math.max(0, (Date.now() - pDate.getTime()) / 60000);
                    } else {
                        minsAgo = 999;
                    }
                }
                v._isFault = v.is_gps_fault || (minsAgo > gpsTimeoutMin);
                v._minsAgo = minsAgo;

                if (v._isFault) {
                    faultsCount++;
                } else if (v.state === 'AT_ORIGIN' || v.state === 'AT_DESTINATION' || v.state === 'DEPOT') {
                    inTerminalsCount++;
                } else {
                    inTransitCount++;
                }

                if (v.wrong_direction_alert) {
                    wrongDirCount++;
                }

                if (isBusVisibleByFilter(v)) {
                    visibleCount++;
                }
            });

            document.getElementById('m-buses').textContent = vehicles.length;
            document.getElementById('m-transit').textContent = inTransitCount;
            document.getElementById('m-terminals').textContent = inTerminalsCount;
            document.getElementById('m-faults').textContent = faultsCount;
            
            const cardWrongDir = document.getElementById('m-card-wrong-dir');
            const lblWrongDir = document.getElementById('m-wrong-dir');
            const btnQuickWrongDir = document.getElementById('btn-quick-wrong-dir');
            const lblQuickWrongDirCount = document.getElementById('lbl-wrong-dir-count');
            if (cardWrongDir && lblWrongDir) {
                lblWrongDir.textContent = wrongDirCount;
                cardWrongDir.style.display = (wrongDirCount > 0) ? 'block' : 'none';
            }
            if (btnQuickWrongDir && lblQuickWrongDirCount) {
                lblQuickWrongDirCount.textContent = wrongDirCount;
                btnQuickWrongDir.style.display = (wrongDirCount > 0) ? 'inline-block' : 'none';
            }

            const visCountEl = document.getElementById('lbl-visible-count');
            if (visCountEl) visCountEl.textContent = visibleCount;
            const totCountEl = document.getElementById('lbl-total-count');
            if (totCountEl) totCountEl.textContent = vehicles.length;
        }

        function updateUI(animate = false) {
            updateHeaderMetrics();
            Object.values(activeVehicles).forEach(v => {
                renderOrUpdateVehicleMarker(v, animate);
            });
            renderFullSidebarList();

            // Auto-enfocar si viene en query ?bus=...
            const urlParams = new URLSearchParams(window.location.search);
            const targetBus = urlParams.get('bus');
            if (targetBus && !window._hasAutoFocusedBus) {
                const targetKey = (CURRENT_AGENCY ? `${CURRENT_AGENCY}_${targetBus}` : null);
                const matchKey = (targetKey && markers[targetKey]) ? targetKey : Object.keys(markers).find(k => k === targetBus || k.endsWith(`_${targetBus}`));
                if (matchKey && markers[matchKey]) {
                    window._hasAutoFocusedBus = true;
                    const m = markers[matchKey];
                    map.setView(m.getLatLng(), 16, { animate: true });
                    setTimeout(() => m.openPopup(), 400);
                }
            }

            const feedEl = document.getElementById('event-feed');
            if (feedEl) {
                feedEl.innerHTML = eventHistory.slice(-15).map(e => `
                    <div class="event-item">
                        <span class="event-time">${e.time ? e.time.slice(11, 19) : ''}</span> [Bus #${e.bus}] <strong>${e.desc}</strong>
                    </div>
                `).reverse().join('');
            }
        }

        function focusBus(busKey) {
            if (markers[busKey]) {
                const m = markers[busKey];
                map.setView(m.getLatLng(), 16, { animate: true });
                m.openPopup();
            }
        }

        /* -------------------------------------------------------------
           Conexión WebSocket Reactiva con Actualización por Bus
        ------------------------------------------------------------- */
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
                            (msg.vehicles || []).forEach(v => {
                                const bKey = getBusKey(v);
                                activeVehicles[bKey] = v;
                                if (busVisibility[bKey] === undefined) busVisibility[bKey] = true;
                            });
                            eventHistory = msg.events || [];
                            updateUI(false);
                        } else if (msg.type === 'vehicle_update' && msg.vehicle) {
                            const v = msg.vehicle;
                            const bKey = getBusKey(v);
                            activeVehicles[bKey] = v;
                            if (busVisibility[bKey] === undefined) busVisibility[bKey] = true;

                            // Actualización reactiva por bus con animación sin redibujar todo
                            renderOrUpdateVehicleMarker(v, true);
                            updateVehicleCardInSidebar(v);
                            updateHeaderMetrics();
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
                (data.vehicles || []).forEach(v => {
                    const bKey = getBusKey(v);
                    activeVehicles[bKey] = v;
                    if (busVisibility[bKey] === undefined) busVisibility[bKey] = true;
                });
                eventHistory = data.events || [];
                updateUI(true);
            } catch (err) {
                console.debug("HTTP fallback error:", err);
            }
        }

        function startPollingFallback() {
            if (!pollingInterval) {
                pollingInterval = setInterval(fetchHttpLive, 15000);
                fetchHttpLive();
            }
        }

        // --- GESTIÓN DE CAPAS WAZE FOR CITIES (CCP) ---
        async function fetchAndRenderWaze() {
            try {
                const res = await fetch('/api/v1/waze/traffic');
                const data = await res.json();
                renderWazeLayers(data);
                const badge = document.getElementById('m-waze');
                if (badge) {
                    badge.textContent = `${data.total_alerts || 0} Inc · ${data.total_jams || 0} Atascos`;
                }
            } catch (err) {
                console.error("Error al obtener Waze CCP:", err);
            }
        }

        function renderWazeLayers(data) {
            wazeJamLayers.forEach(l => map.removeLayer(l));
            wazeAlertLayers.forEach(l => map.removeLayer(l));
            wazeJamLayers = [];
            wazeAlertLayers = [];

            const showJams = document.getElementById('chk-waze-jams')?.checked ?? true;
            const showAlerts = document.getElementById('chk-waze-alerts')?.checked ?? true;

            if (data.jams && Array.isArray(data.jams)) {
                data.jams.forEach(j => {
                    if (!j.line || j.line.length < 2) return;
                    const latlngs = j.line.map(pt => [pt.y, pt.x]);
                    const color = j.color || (j.level >= 4 ? '#ef4444' : (j.level === 3 ? '#f97316' : '#eab308'));
                    
                    const poly = L.polyline(latlngs, {
                        color: color,
                        weight: 7,
                        opacity: 0.90,
                        lineCap: 'round',
                        lineJoin: 'round'
                    });

                    const popupContent = `
                        <div style="min-width: 180px;">
                            <strong style="color: ${color}; font-size: 13px;">🚦 Atasco Waze (${j.level_label || 'Nivel ' + j.level})</strong><br>
                            <b>${j.street}</b> (${j.city || 'Asunción'})<br>
                            Demora Estimada: <b style="color: #ef4444;">+${j.delay_minutes || Math.round(j.delay_seconds/60)} min</b><br>
                            Velocidad en Atasco: <b>${j.speedKMH} km/h</b><br>
                            Longitud Congestión: <b>${j.length_meters}m</b><br>
                            <div style="margin-top: 8px;">
                                <a href="${j.waze_url || 'https://www.waze.com'}" target="_blank" style="background: #0284c7; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; text-decoration: none; font-weight: 700; display: inline-block;">
                                    🚗 Abrir en App Waze
                                </a>
                            </div>
                        </div>
                    `;
                    poly.bindPopup(popupContent);

                    if (showJams) poly.addTo(map);
                    wazeJamLayers.push(poly);
                });
            }

            if (data.alerts && Array.isArray(data.alerts)) {
                data.alerts.forEach(a => {
                    if (!a.location) return;
                    const lat = a.location.y;
                    const lon = a.location.x;
                    const iconEmoji = a.icon || '⚠️';

                    const alertIcon = L.divIcon({
                        className: 'waze-alert-marker',
                        html: `<div style="background: #0f172a; border: 2px solid #f59e0b; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 14px; box-shadow: 0 0 10px rgba(245, 158, 11, 0.6);">${iconEmoji}</div>`,
                        iconSize: [28, 28]
                    });

                    const marker = L.marker([lat, lon], { icon: alertIcon });
                    const popupContent = `
                        <div style="min-width: 200px;">
                            <strong style="color: #fbbf24; font-size: 13px;">${iconEmoji} ${a.type_label || a.type}</strong><br>
                            <b>${a.street}</b> (${a.city || 'Gran Asunción'})<br>
                            <div style="font-size: 11px; margin: 4px 0; color: #cbd5e1;">${a.reportDescription || 'Reportado por comunidad Waze'}</div>
                            <span style="font-size: 10px; color: #94a3b8;">Confianza Waze: ${a.confidence}/5 · Fiabilidad: ${a.reliability}/10</span><br>
                            <div style="margin-top: 8px;">
                                <a href="${a.waze_url || 'https://www.waze.com'}" target="_blank" style="background: #0284c7; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; text-decoration: none; font-weight: 700; display: inline-block;">
                                    🚗 Navegar con Waze
                                </a>
                            </div>
                        </div>
                    `;
                    marker.bindPopup(popupContent);

                    if (showAlerts) marker.addTo(map);
                    wazeAlertLayers.push(marker);
                });
            }
        }

        function toggleWazeLayers() {
            const showJams = document.getElementById('chk-waze-jams')?.checked ?? true;
            const showAlerts = document.getElementById('chk-waze-alerts')?.checked ?? true;

            wazeJamLayers.forEach(l => {
                if (showJams) l.addTo(map); else map.removeLayer(l);
            });
            wazeAlertLayers.forEach(l => {
                if (showAlerts) l.addTo(map); else map.removeLayer(l);
            });
        }

        fetchAndRenderWaze();
        setInterval(fetchAndRenderWaze, 30000);

        initWebSocket();
    </script>
</body>
</html>
"""
    html = html.replace("__COMPANY_BADGE__", company_badge)
    html = html.replace("__COMPANY_NAME__", user_company)
    html = html.replace("__AGENCY_ID__", user_agency or "Todas las Líneas")
    html = html.replace("__CURRENT_AGENCY__", user_agency)
    return html

