# -*- coding: utf-8 -*-
"""
Módulo de Integración Waze for Cities (Connected Citizens Program - CCP)
Poliverso Transit | Sistema Integral de Telemetría y Flota

Estándar: Waze CCP Data Specification (Alerts, Jams, Irregularities)
Proporciona:
1. Ingesta de feed Waze CCP oficial (JSON/GeoJSON).
2. Fallback inteligente con simulación de alta fidelidad para el corredor Gran Asunción
   (Av. Eusebio Ayala, Av. Mariscal López, Ruta PY02, Luque/Silvio Pettirossi).
3. Correlación geoespacial en tiempo real de incidentes y congestiones con los ramales
   de transporte y buses activos.
4. Generación de enlaces profundos (Deep-links) de navegación en Waze.
"""

import os
import time
import math
import logging
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("waze_service")

# Variables de entorno Waze CCP
WAZE_CCP_FEED_URL = os.getenv("WAZE_CCP_FEED_URL", "https://feed.waze.com/partner-feed/asuncion-gran-asuncion")
WAZE_API_KEY = os.getenv("WAZE_API_KEY", "13862442136_53a0f8cb7b11baa42b4af0c384657f6d2b77ece8")

# Cache local en memoria para no saturar requests (45s TTL)
_waze_cache: Dict[str, Any] = {
    "last_fetch": 0,
    "data": None,
    "is_simulated": False
}


def get_waze_deep_link(lat: float, lon: float, navigate: bool = True) -> str:
    """Genera URL oficial de Waze para ubicar o navegar directamente al punto."""
    nav_param = "&navigate=yes" if navigate else ""
    return f"https://www.waze.com/ul?ll={lat},{lon}{nav_param}"


