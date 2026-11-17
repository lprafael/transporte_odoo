# -*- coding: utf-8 -*-
"""
billetaje_service.py - Conector Automático con la Plataforma de Billetaje Electrónico Jaha (EPAS S.A.)
Extrae en tiempo real:
1. Ramal y sentido oficial configurado en el validador a bordo de cada coche.
2. Pasajeros transportados (validaciones) y recaudación bruta/neta en Guaraníes por bus.
3. Resumen financiero diario de la operadora y conciliación de servicios.
"""

import os
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import requests
import urllib3

urllib3.disable_warnings()

logger = logging.getLogger("billetaje_service")
logger.setLevel(logging.INFO)

BILLETAJE_USER = os.getenv("BILLETAJE_USER", "dsosa_srl")
BILLETAJE_PASS = os.getenv("BILLETAJE_PASS", "dssrl32")
BILLETAJE_EID = int(os.getenv("BILLETAJE_EID", "32"))
BILLETAJE_BASE_URL = "https://billetajeelectronico.com.py"

# Mapeo de Identificación de Ruta en Validador Jaha -> Código de Ramal Oficial en Odoo/PostGIS
MAP_IDENT_TO_CODE = {
    ("AVDA. FERNANDO DE LA MORA MERCADO 4", "IDA"): "0056",
    ("AVDA. FERNANDO DE LA MORA MERCADO 4", "VUELTA"): "0057",
    ("AVDA. FERNANDO DE LA MORA", "IDA"): "0056",
    ("AVDA. FERNANDO DE LA MORA", "VUELTA"): "0057",
    ("FERNANDO DE LA MORA", "IDA"): "0056",
    ("FERNANDO DE LA MORA", "VUELTA"): "0057",
    ("IPS", "IDA"): "0052",
    ("IPS", "VUELTA"): "0053",
    ("MERCADO 4", "IDA"): "0054",
    ("MERCADO 4", "VUELTA"): "0055",
    ("AVDA. EUSEBIO AYALA - MERCADO 4", "IDA"): "0058",
    ("AVDA. EUSEBIO AYALA - MERCADO 4", "VUELTA"): "0059",
    ("EUSEBIO AYALA", "IDA"): "0058",
    ("EUSEBIO AYALA", "VUELTA"): "0059",
    ("MCAL. LOPEZ", "IDA"): "0050",
    ("MCAL. LOPEZ", "VUELTA"): "0050",
    ("MCAL. LOPEZ", ""): "0050",
    ("TERMINAL", "IDA"): "0051",
    ("TERMINAL", "VUELTA"): "0051",
    ("TERMINAL", ""): "0051",
    ("PETROPAR", "IDA"): "004a",
    ("PETROPAR", "VUELTA"): "004b",
    ("SALINAS", "IDA"): "004c",
    ("SALINAS", "VUELTA"): "004d",
    ("CAAGUAZU", "IDA"): "004e",
    ("CAAGUAZU", "VUELTA"): "004f",
    ("NOCTURNO IDA", "IDA"): "01ef",
    ("NOCTURNO VUELTA", "VUELTA"): "01f0",
    ("NOCTURNO", "IDA"): "01ef",
    ("NOCTURNO", "VUELTA"): "01f0",
}

