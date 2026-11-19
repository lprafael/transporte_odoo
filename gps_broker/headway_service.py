# -*- coding: utf-8 -*-
"""
Servicio del Tablero Lineal de Intervalos (Headway Monitoring & Bunching Detector)
Calcula la posición relativa de cada bus sobre el shape horizontal del ramal,
detecta pegonamiento (buses muy juntos) y genera la interfaz visual interactiva.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("headway_service")

def is_inside_terminal_or_depot(lat, lon, terminal_stops: List[Dict[str, Any]]) -> bool:
    """Verifica si las coordenadas dadas caen dentro del radio de alguna terminal, parada cabecera o depósito."""
    if lat is None or lon is None or not terminal_stops:
        return False
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if lat_f == 0.0 and lon_f == 0.0:
            return False
        for t in terminal_stops:
            t_lat = t.get("lat")
            t_lon = t.get("lon")
            rad = float(t.get("radius_meters") or 150)
            if t_lat is not None and t_lon is not None:
                dy = (lat_f - float(t_lat)) * 111000.0
                dx = (lon_f - float(t_lon)) * 100000.0
                if (dx * dx + dy * dy) <= (rad * rad):
                    return True
    except Exception:
        pass
    return False

try:
    from billetaje_service import get_cached_billetaje_prod, get_cached_financial_summary
except Exception:
    def get_cached_billetaje_prod(redis_client, bus_id, agency_id="004B"):
        return {}
    def get_cached_financial_summary(redis_client, agency_id="0008"):
        return {}

PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

# Pares de ramales opuestos (Ida <-> Vuelta)
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

def get_opposite_route_code(route_code: str) -> Optional[str]:
    if not route_code:
        return None
    return OPPOSITE_ROUTE_PAIRS.get(route_code.strip().lower())

def get_headway_data(redis_client=None, active_vehicles_memory=None, agency_id: Optional[str] = None) -> Dict[str, Any]:
    """Recopila rutas activas y calcula distancias relativas e intervalos entre buses con soporte multi-tenant."""
    routes_dict = {}
    terminal_stops = []
    
    # 1. Obtener catálogo oficial de ramales y paradas cabecera/terminal desde PostgreSQL
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if agency_id:
            cur.execute("""
                SELECT r.code, r.name, r.direction, r.origin, r.destination,
                       COALESCE(s.total_km, r.distance_km, 18.0) as distance_km,
                       COALESCE(r.line_name, 'Línea General') as line_name
                FROM transit_route r
                JOIN transit_concessionaire c ON r.concessionaire_id = c.id
                LEFT JOIN LATERAL (
                    SELECT total_km
                    FROM transit_route_shape
                    WHERE route_id = r.id
                      AND valid_from <= CURRENT_DATE
                      AND (valid_until IS NULL OR valid_until > CURRENT_DATE)
                    ORDER BY version DESC
                    LIMIT 1
                ) s ON TRUE
                WHERE (c.agency_id = %s OR c.code = %s)
                ORDER BY r.line_name ASC, r.code ASC;
            """, (agency_id, agency_id))
        else:
            cur.execute("""
                SELECT r.code, r.name, r.direction, r.origin, r.destination,
                       COALESCE(s.total_km, r.distance_km, 18.0) as distance_km,
                       COALESCE(r.line_name, 'Línea General') as line_name
                FROM transit_route r
                LEFT JOIN LATERAL (
                    SELECT total_km
                    FROM transit_route_shape
                    WHERE route_id = r.id
                      AND valid_from <= CURRENT_DATE
                      AND (valid_until IS NULL OR valid_until > CURRENT_DATE)
                    ORDER BY version DESC
                    LIMIT 1
                ) s ON TRUE
                ORDER BY r.line_name ASC, r.code ASC;
            """)
        for r in cur.fetchall():
            routes_dict[r['code']] = {
                "route_id": r['code'],
                "name": r['name'],
                "line_name": r.get('line_name') or 'Línea General',
                "direction": r['direction'],
                "direction_label": "Ida" if r['direction'] == 'inbound' else ("Vuelta" if r['direction'] == 'outbound' else "Circular"),
                "origin": r['origin'] or "Cabecera Origen",
                "destination": r['destination'] or "Cabecera Destino",
                "distance_km": float(r['distance_km']) if r['distance_km'] else 18.02,
                "buses": [],
                "headways": [],
                "bunching_count": 0,
                "wrong_direction_count": 0,
                "status": "NO_BUSES"
            }

        # Cargar terminales / cabeceras / cocheras para filtrado espacial preciso
        cur.execute("""
            SELECT id, stop_code, name, stop_type, radius_meters,
                   ST_Y(geom) as lat, ST_X(geom) as lon
            FROM transit_stop
            WHERE stop_type IN ('origin', 'destination', 'terminal', 'depot')
               OR radius_meters >= 100;
        """)
        terminal_stops = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error consultando rutas en PG: {e}")
        # Fallback si PG tiene demora
        fallback_meta = {
            '020c': {'name': 'Ramal 020C - San Lorenzo a Asunción', 'direction': 'inbound', 'label': 'Ida', 'origin': 'San Lorenzo (Azara)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.28},
            '020d': {'name': 'Ramal 020D - Asunción a San Lorenzo', 'direction': 'outbound', 'label': 'Vuelta', 'origin': 'Asunción Centro (Puerto)', 'destination': 'San Lorenzo (Azara)', 'km': 18.02},
            '020e': {'name': 'Ramal 020E - San Lorenzo a Asunción (Variante)', 'direction': 'inbound', 'label': 'Ida', 'origin': 'San Lorenzo (Azara)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.92},
            '020f': {'name': 'Ramal 020F - Asunción a San Lorenzo (Variante)', 'direction': 'outbound', 'label': 'Vuelta', 'origin': 'Asunción Centro (Puerto)', 'destination': 'San Lorenzo (Azara)', 'km': 18.91},
            '0210': {'name': 'Ramal 0210 - Luque (Aeropuerto) a Asunción', 'direction': 'inbound', 'label': 'Ida', 'origin': 'Luque (Rotonda Aeropuerto)', 'destination': 'Asunción Centro (Puerto)', 'km': 18.33},
            '0211': {'name': 'Ramal 0211 - Asunción a Luque (Aeropuerto)', 'direction': 'outbound', 'label': 'Vuelta', 'origin': 'Asunción Centro (Puerto)', 'destination': 'Luque (Rotonda Aeropuerto)', 'km': 18.84},
        }
        for code, m in fallback_meta.items():
            routes_dict[code] = {
                "route_id": code,
                "name": m['name'],
                "direction": m['direction'],
                "direction_label": m['label'],
                "origin": m['origin'],
                "destination": m['destination'],
                "distance_km": m['km'],
                "buses": [],
                "headways": [],
                "bunching_count": 0,
                "status": "NO_BUSES"
            }

    # 2. Obtener vehículos activos de Redis o Memoria filtrados por agency_id
    active_buses = []
    if redis_client:
        try:
            keys = redis_client.keys("vehicle:*")
            for k in keys:
                val = redis_client.get(k)
                if val:
                    data = json.loads(val)
                    bus_agency = data.get("agency_id")
                    if not agency_id or bus_agency == agency_id:
                        active_buses.append(data)
        except Exception as e:
            logger.debug(f"Error Redis headway: {e}")

    if not active_buses and active_vehicles_memory:
        active_buses = [b for b in active_vehicles_memory.values() if (not agency_id or b.get("agency_id") == agency_id)]

    if not active_buses:
        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=2
            )
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if agency_id:
                cur.execute("""
                    SELECT DISTINCT ON (agency_id, bus_internal_code)
                        bus_internal_code as bus_id,
                        license_plate,
                        route_id,
                        agency_id,
                        latitude,
                        longitude,
                        speed_kmh as last_speed_kmh,
                        odometer_km,
                        recorded_at as last_ping_time
                    FROM telemetry_ping
                    WHERE agency_id = %s
                    ORDER BY agency_id, bus_internal_code, recorded_at DESC;
                """, (agency_id,))
            else:
                cur.execute("""
                    SELECT DISTINCT ON (agency_id, bus_internal_code)
                        bus_internal_code as bus_id,
                        license_plate,
                        route_id,
                        agency_id,
                        latitude,
                        longitude,
                        speed_kmh as last_speed_kmh,
                        odometer_km,
                        recorded_at as last_ping_time
                    FROM telemetry_ping
                    ORDER BY agency_id, bus_internal_code, recorded_at DESC;
                """)
            for row in cur.fetchall():
                active_buses.append(dict(row))
            cur.close()
            conn.close()
        except Exception as e:
            logger.debug(f"Error fallback DB headway: {e}")

    # 🛑 Deduplicar buses por agencia + bus_id para evitar evaluar clones o claves duplicadas de Redis
    dedup_buses = {}
    for b in active_buses:
        b_id = str(b.get("bus_id") or "")
        b_ag = str(b.get("agency_id") or agency_id or "")
        dedup_key = f"{b_ag}_{b_id}"
        if b_id:
            if dedup_key not in dedup_buses:
                dedup_buses[dedup_key] = b
            else:
                existing_ping = str(dedup_buses[dedup_key].get("last_ping_time") or "")
                new_ping = str(b.get("last_ping_time") or "")
                if new_ping > existing_ping:
                    dedup_buses[dedup_key] = b
    active_buses = list(dedup_buses.values())

    total_active_buses = 0
    total_bunching_alerts = 0

    # 3. Asignar buses a sus ramales (SOLO UNIDADES EN CIRCULACIÓN)
    for b in active_buses:
        b_bus_id = str(b.get("bus_id") or "")
        b_agency = str(b.get("agency_id") or agency_id or "0008")
        if redis_client and b_bus_id:
            try:
                locked = redis_client.get(f"vehicle_route_lock:{b_agency}:{b_bus_id}") or redis_client.get(f"vehicle_route_lock:{b_bus_id}")
                if locked:
                    locked_r = (locked.decode("utf-8") if isinstance(locked, bytes) else str(locked)).strip().lower()
                    b["route_id"] = locked_r
                    b["route_locked"] = True
            except Exception:
                pass
        r_code = (b.get("route_id") or "").lower()
        if r_code not in routes_dict:
            continue

        state = b.get("state") or b.get("current_state") or "IN_TRANSIT"
        is_gps_fault = b.get("is_gps_fault", False)

        # Comprobar antigüedad del último ping (si lleva >15 min sin reportar, está inactivo / fuera de servicio)
        last_ping = b.get("last_ping_time", "")
        if last_ping:
            try:
                clean_ts = str(last_ping).replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                mins_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
                if mins_ago > 15.0:
                    is_gps_fault = True
            except Exception:
                is_gps_fault = True
        else:
            is_gps_fault = True

        total_km = routes_dict[r_code]["distance_km"]
        dist_km = float(b.get("distance_traveled_km") or 0.0)
        speed = float(b.get("last_speed_kmh") if b.get("last_speed_kmh") is not None else (b.get("speed_kmh") or 0.0))

        # Priorizar el porcentaje de avance exacto calculado por PostGIS sobre el shape
        postgis_pct = float(b.get("progress_percent") or 0.0)
        if postgis_pct > 0:
            pct = min(100.0, max(0.0, round(postgis_pct, 1)))
        elif total_km > 0:
            pct = min(100.0, max(0.0, round((dist_km / total_km) * 100.0, 1)))
        else:
            pct = 0.0

        lat_val = b.get("last_latitude") if b.get("last_latitude") is not None else b.get("latitude")
        lon_val = b.get("last_longitude") if b.get("last_longitude") is not None else b.get("longitude")
        is_in_terminal_area = is_inside_terminal_or_depot(lat_val, lon_val, terminal_stops)

        # 🛑 Detección estricta de Cabecera / Terminal / Depósito / No Circulando:
        is_at_terminal = (
            state in ("AT_ORIGIN", "AT_DESTINATION", "DEPOT", "GPS_FAULT") or
            is_gps_fault or
            (is_in_terminal_area and speed < 8.0) or
            (pct <= 3.0 and speed < 5.0) or
            (pct >= 97.0 and speed < 5.0) or
            (total_km > 0 and (total_km - dist_km) <= 0.6 and speed < 5.0) or
            (dist_km <= 0.6 and speed < 5.0)
        )

        # Excluir del tablero lineal los buses que están en cabecera o sin circulación activa
        if is_at_terminal:
            continue

        total_active_buses += 1
        state_label = b.get("status_display") or ("En Circulación" if state == "IN_TRANSIT" else ("En Cabecera" if state == "AT_ORIGIN" else ("En Destino" if state == "AT_DESTINATION" else ("Desviado" if state == "OFF_ROUTE" else "En Depósito"))))

        lat = b.get("last_latitude") if b.get("last_latitude") is not None else b.get("latitude")
        lon = b.get("last_longitude") if b.get("last_longitude") is not None else b.get("longitude")
        speed = float(b.get("last_speed_kmh") if b.get("last_speed_kmh") is not None else (b.get("speed_kmh") or 0.0))

        bus_entry = {
            "bus_id": b.get("bus_id"),
            "license_plate": b.get("license_plate") or f"COCHE-{b.get('bus_id')}",
            "agency_id": b.get("agency_id", "004B"),
            "route_id": r_code,
            "route_name": routes_dict[r_code]["name"],
            "route_total_km": total_km,
            "direction_label": routes_dict[r_code]["direction_label"],
            "origin": routes_dict[r_code]["origin"],
            "destination": routes_dict[r_code]["destination"],
            "state": state,
            "state_label": state_label,
            "street_name": b.get("street_name") or "",
            "approaching": b.get("approaching") or "",
            "driver_id": b.get("driver_id") or "--",
            "odometer_km": round(float(b.get("odometer_km") or 0.0), 1),
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lon) if lon is not None else None,
            "speed_kmh": round(speed, 1),
            "distance_traveled_km": round(dist_km, 2),
            "progress_percent": pct,
            "deviation_meters": round(float(b.get("deviation_meters") or 0.0), 1),
            "last_ping_time": b.get("last_ping_time"),
            "line_name": routes_dict[r_code].get("line_name", ""),
            "wrong_direction_alert": bool(b.get("wrong_direction_alert", False)),
            "wrong_direction_reason": b.get("wrong_direction_reason", ""),
            "suggested_opposite_route": b.get("suggested_opposite_route") or (get_opposite_route_code(r_code) if b.get("wrong_direction_alert") else ""),
            "heading_diff_deg": b.get("heading_diff_deg"),
            "route_bearing_deg": b.get("route_bearing_deg"),
            "is_bunching": False,
            "bunching_with": None,
            "bunching_gap_m": None,
            "bunching_gap_min": None,
        }

        # Datos de Billetaje Electrónico Jaha (Validaciones & Recaudación)
        try:
            prod = get_cached_billetaje_prod(redis_client, b.get("bus_id"), agency_id=b.get("agency_id", agency_id or "0008"))
            pax = int(prod.get("passengers_today") or 0)
            trips = int(prod.get("trips_today") or 0)
            pax_round = round(pax / trips, 1) if trips > 0 else (float(pax) if pax > 0 else 0.0)
            bus_entry["passengers_today"] = pax
            bus_entry["revenue_today"] = int(prod.get("revenue_today") or 0)
            bus_entry["trips_today"] = trips
            bus_entry["pax_per_round"] = pax_round
            bus_entry["validator_service"] = prod.get("service_type") or b.get("validator_service") or "DIFERENCIAL"
        except Exception:
            bus_entry["passengers_today"] = 0
            bus_entry["revenue_today"] = 0
            bus_entry["trips_today"] = 0
            bus_entry["pax_per_round"] = 0.0
            bus_entry["validator_service"] = "DIFERENCIAL"

        routes_dict[r_code]["buses"].append(bus_entry)

    # 4. Ordenar buses a lo largo de cada carril y calcular Pegonamiento (Bunching)
    for r_code, r_data in routes_dict.items():
        # Ordenar por distancia recorrida (0 km a total_km)
        r_data["buses"].sort(key=lambda x: x["distance_traveled_km"])
        
        buses = r_data["buses"]
        n = len(buses)
        
        total_pax = sum(b.get("passengers_today", 0) for b in buses)
        total_trips = sum(b.get("trips_today", 0) for b in buses)
        r_data["total_passengers"] = total_pax
        r_data["total_trips"] = total_trips
        r_data["avg_pax_per_round"] = round(total_pax / total_trips, 1) if total_trips > 0 else (float(total_pax) if total_pax > 0 else 0.0)

        if n == 0:
            r_data["status"] = "SIN_BUSES"
        elif n == 1:
            r_data["status"] = "UN_BUS"
        else:
            r_data["status"] = "OPTIMO"

        # Calcular intervalos entre coches consecutivos
        for i in range(n - 1):
            b_leader = buses[i + 1]  # Bus más adelantado
            b_trailer = buses[i]     # Bus que viene detrás
            
            # 🛑 NUNCA comparar un bus consigo mismo
            if str(b_leader.get("bus_id")) == str(b_trailer.get("bus_id")):
                continue
            
            gap_km = round(b_leader["distance_traveled_km"] - b_trailer["distance_traveled_km"], 2)
            
            # Estimar minutos de separación (~25 km/h promedio en ciudad)
            est_minutes = round(gap_km * 2.4, 1)

            # 🛑 Obviar los pegonamientos en las terminales / cabeceras (espera o regulación programada)
            b_lead_in_term = is_inside_terminal_or_depot(b_leader.get("latitude"), b_leader.get("longitude"), terminal_stops)
            b_trail_in_term = is_inside_terminal_or_depot(b_trailer.get("latitude"), b_trailer.get("longitude"), terminal_stops)

            is_terminal_wait = (
                b_lead_in_term or b_trail_in_term or
                b_leader.get("state") in ("AT_ORIGIN", "AT_DESTINATION", "DEPOT", "GPS_FAULT") or
                b_trailer.get("state") in ("AT_ORIGIN", "AT_DESTINATION", "DEPOT", "GPS_FAULT") or
                b_leader.get("progress_percent", 0.0) <= 6.0 or b_leader.get("progress_percent", 0.0) >= 94.0 or
                b_trailer.get("progress_percent", 0.0) <= 6.0 or b_trailer.get("progress_percent", 0.0) >= 94.0 or
                b_leader.get("distance_traveled_km", 0.0) <= 2.2 or
                b_trailer.get("distance_traveled_km", 0.0) <= 2.2 or
                (total_km > 0 and (total_km - b_leader.get("distance_traveled_km", 0.0)) <= 1.0) or
                (total_km > 0 and (total_km - b_trailer.get("distance_traveled_km", 0.0)) <= 1.0)
            )

            # 🚏 Pegonamiento permitido en paradas (ascenso/descenso de pasajeros o espera operativa):
            # En las paradas los buses se juntan de forma natural y permitida.
            # Si ambos coches están detenidos (<= 5 km/h) o al menos uno está operando detenido en parada,
            # NO constituye pegonamiento en servicio.
            is_stop_dwell = (
                (b_leader.get("speed_kmh", 0.0) <= 5.0 or b_trailer.get("speed_kmh", 0.0) <= 5.0)
            )

            # Clasificación de Intervalo y Detección Real de Pegonamiento
            if is_terminal_wait:
                severity = "TERMINAL_WAIT"  # 🟡 En espera en cabecera / terminal (obviar pegonamiento)
            elif is_stop_dwell:
                severity = "STOP_DWELL"     # 🚏 En parada (permitido: coincidencia en parada de pasajeros)
                b_leader["is_at_stop"] = True
                b_trailer["is_at_stop"] = True
            elif gap_km < 0.35 and (b_leader.get("speed_kmh", 0.0) > 5.0 and b_trailer.get("speed_kmh", 0.0) > 5.0):
                # 🚨 Pegonamiento real en calle (< 350 metros y AMBOS en movimiento en la vía pública)
                severity = "CRITICAL"
                b_leader["is_bunching"] = True
                b_trailer["is_bunching"] = True
                b_leader["bunching_with"] = b_trailer["bus_id"]
                b_trailer["bunching_with"] = b_leader["bus_id"]
                b_leader["bunching_gap_m"] = int(gap_km * 1000)
                b_trailer["bunching_gap_m"] = int(gap_km * 1000)
                b_leader["bunching_gap_min"] = est_minutes
                b_trailer["bunching_gap_min"] = est_minutes
                r_data["bunching_count"] += 1
                total_bunching_alerts += 1
                r_data["status"] = "PEGONAMIENTO"
            elif gap_km <= 0.80:
                severity = "WARNING"  # ⚠️ Intervalo corto (350m - 800m) - Precaución preventiva pero no pegonamiento crítico
                if r_data["status"] != "PEGONAMIENTO":
                    r_data["status"] = "ADVERTENCIA"
            elif gap_km <= 5.5:
                severity = "OPTIMAL"  # 🟢 Intervalo regular
            else:
                severity = "GAP"      # ⏳ Hueco excesivo

            hw_entry = {
                "trailer_id": b_trailer["bus_id"],
                "leader_id": b_leader["bus_id"],
                "gap_km": gap_km,
                "gap_meters": int(gap_km * 1000),
                "est_minutes": est_minutes,
                "severity": severity,
                "left_pct": b_trailer["progress_percent"],
                "width_pct": max(1.0, round(b_leader["progress_percent"] - b_trailer["progress_percent"], 1))
            }
            r_data["headways"].append(hw_entry)

    # 5. Correlacionar con trafico e incidentes en tiempo real de Waze CCP
    try:
        from waze_service import fetch_waze_ccp_feed, correlate_waze_with_transit
        waze_feed = fetch_waze_ccp_feed()
        correlations = correlate_waze_with_transit(waze_feed, list(routes_dict.values()))
        for r_code, r_data in routes_dict.items():
            r_data["waze_impact"] = correlations.get(r_code, {})
    except Exception as e:
        logger.debug(f"Error correlacionando Waze en Headway: {e}")

    total_wrong_direction_alerts = 0
    for r_code, r_data in routes_dict.items():
        w_cnt = sum(1 for bus in r_data["buses"] if bus.get("wrong_direction_alert"))
        r_data["wrong_direction_count"] = w_cnt
        total_wrong_direction_alerts += w_cnt

    fin_summary = {}
    try:
        fin_summary = get_cached_financial_summary(redis_client, agency_id=agency_id or "0008")
    except Exception:
        pass

    return {
        "timestamp": datetime.now().isoformat(),
        "total_active_buses": total_active_buses,
        "total_bunching_alerts": total_bunching_alerts,
        "total_wrong_direction_alerts": total_wrong_direction_alerts,
        "financial_summary": fin_summary,
        "routes": list(routes_dict.values())
    }

def get_headway_html(user: Optional[Dict[str, Any]] = None) -> str:
    """Retorna la página HTML interactiva del Tablero Lineal con integración de sesión Odoo."""
    user_name = (user.get("name") or user.get("login") or "Operador") if user else "Operador"
    conc_name = (user.get("concessionaire_name") or "Consorcio Arapotí") if user else "Consorcio Arapotí"
    user_badge_html = f'''
            <div class="user-badge" style="display:inline-flex; align-items:center; gap:8px; background:rgba(30, 41, 59, 0.85); border:1px solid rgba(56, 189, 248, 0.3); padding:5px 12px; border-radius:9999px; font-size:11px;">
                <span style="color:#38bdf8;">👤</span>
                <span style="font-weight:700; color:#f8fafc;">{user_name}</span>
                <span style="color:#94a3b8; font-size:10px; background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px;">{conc_name}</span>
            </div>
            <a href="/logout" class="nav-btn" style="border-color:rgba(239, 68, 68, 0.4); color:#fca5a5;" title="Cerrar sesión de Odoo">
                <span>🚪 Salir</span>
            </a>
    '''
    html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poliverso Transit | Tablero Lineal de Intervalos & Pegonamiento</title>
    <link rel="icon" href="data:,">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #060b14;
            --bg-card: #0d1527;
            --bg-card-hover: #131d36;
            --border: #1e293b;
            --border-glow: rgba(56, 189, 248, 0.3);
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.4);
            --accent: #818cf8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.5);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        /* Top Header */
        header {
            background: rgba(13, 21, 39, 0.9);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            padding: 12px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .brand-group {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #0284c7, #6366f1);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);
        }

        .brand-title {
            font-size: 16px;
            font-weight: 800;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #f8fafc, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-subtitle {
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .nav-btn {
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .nav-btn:hover {
            background: #334155;
            color: #fff;
            border-color: var(--primary);
        }

        .sound-btn-active {
            background: rgba(16, 185, 129, 0.15);
            border-color: rgba(16, 185, 129, 0.4);
            color: #34d399;
        }

        .sound-btn-muted {
            background: rgba(239, 68, 68, 0.15);
            border-color: rgba(239, 68, 68, 0.4);
            color: #f87171;
        }

        .pulse-live {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 11px;
            font-weight: 700;
            color: #34d399;
            background: rgba(16, 185, 129, 0.15);
            padding: 5px 10px;
            border-radius: 20px;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 10px #10b981;
            animation: pulse-ring 1.5s infinite;
        }

        @keyframes pulse-ring {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        /* Pegonamiento Global Alert Banner */
        .bunching-banner {
            background: linear-gradient(90deg, #991b1b, #dc2626, #b91c1c);
            border-bottom: 1px solid #f87171;
            padding: 10px 28px;
            box-shadow: 0 4px 20px rgba(220, 38, 38, 0.4);
            animation: banner-glow 1.5s infinite alternate;
        }

        @keyframes banner-glow {
            0% { box-shadow: 0 4px 15px rgba(220, 38, 38, 0.3); }
            100% { box-shadow: 0 4px 28px rgba(239, 68, 68, 0.7); }
        }

        .bunching-banner-content {
            max-width: 1600px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }

        .bunching-banner-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .banner-icon {
            font-size: 24px;
            animation: bounce-alert 0.8s infinite alternate;
        }

        .banner-title {
            font-size: 14px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.01em;
        }

        .banner-subtitle {
            font-size: 12px;
            color: #fecaca;
            font-weight: 500;
        }

        .banner-btn {
            background: #ffffff;
            color: #991b1b;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 800;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.2s ease;
        }

        .banner-btn:hover {
            background: #fef2f2;
            transform: scale(1.04);
        }

        /* KPI Top Strip */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            padding: 20px 28px 10px 28px;
            max-width: 1600px;
            margin: 0 auto;
            width: 100%;
        }

        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            position: relative;
            overflow: hidden;
        }

        .kpi-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
        }

        .kpi-bunching::before { background: var(--danger); box-shadow: 0 0 12px var(--danger); }
        .kpi-buses::before { background: var(--primary); }
        .kpi-routes::before { background: var(--accent); }
        .kpi-sync::before { background: var(--success); }

        .kpi-bunching.has-alerts {
            border-color: rgba(239, 68, 68, 0.6);
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.12), #0d1527);
            animation: kpi-alert-pulse 1.2s infinite alternate;
        }

        @keyframes kpi-alert-pulse {
            0% { box-shadow: 0 0 8px rgba(239, 68, 68, 0.2); }
            100% { box-shadow: 0 0 22px rgba(239, 68, 68, 0.6); }
        }

        .kpi-info h4 {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }

        .kpi-value {
            font-size: 26px;
            font-weight: 900;
            letter-spacing: -0.02em;
            display: flex;
            align-items: baseline;
            gap: 6px;
        }

        .kpi-icon {
            font-size: 28px;
            opacity: 0.85;
        }

        /* Main Workspace */
        main {
            flex: 1;
            padding: 14px 28px 40px 28px;
            max-width: 1600px;
            margin: 0 auto;
            width: 100%;
        }

        /* Filter Pills */
        .filter-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
            overflow-x: auto;
            padding-bottom: 6px;
        }

        .filter-pill {
            background: #111a2e;
            border: 1px solid #1e293b;
            color: #94a3b8;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .filter-pill:hover, .filter-pill.active {
            background: #0284c7;
            color: #fff;
            border-color: #38bdf8;
            box-shadow: 0 2px 10px rgba(56, 189, 248, 0.25);
        }

        .filter-pill.bunching-filter.active {
            background: #dc2626;
            border-color: #f87171;
            box-shadow: 0 2px 10px rgba(239, 68, 68, 0.4);
        }

        .filter-pill.wrong-dir-filter {
            border-color: rgba(245, 158, 11, 0.4);
            color: #fbbf24;
        }

        .filter-pill.wrong-dir-filter.active {
            background: #d97706;
            border-color: #fbbf24;
            color: #fff;
            box-shadow: 0 2px 10px rgba(245, 158, 11, 0.4);
        }

        .filter-pill.line-pill {
            background: #1e293b;
            border-color: #3b82f6;
            color: #93c5fd;
        }

        .filter-pill.line-pill.active {
            background: #2563eb;
            color: #ffffff;
            border-color: #60a5fa;
            box-shadow: 0 2px 12px rgba(37, 99, 235, 0.4);
        }

        .line-section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: linear-gradient(90deg, #1e293b, #0f172a);
            border-left: 4px solid #3b82f6;
            border-radius: 8px;
            padding: 10px 16px;
            margin: 24px 0 14px 0;
            font-size: 14px;
            font-weight: 800;
            color: #f1f5f9;
            letter-spacing: 0.05em;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        .line-section-header .line-badge-count {
            font-size: 11px;
            background: #3b82f6;
            color: #ffffff;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 700;
        }

        .route-line-badge {
            background: rgba(59, 130, 246, 0.2);
            color: #93c5fd;
            border: 1px solid rgba(59, 130, 246, 0.4);
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        }

        /* Track Container Cards */
        .route-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px 24px;
            margin-bottom: 22px;
            transition: all 0.25s ease;
            position: relative;
        }

        .route-card:hover {
            border-color: var(--border-glow);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
        }

        .route-card.bunching-card {
            border-color: rgba(239, 68, 68, 0.5);
            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.15);
        }

        .route-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 22px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .route-id-badge {
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
            font-weight: 900;
            font-size: 14px;
            padding: 6px 14px;
            border-radius: 8px;
            letter-spacing: 0.05em;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);
        }

        .route-meta {
            display: flex;
            align-items: center;
            gap: 14px;
            flex-wrap: wrap;
        }

        .route-name {
            font-size: 15px;
            font-weight: 700;
            color: #e2e8f0;
        }

        .route-length {
            font-size: 12px;
            color: var(--text-muted);
            background: #111a2e;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #1e293b;
        }

        .route-status-pill {
            font-size: 11px;
            font-weight: 800;
            padding: 4px 12px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            text-transform: uppercase;
        }

        .pill-bunching {
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.4);
            animation: bunching-flash 1s infinite alternate;
        }

        @keyframes bunching-flash {
            0% { box-shadow: 0 0 4px rgba(239, 68, 68, 0.4); }
            100% { box-shadow: 0 0 16px rgba(239, 68, 68, 0.8); }
        }

        .pill-optimal {
            background: rgba(16, 185, 129, 0.15);
            color: #6ee7b7;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .pill-warning {
            background: rgba(245, 158, 11, 0.15);
            color: #fcd34d;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .pill-empty {
            background: rgba(148, 163, 184, 0.1);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.2);
        }

        /* The Horizontal Track */
        .track-wrapper {
            position: relative;
            padding: 34px 20px 24px 20px;
            margin: 10px 0 20px 0;
            background: #090e1a;
            border-radius: 12px;
            border: 1px solid #162032;
        }

        .terminal-labels {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #64748b;
            font-weight: 700;
            margin-bottom: 58px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .terminal-labels span {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .rail-track {
            position: relative;
            height: 10px;
            background: #1e293b;
            border-radius: 5px;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
        }

        .rail-track-progress {
            position: absolute;
            top: 0; left: 0; height: 100%;
            background: linear-gradient(90deg, #0284c7, #38bdf8);
            border-radius: 5px;
            opacity: 0.7;
        }

        /* Kilometer Ticks */
        .tick-marks {
            position: relative;
            height: 16px;
            margin-top: 6px;
        }

        .tick {
            position: absolute;
            font-size: 9px;
            color: #475569;
            transform: translateX(-50%);
            font-weight: 600;
        }

        .tick::before {
            content: '';
            position: absolute;
            top: -10px;
            left: 50%;
            width: 1px;
            height: 5px;
            background: #334155;
        }

        /* Bus Marker on Track */
        .bus-marker {
            position: absolute;
            bottom: 10px;
            transform: translateX(-50%);
            display: flex;
            flex-direction: column;
            align-items: center;
            cursor: pointer;
            z-index: 25;
            transition: left 15s linear, transform 0.2s ease;
        }

        .bus-marker:hover {
            transform: translateX(-50%) translateY(-3px) scale(1.08);
            z-index: 50;
        }

        .bus-marker-bubble {
            background: #0284c7;
            color: white;
            padding: 4px 8px 3px 8px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.45);
            border: 2px solid #38bdf8;
            white-space: nowrap;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            gap: 1px;
            min-width: 62px;
        }

        .bus-bubble-id {
            font-size: 11px;
            font-weight: 800;
            line-height: 1.15;
            letter-spacing: -0.01em;
            color: #ffffff;
        }

        .bus-bubble-time {
            font-size: 9.5px;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.9);
            line-height: 1.1;
        }

        .bus-bubble-icon {
            font-size: 14px;
            line-height: 1.1;
            margin-top: 1px;
        }

        .bus-marker:hover .bus-marker-bubble {
            border-color: #ffffff;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.8);
        }

        .bus-marker.bunching .bus-marker-bubble {
            background: #dc2626;
            border-color: #f87171;
            box-shadow: 0 0 16px rgba(239, 68, 68, 0.8);
            animation: bounce-alert 0.8s infinite alternate;
        }

        .bus-marker.wrong-dir .bus-marker-bubble {
            background: linear-gradient(135deg, #d97706, #b45309) !important;
            border-color: #fbbf24 !important;
            box-shadow: 0 0 16px rgba(245, 158, 11, 0.8) !important;
            animation: bounce-alert 0.8s infinite alternate;
        }

        @keyframes bounce-alert {
            0% { transform: translateY(0); }
            100% { transform: translateY(-4px); }
        }

        .bus-marker-pointer {
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #0284c7;
            margin-top: -1px;
        }

        .bus-marker.bunching .bus-marker-pointer {
            border-top-color: #dc2626;
        }

        .bus-marker.wrong-dir .bus-marker-pointer {
            border-top-color: #d97706 !important;
        }

        .kpi-card.kpi-wrong-dir.has-alerts {
            border-color: #f59e0b;
            box-shadow: 0 0 15px rgba(245, 158, 11, 0.35);
        }

        /* Headway Connector Bar */
        .headway-segment {
            position: absolute;
            top: -12px;
            height: 4px;
            background: rgba(56, 189, 248, 0.4);
            border-radius: 2px;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10;
            transition: left 15s linear, width 15s linear;
        }

        .headway-segment.critical {
            background: rgba(239, 68, 68, 0.7);
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.6);
            height: 6px;
            top: -13px;
        }

        .headway-segment.terminal {
            background: rgba(245, 158, 11, 0.35);
            height: 4px;
            top: -12px;
        }

        .headway-segment.stop_dwell {
            background: rgba(56, 189, 248, 0.45);
            height: 4px;
            top: -12px;
        }

        .headway-badge {
            background: #0f172a;
            border: 1px solid #334155;
            padding: 2px 7px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 700;
            color: #94a3b8;
            white-space: nowrap;
            position: absolute;
            top: -20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
        }

        .headway-badge.terminal {
            background: rgba(120, 53, 15, 0.85);
            border-color: #f59e0b;
            color: #fef3c7;
        }

        .headway-badge.stop_dwell {
            background: rgba(15, 23, 42, 0.95);
            border-color: #38bdf8;
            color: #7dd3fc;
            font-weight: 700;
        }

        .headway-badge.critical {
            background: #7f1d1d;
            border-color: #ef4444;
            color: #fef2f2;
            font-weight: 900;
            animation: pulse-ring 1s infinite;
        }

        /* Bus Details Mini Table */
        .bus-table-box {
            margin-top: 14px;
            overflow-x: auto;
        }

        .bus-mini-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }

        .bus-mini-table th {
            text-align: left;
            color: #64748b;
            font-weight: 600;
            padding: 6px 10px;
            border-bottom: 1px solid #1e293b;
        }

        .bus-mini-table td {
            padding: 9px 10px;
            border-bottom: 1px solid #162032;
            color: #cbd5e1;
            transition: background 0.15s ease;
        }

        .bus-mini-table tr.clickable-row {
            cursor: pointer;
        }

        .bus-mini-table tr.clickable-row:hover td {
            background: rgba(56, 189, 248, 0.08);
            color: #ffffff;
        }

        .bus-mini-table tr.clickable-row.bunching-row:hover td {
            background: rgba(239, 68, 68, 0.12);
        }

        .empty-state {
            text-align: center;
            padding: 30px;
            color: #64748b;
            font-size: 13px;
        }

        /* Bus Inspection Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(4, 8, 16, 0.75);
            backdrop-filter: blur(8px);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            animation: fadeIn 0.2s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .modal-card {
            background: #0d1527;
            border: 1px solid #1e293b;
            border-radius: 18px;
            width: 100%;
            max-width: 580px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(56, 189, 248, 0.15);
            overflow: hidden;
            animation: scaleUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes scaleUp {
            from { transform: scale(0.93) translateY(10px); opacity: 0; }
            to { transform: scale(1) translateY(0); opacity: 1; }
        }

        .modal-header {
            background: #111a2e;
            padding: 16px 22px;
            border-bottom: 1px solid #1e293b;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .modal-title-box {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .modal-bus-icon {
            font-size: 26px;
            background: #0284c7;
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4);
        }

        .modal-header h3 {
            font-size: 17px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.01em;
        }

        .modal-plate-tag {
            font-size: 11px;
            color: #94a3b8;
            font-weight: 600;
        }

        .modal-close-btn {
            background: transparent;
            border: none;
            color: #64748b;
            font-size: 20px;
            cursor: pointer;
            padding: 6px;
            border-radius: 8px;
            line-height: 1;
            transition: all 0.2s ease;
        }

        .modal-close-btn:hover {
            color: #f8fafc;
            background: #1e293b;
        }

        .modal-bunching-alert {
            background: linear-gradient(90deg, rgba(239, 68, 68, 0.2), rgba(185, 28, 28, 0.25));
            border-bottom: 1px solid rgba(239, 68, 68, 0.4);
            padding: 12px 22px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: #fca5a5;
        }

        .modal-alert-icon {
            font-size: 22px;
            animation: bounce-alert 0.8s infinite alternate;
        }

        .modal-bunching-alert strong {
            color: #ffffff;
            font-size: 13px;
            display: block;
            margin-bottom: 2px;
        }

        .modal-bunching-alert span {
            font-size: 12px;
            color: #fecaca;
        }

        .modal-body-grid {
            padding: 20px 22px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            max-height: 55vh;
            overflow-y: auto;
        }

        .modal-metric {
            background: #090e1a;
            border: 1px solid #162032;
            padding: 10px 14px;
            border-radius: 10px;
        }

        .modal-col-2 {
            grid-column: span 2;
        }

        .modal-metric .lbl {
            font-size: 10px;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: block;
            margin-bottom: 3px;
        }

        .modal-metric .val {
            font-size: 13px;
            font-weight: 700;
            color: #e2e8f0;
        }

        .modal-metric .val.highlight {
            color: var(--primary);
            font-size: 15px;
        }

        .modal-footer {
            background: #111a2e;
            padding: 14px 22px;
            border-top: 1px solid #1e293b;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 12px;
        }

        .btn-locate-map {
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #ffffff;
            border: none;
            padding: 9px 18px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
            transition: all 0.2s ease;
        }

        .btn-locate-map:hover {
            background: linear-gradient(135deg, #0369a1, #1d4ed8);
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(37, 99, 235, 0.6);
        }

        .btn-modal-close {
            background: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            padding: 9px 16px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .btn-modal-close:hover {
            color: #ffffff;
            background: #334155;
        }
    </style>
</head>
<body>

    <!-- Header -->
    <header>
        <div class="brand-group">
            <div class="brand-icon">🚌</div>
            <div>
                <div class="brand-title">Poliverso Transit | Control de Frecuencias & Headway</div>
                <div class="brand-subtitle">Monitoreo Lineal de Regularidad y Detección de Pegonamiento (Bunching)</div>
            </div>
        </div>

        <div class="header-actions">
            <div class="pulse-live">
                <div class="pulse-dot"></div>
                <span>EN VIVO (TELEMETRÍA GPS)</span>
            </div>

            <!-- Botón de Control de Alarma Sonora -->
            <button id="btn-sound-toggle" class="nav-btn sound-btn-active" onclick="toggleSoundAlert()" title="Activar/Silenciar Alerta Sonora de Pegonamiento">
                <span id="sound-icon">🔊</span>
                <span id="sound-text">Alarma: ACTIVA</span>
            </button>

            <a href="/map" class="nav-btn">
                <span>🗺️ Radar Satelital</span>
            </a>
            <a id="odoo-erp-nav-btn" href="/web" target="_blank" class="nav-btn">
                <span>⚡ Odoo ERP</span>
            </a>
            <a href="/web#action=transit_operations.action_transit_requirement" target="_blank" class="nav-btn" style="background: rgba(16, 185, 129, 0.2); border-color: #10b981; color: #34d399;" title="Enviar requerimiento o sugerencia de ajuste técnico">
                <span>🛠️ Solicitar Ajuste / Soporte</span>
            </a>
            {user_badge_html}
        </div>
    </header>

    <!-- Banner Global de Alerta de Pegonamiento -->
    <div id="global-bunching-banner" class="bunching-banner" style="display: none;">
        <div class="bunching-banner-content">
            <div class="bunching-banner-left">
                <span class="banner-icon">🚨</span>
                <div>
                    <div class="banner-title">¡ALERTA CRÍTICA: PEGONAMIENTO DE UNIDADES DETECTADO!</div>
                    <div class="banner-subtitle" id="banner-msg">Se registran unidades circulando con separación menor a 800m. Riesgo inminente de canibalización de frecuencias.</div>
                </div>
            </div>
            <button class="banner-btn" onclick="filterByBunchingOnly()">Filtrar Afectados</button>
        </div>
    </div>

    <!-- Top KPI Cards -->
    <section class="kpi-container">
        <div class="kpi-card kpi-bunching" id="kpi-bunching-card">
            <div class="kpi-info">
                <h4>Alertas de Pegonamiento</h4>
                <div class="kpi-value" id="kpi-bunching" style="color: var(--danger);">0</div>
            </div>
            <div class="kpi-icon">🚨</div>
        </div>

        <div class="kpi-card kpi-wrong-dir" id="kpi-wrong-dir-card" style="border-left: 3px solid #f59e0b;">
            <div class="kpi-info">
                <h4>IDRuta en Contrasentido</h4>
                <div class="kpi-value" id="kpi-wrong-dir" style="color: #f59e0b;">0</div>
            </div>
            <div class="kpi-icon">⚠️</div>
        </div>

        <div class="kpi-card kpi-buses">
            <div class="kpi-info">
                <h4>Buses en Operación</h4>
                <div class="kpi-value" id="kpi-buses" style="color: var(--primary);">0</div>
            </div>
            <div class="kpi-icon">🚍</div>
        </div>

        <div class="kpi-card kpi-routes">
            <div class="kpi-info">
                <h4>Ramales Monitoreados</h4>
                <div class="kpi-value" id="kpi-routes" style="color: var(--accent);">6</div>
            </div>
            <div class="kpi-icon">🛣️</div>
        </div>

        <div class="kpi-card kpi-sync">
            <div class="kpi-info">
                <h4>Última Actualización</h4>
                <div class="kpi-value" id="kpi-time" style="font-size: 18px; color: var(--success);">--:--:--</div>
            </div>
            <div class="kpi-icon">⏱️</div>
        </div>

        <div class="kpi-card" style="border-left: 3px solid #10b981;">
            <div class="kpi-info">
                <h4>Validaciones Jaha Hoy</h4>
                <div class="kpi-value" id="kpi-billetaje-pax" style="color: #34d399;">--</div>
                <div style="font-size: 11px; color: #94a3b8; font-weight: 500;" id="kpi-billetaje-monto">Recaudación: Gs. --</div>
            </div>
            <div class="kpi-icon">💳</div>
        </div>
    </section>

    <!-- Main Content -->
    <main>
        <!-- Filter Tabs -->
        <div class="filter-bar" id="route-filter-bar">
            <div class="filter-pill active" onclick="filterRoute('all')">Todos los Ramales</div>
            <div class="filter-pill bunching-filter" id="pill-filter-bunching" onclick="filterRoute('bunching')">🚨 Con Pegonamiento</div>
        </div>

        <!-- Dynamic Tracks Container -->
        <div id="tracks-container">
            <div class="empty-state">Cargando telemetría geoespacial y trazados lineales...</div>
        </div>
    </main>

    <!-- Bus Detail & Telemetry Inspection Modal -->
    <div id="bus-modal" class="modal-overlay" style="display: none;" onclick="closeModalOnBackdrop(event)">
        <div class="modal-card">
            <div class="modal-header">
                <div class="modal-title-box">
                    <span class="modal-bus-icon">🚌</span>
                    <div>
                        <h3 id="modal-bus-id">Coche #00000</h3>
                        <span id="modal-bus-plate" class="modal-plate-tag">COCHE-00000</span>
                    </div>
                </div>
                <button class="modal-close-btn" onclick="closeBusModal()">✕</button>
            </div>

            <!-- Alerta Crítica en Modal si tiene pegonamiento -->
            <div id="modal-bunching-box" class="modal-bunching-alert" style="display: none;">
                <span class="modal-alert-icon">🚨</span>
                <div>
                    <strong>PEGONAMIENTO CRÍTICO ACTIVO</strong>
                    <span id="modal-bunching-desc">Circulando a menos de 800m de la unidad líder.</span>
                </div>
            </div>

            <!-- Alerta de IDRuta Invertido / Contrasentido en Modal -->
            <div id="modal-wrong-dir-box" class="modal-bunching-alert" style="display: none; background: rgba(245, 158, 11, 0.18); border-color: #f59e0b; color: #fbbf24;">
                <span class="modal-alert-icon">⚠️</span>
                <div>
                    <strong style="color: #f59e0b;">ALERTA: IDRUTA EN CONTRASENTIDO</strong>
                    <div id="modal-wrong-dir-desc" style="font-size: 11px; color: #cbd5e1; margin-top: 2px;">El bus se desplaza en sentido contrario a la ruta configurada.</div>
                </div>
            </div>

            <!-- Grilla de Telemetría -->
            <div class="modal-body-grid">
                <div class="modal-metric">
                    <span class="lbl">Estado Operativo</span>
                    <span class="val" id="modal-state">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Velocidad Actual</span>
                    <span class="val highlight" id="modal-speed">0 km/h</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Ramal Asignado</span>
                    <span class="val" id="modal-route">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Sentido / Trayecto</span>
                    <span class="val" id="modal-direction">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Progreso en Traza</span>
                    <span class="val" id="modal-progress">0%</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Km en Recorrido</span>
                    <span class="val" id="modal-dist">0.0 km</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Desvío de Eje Oficial</span>
                    <span class="val" id="modal-deviation">0 m</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Conductor Asignado</span>
                    <span class="val" id="modal-driver">--</span>
                </div>
                <div class="modal-metric modal-col-2">
                    <span class="lbl">Ubicación / Calle Aproximada</span>
                    <span class="val" id="modal-location">--</span>
                </div>
                <div class="modal-metric modal-col-2">
                    <span class="lbl">Próxima Parada / Hito</span>
                    <span class="val" id="modal-approaching">--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Último Ping GPS</span>
                    <span class="val" id="modal-ping">--:--:--</span>
                </div>
                <div class="modal-metric">
                    <span class="lbl">Odómetro Total</span>
                    <span class="val" id="modal-odometer">0.0 km</span>
                </div>
                <!-- Sección Waze CCP en Modal -->
                <div id="modal-waze-card" class="modal-metric modal-col-2" style="background: rgba(2, 132, 199, 0.08); border: 1px solid rgba(56, 189, 248, 0.25);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px;">
                        <span class="lbl" style="color: #38bdf8;">🚦 Waze for Cities (CCP) · Tráfico en Corredor</span>
                        <a id="modal-waze-nav-btn" href="#" target="_blank" style="background: #0284c7; color: white; padding: 2px 8px; border-radius: 4px; font-size: 10px; text-decoration: none; font-weight: 700; display: inline-flex; align-items: center; gap: 3px;">
                            <span>🚗 Abrir en Waze</span>
                        </a>
                    </div>
                    <span class="val" id="modal-waze-info" style="font-size: 12px; font-weight: 500; color: #cbd5e1;">Evaluando condiciones de tráfico satelital...</span>
                </div>
                <!-- Sección Billetaje Electrónico Jaha en Modal -->
                <div id="modal-billetaje-card" class="modal-metric modal-col-2" style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px;">
                        <span class="lbl" style="color: #34d399;">💳 Billetaje Electrónico Jaha (Validador en Vivo)</span>
                        <span id="modal-billetaje-srv-badge" style="background: #059669; color: white; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;">CONVENCIONAL</span>
                    </div>
                    <span class="val" id="modal-billetaje-info" style="font-size: 12px; font-weight: 600; color: #f8fafc;">Consultando validaciones del coche...</span>
                </div>
            </div>

            <!-- Selector de Reasignación Rápida de Ramal (1 Clic) -->
            <div id="modal-reassign-container" style="margin-top: 14px; padding: 12px 14px; background: rgba(30, 41, 59, 0.75); border: 1px solid #334155; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 5px;">
                        <span>🔄</span> Reasignar / Corregir Ramal Activo
                    </span>
                    <span id="modal-reassign-badge" style="font-size: 10px; color: #94a3b8; background: #0f172a; padding: 2px 8px; border-radius: 4px; border: 1px solid #334155;">
                        Control Operativo
                    </span>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <select id="modal-reassign-select" style="flex: 1; background: #0f172a; color: #f8fafc; border: 1px solid #475569; padding: 7px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; outline: none; cursor: pointer;">
                        <option value="">Cargando ramales de la empresa...</option>
                    </select>
                    <button id="modal-reassign-btn" onclick="executeRouteReassign()" style="background: #2563eb; color: white; border: none; padding: 7px 16px; border-radius: 6px; font-weight: 700; font-size: 12px; cursor: pointer; transition: all 0.2s; white-space: nowrap;">
                        Aplicar Cambio
                    </button>
                </div>
                <div id="modal-reassign-status" style="font-size: 11px; margin-top: 6px; font-weight: 600; display: none;"></div>
            </div>

            <!-- Modal Footer con Acción Directa a GPS -->
            <div class="modal-footer">
                <button class="btn-locate-map" onclick="locateSelectedBusOnMap()">
                    <span>🗺️ Ubicar en Radar GPS</span>
                </button>
                <button class="btn-modal-close" onclick="closeBusModal()">Cerrar</button>
            </div>
        </div>
    </div>

    <script>
        let currentFilter = 'all';
        let latestDashboardData = null;
        const busRegistry = {};
        let selectedBusId = null;

        // --- SISTEMA DE ALERTA SONORA (Web Audio API Synthesizer) ---
        let audioCtx = null;
        let soundEnabled = localStorage.getItem('headway_sound_enabled') !== 'false';
        let lastAlertSoundTime = 0;
        const ALERT_SOUND_COOLDOWN_MS = 14000; // Repetir cada 14s si persiste el pegonamiento

        function initAudioContext() {
            if (!audioCtx) {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (AudioContextClass) {
                    audioCtx = new AudioContextClass();
                }
            }
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            return audioCtx;
        }

        // Desbloquear audio automáticamente al hacer clic en cualquier lugar
        document.addEventListener('click', () => {
            initAudioContext();
        }, { once: false });

        function updateSoundButtonUI() {
            const btn = document.getElementById('btn-sound-toggle');
            const icon = document.getElementById('sound-icon');
            const txt = document.getElementById('sound-text');
            if (soundEnabled) {
                btn.className = 'nav-btn sound-btn-active';
                icon.textContent = '🔊';
                txt.textContent = 'Alarma: ACTIVA';
            } else {
                btn.className = 'nav-btn sound-btn-muted';
                icon.textContent = '🔇';
                txt.textContent = 'Alarma: SILENCIADA';
            }
        }

        function toggleSoundAlert() {
            initAudioContext();
            soundEnabled = !soundEnabled;
            localStorage.setItem('headway_sound_enabled', soundEnabled ? 'true' : 'false');
            updateSoundButtonUI();
            if (soundEnabled) {
                playBunchingTone(true); // Test chime
            }
        }

        function playBunchingTone(forceTest = false) {
            if (!soundEnabled && !forceTest) return;
            const ctx = initAudioContext();
            if (!ctx) return;

            try {
                const now = ctx.currentTime;

                // Tono 1: Chime de alerta bitonal agudo (880Hz -> 659Hz -> 880Hz)
                const osc1 = ctx.createOscillator();
                const gain1 = ctx.createGain();
                osc1.type = 'sine';
                osc1.frequency.setValueAtTime(880, now);
                osc1.frequency.setValueAtTime(659, now + 0.16);
                osc1.frequency.setValueAtTime(880, now + 0.32);

                gain1.gain.setValueAtTime(0.0, now);
                gain1.gain.linearRampToValueAtTime(0.28, now + 0.04);
                gain1.gain.setValueAtTime(0.28, now + 0.42);
                gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.85);

                osc1.connect(gain1);
                gain1.connect(ctx.destination);
                osc1.start(now);
                osc1.stop(now + 0.86);

                // Tono 2: Armónico de resonancia (440Hz -> 330Hz -> 440Hz)
                const osc2 = ctx.createOscillator();
                const gain2 = ctx.createGain();
                osc2.type = 'triangle';
                osc2.frequency.setValueAtTime(440, now);
                osc2.frequency.setValueAtTime(330, now + 0.16);
                osc2.frequency.setValueAtTime(440, now + 0.32);

                gain2.gain.setValueAtTime(0.0, now);
                gain2.gain.linearRampToValueAtTime(0.14, now + 0.04);
                gain2.gain.setValueAtTime(0.14, now + 0.42);
                gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.85);

                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.start(now);
                osc2.stop(now + 0.86);
            } catch (err) {
                console.warn("AudioContext error:", err);
            }
        }

        // Inicializar botón de sonido
        updateSoundButtonUI();

        // --- FILTROS DE VISTA ---
        function filterRoute(code) {
            currentFilter = code;
            document.querySelectorAll('.filter-pill').forEach(el => {
                const targetFilter = el.getAttribute('data-filter');
                if (targetFilter) {
                    el.classList.toggle('active', targetFilter === code);
                } else {
                    const txt = el.textContent.toLowerCase();
                    if (code === 'all' && txt.includes('todos')) {
                        el.classList.add('active');
                    } else if (code === 'bunching' && txt.includes('pegonamiento')) {
                        el.classList.add('active');
                    } else if (code === 'wrong_dir' && txt.includes('contrasentido')) {
                        el.classList.add('active');
                    } else if (code !== 'all' && code !== 'bunching' && code !== 'wrong_dir' && txt.includes(code)) {
                        el.classList.add('active');
                    } else {
                        el.classList.remove('active');
                    }
                }
            });
            if (latestDashboardData) {
                renderDashboard(latestDashboardData);
            }
        }

        function filterByBunchingOnly() {
            filterRoute('bunching');
        }

        function filterByWrongDirOnly() {
            filterRoute('wrong_dir');
        }

        // --- FETCH Y RENDERIZADO DEL DASHBOARD ---
        async function fetchHeadwayData() {
            try {
                const res = await fetch('/api/v1/headway/data');
                if (res.status === 401) {
                    window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
                    return;
                }
                const data = await res.json();
                latestDashboardData = data;
                renderDashboard(data);
            } catch (err) {
                console.error("Error al actualizar headway:", err);
            }
        }

        function renderDashboard(data) {
            const bunchingCount = data.total_bunching_alerts || 0;
            const wrongDirCount = data.total_wrong_direction_alerts || 0;
            document.getElementById('kpi-bunching').textContent = bunchingCount;
            document.getElementById('kpi-buses').textContent = data.total_active_buses || 0;
            
            const kpiWrongDirEl = document.getElementById('kpi-wrong-dir');
            if (kpiWrongDirEl) {
                kpiWrongDirEl.textContent = wrongDirCount;
            }
            const kpiWrongDirCard = document.getElementById('kpi-wrong-dir-card');
            if (kpiWrongDirCard) {
                if (wrongDirCount > 0) {
                    kpiWrongDirCard.classList.add('has-alerts');
                } else {
                    kpiWrongDirCard.classList.remove('has-alerts');
                }
            }

            const kpiRoutesEl = document.getElementById('kpi-routes');
            if (kpiRoutesEl) {
                kpiRoutesEl.textContent = (data.routes || []).length;
            }
            const now = new Date();
            document.getElementById('kpi-time').textContent = now.toLocaleTimeString();

            // KPI Billetaje Jaha
            const fin = data.financial_summary || {};
            const kpiPax = document.getElementById('kpi-billetaje-pax');
            const kpiMonto = document.getElementById('kpi-billetaje-monto');
            if (kpiPax && fin.cantidad !== undefined) {
                kpiPax.textContent = Number(fin.cantidad).toLocaleString('es-PY');
            }
            if (kpiMonto && fin.brutoTotal !== undefined) {
                kpiMonto.textContent = `Recaudación: Gs. ${Number(fin.brutoTotal).toLocaleString('es-PY')}`;
            }

            // Renderizar dinámicamente los botones de filtro de ramal agrupados por línea comercial
            const filterBar = document.getElementById('route-filter-bar');
            if (filterBar && Array.isArray(data.routes)) {
                // Obtener líneas comerciales únicas
                const uniqueLines = [];
                data.routes.forEach(r => {
                    const ln = r.line_name || 'Línea Regular';
                    if (!uniqueLines.includes(ln)) uniqueLines.push(ln);
                });

                let linePillsHtml = '';
                if (uniqueLines.length > 1 || (uniqueLines.length === 1 && uniqueLines[0] !== 'Línea Regular')) {
                    linePillsHtml = uniqueLines.map(ln => {
                        const countInLine = data.routes
                            .filter(r => (r.line_name || 'Línea Regular') === ln)
                            .reduce((acc, r) => acc + (r.buses ? r.buses.length : 0), 0);
                        const isLineActive = (currentFilter === `LINE:${ln}`);
                        return `<div class="filter-pill line-pill ${isLineActive ? 'active' : ''}" data-filter="LINE:${ln}" onclick="filterRoute('LINE:${ln}')">🚍 ${ln} (${countInLine})</div>`;
                    }).join('');
                }

                const wrongDirPillHtml = wrongDirCount > 0 
                    ? `<div class="filter-pill wrong-dir-filter ${currentFilter === 'wrong_dir' ? 'active' : ''}" data-filter="wrong_dir" onclick="filterRoute('wrong_dir')">⚠️ Contrasentido (${wrongDirCount})</div>`
                    : '';

                const routePillsHtml = data.routes.map(r => {
                    const rCode = String(r.route_id || '').toLowerCase();
                    const isActive = (currentFilter === rCode) ? 'active' : '';
                    const busCountBadge = (r.buses && r.buses.length > 0) ? ` (${r.buses.length})` : '';
                    const linePrefix = r.line_name ? `${r.line_name.replace('Línea ', 'L')} - ` : '';
                    return `<div class="filter-pill ${isActive}" data-filter="${rCode}" onclick="filterRoute('${rCode}')">${linePrefix}${rCode.toUpperCase()}${busCountBadge}</div>`;
                }).join('');

                filterBar.innerHTML = `
                    <div class="filter-pill ${currentFilter === 'all' ? 'active' : ''}" data-filter="all" onclick="filterRoute('all')">Todos los Ramales</div>
                    <div class="filter-pill bunching-filter ${currentFilter === 'bunching' ? 'active' : ''}" data-filter="bunching" id="pill-filter-bunching" onclick="filterRoute('bunching')">🚨 Pegonamiento (${bunchingCount})</div>
                    ${wrongDirPillHtml}
                    ${linePillsHtml}
                    ${routePillsHtml}
                `;
            }

            // Gestionar Alerta Sonora y Banner Global
            const bunchingBanner = document.getElementById('global-bunching-banner');
            const kpiCard = document.getElementById('kpi-bunching-card');

            if (bunchingCount > 0) {
                bunchingBanner.style.display = 'block';
                document.getElementById('banner-msg').textContent = `Se detectaron ${bunchingCount} evento(s) de pegonamiento activo entre unidades a menos de 800m.`;
                kpiCard.classList.add('has-alerts');

                // Emitir sonido si ha pasado el cooldown
                const currentTime = Date.now();
                if (currentTime - lastAlertSoundTime > ALERT_SOUND_COOLDOWN_MS) {
                    lastAlertSoundTime = currentTime;
                    playBunchingTone();
                }
            } else {
                bunchingBanner.style.display = 'none';
                kpiCard.classList.remove('has-alerts');
            }

            const container = document.getElementById('tracks-container');
            let filteredRoutes = data.routes || [];

            if (currentFilter === 'bunching') {
                filteredRoutes = filteredRoutes.filter(r => r.bunching_count > 0 || r.status === 'PEGONAMIENTO');
            } else if (currentFilter === 'wrong_dir') {
                filteredRoutes = filteredRoutes.filter(r => (r.wrong_direction_count || 0) > 0 || (r.buses || []).some(b => b.wrong_direction_alert));
            } else if (currentFilter.startsWith('LINE:')) {
                const targetLine = currentFilter.substring(5);
                filteredRoutes = filteredRoutes.filter(r => (r.line_name || 'Línea Regular') === targetLine);
            } else if (currentFilter !== 'all') {
                filteredRoutes = filteredRoutes.filter(r => String(r.route_id || '').toLowerCase() === currentFilter.toLowerCase());
            }

            if (filteredRoutes.length === 0) {
                container.innerHTML = '<div class="empty-state">No hay datos para el filtro seleccionado.</div>';
                return;
            }

            // Registrar buses en memoria global para modal
            (data.routes || []).forEach(r => {
                (r.buses || []).forEach(b => {
                    busRegistry[b.bus_id] = b;
                });
            });

            // Mantener el modal sincronizado en tiempo real si está abierto
            if (selectedBusId && busRegistry[selectedBusId]) {
                updateModalContent(busRegistry[selectedBusId]);
            }

            // Agrupar ramales filtrados por Línea Comercial (Línea 15 vs Línea 47, etc.)
            const routesByLine = {};
            filteredRoutes.forEach(r => {
                const ln = r.line_name || 'Línea Regular';
                if (!routesByLine[ln]) routesByLine[ln] = [];
                routesByLine[ln].push(r);
            });

            let html = '';
            const lineNames = Object.keys(routesByLine);
            const showLineHeaders = lineNames.length > 1 || (lineNames.length === 1 && lineNames[0] !== 'Línea Regular');

            lineNames.forEach(lineName => {
                const lineRoutes = routesByLine[lineName];
                const totalBusesInLine = lineRoutes.reduce((acc, r) => acc + (r.buses ? r.buses.length : 0), 0);
                const totalWrongDirInLine = lineRoutes.reduce((acc, r) => acc + (r.wrong_direction_count || 0), 0);
                const totalBunchingInLine = lineRoutes.reduce((acc, r) => acc + (r.bunching_count || 0), 0);

                if (showLineHeaders) {
                    html += `
                    <div class="line-section-header">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 16px;">🚍</span>
                            <span>${lineName.toUpperCase()}</span>
                            <span class="line-badge-count">${lineRoutes.length} Ramales</span>
                            <span style="font-size: 11px; color: #94a3b8; font-weight: 500;">· ${totalBusesInLine} buses activos</span>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            ${totalWrongDirInLine > 0 ? `<span style="background: #d97706; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">⚠️ ${totalWrongDirInLine} en contrasentido</span>` : ''}
                            ${totalBunchingInLine > 0 ? `<span style="background: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">🚨 ${totalBunchingInLine} pegonamiento(s)</span>` : ''}
                        </div>
                    </div>
                    `;
                }

                lineRoutes.forEach(r => {
                    const totalKm = r.distance_km;
                    const buses = r.buses || [];
                    const headways = r.headways || [];
                    const hasBunching = r.status === 'PEGONAMIENTO' || r.bunching_count > 0;
                    const hasWrongDir = (r.wrong_direction_count || 0) > 0;

                    let statusBadge = '<span class="route-status-pill pill-empty">Sin buses</span>';
                    if (hasBunching) {
                        statusBadge = `<span class="route-status-pill pill-bunching">🚨 ${r.bunching_count} Pegonamiento(s)</span>`;
                    } else if (r.status === 'ADVERTENCIA') {
                        statusBadge = '<span class="route-status-pill pill-warning">⚠️ Intervalo Corto</span>';
                    } else if (r.status === 'OPTIMO') {
                        statusBadge = '<span class="route-status-pill pill-optimal">✓ Intervalo Regular</span>';
                    } else if (r.status === 'UN_BUS') {
                        statusBadge = '<span class="route-status-pill pill-optimal">1 Bus en Ruta</span>';
                    }

                    html += `
                    <div class="route-card ${hasBunching ? 'bunching-card' : ''}" style="${hasWrongDir ? 'border-left: 4px solid #f59e0b;' : ''}">
                        <div class="route-header">
                            <div class="route-meta">
                                ${r.line_name ? `<span class="route-line-badge">🚍 ${r.line_name}</span>` : ''}
                                <span class="route-id-badge">${r.route_id.toUpperCase()}</span>
                                <span class="route-name">${r.name}</span>
                                <span class="route-length">🛣️ ${totalKm} km · Sentido: ${r.direction_label}</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                ${hasWrongDir ? `
                                    <span class="route-status-pill" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.5);">
                                        ⚠️ ${r.wrong_direction_count} Contrasentido
                                    </span>
                                ` : ''}
                                ${r.waze_impact && r.waze_impact.total_delay_minutes > 0 ? `
                                    <span class="route-status-pill" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);">
                                        🚦 Waze: +${r.waze_impact.total_delay_minutes} min demora
                                    </span>
                                ` : ''}
                                ${statusBadge}
                            </div>
                        </div>

                        <!-- Horizontal Track Visualizer -->
                        <div class="track-wrapper">
                            <div class="terminal-labels">
                                <span>🏁 ${r.origin} (0.0 km)</span>
                                <span>🎯 ${r.destination} (${totalKm} km)</span>
                            </div>

                            <div class="rail-track">
                                <div class="rail-track-progress" style="width: 100%;"></div>

                                <!-- Headway Connecting Segments -->
                                ${headways.map(hw => {
                                    const isCrit = hw.severity === 'CRITICAL';
                                    const isTerminal = hw.severity === 'TERMINAL_WAIT';
                                    const isStopDwell = hw.severity === 'STOP_DWELL';
                                    const cls = isCrit ? 'critical' : (isTerminal ? 'terminal' : (isStopDwell ? 'stop_dwell' : (hw.severity === 'WARNING' ? 'warning' : 'optimal')));
                                    const badgePrefix = isCrit ? '🚨 Pegonamiento: ' : (isTerminal ? '🟡 Cabecera: ' : (isStopDwell ? '🚏 En Parada (Permitido): ' : (hw.severity === 'WARNING' ? '⚠️ Corto: ' : '')));
                                    return `
                                        <div class="headway-segment ${cls}" style="left: ${hw.left_pct}%; width: ${hw.width_pct}%;">
                                            <div class="headway-badge ${cls}">
                                                ${badgePrefix}Δ ${hw.gap_km} km (${hw.est_minutes} min)
                                            </div>
                                        </div>
                                    `;
                                }).join('')}

                                <!-- Bus Markers on Track (Clickable) -->
                                ${buses.map(b => {
                                    const isBunch = b.is_bunching;
                                    const isWrongDir = b.wrong_direction_alert;
                                    const hexId = String(b.bus_id || '');
                                    const decNum = parseInt(hexId, 16);
                                    const busDisplay = !isNaN(decNum) ? `${hexId} (${decNum})` : hexId;
                                    const wrongDirTooltip = isWrongDir ? ` | ⚠️ ALERTA CONTRASENTIDO: Se desplaza en sentido contrario a ruta ${r.route_id.toUpperCase()}${b.suggested_opposite_route ? ' (Sugerido: ' + b.suggested_opposite_route.toUpperCase() + ')' : ''}` : '';
                                    return `
                                        <div class="bus-marker ${isBunch ? 'bunching' : ''} ${isWrongDir ? 'wrong-dir' : ''}" 
                                             style="left: ${b.progress_percent}%;" 
                                             onclick="openBusModal('${b.bus_id}')"
                                             title="Coche #${hexId} (${!isNaN(decNum) ? decNum : hexId}) | ${b.speed_kmh} km/h${wrongDirTooltip} | Clic para ver detalles y ubicar en GPS">
                                            <div class="bus-marker-bubble">
                                                <span class="bus-bubble-id">${busDisplay}</span>
                                                <span class="bus-bubble-time">(${b.speed_kmh}k)</span>
                                                <span class="bus-bubble-icon">${isWrongDir ? '⚠️' : '🚌'}</span>
                                            </div>
                                            <div class="bus-marker-pointer"></div>
                                        </div>
                                    `;
                                }).join('')}
                            </div>

                            <!-- Kilometer Ticks -->
                            <div class="tick-marks">
                                <span class="tick" style="left: 0%;">0 km</span>
                                <span class="tick" style="left: 25%;">${(totalKm * 0.25).toFixed(1)} km</span>
                                <span class="tick" style="left: 50%;">${(totalKm * 0.5).toFixed(1)} km</span>
                                <span class="tick" style="left: 75%;">${(totalKm * 0.75).toFixed(1)} km</span>
                                <span class="tick" style="left: 100%;">${totalKm} km</span>
                            </div>
                        </div>

                        <!-- Mini Bus Audit Table (Clickable Rows) -->
                        ${buses.length > 0 ? `
                        <div class="bus-table-box">
                            <table class="bus-mini-table">
                                <thead>
                                    <tr>
                                        <th>Coche (Clic para inspeccionar)</th>
                                        <th>Estado</th>
                                        <th>Velocidad</th>
                                        <th>Km en Shape</th>
                                        <th>Progreso</th>
                                        <th>Desvío del Eje</th>
                                        <th>Último Ping</th>
                                        <th>Billetaje Jaha (Pax / Redondo)</th>
                                        <th>Estado de Intervalo</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${buses.map(b => `
                                        <tr class="clickable-row ${b.is_bunching ? 'bunching-row' : ''}" onclick="openBusModal('${b.bus_id}')" title="Clic para ver ficha completa y ubicar en mapa">
                                            <td><strong>🚌 ${formatBusHexDec(b.bus_id)}</strong> (${b.license_plate})</td>
                                            <td><span style="background: rgba(16, 185, 129, 0.15); color: #34d399; padding: 2px 7px; border-radius: 4px; font-weight: 700; font-size: 11px;">${b.state_label || 'En Circulación'}</span></td>
                                            <td>${b.speed_kmh} km/h</td>
                                            <td><strong>${b.distance_traveled_km} km</strong> / ${totalKm} km</td>
                                            <td>
                                                <div style="display: flex; align-items: center; gap: 8px;">
                                                    <div style="flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; width: 60px;">
                                                        <div style="width: ${b.progress_percent}%; height: 100%; background: ${b.wrong_direction_alert ? '#f59e0b' : (b.is_bunching ? '#ef4444' : '#38bdf8')};"></div>
                                                    </div>
                                                    <span>${b.progress_percent}%</span>
                                                </div>
                                            </td>
                                            <td>${b.deviation_meters} m</td>
                                            <td>${b.last_ping_time ? b.last_ping_time.substring(11, 19) : '--:--'}</td>
                                            <td>
                                                <span style="background: rgba(16, 185, 129, 0.12); color: #34d399; padding: 2px 7px; border-radius: 4px; font-weight: 700; font-size: 11px;">🎫 ${(b.passengers_today || 0).toLocaleString('es-PY')} pax</span>
                                                <div style="font-size: 10px; color: ${b.trips_today > 0 ? '#fbbf24' : '#94a3b8'}; font-weight: 700; margin-top: 2px;">
                                                    🔄 ${b.trips_today > 0 ? `${b.trips_today} redondos` : '1er redondo'} · <strong>${b.trips_today > 0 ? `${b.pax_per_round || 0} pax/red` : `${b.passengers_today || 0} pax`}</strong>
                                                </div>
                                            </td>
                                            <td>
                                                ${b.wrong_direction_alert
                                                    ? `<span style="color: #fbbf24; font-weight: 700;">⚠️ CONTRASENTIDO (${b.heading_diff_deg || 180}° opuesto${b.suggested_opposite_route ? ' · Sugerido: ' + b.suggested_opposite_route.toUpperCase() : ''})</span>`
                                                    : (b.is_bunching 
                                                        ? '<span style="color: #f87171; font-weight: 700;">🚨 PEGONAMIENTO DETECTADO</span>' 
                                                        : (b.speed_kmh <= 5.0 && b.state !== 'AT_ORIGIN' && b.state !== 'AT_DESTINATION' && b.state !== 'GPS_FAULT'
                                                            ? '<span style="color: #38bdf8; font-weight: 600;">🚏 En Parada (Permitido)</span>' 
                                                            : (b.state === 'AT_ORIGIN' || b.state === 'AT_DESTINATION'
                                                                ? '<span style="color: #fbbf24; font-weight: 600;">🟡 En Terminal / Cabecera</span>'
                                                                : '<span style="color: #34d399;">✓ Intervalo Regular</span>'
                                                              )
                                                          )
                                                      )
                                                }
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                        ` : '<div style="font-size: 12px; color: #64748b; padding-top: 6px;">No hay unidades transmitiendo en este ramal actualmente.</div>'}
                    </div>
                    `;
                });
            });

            container.innerHTML = html;
        }

        // Número interno de coche (con identificador telemático hex entre paréntesis)
        function formatBusHexDec(busId) {
            const hexId = String(busId || '').trim();
            const decNum = parseInt(hexId, 16);
            if (hexId && !isNaN(decNum) && String(decNum) !== hexId) {
                return `Coche ${decNum} (#${hexId})`;
            }
            return hexId ? `Coche ${hexId}` : '';
        }

        // --- MODAL DE DETALLES Y UBICAR EN MAPA ---
        function updateModalContent(b) {
            if (!b) return;
            document.getElementById('modal-bus-id').textContent = formatBusHexDec(b.bus_id);
            document.getElementById('modal-bus-plate').textContent = `${b.license_plate} · Empresa ${b.agency_id}`;
            document.getElementById('modal-state').textContent = b.state_label || 'En Circulación';
            document.getElementById('modal-speed').textContent = `${b.speed_kmh} km/h`;
            document.getElementById('modal-route').textContent = `${(b.route_id || '').toUpperCase()} - ${b.route_name || 'Troncal'}`;
            document.getElementById('modal-direction').textContent = b.direction_label ? `${b.direction_label} (${b.origin || ''} ➔ ${b.destination || ''})` : 'Itinerario Regular';
            document.getElementById('modal-progress').textContent = `${b.progress_percent}%`;
            document.getElementById('modal-dist').textContent = `${b.distance_traveled_km} km de ${b.route_total_km || '--'} km`;
            document.getElementById('modal-deviation').textContent = `${b.deviation_meters} metros`;
            document.getElementById('modal-driver').textContent = b.driver_id || 'Conductor No Asignado';
            document.getElementById('modal-location').textContent = b.street_name || 'En calzada principal de itinerario';
            document.getElementById('modal-approaching').textContent = b.approaching || 'Avanzando en secuencia normal de paradas';
            document.getElementById('modal-ping').textContent = b.last_ping_time ? b.last_ping_time.substring(11, 19) : '--:--:--';
            document.getElementById('modal-odometer').textContent = `${b.odometer_km || 0.0} km`;

            // Configurar enlace Waze y reporte de tráfico
            const wazeBtn = document.getElementById('modal-waze-nav-btn');
            const wazeInfo = document.getElementById('modal-waze-info');
            const lat = b.latitude || -25.30;
            const lon = b.longitude || -57.58;
            wazeBtn.href = `https://www.waze.com/ul?ll=${lat},${lon}&navigate=yes`;

            if (b.waze_alert) {
                wazeInfo.innerHTML = `⚠️ <strong style="color:#f87171;">Congestión Nivel ${b.waze_alert.level}</strong> en ${b.waze_alert.street} (Demora: +${b.waze_alert.delay_minutes} min, Vel: ${b.waze_alert.speedKMH} km/h).`;
            } else {
                wazeInfo.innerHTML = `✓ Circulando con velocidad normal en el corredor según red Waze Asunción.`;
            }

            const bunchBox = document.getElementById('modal-bunching-box');
            if (b.is_bunching) {
                bunchBox.style.display = 'flex';
                document.getElementById('modal-bunching-desc').textContent = 
                    `Circulando pegado a coche #${b.bunching_with} a una distancia crítica de ${b.bunching_gap_m} m (~${b.bunching_gap_min} min de separación).`;
            } else {
                bunchBox.style.display = 'none';
            }

            // Alerta de IDRuta en Contrasentido
            const wrongDirBox = document.getElementById('modal-wrong-dir-box');
            if (wrongDirBox) {
                if (b.wrong_direction_alert) {
                    wrongDirBox.style.display = 'flex';
                    const sugMsg = b.suggested_opposite_route 
                        ? `<br/><div style="margin-top: 8px;"><button type="button" onclick="quickApplySuggestedRoute('${b.suggested_opposite_route}')" style="background: #f59e0b; color: #0f172a; border: none; padding: 6px 14px; border-radius: 6px; font-weight: 800; font-size: 11px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 6px rgba(245, 158, 11, 0.4); transition: transform 0.1s;">⚡ Aplicar Sugerencia: Cambiar al Ramal ${b.suggested_opposite_route.toUpperCase()} (1 Clic)</button></div>`
                        : '';
                    document.getElementById('modal-wrong-dir-desc').innerHTML = 
                        `<strong>${b.wrong_direction_reason || 'El bus se desplaza en sentido contrario a la ruta configurada.'}</strong> (Diferencia de rumbo: ${b.heading_diff_deg || 180}°).${sugMsg}`;
                } else {
                    wrongDirBox.style.display = 'none';
                }
            }

            // Datos de Billetaje Jaha
            const pax = b.passengers_today || 0;
            const rev = b.revenue_today || 0;
            const trips = b.trips_today || 0;
            const pRound = b.pax_per_round !== undefined ? b.pax_per_round : (trips > 0 ? (pax / trips).toFixed(1) : pax);
            const srv = b.validator_service || 'DIFERENCIAL';
            const srvBadge = document.getElementById('modal-billetaje-srv-badge');
            if (srvBadge) srvBadge.textContent = srv;
            const bInfo = document.getElementById('modal-billetaje-info');
            if (bInfo) {
                bInfo.innerHTML = `🎫 <strong>${pax.toLocaleString('es-PY')}</strong> pasajes cobrados hoy · 🔄 <strong>${trips > 0 ? `${trips} redondos completados` : '1er redondo en curso'}</strong> · 📊 Promedio: <strong style="color: #fbbf24;">${pRound} pax/redondo</strong> · Gs. ${rev.toLocaleString('es-PY')} recaudados`;
            }
        }

        function openBusModal(busId) {
            initAudioContext();
            const b = busRegistry[busId];
            if (!b) return;

            selectedBusId = busId;
            updateModalContent(b);

            // Poblar selector de reasignación agrupado por Línea Comercial
            const sel = document.getElementById('modal-reassign-select');
            const statusEl = document.getElementById('modal-reassign-status');
            if (statusEl) statusEl.style.display = 'none';

            if (sel) {
                if (latestDashboardData && Array.isArray(latestDashboardData.routes) && latestDashboardData.routes.length > 0) {
                    const curRoute = String(b.route_id || '').toLowerCase();
                    const sugOpposite = String(b.suggested_opposite_route || '').toLowerCase();

                    // Agrupar opciones por Línea Comercial
                    const byLine = {};
                    latestDashboardData.routes.forEach(r => {
                        const ln = r.line_name || 'Línea Regular';
                        if (!byLine[ln]) byLine[ln] = [];
                        byLine[ln].push(r);
                    });

                    let optHtml = '';
                    for (const [ln, routes] of Object.entries(byLine)) {
                        optHtml += `<optgroup label="🚍 ${ln}">`;
                        routes.forEach(r => {
                            const rCode = String(r.route_id || '').toLowerCase();
                            const isCur = (rCode === curRoute);
                            const isSug = (rCode === sugOpposite && !isCur);
                            // Si el coche está en contrasentido y hay sugerencia operativa, preseleccionarla automáticamente
                            const isSelected = (b.wrong_direction_alert && sugOpposite) ? isSug : isCur;
                            const sugTag = isSug ? ' ⚡ [SUGERIDO POR SENTIDO]' : (isCur ? ' [ACTUAL]' : '');
                            optHtml += `<option value="${rCode}" ${isSelected ? 'selected' : ''}>${r.route_id.toUpperCase()} - ${r.name} (${r.direction_label})${sugTag}</option>`;
                        });
                        optHtml += `</optgroup>`;
                    }
                    sel.innerHTML = optHtml;
                } else {
                    sel.innerHTML = `<option value="${b.route_id || ''}">${(b.route_id || '').toUpperCase()} - Actual</option>`;
                }
            }

            document.getElementById('bus-modal').style.display = 'flex';
        }

        function quickApplySuggestedRoute(routeCode) {
            const sel = document.getElementById('modal-reassign-select');
            if (sel && routeCode) {
                sel.value = routeCode.toLowerCase();
            }
            executeRouteReassign();
        }

        async function executeRouteReassign() {
            if (!selectedBusId) return;
            const b = busRegistry[selectedBusId];
            if (!b) return;
            const sel = document.getElementById('modal-reassign-select');
            const newRoute = sel.value;
            if (!newRoute) return;

            const btn = document.getElementById('modal-reassign-btn');
            const statusEl = document.getElementById('modal-reassign-status');
            btn.disabled = true;
            btn.textContent = 'Guardando...';
            statusEl.style.display = 'block';
            statusEl.style.color = '#38bdf8';
            statusEl.textContent = 'Enviando reasignación a la central de tráfico...';

            try {
                const res = await fetch('/api/v1/headway/reassign_route', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        bus_id: b.bus_id,
                        agency_id: b.agency_id || '0008',
                        new_route_code: newRoute
                    })
                });
                const data = await res.json();
                if (data.success) {
                    statusEl.style.color = '#4ade80';
                    statusEl.textContent = `✓ ${data.message || 'Ramal reasignado correctamente'}`;
                    b.route_id = newRoute;
                    b.route_name = data.route_name || newRoute.toUpperCase();
                    b.wrong_direction_alert = false;
                    b.wrong_direction_reason = '';
                    b.suggested_opposite_route = null;
                    const wrongDirBox = document.getElementById('modal-wrong-dir-box');
                    if (wrongDirBox) wrongDirBox.style.display = 'none';
                    await fetchHeadwayData();
                    setTimeout(() => {
                        closeBusModal();
                    }, 1200);
                } else {
                    statusEl.style.color = '#f87171';
                    statusEl.textContent = `Error: ${data.detail || data.message || 'No se pudo reasignar'}`;
                }
            } catch (err) {
                statusEl.style.color = '#f87171';
                statusEl.textContent = `Error de red: ${err.message}`;
            } finally {
                btn.disabled = false;
                btn.textContent = 'Aplicar Cambio';
            }
        }

        function closeBusModal() {
            document.getElementById('bus-modal').style.display = 'none';
            selectedBusId = null;
        }

        function closeModalOnBackdrop(e) {
            if (e.target.id === 'bus-modal') {
                closeBusModal();
            }
        }

        function locateSelectedBusOnMap() {
            if (!selectedBusId) return;
            // Abre o redirige al Radar GPS con el parámetro del bus
            const targetUrl = `/map?bus=${encodeURIComponent(selectedBusId)}`;
            window.open(targetUrl, '_blank');
        }

        // Cierre con tecla Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeBusModal();
        });

        // Refresco automático cada 15 segundos
        fetchHeadwayData();
        setInterval(fetchHeadwayData, 15000);
    </script>
</body>
</html>
"""
    return html_content.replace("{user_badge_html}", user_badge_html)