def _generate_simulated_waze_data() -> Dict[str, Any]:
    """
    Genera un feed CCP de Waze auténtico y contextualizado para Gran Asunción.
    Cubre los corredores troncales reales donde operan los 6 ramales del sistema.
    """
    now_ms = int(time.time() * 1000)

    alerts = [
        {
            "id": "waze_alert_01",
            "uuid": "wz-asu-2026-acc-01",
            "pubMillis": now_ms - (12 * 60 * 1000),
            "type": "ACCIDENT",
            "subtype": "ACCIDENT_MINOR",
            "street": "Av. Doctor Eusebio Ayala",
            "city": "Asunción",
            "location": {"x": -57.59039, "y": -25.310821},
            "magvar": 280,
            "reportDescription": "Colisión leve sobre carril derecho frente al Colegio Nacional. Tránsito restringido.",
            "confidence": 5,
            "reliability": 9,
            "reportRating": 4,
            "icon": "💥🚗",
            "type_label": "Accidente de Tránsito",
            "corridor": "020d",
            "waze_url": get_waze_deep_link(-25.310821, -57.59039)
        },
        {
            "id": "waze_alert_02",
            "uuid": "wz-asu-2026-cst-02",
            "pubMillis": now_ms - (35 * 60 * 1000),
            "type": "CONSTRUCTION",
            "subtype": "ROAD_CLOSED_CONSTRUCTION",
            "street": "Av. Mariscal López",
            "city": "Fernando de la Mora",
            "location": {"x": -57.543601, "y": -25.305308},
            "magvar": 95,
            "reportDescription": "Obras de bacheo y pavimentación MOPC. Media calzada habilitada.",
            "confidence": 5,
            "reliability": 10,
            "reportRating": 5,
            "icon": "🚧",
            "type_label": "Obras en Calzada",
            "corridor": "020f",
            "waze_url": get_waze_deep_link(-25.305308, -57.543601)
        },
        {
            "id": "waze_alert_03",
            "uuid": "wz-asu-2026-haz-03",
            "pubMillis": now_ms - (8 * 60 * 1000),
            "type": "HAZARD",
            "subtype": "HAZARD_ON_ROAD_CAR_STOPPED",
            "street": "Ruta PY02 (Mcal. Estigarribia)",
            "city": "San Lorenzo",
            "location": {"x": -57.519194, "y": -25.341317},
            "magvar": 110,
            "reportDescription": "Ómnibus de larga distancia con avería mecánica ocupando media calzada.",
            "confidence": 4,
            "reliability": 8,
            "reportRating": 4,
            "icon": "⚠️🚌",
            "type_label": "Vehículo Detenido / Peligro",
            "corridor": "020c",
            "waze_url": get_waze_deep_link(-25.341317, -57.519194)
        },
        {
            "id": "waze_alert_04",
            "uuid": "wz-asu-2026-jam-04",
            "pubMillis": now_ms - (5 * 60 * 1000),
            "type": "JAM",
            "subtype": "JAM_HEAVY_TRAFFIC",
            "street": "Av. Aviador Silvio Pettirossi",
            "city": "Luque",
            "location": {"x": -57.524798, "y": -25.262735},
            "magvar": 215,
            "reportDescription": "Congestión por sincronización semafórica en rotonda de acceso.",
            "confidence": 4,
            "reliability": 8,
            "reportRating": 3,
            "icon": "🚦",
            "type_label": "Congestión Severa",
            "corridor": "0210",
            "waze_url": get_waze_deep_link(-25.262735, -57.524798)
        }
    ]

    jams = [
        {
            "id": "waze_jam_01",
            "uuid": "wz-jam-eusebio-ayala",
            "pubMillis": now_ms - (6 * 60 * 1000),
            "street": "Av. Doctor Eusebio Ayala",
            "city": "Asunción",
            "level": 4, # 1: Suave, 2: Lento, 3: Pesado, 4: Muy Pesado, 5: Detenido
            "level_label": "Muy Pesado (Parado por tramos)",
            "speedKMH": 7.4,
            "delay_seconds": 660, # 11 minutos de demora
            "delay_minutes": 11,
            "length_meters": 1720,
            "corridor": "020d",
            "color": "#ef4444",
            "line": [
                {
                                "x": -57.604924,
                                "y": -25.305835
                },
                {
                                "x": -57.603389,
                                "y": -25.306315
                },
                {
                                "x": -57.602371,
                                "y": -25.306645
                },
                {
                                "x": -57.602206,
                                "y": -25.3067
                },
                {
                                "x": -57.601769,
                                "y": -25.306845
                },
                {
                                "x": -57.600891,
                                "y": -25.307151
                },
                {
                                "x": -57.599063,
                                "y": -25.30778
                },
                {
                                "x": -57.597871,
                                "y": -25.308176
                },
                {
                                "x": -57.597389,
                                "y": -25.308329
                },
                {
                                "x": -57.597078,
                                "y": -25.308434
                },
                {
                                "x": -57.596428,
                                "y": -25.308674
                },
                {
                                "x": -57.596333,
                                "y": -25.308711
                },
                {
                                "x": -57.595301,
                                "y": -25.309089
                },
                {
                                "x": -57.594234,
                                "y": -25.309471
                },
                {
                                "x": -57.593097,
                                "y": -25.309864
                },
                {
                                "x": -57.59223,
                                "y": -25.310176
                },
                {
                                "x": -57.59039,
                                "y": -25.310821
                },
                {
                                "x": -57.587352,
                                "y": -25.311884
                },
                {
                                "x": -57.586268,
                                "y": -25.312249
                },
                {
                                "x": -57.585469,
                                "y": -25.312525
                },
                {
                                "x": -57.584223,
                                "y": -25.312959
                },
                {
                                "x": -57.58399,
                                "y": -25.313041
                },
                {
                                "x": -57.582969,
                                "y": -25.313402
                },
                {
                                "x": -57.581869,
                                "y": -25.313796
                },
                {
                                "x": -57.581658,
                                "y": -25.313871
                },
                {
                                "x": -57.580479,
                                "y": -25.314297
                },
                {
                                "x": -57.579309,
                                "y": -25.314719
                },
                {
                                "x": -57.579118,
                                "y": -25.314788
                },
                {
                                "x": -57.579016,
                                "y": -25.314824
                },
                {
                                "x": -57.577895,
                                "y": -25.315213
                },
                {
                                "x": -57.577684,
                                "y": -25.315291
                },
                {
                                "x": -57.57698,
                                "y": -25.315521
                },
                {
                                "x": -57.576292,
                                "y": -25.315745
                }
]
        },
        {
            "id": "waze_jam_02",
            "uuid": "wz-jam-mcal-lopez",
            "pubMillis": now_ms - (10 * 60 * 1000),
            "street": "Av. Mariscal López",
            "city": "Fernando de la Mora",
            "level": 3,
            "level_label": "Pesado (Fila lenta)",
            "speedKMH": 13.8,
            "delay_seconds": 420, # 7 minutos
            "delay_minutes": 7,
            "length_meters": 1350,
            "corridor": "020f",
            "color": "#f97316",
            "line": [
                {
                                "x": -57.557978,
                                "y": -25.304837
                },
                {
                                "x": -57.555814,
                                "y": -25.306033
                },
                {
                                "x": -57.553978,
                                "y": -25.307101
                },
                {
                                "x": -57.553359,
                                "y": -25.307459
                },
                {
                                "x": -57.553049,
                                "y": -25.30763
                },
                {
                                "x": -57.552663,
                                "y": -25.307837
                },
                {
                                "x": -57.552351,
                                "y": -25.307989
                },
                {
                                "x": -57.55204,
                                "y": -25.308096
                },
                {
                                "x": -57.551611,
                                "y": -25.308193
                },
                {
                                "x": -57.551162,
                                "y": -25.308248
                },
                {
                                "x": -57.55076,
                                "y": -25.308238
                },
                {
                                "x": -57.550272,
                                "y": -25.308135
                },
                {
                                "x": -57.548127,
                                "y": -25.307521
                },
                {
                                "x": -57.54752,
                                "y": -25.307266
                },
                {
                                "x": -57.546598,
                                "y": -25.306803
                },
                {
                                "x": -57.545707,
                                "y": -25.306359
                },
                {
                                "x": -57.544737,
                                "y": -25.305878
                },
                {
                                "x": -57.543601,
                                "y": -25.305308
                },
                {
                                "x": -57.542768,
                                "y": -25.304916
                },
                {
                                "x": -57.542029,
                                "y": -25.304682
                },
                {
                                "x": -57.54154,
                                "y": -25.304585
                },
                {
                                "x": -57.541167,
                                "y": -25.304543
                },
                {
                                "x": -57.540255,
                                "y": -25.304502
                },
                {
                                "x": -57.539432,
                                "y": -25.304439
                },
                {
                                "x": -57.538463,
                                "y": -25.304231
                },
                {
                                "x": -57.537828,
                                "y": -25.304116
                },
                {
                                "x": -57.537296,
                                "y": -25.304254
                },
                {
                                "x": -57.536064,
                                "y": -25.304922
                },
                {
                                "x": -57.534855,
                                "y": -25.305893
                },
                {
                                "x": -57.534161,
                                "y": -25.306541
                },
                {
                                "x": -57.533715,
                                "y": -25.30712
                },
                {
                                "x": -57.532398,
                                "y": -25.308856
                },
                {
                                "x": -57.531549,
                                "y": -25.309987
                },
                {
                                "x": -57.530765,
                                "y": -25.311012
                }
]
        },
        {
            "id": "waze_jam_03",
            "uuid": "wz-jam-py02-san-lorenzo",
            "pubMillis": now_ms - (4 * 60 * 1000),
            "street": "Ruta PY02 (Mcal. Estigarribia)",
            "city": "San Lorenzo",
            "level": 4,
            "level_label": "Muy Pesado",
            "speedKMH": 6.8,
            "delay_seconds": 780, # 13 minutos
            "delay_minutes": 13,
            "length_meters": 1850,
            "corridor": "020c",
            "color": "#ef4444",
            "line": [
                {
                                "x": -57.534894,
                                "y": -25.33471
                },
                {
                                "x": -57.533591,
                                "y": -25.335207
                },
                {
                                "x": -57.53177,
                                "y": -25.335902
                },
                {
                                "x": -57.529954,
                                "y": -25.336559
                },
                {
                                "x": -57.526947,
                                "y": -25.337684
                },
                {
                                "x": -57.526381,
                                "y": -25.337906
                },
                {
                                "x": -57.525721,
                                "y": -25.338182
                },
                {
                                "x": -57.523973,
                                "y": -25.338829
                },
                {
                                "x": -57.523495,
                                "y": -25.33895
                },
                {
                                "x": -57.52281,
                                "y": -25.339212
                },
                {
                                "x": -57.521799,
                                "y": -25.339592
                },
                {
                                "x": -57.521578,
                                "y": -25.339691
                },
                {
                                "x": -57.520855,
                                "y": -25.340115
                },
                {
                                "x": -57.520398,
                                "y": -25.340407
                },
                {
                                "x": -57.519876,
                                "y": -25.340757
                },
                {
                                "x": -57.518911,
                                "y": -25.341569
                },
                {
                                "x": -57.517847,
                                "y": -25.342689
                },
                {
                                "x": -57.517179,
                                "y": -25.343685
                },
                {
                                "x": -57.516613,
                                "y": -25.344597
                },
                {
                                "x": -57.515717,
                                "y": -25.345235
                },
                {
                                "x": -57.515189,
                                "y": -25.345615
                },
                {
                                "x": -57.514475,
                                "y": -25.34688
                },
                {
                                "x": -57.513923,
                                "y": -25.347821
                },
                {
                                "x": -57.51386,
                                "y": -25.347898
                },
                {
                                "x": -57.513761,
                                "y": -25.347936
                },
                {
                                "x": -57.513654,
                                "y": -25.347918
                },
                {
                                "x": -57.512647,
                                "y": -25.347453
                },
                {
                                "x": -57.511871,
                                "y": -25.347077
                },
                {
                                "x": -57.508573,
                                "y": -25.345495
                },
                {
                                "x": -57.505535,
                                "y": -25.344088
                }
]
        },
        {
            "id": "waze_jam_04",
            "uuid": "wz-jam-pettirossi-luque",
            "pubMillis": now_ms - (3 * 60 * 1000),
            "street": "Av. Aviador Silvio Pettirossi",
            "city": "Luque",
            "level": 3,
            "level_label": "Pesado",
            "speedKMH": 16.5,
            "delay_seconds": 360, # 6 minutos
            "delay_minutes": 6,
            "length_meters": 1100,
            "corridor": "0210",
            "color": "#f97316",
            "line": [
                {
                                "x": -57.512076,
                                "y": -25.243754
                },
                {
                                "x": -57.512256,
                                "y": -25.243939
                },
                {
                                "x": -57.512304,
                                "y": -25.244275
                },
                {
                                "x": -57.51223,
                                "y": -25.244441
                },
                {
                                "x": -57.511723,
                                "y": -25.245264
                },
                {
                                "x": -57.511667,
                                "y": -25.245555
                },
                {
                                "x": -57.512281,
                                "y": -25.24808
                },
                {
                                "x": -57.513191,
                                "y": -25.251779
                },
                {
                                "x": -57.513518,
                                "y": -25.253138
                },
                {
                                "x": -57.514009,
                                "y": -25.255172
                },
                {
                                "x": -57.514528,
                                "y": -25.257324
                },
                {
                                "x": -57.514702,
                                "y": -25.257933
                },
                {
                                "x": -57.514812,
                                "y": -25.258221
                },
                {
                                "x": -57.515134,
                                "y": -25.258811
                },
                {
                                "x": -57.51544,
                                "y": -25.259208
                },
                {
                                "x": -57.516065,
                                "y": -25.259757
                },
                {
                                "x": -57.518683,
                                "y": -25.261814
                },
                {
                                "x": -57.520202,
                                "y": -25.262788
                },
                {
                                "x": -57.521706,
                                "y": -25.2631
                },
                {
                                "x": -57.524798,
                                "y": -25.262735
                },
                {
                                "x": -57.527177,
                                "y": -25.26243
                },
                {
                                "x": -57.527768,
                                "y": -25.262343
                },
                {
                                "x": -57.530337,
                                "y": -25.262009
                },
                {
                                "x": -57.531059,
                                "y": -25.262018
                },
                {
                                "x": -57.531723,
                                "y": -25.26213
                },
                {
                                "x": -57.532384,
                                "y": -25.262358
                },
                {
                                "x": -57.532951,
                                "y": -25.262663
                },
                {
                                "x": -57.533472,
                                "y": -25.263055
                },
                {
                                "x": -57.533934,
                                "y": -25.263559
                },
                {
                                "x": -57.535594,
                                "y": -25.266216
                },
                {
                                "x": -57.538019,
                                "y": -25.270171
                },
                {
                                "x": -57.538769,
                                "y": -25.271354
                },
                {
                                "x": -57.539135,
                                "y": -25.271812
                },
                {
                                "x": -57.539611,
                                "y": -25.272277
                },
                {
                                "x": -57.540105,
                                "y": -25.272657
                },
                {
                                "x": -57.541754,
                                "y": -25.273664
                },
                {
                                "x": -57.542505,
                                "y": -25.274163
                },
                {
                                "x": -57.543406,
                                "y": -25.274633
                },
                {
                                "x": -57.544527,
                                "y": -25.275072
                }
]
        }
    ]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "WAZE_CONNECTED_CITIZENS_PROGRAM_ASUNCION",
        "feed_url": WAZE_CCP_FEED_URL,
        "is_simulated": True,
        "total_alerts": len(alerts),
        "total_jams": len(jams),
        "alerts": alerts,
        "jams": jams
    }