class BilletajeConnector:
    def __init__(self, username=BILLETAJE_USER, password=BILLETAJE_PASS, eid=BILLETAJE_EID):
        self.username = username
        self.password = password
        self.eid = eid
        self.session: Optional[requests.Session] = None
        self._lock = threading.Lock()
        self.last_login_time = 0

    def _get_session(self) -> requests.Session:
        with self._lock:
            if self.session is None:
                self._authenticate()
            return self.session

    def _authenticate(self) -> bool:
        """Inicia sesión en la plataforma de billetaje de Jaha."""
        logger.info(f"🔑 Autenticando en Billetaje Electrónico Jaha como '{self.username}'...")
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
        })
        try:
            # 1. Visitar raíz para obtener cookies iniciales
            s.get(f"{BILLETAJE_BASE_URL}/", verify=False, timeout=10)
            # 2. Enviar login
            resp = s.post(
                f"{BILLETAJE_BASE_URL}/loginProcess",
                data={"username": self.username, "password": self.password},
                verify=False,
                timeout=12,
                allow_redirects=True
            )
            if "dashboard-operadoras" in resp.url or resp.status_code == 200:
                self.session = s
                self.last_login_time = datetime.now(timezone.utc).timestamp()
                logger.info("✅ Sesión establecida exitosamente con Jaha Billetaje Electrónico.")
                return True
            else:
                logger.error(f"❌ Error en autenticación Billetaje Jaha (Status: {resp.status_code}, URL: {resp.url})")
                return False
        except Exception as e:
            logger.error(f"❌ Error conectando a Billetaje Jaha: {e}")
            return False

    def fetch_json(self, url: str) -> Optional[Any]:
        """Ejecuta una petición GET con re-autenticación automática si la sesión expiró."""
        for attempt in range(2):
            s = self._get_session()
            try:
                r = s.get(url, verify=False, timeout=12)
                if r.status_code == 200 and r.text.strip().startswith(("{", "[")):
                    return r.json()
                elif r.status_code in (401, 403) or "login" in r.url or "<!DOCTYPE" in r.text[:100]:
                    logger.warning("⚠️ Sesión Billetaje expirada. Reautenticando...")
                    with self._lock:
                        self.session = None
                    self._authenticate()
                else:
                    logger.debug(f"Aviso fetch_json {url}: status {r.status_code}")
            except Exception as e:
                logger.debug(f"Excepción en fetch_json {url}: {e}")
                with self._lock:
                    self.session = None
        return None

# Instancias de conectores por empresa (Multi-Tenant)
_connectors: Dict[str, BilletajeConnector] = {}
_connectors_lock = threading.Lock()

def get_connector(username: str = BILLETAJE_USER, password: str = BILLETAJE_PASS, eid: int = BILLETAJE_EID) -> BilletajeConnector:
    key = f"{username}:{eid}"
    with _connectors_lock:
        if key not in _connectors:
            _connectors[key] = BilletajeConnector(username=username, password=password, eid=eid)
        else:
            conn = _connectors[key]
            if conn.password != password:
                conn.password = password
                with conn._lock:
                    conn.session = None
        return _connectors[key]

# Instancia por defecto compatible
_connector = get_connector()

def get_db_billetaje_concessionaires() -> List[Dict[str, Any]]:
    """Consulta en transit_concessionaire (flota_db) las empresas con integración de billetaje activa."""
    try:
        from admin_service import get_db_connection
        from psycopg2.extras import RealDictCursor
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, code, agency_id, billetaje_provider, 
                   billetaje_user, billetaje_password, billetaje_eid, billetaje_active
            FROM transit_concessionaire
            WHERE active = true 
              AND billetaje_active = true 
              AND billetaje_provider = 'jaha'
              AND billetaje_user IS NOT NULL 
              AND billetaje_password IS NOT NULL;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.debug(f"Aviso consultando credenciales de billetaje en DB: {e}")
        return []

def resolve_route_from_validator(identificacion: str, sentido: str) -> Optional[str]:
    """Mapea la cadena de identificación del validador y el sentido a nuestro código de ruta oficial."""
    if not identificacion or identificacion.strip() == "-":
        return None
    
    clean_ident = identificacion.strip().upper()
    clean_sentido = (sentido or "").strip().upper()

    # 1. Búsqueda exacta
    key = (clean_ident, clean_sentido)
    if key in MAP_IDENT_TO_CODE:
        return MAP_IDENT_TO_CODE[key]

    # 2. Búsqueda parcial de patrones conocidos
    if "FERNANDO DE LA MORA" in clean_ident:
        return "0057" if clean_sentido == "VUELTA" else "0056"
    if "EUSEBIO AYALA" in clean_ident:
        return "0059" if clean_sentido == "VUELTA" else "0058"
    if "IPS" in clean_ident:
        return "0053" if clean_sentido == "VUELTA" else "0052"
    if "MERCADO 4" in clean_ident:
        return "0055" if clean_sentido == "VUELTA" else "0054"
    if "MCAL. LOPEZ" in clean_ident:
        return "0050"
    if "TERMINAL" in clean_ident:
        return "0051"
    if "PETROPAR" in clean_ident:
        return "004b" if clean_sentido == "VUELTA" else "004a"
    if "SALINAS" in clean_ident:
        return "004d" if clean_sentido == "VUELTA" else "004c"
    if "CAAGUAZU" in clean_ident:
        return "004f" if clean_sentido == "VUELTA" else "004e"
    if "NOCTURNO" in clean_ident:
        return "01f0" if clean_sentido == "VUELTA" else "01ef"

    return None

def sync_billetaje_for_concessionaire(redis_client, agency_id: str, username: str, password: str, eid: int) -> Dict[str, Any]:
    """Sincroniza datos de billetaje en Redis para una empresa concesionaria específica."""
    connector = get_connector(username, password, eid)
    res = {
        "status": "success",
        "agency_id": agency_id,
        "units_synced": 0,
        "productivity_synced": 0,
        "financial_summary": {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # 1. Monitoreo en Tiempo Real de Validadores
    url_mon = f"{BILLETAJE_BASE_URL}/api1/api/v1/getMonitoreoPorEmpresa?empresa={eid}"
    mon_data = connector.fetch_json(url_mon)
    if isinstance(mon_data, list):
        for item in mon_data:
            dec_unit = str(item.get("unidad") or "").strip()
            if not dec_unit or dec_unit == "0":
                continue
            
            try:
                dec_int = int(dec_unit)
                hex_id = f"{dec_int:05x}"
            except Exception:
                hex_id = dec_unit

            ident = item.get("identificacion") or ""
            sentido = item.get("sentido") or ""
            tipo_srv = item.get("tipo_servicio") or "DIFERENCIAL"
            speed = float(item.get("velocidad") or 0.0)
            hora = item.get("hora") or ""
            estado = item.get("estado") or "En movimiento"
            id_ruta = item.get("id_ruta")

            resolved_code = resolve_route_from_validator(ident, sentido)

            unit_info = {
                "unit_dec": dec_unit,
                "unit_hex": hex_id,
                "agency_id": agency_id,
                "identificacion": ident,
                "sentido": sentido,
                "tipo_servicio": tipo_srv,
                "id_ruta": id_ruta,
                "resolved_route_code": resolved_code,
                "velocidad": speed,
                "hora_validador": hora,
                "estado": estado,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            if redis_client:
                try:
                    payload = json.dumps(unit_info)
                    redis_client.setex(f"billetaje:unit:{agency_id}:{dec_unit}", 300, payload)
                    redis_client.setex(f"billetaje:unit:{agency_id}:{hex_id}", 300, payload)

                    # Si pudimos resolver el ramal oficial del validador, aplicar bloqueo suave de ruta
                    if resolved_code:
                        redis_client.setex(f"vehicle_route_lock:{agency_id}:{hex_id}", 3600, resolved_code)
                        redis_client.setex(f"vehicle_route_lock:{agency_id}:{dec_unit}", 3600, resolved_code)

                        # Actualizar vehículo activo en Redis si ya está hidratado
                        for bus_k in (hex_id, dec_unit):
                            v_raw = redis_client.get(f"vehicle:{agency_id}:{bus_k}") or redis_client.get(f"vehicle:{bus_k}")
                            if v_raw:
                                try:
                                    v_dict = json.loads(v_raw)
                                    v_dict["route_id"] = resolved_code
                                    v_dict["validator_service"] = tipo_srv
                                    v_dict["validator_ident"] = ident
                                    v_dict["validator_sentido"] = sentido
                                    v_dict["route_locked"] = True
                                    redis_client.setex(f"vehicle:{agency_id}:{bus_k}", 300, json.dumps(v_dict))
                                except Exception:
                                    pass
                except Exception as e:
                    logger.debug(f"Aviso guardando unidad en Redis: {e}")

            res["units_synced"] += 1

    # 2. Productividad y Pasajeros por Unidad
    url_prod = f"{BILLETAJE_BASE_URL}/api1/api/v1/getMonitoreoPorEmpresaProductividadPorUnidad?empresa={eid}"
    prod_data = connector.fetch_json(url_prod)
    if isinstance(prod_data, list):
        for p in prod_data:
            dec_unit = str(p.get("unidad") or "").strip()
            if not dec_unit or dec_unit == "0":
                continue
            try:
                dec_int = int(dec_unit)
                hex_id = f"{dec_int:05x}"
            except Exception:
                hex_id = dec_unit

            pax_count = int(p.get("cantidad_pasajes") or 0)
            amount = int(p.get("monto_pasajes") or 0)
            trips = int(p.get("cantidad_rutas") or 0)
            last_up = p.get("ultima_actualizacion") or ""

            prod_info = {
                "unit_dec": dec_unit,
                "unit_hex": hex_id,
                "agency_id": agency_id,
                "passengers_today": pax_count,
                "revenue_today": amount,
                "trips_today": trips,
                "last_update": last_up,
            }

            if redis_client:
                try:
                    payload = json.dumps(prod_info)
                    redis_client.setex(f"billetaje:prod:{agency_id}:{dec_unit}", 600, payload)
                    redis_client.setex(f"billetaje:prod:{agency_id}:{hex_id}", 600, payload)
                except Exception:
                    pass

            res["productivity_synced"] += 1

    # 3. Resumen Financiero Diario
    today_str = datetime.now().strftime("%Y-%m-%d")
    url_fin = f"{BILLETAJE_BASE_URL}/getNetoAndComision?fechaInicio={today_str}&fechaFin={today_str}"
    fin_data = connector.fetch_json(url_fin)
    if isinstance(fin_data, dict) and fin_data.get("cantidad") is not None:
        res["financial_summary"] = fin_data
        if redis_client:
            try:
                redis_client.setex(f"billetaje:financial_summary:{agency_id}", 900, json.dumps(fin_data))
            except Exception:
                pass

    logger.info(
        f"✅ [{agency_id}] Sincronización Billetaje Jaha completada: {res['units_synced']} validadores, "
        f"{res['productivity_synced']} unidades con pasajes cobrados hoy. "
        f"Total pasajes hoy: {res['financial_summary'].get('cantidad', '--')}."
    )
    return res

def sync_billetaje_all(redis_client, agency_id: Optional[str] = None) -> Dict[str, Any]:
    """Sincroniza para una agencia específica o para todas las que tengan credenciales en BD."""
    db_configs = get_db_billetaje_concessionaires()

    if agency_id and agency_id != "all":
        target_cfg = next((c for c in db_configs if c.get("agency_id") == agency_id), None)
        if target_cfg:
            return sync_billetaje_for_concessionaire(
                redis_client,
                agency_id=target_cfg["agency_id"],
                username=target_cfg["billetaje_user"],
                password=target_cfg["billetaje_password"],
                eid=int(target_cfg.get("billetaje_eid") or BILLETAJE_EID)
            )
        else:
            return sync_billetaje_for_concessionaire(
                redis_client,
                agency_id=agency_id,
                username=BILLETAJE_USER,
                password=BILLETAJE_PASS,
                eid=BILLETAJE_EID
            )

    if db_configs:
        results = {}
        for cfg in db_configs:
            ag = cfg.get("agency_id") or "0008"
            results[ag] = sync_billetaje_for_concessionaire(
                redis_client,
                agency_id=ag,
                username=cfg["billetaje_user"],
                password=cfg["billetaje_password"],
                eid=int(cfg.get("billetaje_eid") or BILLETAJE_EID)
            )
        return {"status": "success", "companies": results}
    else:
        return sync_billetaje_for_concessionaire(
            redis_client,
            agency_id="0008",
            username=BILLETAJE_USER,
            password=BILLETAJE_PASS,
            eid=BILLETAJE_EID
        )

def get_cached_billetaje_prod(redis_client, bus_id: str, agency_id: str = "004B") -> Dict[str, Any]:
    """Obtiene los pasajes y recaudación del día para un bus desde Redis."""
    if not redis_client or not bus_id:
        return {}
    clean_id = str(bus_id).strip()
    candidates = [clean_id]
    try:
        dec_num = str(int(clean_id, 16))
        candidates.append(dec_num)
    except Exception:
        pass

    for c in candidates:
        for ag in (agency_id, "0008", "004B"):
            raw = redis_client.get(f"billetaje:prod:{ag}:{c}")
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    pass
    return {}

def get_cached_financial_summary(redis_client, agency_id: str = "0008") -> Dict[str, Any]:
    """Retorna el resumen financiero global del día desde Redis."""
    if not redis_client:
        return {}
    raw = redis_client.get(f"billetaje:financial_summary:{agency_id}")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {}