def fetch_waze_ccp_feed(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Obtiene el feed de Waze for Cities (CCP).
    Intenta conexión con el endpoint oficial; si no está disponible o requiere
    IP autorizada del partner, activa automáticamente la simulación en tiempo real.
    """
    global _waze_cache
    now = time.time()

    if not force_refresh and _waze_cache["data"] and (now - _waze_cache["last_fetch"] < 45):
        return _waze_cache["data"]

    # 1. Intentar conexión real a Waze CCP Feed
    feed_url = WAZE_CCP_FEED_URL.strip()
    headers = {
        "User-Agent": "PoliversoTransit-WazeCCP/3.0",
        "X-API-KEY": WAZE_API_KEY,
        "Authorization": f"Bearer {WAZE_API_KEY}",
        "Accept": "application/json"
    }
    params = {
        "token": WAZE_API_KEY,
        "format": "json"
    }

    try:
        logger.info(f"Conectando a Waze CCP Feed: {feed_url}...")
        resp = requests.get(feed_url, headers=headers, params=params, timeout=3.5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and ("alerts" in data or "jams" in data):
                logger.info(f"✅ Feed Waze CCP oficial recibido con éxito! Alerts: {len(data.get('alerts', []))}, Jams: {len(data.get('jams', []))}")
                waze_result = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "WAZE_CCP_LIVE_FEED",
                    "feed_url": feed_url,
                    "is_simulated": False,
                    "total_alerts": len(data.get("alerts", [])),
                    "total_jams": len(data.get("jams", [])),
                    "alerts": data.get("alerts", []),
                    "jams": data.get("jams", [])
                }
                _waze_cache = {
                    "last_fetch": now,
                    "data": waze_result,
                    "is_simulated": False
                }
                return waze_result
        else:
            logger.warning(f"Waze CCP Feed retornó código HTTP {resp.status_code}. Activando motor de contingencia de Gran Asunción.")
    except Exception as e:
        logger.warning(f"No se pudo contactar endpoint externo de Waze ({e}). Activando motor de contingencia Gran Asunción.")

    # 2. Contingencia / Motor Gran Asunción activo
    simulated_data = _generate_simulated_waze_data()
    _waze_cache = {
        "last_fetch": now,
        "data": simulated_data,
        "is_simulated": True
    }
    return simulated_data


def correlate_waze_with_transit(waze_data: Dict[str, Any], routes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Cruza la información de incidentes y atascos de Waze con cada uno de los
    ramales de ómnibus y sus coches en operación.
    Calcula demoras inducidas y explica por qué ocurren pegonamientos o huecos.
    """
    alerts = waze_data.get("alerts", [])
    jams = waze_data.get("jams", [])

    corridor_impacts: Dict[str, Any] = {}

    for r in routes_data:
        r_id = (r.get("route_id") or "").lower()
        affecting_alerts = [a for a in alerts if a.get("corridor") == r_id or r_id in (a.get("corridor") or "")]
        affecting_jams = [j for j in jams if j.get("corridor") == r_id or r_id in (j.get("corridor") or "")]

        total_delay_min = sum(j.get("delay_minutes", 0) for j in affecting_jams)
        max_level = max([j.get("level", 0) for j in affecting_jams] + [0])

        severity = "NORMAL"
        if max_level >= 4 or any(a.get("type") in ("ACCIDENT", "ROAD_CLOSED") for a in affecting_alerts):
            severity = "CRITICAL"
        elif max_level >= 2 or len(affecting_alerts) > 0:
            severity = "MODERATE"

        # Identificar buses de este ramal que circulan por la calle afectada
        buses = r.get("buses", [])
        affected_bus_ids = []
        for b in buses:
            b_street = (b.get("street_name") or "").lower()
            for j in affecting_jams:
                j_street = (j.get("street") or "").lower()
                if any(word in b_street for word in j_street.split() if len(word) > 4):
                    affected_bus_ids.append(b.get("bus_id"))
                    b["waze_alert"] = {
                        "level": j.get("level"),
                        "street": j.get("street"),
                        "delay_minutes": j.get("delay_minutes"),
                        "speedKMH": j.get("speedKMH"),
                        "waze_url": get_waze_deep_link(b.get("latitude") or -25.3, b.get("longitude") or -57.6)
                    }

        corridor_impacts[r_id] = {
            "route_id": r_id,
            "route_name": r.get("name"),
            "severity": severity,
            "max_traffic_level": max_level,
            "total_delay_minutes": total_delay_min,
            "alerts_count": len(affecting_alerts),
            "jams_count": len(affecting_jams),
            "affecting_alerts": affecting_alerts,
            "affecting_jams": affecting_jams,
            "affected_buses": list(set(affected_bus_ids)),
            "summary_text": f"Retraso estimado +{total_delay_min} min ({len(affecting_jams)} atasco(s), {len(affecting_alerts)} incidente(s))" if total_delay_min > 0 else "Tránsito normal en Waze"
        }

    return corridor_impacts
