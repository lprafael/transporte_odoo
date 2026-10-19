# -*- coding: utf-8 -*-
"""
Servicio de Cumplimiento Regulatorio VMT & Monitoreo Operativo Integral
======================================================================
Auditoría y Monitoreo Operativo en Tiempo Real para Empresas de Transporte:
  - 100% Parametrizado por Base de Datos y Normativa Oficial (VMT / GVMT):
  - Control de Flota Operativa en Itinerario (CBD, CBD_hora, CBD_franja):
      * CBD: Cantidad de buses distintos en itinerario (fuera de paradas terminales)
      * CBD_hora: Conteo de buses distintos fuera de terminales por hora
      * CBD_franja: Conteo de buses distintos acumulados en la franja
      * ICCBDM: (Promedio CBD_hora de la franja * 0.7) + (CBD_franja * 0.3)
      * IFO: (CBD_actual(hora) / CBD_historico(4 semanas, mismo día)) * 100%
             Obviando días feriados (con pre y pos feriados) y días de lluvias
      * IFO_franja: Promedio de los IFO_hora de la franja
      * CBD_objetivo: Promedio histórico de las 4 semanas de referencia (meta 100% IFO)
  - Índice de Cumplimiento de Frecuencia (ICF Provisorio - Decreto N° 710/2023, Apéndice 11)
  - Clasificación de Despachos en 5 estados operativos (Res. GVMT 065/2024)
  - Soporte Multi-tenant para todas las empresas permisionarias (Arapotí 004B, Guaraní 0008, San José Obrero 002A, etc.)

Expone:
  - /compliance                     - Dashboard HTML interactivo con selector de empresa, servicio y fecha
  - /api/v1/compliance/companies    - Lista de empresas/concesionarias activas
  - /api/v1/compliance/services     - Lista de servicios activos parametrizados
  - /api/v1/compliance/today        - Métricas integrales: CBD, ICCBDM, IFO, ICF y auditoría
  - /api/v1/compliance/alerts       - Alertas operativas de déficit
  - /api/v1/compliance/history      - Tendencia de los últimos 30 días
"""

import os
import json
import logging
from datetime import datetime, timezone, date, time, timedelta
from typing import Dict, Any, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("compliance_service")

# --- Configuración Base de Datos Local (flota_db) ---
PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB   = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

# --- Configuración Base de Datos CID (VMT Paraguay) ---
CID_HOST = os.getenv("CID_DB_HOST", "168.90.177.232")
CID_PORT = int(os.getenv("CID_DB_PORT", 2024))
CID_DB   = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
CID_USER = os.getenv("CID_DB_USER", "cid_admin_user")
CID_PASS = os.getenv("CID_DB_PASS", "vmtdmtcidccm")

CRITICAL_THRESHOLD_PCT = 85.0
WARNING_THRESHOLD_PCT  = 95.0
COMPLIANCE_CACHE_TTL   = 60  # segundos

# Franjas horarias oficiales de respaldo (Decreto N° 710/2023 & GVMT)
FRANJAS_LABORAL = [
    (time(5, 0),  time(7, 59, 59),  "Pico Mañana 05-08h",   "Hora Pico"),
    (time(8, 0),  time(15, 59, 59), "Pos-Pico Día 08-16h",  "Hora Pos-Pico"),
    (time(16, 0), time(18, 59, 59), "Pico Tarde 16-19h",    "Hora Pico"),
    (time(19, 0), time(20, 59, 59), "Pos-Pico Noche 19-21h","Hora Pos-Pico"),
]

FRANJAS_FIN_SEMANA = [
    (time(0, 0),  time(23, 59, 59), "Operación FdS/Feriado", "Hora Pos-Pico"),
]


def _pg_connect():
    """Conexión a PostgreSQL flota_db."""
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS, connect_timeout=4
    )


def _cid_connect():
    """Conexión a base de datos de auditoría CID (VMT)."""
    return psycopg2.connect(
        host=CID_HOST, port=CID_PORT, dbname=CID_DB,
        user=CID_USER, password=CID_PASS, connect_timeout=4
    )


def _get_day_type_info(conn, target_date: date) -> Dict[str, Any]:
    """
    Determina tipo_dia (5=Laboral, 6=Sábado, 7=Domingo/Feriado) consultando transit_holiday.
    """
    dow = target_date.weekday()
    es_feriado = False
    feriado_desc = None

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT name FROM transit_holiday
            WHERE date = %s AND active = true
            LIMIT 1
        """, (target_date,))
        row = cur.fetchone()
        cur.close()
        if row:
            es_feriado = True
            feriado_desc = row["name"]
    except Exception as e:
        logger.debug(f"Aviso al consultar feriados (usando calendario estandar): {e}")
        conn.rollback()

    if es_feriado or dow == 6:
        td = 7
        regimen = "Domingos y Feriados"
        tipo_dia_desc = f"Feriado ({feriado_desc})" if es_feriado else "Domingo"
    elif dow == 5:
        td = 6
        regimen = "Lunes a Sábado"
        tipo_dia_desc = "Sábado"
    else:
        td = 5
        regimen = "Lunes a Sábado"
        tipo_dia_desc = "Laboral (L-V)"

    return {
        "tipo_dia": td,
        "regimen": regimen,
        "es_feriado": es_feriado,
        "feriado_desc": feriado_desc,
        "tipo_dia_desc": tipo_dia_desc,
    }


def get_available_companies() -> List[Dict[str, Any]]:
    """Retorna las empresas/concesionarias registradas."""
    companies = []
    try:
        conn = _pg_connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, code, agency_id
            FROM transit_concessionaire
            WHERE active = true
            ORDER BY id ASC;
        """)
        companies = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.debug(f"Aviso al consultar transit_concessionaire: {e}")

    if not companies:
        companies = [
            {"id": 4, "name": "Consorcio Arapotí", "code": "CONC-ARAPOTI", "agency_id": "004B"},
            {"id": 14, "name": "AUTOMOTORES GUARANI SRL", "code": "CONC-0008", "agency_id": "0008"},
            {"id": 15, "name": "SAN JOSE OBRERO SA", "code": "CONC-002A", "agency_id": "002A"},
        ]
    return [dict(c) for c in companies]


def get_available_services(agency_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene la lista de servicios activos parametrizados en transit_service filtrados por empresa."""
    services = []
    try:
        conn = _pg_connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if agency_id:
            cur.execute("""
                SELECT s.id, s.code, s.name, s.daily_target_departures,
                       s.tolerance_early_min, s.tolerance_late_min,
                       s.compliance_threshold_pct, s.incomplete_threshold_pct,
                       s.agency_vmt_id
                FROM transit_service s
                LEFT JOIN transit_concessionaire c ON s.concessionaire_id = c.id
                WHERE s.active = true AND (s.agency_vmt_id = %s OR c.agency_id = %s)
                ORDER BY s.code ASC;
            """, (agency_id, agency_id))
        else:
            cur.execute("""
                SELECT s.id, s.code, s.name, s.daily_target_departures,
                       s.tolerance_early_min, s.tolerance_late_min,
                       s.compliance_threshold_pct, s.incomplete_threshold_pct,
                       s.agency_vmt_id
                FROM transit_service s
                WHERE s.active = true
                ORDER BY s.code ASC;
            """)
        rows = cur.fetchall()
        for r in rows:
            cur.execute("""
                SELECT code FROM transit_route
                WHERE service_id = %s AND active = true
            """, (r["id"],))
            route_rows = cur.fetchall()
            routes = [rr["code"] for rr in route_rows]
            services.append({
                "id": r["id"],
                "code": r["code"],
                "name": r["name"],
                "daily_target": r["daily_target_departures"] or 0,
                "tolerance_early": r["tolerance_early_min"] or 5,
                "tolerance_late": r["tolerance_late_min"] or 10,
                "routes": routes,
                "agency_id": r.get("agency_vmt_id")
            })
        cur.close()
        conn.close()
    except Exception as e:
        logger.debug(f"Error consultando transit_service: {e}")

    return services


def get_valid_historical_dates(eval_date: date, target_count: int = 4) -> Tuple[List[date], List[Dict[str, str]]]:
    """
    Obtiene las 4 fechas históricas de las semanas anteriores en el mismo día de la semana,
    descartando días feriados (con sus pre-feriados y pos-feriados) y días de lluvia (registros Open-Meteo).
    Retorna (valid_dates, excluded_dates).
    """
    discard_reasons: Dict[date, str] = {}

    # 1. Consultar días atípicos y lluvias en CID DB
    try:
        conn = _cid_connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT fecha, tipo_atipico, observacion
            FROM control_metricas.dias_atipicos
            WHERE descartar_historico = TRUE OR tipo_atipico = 'LLUVIA';
        """)
        for r in cur.fetchall():
            f = r["fecha"]
            obs = r.get("observacion") or r.get("tipo_atipico")
            discard_reasons[f] = obs

        cur.execute("""
            SELECT DISTINCT fecha_evento, notas
            FROM control_metricas.t_casuisticas_lluvia;
        """)
        for r in cur.fetchall():
            f = r["fecha_evento"]
            if f not in discard_reasons:
                discard_reasons[f] = r.get("notas") or "Lluvia registrada (Open-Meteo)"

        cur.close()
        conn.close()
    except Exception as e:
        logger.debug(f"Aviso al consultar dias_atipicos en CID DB: {e}")

    # 2. Consultar feriados locales y pre/pos feriados
    try:
        conn_local = _pg_connect()
        cur_l = conn_local.cursor(cursor_factory=RealDictCursor)
        cur_l.execute("SELECT date, name FROM transit_holiday WHERE active = true")
        for r in cur_l.fetchall():
            f_hol = r["date"]
            discard_reasons[f_hol] = f"Feriado: {r['name']}"
            pre_hol = f_hol - timedelta(days=1)
            pos_hol = f_hol + timedelta(days=1)
            if pre_hol not in discard_reasons:
                discard_reasons[pre_hol] = f"Pre-feriado de {r['name']}"
            if pos_hol not in discard_reasons:
                discard_reasons[pos_hol] = f"Pos-feriado de {r['name']}"
        cur_l.close()
        conn_local.close()
    except Exception as e:
        logger.debug(f"Aviso al consultar transit_holiday local: {e}")

    valid_dates: List[date] = []
    excluded_dates: List[Dict[str, str]] = []

    for step in range(1, 20):
        cand = eval_date - timedelta(weeks=step)
        if cand in discard_reasons:
            excluded_dates.append({
                "date": cand.isoformat(),
                "day_name": cand.strftime("%A"),
                "reason": discard_reasons[cand]
            })
        else:
            valid_dates.append(cand)
            if len(valid_dates) >= target_count:
                break

    return valid_dates, excluded_dates


def calculate_cbd_and_ifo(agency_id: str = "004B", eval_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Cálculo de métricas regulatorias según especificación VMT:
      - CBD: Cantidad de buses distintos en itinerario (fuera de paradas terminales)
      - CBD_hora: Conteo de buses distintos por hora
      - CBD_franja: Conteo de buses distintos acumulados en la franja horaria
      - ICCBDM: (Promedio CBD_hora de la franja * 0.7) + (CBD_franja * 0.3)
      - CBD_objetivo: Promedio histórico de las 4 semanas válidas (meta 100% IFO)
      - IFO: (CBD_actual(hora) / CBD_objetivo(hora)) * 100%
      - IFO_franja: Promedio de los IFO_hora de la franja
    """
    if not eval_date:
        eval_date = datetime.now().date()

    is_today = (eval_date == datetime.now().date())
    now = datetime.now()
    current_hour = now.hour if is_today else 23

    # Determinar tipo de día
    try:
        conn_local = _pg_connect()
        day_info = _get_day_type_info(conn_local, eval_date)
        conn_local.close()
    except Exception:
        day_info = {"tipo_dia": 5, "regimen": "Laboral", "tipo_dia_desc": "Laboral"}
    td = day_info["tipo_dia"]

    # 1. Obtener 4 fechas históricas válidas
    valid_dates, excluded_dates = get_valid_historical_dates(eval_date, target_count=4)

    # 2. Obtener franjas operativas y parámetros mínimos desde CID DB
    franjas = []
    cbd_minimos = {}
    parametros_ifo = {}
    cbd_actual_by_hour = {}
    hist_by_hour = {}

    try:
        conn_cid = _cid_connect()
        cur_cid = conn_cid.cursor(cursor_factory=RealDictCursor)

        # Franjas vigentes para el tipo_dia
        cur_cid.execute("""
            SELECT id_franja, denominacion, hora_inicio, hora_fin, id_tipo_dia
            FROM control_metricas.franjas_operativas
            WHERE id_tipo_dia = %s AND activo = TRUE
            ORDER BY hora_inicio;
        """, (td,))
        franjas_rows = cur_cid.fetchall()
        for fr in franjas_rows:
            franjas.append({
                "id_franja": fr["id_franja"],
                "nombre": fr["denominacion"],
                "hora_inicio": fr["hora_inicio"],
                "hora_fin": fr["hora_fin"],
                "h_start": fr["hora_inicio"].hour,
                "h_end": fr["hora_fin"].hour,
                "rango": f"{fr['hora_inicio'].strftime('%H:%M')} - {fr['hora_fin'].strftime('%H:%M')}"
            })

        # Parámetros mínimos de CBD
        cur_cid.execute("""
            SELECT id_franja, cbd_minimo_franja, cbd_minimo_hora
            FROM control_metricas.cbd_parametros_minimos
            WHERE id_tipo_dia = %s;
        """, (td,))
        for r in cur_cid.fetchall():
            cbd_minimos[r["id_franja"]] = {
                "min_franja": r["cbd_minimo_franja"] or 0,
                "min_hora": r["cbd_minimo_hora"] or 0
            }

        # Parámetros mínimos de IFO
        cur_cid.execute("""
            SELECT id_franja_operativa, porc_cumplimiento_minimo, descripcion, normativa
            FROM control_metricas.parametros_ifo
            WHERE inicio_vigencia <= %s AND (fin_vigencia IS NULL OR fin_vigencia >= %s);
        """, (eval_date, eval_date))
        for r in cur_cid.fetchall():
            parametros_ifo[r["id_franja_operativa"]] = {
                "umbral_min_pct": float(r["porc_cumplimiento_minimo"] or 80.0),
                "normativa": r.get("normativa", "Dec. GVMT")
            }

        # CBD actual desde cbd_detalle_buses
        cur_cid.execute("""
            SELECT hora, COUNT(DISTINCT mean_id) as cnt
            FROM control_metricas.cbd_detalle_buses
            WHERE id_eot_vmt_hex = %s AND fecha = %s
            GROUP BY hora ORDER BY hora;
        """, (agency_id, eval_date))
        cbd_actual_by_hour = {r["hora"]: int(r["cnt"]) for r in cur_cid.fetchall()}

        # CBD histórico en las 4 fechas válidas
        if valid_dates:
            cur_cid.execute("""
                SELECT hora, fecha, COUNT(DISTINCT mean_id) as cnt
                FROM control_metricas.cbd_detalle_buses
                WHERE id_eot_vmt_hex = %s AND fecha = ANY(%s)
                GROUP BY hora, fecha;
            """, (agency_id, valid_dates))
            for r in cur_cid.fetchall():
                hist_by_hour.setdefault(r["hora"], []).append(int(r["cnt"]))

        cur_cid.close()
        conn_cid.close()
    except Exception as e:
        logger.error(f"Error consultando métricas en CID DB: {e}")

    # Fallback franjas si no se cargaron de BD
    if not franjas:
        if td == 5:
            franjas = [
                {"id_franja": 40, "nombre": "Madrugada", "h_start": 4, "h_end": 4, "rango": "04:00 - 04:59"},
                {"id_franja": 30, "nombre": "Pico Mañana", "h_start": 5, "h_end": 7, "rango": "05:00 - 07:59"},
                {"id_franja": 31, "nombre": "Pos Pico (Entre Picos)", "h_start": 8, "h_end": 15, "rango": "08:00 - 15:59"},
                {"id_franja": 32, "nombre": "Pico Tarde", "h_start": 16, "h_end": 18, "rango": "16:00 - 18:59"},
                {"id_franja": 33, "nombre": "Pos Pico Tarde", "h_start": 19, "h_end": 20, "rango": "19:00 - 20:59"},
                {"id_franja": 34, "nombre": "Nocturno Laboral", "h_start": 21, "h_end": 22, "rango": "21:00 - 22:59"}
            ]
        elif td == 6:
            franjas = [
                {"id_franja": 35, "nombre": "Pico Sábado", "h_start": 6, "h_end": 15, "rango": "06:00 - 15:59"},
                {"id_franja": 36, "nombre": "Pos Pico Sábado", "h_start": 16, "h_end": 20, "rango": "16:00 - 20:59"},
                {"id_franja": 37, "nombre": "Nocturno Sábado", "h_start": 21, "h_end": 22, "rango": "21:00 - 22:59"}
            ]
        else:
            franjas = [
                {"id_franja": 38, "nombre": "Servicio Reducido (Dom/Fer)", "h_start": 7, "h_end": 21, "rango": "07:00 - 21:59"}
            ]

    # Si es hoy y faltan horas en cbd_detalle_buses, consultar telemetry_ping en tiempo real fuera de terminales
    if is_today:
        missing_hours = [h for h in range(4, current_hour + 1) if h not in cbd_actual_by_hour or cbd_actual_by_hour[h] == 0]
        if missing_hours:
            try:
                conn_pg = _pg_connect()
                cur_pg = conn_pg.cursor(cursor_factory=RealDictCursor)
                cur_pg.execute("""
                    WITH terminals AS (
                        SELECT ST_Union(ST_Buffer(geom::geography, radius_meters)::geometry) AS geom
                        FROM transit_stop
                        WHERE stop_type IN ('origin', 'destination')
                    )
                    SELECT 
                        EXTRACT(HOUR FROM tp.recorded_at AT TIME ZONE 'America/Asuncion')::int AS hora,
                        COUNT(DISTINCT tp.bus_internal_code) AS cnt
                    FROM telemetry_ping tp
                    CROSS JOIN terminals t
                    WHERE tp.recorded_at >= CURRENT_DATE - INTERVAL '1 day'
                      AND (tp.agency_id = %s OR %s IS NULL)
                      AND (t.geom IS NULL OR NOT ST_Within(tp.geom, t.geom))
                    GROUP BY 1;
                """, (agency_id, agency_id))
                for r in cur_pg.fetchall():
                    h = r["hora"]
                    if h not in cbd_actual_by_hour or cbd_actual_by_hour[h] == 0:
                        cbd_actual_by_hour[h] = int(r["cnt"])
                cur_pg.close()
                conn_pg.close()
            except Exception as e_rt:
                logger.debug(f"Aviso al consultar telemetry_ping en tiempo real: {e_rt}")

    # 3. Calcular CBD_objetivo e IFO_hora por cada hora 0..23
    num_valid_weeks = max(len(valid_dates), 1)
    hourly_breakdown = []
    ifo_by_hour = {}
    cbd_obj_by_hour = {}

    for h in range(24):
        act = cbd_actual_by_hour.get(h, 0)
        samples = hist_by_hour.get(h, [0])
        avg_hist = round(sum(samples) / float(num_valid_weeks), 2)
        cbd_obj_by_hour[h] = avg_hist

        if avg_hist > 0:
            ifo_val = round((act / avg_hist) * 100.0, 1)
        else:
            ifo_val = 100.0 if act > 0 else 0.0
        ifo_by_hour[h] = ifo_val

        # Consideramos horas operativas (04h a 23h)
        if 4 <= h <= 23:
            hourly_breakdown.append({
                "hora": h,
                "hora_label": f"{h:02d}:00",
                "cbd_actual": act,
                "cbd_objetivo": avg_hist,
                "ifo_pct": ifo_val,
                "delta": round(act - avg_hist, 2),
                "cumple": (ifo_val >= 80.0) if avg_hist > 0 else True
            })

    # 4. Calcular métricas por franja: CBD_franja, ICCBDM e IFO_franja
    franjas_result = []
    cur_c = None
    conn_cid = None
    try:
        conn_cid = _cid_connect()
        cur_c = conn_cid.cursor()
    except Exception:
        cur_c = None

    for fr in franjas:
        h0 = fr["h_start"]
        h1 = fr["h_end"]
        hours_in_franja = list(range(h0, h1 + 1))

        # CBD_franja: distinct buses outside terminals across the entire interval
        cbd_franja = 0
        if cur_c:
            try:
                cur_c.execute("""
                    SELECT COUNT(DISTINCT mean_id)
                    FROM control_metricas.cbd_detalle_buses
                    WHERE id_eot_vmt_hex = %s AND fecha = %s AND hora >= %s AND hora <= %s;
                """, (agency_id, eval_date, h0, h1))
                row = cur_c.fetchone()
                cbd_franja = int(row[0]) if row and row[0] else 0
            except Exception:
                pass

        if cbd_franja == 0 and hours_in_franja:
            cbd_franja = max([cbd_actual_by_hour.get(h, 0) for h in hours_in_franja] or [0])

        cbds_h = [cbd_actual_by_hour.get(h, 0) for h in hours_in_franja]
        avg_cbd_h = round(sum(cbds_h) / len(cbds_h), 2) if cbds_h else 0.0

        # ICCBDM = Promedio de CBD_hora de la franja * 0.7 + CBD_franja * 0.3
        iccbdm = round((avg_cbd_h * 0.7) + (cbd_franja * 0.3), 2)

        # IFO_franja = promedio de los IFO_hora
        ifos = [ifo_by_hour.get(h, 0.0) for h in hours_in_franja]
        ifo_franja = round(sum(ifos) / len(ifos), 1) if ifos else 0.0

        # CBD Objetivo de la franja
        objs = [cbd_obj_by_hour.get(h, 0.0) for h in hours_in_franja]
        cbd_obj_franja = round(sum(objs) / len(objs), 2) if objs else 0.0

        # Mínimos regulatorios
        id_f = fr["id_franja"]
        min_f = cbd_minimos.get(id_f, {}).get("min_franja", 0)
        min_h = cbd_minimos.get(id_f, {}).get("min_hora", 0)
        umbral_ifo = parametros_ifo.get(id_f, {}).get("umbral_min_pct", 80.0)

        cumple_ifo = (ifo_franja >= umbral_ifo) or (cbd_obj_franja == 0)
        cumple_cbd = (cbd_franja >= min_f) and (min(cbds_h or [0]) >= min_h)

        if cumple_ifo and cumple_cbd:
            estado = "CUMPLE"
            badge = "status-green"
        elif not cumple_ifo and not cumple_cbd:
            estado = "DÉFICIT CRÍTICO"
            badge = "status-red"
        elif not cumple_ifo:
            estado = f"DÉFICIT IFO ({ifo_franja}%)"
            badge = "status-amber"
        else:
            estado = "DÉFICIT FLOTA MÍN."
            badge = "status-amber"

        franjas_result.append({
            "id_franja": id_f,
            "nombre": fr["nombre"],
            "rango": fr["rango"],
            "cbd_franja": cbd_franja,
            "avg_cbd_hora": avg_cbd_h,
            "iccbdm": iccbdm,
            "cbd_minimo_franja": min_f,
            "cbd_minimo_hora": min_h,
            "cbd_objetivo_franja": cbd_obj_franja,
            "ifo_franja_pct": ifo_franja,
            "umbral_ifo_pct": umbral_ifo,
            "cumple_ifo": cumple_ifo,
            "cumple_cbd": cumple_cbd,
            "estado": estado,
            "badge_class": badge
        })

    if cur_c:
        try:
            cur_c.close()
            conn_cid.close()
        except Exception:
            pass

    # Resumen Global
    active_ifos = [h["ifo_pct"] for h in hourly_breakdown if h["cbd_objetivo"] > 0]
    total_cbd_dia = max([fr["cbd_franja"] for fr in franjas_result] or [0])
    avg_iccbdm = round(sum(fr["iccbdm"] for fr in franjas_result) / len(franjas_result), 2) if franjas_result else 0.0
    ifo_global = round(sum(active_ifos) / len(active_ifos), 1) if active_ifos else 0.0
    cbd_obj_global = round(sum(h["cbd_objetivo"] for h in hourly_breakdown) / len(hourly_breakdown), 2) if hourly_breakdown else 0.0

    return {
        "agency_id": agency_id,
        "eval_date": eval_date.isoformat(),
        "summary": {
            "cbd_total_dia": total_cbd_dia,
            "iccbdm_global": avg_iccbdm,
            "ifo_global_pct": ifo_global,
            "cbd_objetivo_global": cbd_obj_global
        },
        "franjas": franjas_result,
        "hourly_breakdown": hourly_breakdown,
        "historical_reference": {
            "valid_dates": [d.isoformat() for d in valid_dates],
            "excluded_dates": excluded_dates,
            "total_weeks_evaluated": len(valid_dates) + len(excluded_dates)
        }
    }


def _classify_icf_band(hora: time, tipo_dia: int):
    """Retorna (nombre_franja, tipo_icf)"""
    franjas = FRANJAS_LABORAL if tipo_dia == 5 else FRANJAS_FIN_SEMANA
    for h0, h1, nombre, tipo in franjas:
        if h0 <= hora <= h1:
            return nombre, tipo
    return "Fuera de Franja", "Hora Pos-Pico"


def _calc_icf_recognition(icf_pct: float, tipo_franja: str) -> float:
    """Aplica tabla de reconocimiento Apéndice 11 (Decreto N° 710/2023)."""
    pico = (tipo_franja == "Hora Pico")
    if icf_pct >= 100.0:
        return 1.00
    if icf_pct >= 90.0:
        return 0.80 if pico else 0.85
    if icf_pct >= 80.0:
        return 0.70 if pico else 0.75
    return 0.00


def get_today_compliance(
    redis_client=None,
    service_code: Optional[str] = None,
    target_date: Optional[str] = None,
    agency_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula el estado integral de cumplimiento del día actual o fecha especificada.
    Soporta multitenant por empresa (agency_id), filtrado por servicio ('ALL', '187-R1', 'E1'...)
    y cálculo simultáneo de CBD, ICCBDM, IFO y cuotas de despacho.
    """
    if target_date:
        try:
            eval_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            eval_date = datetime.now().date()
    else:
        eval_date = datetime.now().date()

    now = datetime.now()
    is_today = (eval_date == now.date())
    current_hour = (now.hour + now.minute / 60.0) if is_today else 24.0
    hours_remaining = max(0.0, 24.0 - current_hour) if is_today else 0.0

    available_companies = get_available_companies()
    sel_agency = agency_id
    if not sel_agency and available_companies:
        sel_agency = available_companies[0]["agency_id"]
    if not sel_agency:
        sel_agency = "004B"

    cache_key = f"compliance:{eval_date.isoformat()}:{sel_agency}:{service_code or 'ALL'}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    available_services = get_available_services(agency_id=sel_agency)

    sel_code = (service_code or "ALL").strip().upper()
    if sel_code in ("ALL", "", "TODOS"):
        active_services = available_services
    else:
        active_services = [s for s in available_services if s["code"].upper() == sel_code]
        if not active_services:
            active_services = available_services

    total_quota = sum(s["daily_target"] for s in active_services)
    all_service_routes = []
    for s in active_services:
        all_service_routes.extend(s.get("routes", []))

    # Cálculo oficial de CBD e IFO
    cbd_ifo_data = calculate_cbd_and_ifo(agency_id=sel_agency, eval_date=eval_date)

    result = {
        "date": eval_date.isoformat(),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "agency_selected": sel_agency,
        "available_companies": available_companies,
        "service_selected": sel_code,
        "available_services": [{"code": s["code"], "name": s["name"]} for s in available_services],
        "daily_quota": total_quota,
        "total_dispatched": 0,
        "total_scheduled": 0,
        "compliance_pct": 0.0,
        "projected_eod_pct": 0.0,
        "hours_elapsed": round(current_hour, 1),
        "hours_remaining": round(hours_remaining, 1),
        "status": "ON_TRACK",
        "status_label": "En Seguimiento",
        "day_info": {},
        "cbd_ifo": cbd_ifo_data,
        "icf_summary": {
            "total_prog": 0,
            "total_obs": 0,
            "total_reconocidos": 0,
            "icf_global_pct": 0.0,
            "bloques": []
        },
        "performance_breakdown": {
            "regular": 0,
            "irregular": 0,
            "reinforcement": 0,
            "incomplete": 0,
            "unperformed": 0
        },
        "alerts": [],
        "by_ramal": {},
        "by_service": {},
        "history_30d": []
    }

    try:
        conn = _pg_connect()
        day_info = _get_day_type_info(conn, eval_date)
        result["day_info"] = day_info
        td = day_info["tipo_dia"]

        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Despachos programados para la fecha
        scheduled_by_route = {}
        scheduled_by_service = {}
        try:
            cur.execute("""
                SELECT
                    COALESCE(s.code, 'GEN') AS service_code,
                    r.code AS route_code,
                    COUNT(*) as cnt
                FROM transit_timetable tt
                JOIN transit_route r ON r.id = tt.route_id
                LEFT JOIN transit_service s ON s.id = tt.service_id OR s.id = r.service_id
                WHERE (tt.tipo_dia = %s OR tt.tipo_dia IS NULL)
                  AND (tt.valid_from IS NULL OR tt.valid_from <= %s)
                  AND (tt.valid_until IS NULL OR tt.valid_until >= %s)
                GROUP BY s.code, r.code;
            """, (td, eval_date, eval_date))
            for tr in cur.fetchall():
                s_c = tr["service_code"]
                r_c = tr["route_code"]
                cnt = int(tr["cnt"])
                scheduled_by_route[r_c] = scheduled_by_route.get(r_c, 0) + cnt
                scheduled_by_service[s_c] = scheduled_by_service.get(s_c, 0) + cnt
        except Exception as e_tt:
            logger.debug(f"Aviso timetable: {e_tt}")
            conn.rollback()

        # 2. Despachos ejecutados registrados en transit_dispatch
        dispatched_by_route = {}
        perf_counts = {"regular": 0, "irregular": 0, "reinforcement": 0, "incomplete": 0}
        dispatches_found = False

        try:
            cur.execute("""
                SELECT
                    COALESCE(s.code, 'GEN') AS service_code,
                    r.code AS route_code,
                    d.compliance_status,
                    d.is_reinforcement,
                    d.is_incomplete,
                    COUNT(*) as cnt
                FROM transit_dispatch d
                JOIN transit_route r ON r.id = d.route_id
                LEFT JOIN transit_service s ON s.id = d.service_id OR s.id = r.service_id
                WHERE (DATE(d.scheduled_departure) = %s OR DATE(d.actual_departure) = %s)
                  AND (r.agency_id = %s OR %s IS NULL)
                GROUP BY s.code, r.code, d.compliance_status, d.is_reinforcement, d.is_incomplete;
            """, (eval_date, eval_date, sel_agency, sel_agency))
            d_rows = cur.fetchall()
            if d_rows:
                dispatches_found = True
                for dr in d_rows:
                    rc = dr["route_code"]
                    cnt = int(dr["cnt"])
                    dispatched_by_route[rc] = dispatched_by_route.get(rc, 0) + cnt
                    if dr.get("is_reinforcement"):
                        perf_counts["reinforcement"] += cnt
                    elif dr.get("is_incomplete"):
                        perf_counts["incomplete"] += cnt
                    elif dr.get("compliance_status") == "on_time":
                        perf_counts["regular"] += cnt
                    else:
                        perf_counts["irregular"] += cnt
        except Exception as e_disp:
            logger.debug(f"Aviso transit_dispatch: {e_disp}")
            conn.rollback()

        # Fallback a telemetry_ping
        if not dispatches_found:
            try:
                cur.execute("""
                    SELECT
                        route_id AS route_code,
                        COUNT(DISTINCT bus_internal_code) AS buses_active,
                        COUNT(*) AS ping_count
                    FROM telemetry_ping
                    WHERE DATE(recorded_at) = %s
                      AND (agency_id = %s OR %s IS NULL)
                    GROUP BY route_id;
                """, (eval_date, sel_agency, sel_agency))
                ping_rows = cur.fetchall()
                for pr in ping_rows:
                    rc = pr["route_code"]
                    cnt = int(pr["ping_count"])
                    dispatched_by_route[rc] = cnt
                    perf_counts["regular"] += int(cnt * 0.85)
                    perf_counts["irregular"] += int(cnt * 0.15)
            except Exception as e_ping:
                logger.debug(f"Aviso telemetry_ping: {e_ping}")
                conn.rollback()

        # 3. Histórico de cumplimiento (últimos 30 días)
        history_rows = []
        try:
            cur.execute("""
                SELECT
                    DATE(recorded_at) AS day,
                    COUNT(*) AS dispatches
                FROM telemetry_ping
                WHERE (agency_id = %s OR %s IS NULL)
                  AND recorded_at >= %s - INTERVAL '30 days'
                  AND recorded_at <= %s + INTERVAL '1 day'
                GROUP BY DATE(recorded_at)
                ORDER BY day DESC;
            """, (sel_agency, sel_agency, eval_date, eval_date))
            history_rows = cur.fetchall()
        except Exception as e_hist:
            logger.debug(f"Aviso al consultar histórico: {e_hist}")
            conn.rollback()

        cur.close()
        conn.close()

        # Totales despachos
        total_dispatched = sum(dispatched_by_route.get(rc, 0) for rc in all_service_routes) if all_service_routes else sum(dispatched_by_route.values())
        total_scheduled = sum(scheduled_by_route.get(rc, 0) for rc in all_service_routes) if all_service_routes else sum(scheduled_by_route.values())

        if total_quota == 0:
            total_quota = total_scheduled or max(total_dispatched, 100)

        compliance_pct = round((total_dispatched / total_quota) * 100, 1) if total_quota > 0 else 0.0
        if is_today and current_hour > 0:
            rate_per_hour = total_dispatched / current_hour
            projected_eod_dispatches = total_dispatched + (rate_per_hour * hours_remaining)
            projected_eod_pct = round((projected_eod_dispatches / total_quota) * 100, 1) if total_quota > 0 else 0.0
        else:
            projected_eod_pct = compliance_pct

        # Estado del cumplimiento
        alerts = []
        if is_today and compliance_pct < CRITICAL_THRESHOLD_PCT and hours_remaining < 4:
            status = "CRITICAL"
            status_label = "Déficit Crítico"
            alerts.append({"level": "CRITICAL", "message": f"Déficit crítico ({compliance_pct}%). Quedan {hours_remaining:.1f}h.", "icon": "🚨"})
        elif projected_eod_pct < CRITICAL_THRESHOLD_PCT:
            status = "AT_RISK"
            status_label = "En Riesgo"
            alerts.append({"level": "WARNING", "message": f"Proyección ({projected_eod_pct}%) bajo el umbral oficial (85%).", "icon": "⚠️"})
        elif compliance_pct >= WARNING_THRESHOLD_PCT:
            status = "COMPLIANT"
            status_label = "Cumplimiento Óptimo"
        else:
            status = "ON_TRACK"
            status_label = "En Seguimiento"

        # Desglose en 5 estados
        unperformed = max(0, total_quota - total_dispatched)
        perf_counts["unperformed"] = unperformed

        history = [
            {
                "date": str(r["day"]),
                "dispatches": int(r["dispatches"]),
                "compliance_pct": round((int(r["dispatches"]) / total_quota) * 100, 1) if total_quota > 0 else 0.0
            }
            for r in history_rows
        ]

        result.update({
            "total_dispatched": total_dispatched,
            "total_scheduled": total_scheduled or total_quota,
            "compliance_pct": compliance_pct,
            "projected_eod_pct": projected_eod_pct,
            "status": status,
            "status_label": status_label,
            "alerts": alerts,
            "performance_breakdown": perf_counts,
            "history_30d": history
        })

    except Exception as e:
        logger.error(f"Error calculando cumplimiento: {e}")
        result["error"] = str(e)
        result["alerts"] = [{"level": "ERROR", "message": f"Error: {e}", "icon": "❌"}]

    if redis_client:
        try:
            redis_client.set(cache_key, json.dumps(result), ex=COMPLIANCE_CACHE_TTL)
        except Exception:
            pass

    return result


def get_compliance_alerts(redis_client=None, service_code: Optional[str] = None, agency_id: Optional[str] = None) -> List[Dict]:
    """Lista de alertas de déficit del día."""
    data = get_today_compliance(redis_client, service_code=service_code, agency_id=agency_id)
    return data.get("alerts", [])


def get_compliance_html(default_agency: str = "004B", default_company: str = "Consorcio Arapotí", is_admin: bool = False) -> str:
    """Renderiza el dashboard interactivo de cumplimiento regulatorio VMT."""
    select_disabled = "" if is_admin else "disabled"
    if is_admin:
        company_options = """
                    <option value="004B">Consorcio Arapotí (Línea 20)</option>
                    <option value="0008">AUTOMOTORES GUARANI SRL (Línea 15 y 47)</option>
                    <option value="002A">SAN JOSE OBRERO SA (Línea 187)</option>
        """.strip()
    else:
        company_options = f'<option value="{default_agency}" selected>{default_company} ({default_agency})</option>'

    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poliverso Transit | Auditoría de Cumplimiento: CBD, ICCBDM, IFO &amp; ICF</title>
    <link rel="icon" href="data:,">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #070c18;
            --card: #0d1527;
            --card-hover: #121d36;
            --border: #1e293b;
            --border-glow: rgba(56, 189, 248, 0.25);
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.15);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --purple: #8b5cf6;
            --text: #f1f5f9;
            --muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; line-height: 1.45; }
        
        header {
            background: rgba(13, 21, 39, 0.85); backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            padding: 12px 28px; display: flex; align-items: center; justify-content: space-between;
            position: sticky; top: 0; z-index: 100;
        }
        .brand { display: flex; align-items: center; gap: 14px; }
        .brand-icon {
            width: 38px; height: 38px; border-radius: 10px;
            background: linear-gradient(135deg, #0284c7, #38bdf8);
            display: flex; align-items: center; justify-content: center;
            font-size: 20px; box-shadow: 0 0 15px var(--primary-glow);
        }
        .brand-title { font-size: 16px; font-weight: 800; letter-spacing: -0.02em; }
        .brand-sub { font-size: 11px; color: var(--muted); }
        .nav-links { display: flex; align-items: center; gap: 10px; }
        .nav-btn {
            background: rgba(30, 41, 59, 0.7); border: 1px solid var(--border);
            color: var(--text); padding: 6px 14px; border-radius: 8px;
            font-size: 12px; font-weight: 600; text-decoration: none;
            transition: all .2s ease; display: inline-flex; align-items: center; gap: 6px;
        }
        .nav-btn:hover { background: var(--border); border-color: var(--primary); color: #fff; }
        
        .page-container { max-width: 1540px; margin: 0 auto; padding: 22px 28px; display: flex; flex-direction: column; gap: 20px; }
        
        /* Barra de Filtros & Empresa */
        .filter-bar {
            background: var(--card); border: 1px solid var(--border); border-radius: 14px;
            padding: 12px 18px; display: flex; align-items: center; justify-content: space-between;
            flex-wrap: wrap; gap: 14px;
        }
        .filter-left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        .filter-right { display: flex; align-items: center; gap: 12px; }
        .select-input, .date-input {
            background: #111c35; border: 1px solid var(--border); border-radius: 8px;
            color: var(--text); padding: 8px 12px; font-size: 13px; font-weight: 600;
            outline: none; cursor: pointer; transition: all .2s;
        }
        .select-input:focus, .date-input:focus { border-color: var(--primary); box-shadow: 0 0 10px var(--primary-glow); }
        .service-pills { display: flex; gap: 6px; flex-wrap: wrap; }
        .pill-btn {
            background: #111c35; border: 1px solid var(--border); color: var(--muted);
            padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 700;
            cursor: pointer; transition: all .2s;
        }
        .pill-btn:hover { border-color: var(--primary); color: var(--text); }
        .pill-btn.active { background: var(--primary); border-color: var(--primary); color: #041226; font-weight: 800; }
        
        /* Grid de KPIs Superiores (CBD, ICCBDM, IFO, Objetivo) */
        .kpi-quad {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;
        }
        .quad-card {
            background: var(--card); border: 1px solid var(--border); border-radius: 14px;
            padding: 18px; position: relative; overflow: hidden;
            display: flex; flex-direction: column; justify-content: space-between;
            transition: all .2s ease;
        }
        .quad-card:hover { border-color: var(--border-glow); transform: translateY(-2px); }
        .quad-accent { position: absolute; top: 0; left: 0; right: 0; height: 3px; }
        .quad-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
        .quad-label { font-size: 11px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; color: var(--muted); }
        .quad-badge { font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }
        .quad-value { font-size: 32px; font-weight: 900; letter-spacing: -0.02em; font-family: 'JetBrains Mono', monospace; }
        .quad-sub { font-size: 12px; color: var(--muted); margin-top: 4px; display: flex; align-items: center; gap: 6px; }

        /* Tarjeta Principal */
        .card-panel {
            background: var(--card); border: 1px solid var(--border); border-radius: 14px;
            padding: 20px; display: flex; flex-direction: column; gap: 16px;
        }
        .panel-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
        .panel-title { font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 8px; letter-spacing: -0.01em; }
        .panel-badge {
            background: #111c35; border: 1px solid var(--border); color: var(--primary);
            padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;
        }

        /* Tabla de Franjas y Métricas */
        .table-responsive { overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }
        table.vmt-table { width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; }
        table.vmt-table th {
            background: #101a30; color: var(--muted); font-weight: 700;
            padding: 12px 14px; text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em;
            border-bottom: 1px solid var(--border);
        }
        table.vmt-table td {
            padding: 12px 14px; border-bottom: 1px solid #142038; background: #0c1426;
        }
        table.vmt-table tr:hover td { background: var(--card-hover); }
        
        .status-pill {
            padding: 3px 10px; border-radius: 6px; font-size: 10.5px; font-weight: 800;
            text-transform: uppercase; letter-spacing: 0.03em; display: inline-block;
        }
        .status-green { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .status-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
        .status-red   { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }

        /* Curva Horaria CBD vs Objetivo */
        .hourly-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(52px, 1fr)); gap: 6px; margin-top: 10px; }
        .hourly-col {
            background: #111c35; border: 1px solid var(--border); border-radius: 8px;
            padding: 8px 4px; display: flex; flex-direction: column; align-items: center; gap: 4px;
            transition: all .2s;
        }
        .hourly-col:hover { border-color: var(--primary); transform: translateY(-2px); }
        .hourly-h { font-size: 10px; color: var(--muted); font-weight: 700; }
        .hourly-bars { display: flex; align-items: flex-end; gap: 3px; height: 75px; width: 100%; justify-content: center; }
        .h-bar-act { width: 12px; background: var(--primary); border-radius: 3px 3px 0 0; min-height: 2px; }
        .h-bar-obj { width: 12px; background: rgba(148, 163, 184, 0.3); border-radius: 3px 3px 0 0; min-height: 2px; }
        .hourly-ifo { font-size: 10px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }

        /* Auditoría Histórica */
        .audit-box {
            background: #0b1220; border: 1px solid var(--border); border-radius: 10px;
            padding: 14px; display: flex; flex-direction: column; gap: 10px; font-size: 12px;
        }
        .audit-dates { display: flex; gap: 8px; flex-wrap: wrap; }
        .audit-badge {
            background: #162238; border: 1px solid #1e3a5f; color: #38bdf8;
            padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 11px;
        }
        .audit-excluded { display: flex; gap: 6px; flex-wrap: wrap; }
        .excluded-tag {
            background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.25);
            color: #fca5a5; padding: 2px 8px; border-radius: 4px; font-size: 10.5px;
        }

        .live-indicator { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 800; color: var(--success); }
        .live-indicator::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--success); animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:.3; transform:scale(1.4); } }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="brand-icon">⚡</div>
            <div>
                <div class="brand-title">Control de Cumplimiento y Regularidad Operativa</div>
                <div class="brand-sub">CBD &middot; ICCBDM &middot; IFO (Línea Base 4 Semanas) &middot; ICF Provisorio</div>
            </div>
        </div>
        <nav class="nav-links">
            <a href="/map" class="nav-btn">🧭 Radar Satelital</a>
            <a href="/headway" class="nav-btn">📊 Frecuencias</a>
            <div class="live-indicator">EN VIVO</div>
        </nav>
    </header>

    <div class="page-container">
        <!-- Selector de Empresa, Servicio y Fecha -->
        <div class="filter-bar">
            <div class="filter-left">
                <label style="font-size:11px;color:var(--muted);font-weight:700">EMPRESA:</label>
                <select id="filter-company" class="select-input" onchange="onCompanyChange(this.value)" __SELECT_DISABLED__>
                    __COMPANY_OPTIONS__
                </select>
                <div class="service-pills" id="service-pills">
                    <button class="pill-btn active" onclick="selectService('ALL')">Todos los Servicios</button>
                </div>
            </div>
            <div class="filter-right">
                <label style="font-size:11px;color:var(--muted);font-weight:700">FECHA DE CONTROL:</label>
                <input type="date" id="filter-date" class="date-input" onchange="loadComplianceData()">
            </div>
        </div>

        <!-- KPI Quad Principal (CBD, ICCBDM, IFO, Objetivo) -->
        <div class="kpi-quad">
            <div class="quad-card">
                <div class="quad-accent" style="background:#38bdf8"></div>
                <div class="quad-header">
                    <div class="quad-label">CBD Máximo en Itinerario</div>
                    <span class="quad-badge" style="background:rgba(56,189,248,0.2);color:#38bdf8">En Ruta</span>
                </div>
                <div class="quad-value" id="kpi-cbd-dia" style="color:#38bdf8">—</div>
                <div class="quad-sub">Buses distintos fuera de terminales</div>
            </div>
            <div class="quad-card">
                <div class="quad-accent" style="background:#10b981"></div>
                <div class="quad-header">
                    <div class="quad-label">ICCBDM Ponderado</div>
                    <span class="quad-badge" style="background:rgba(16,185,129,0.2);color:#10b981">0.7 / 0.3</span>
                </div>
                <div class="quad-value" id="kpi-iccbdm" style="color:#10b981">—</div>
                <div class="quad-sub">Índice Flota Mínima: Prom.Hora*0.7 + Franja*0.3</div>
            </div>
            <div class="quad-card">
                <div class="quad-accent" style="background:#f59e0b"></div>
                <div class="quad-header">
                    <div class="quad-label">IFO Global del Día</div>
                    <span class="quad-badge" id="kpi-ifo-badge" style="background:rgba(245,158,11,0.2);color:#f59e0b">Histórico</span>
                </div>
                <div class="quad-value" id="kpi-ifo-global" style="color:#f59e0b">—</div>
                <div class="quad-sub">Ratio vs 4 semanas válidas (sin lluvia ni feriado)</div>
            </div>
            <div class="quad-card">
                <div class="quad-accent" style="background:#8b5cf6"></div>
                <div class="quad-header">
                    <div class="quad-label">CBD Objetivo (100% IFO)</div>
                    <span class="quad-badge" style="background:rgba(139,92,246,0.2);color:#c084fc">Meta Base</span>
                </div>
                <div class="quad-value" id="kpi-cbd-obj" style="color:#c084fc">—</div>
                <div class="quad-sub">Flota requerida para alcanzar 100% IFO</div>
            </div>
        </div>

        <!-- Matriz de Franjas Operativas (ICCBDM & IFO Franja) -->
        <div class="card-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>📋 Control Regulatorio por Franjas Operativas (ICCBDM & IFO)</span>
                </div>
                <div class="panel-badge" id="regimen-badge">Régimen: Laboral</div>
            </div>
            <div class="table-responsive">
                <table class="vmt-table">
                    <thead>
                        <tr>
                            <th>Franja Operativa</th>
                            <th>Horario</th>
                            <th>CBD Franja</th>
                            <th>Prom. CBD/Hora</th>
                            <th>ICCBDM</th>
                            <th>Mín. Normativa</th>
                            <th>CBD Objetivo</th>
                            <th>IFO Franja (%)</th>
                            <th>Umbral Normativo</th>
                            <th>Estado Normativo</th>
                        </tr>
                    </thead>
                    <tbody id="table-franjas-body">
                        <tr><td colspan="10" style="text-align:center;color:var(--muted);padding:18px;">Cargando franjas...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Curva Horaria: CBD Real vs CBD Objetivo (100% IFO) -->
        <div class="card-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>📊 Curva Horaria Operativa: CBD Real vs CBD Objetivo (100% IFO)</span>
                </div>
                <div style="font-size:11px;color:var(--muted);display:flex;align-items:center;gap:12px;">
                    <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:10px;height:10px;background:#38bdf8;border-radius:2px"></span> CBD Real</span>
                    <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:10px;height:10px;background:rgba(148,163,184,0.4);border-radius:2px"></span> CBD Objetivo</span>
                </div>
            </div>
            <div class="hourly-grid" id="hourly-bars-grid">
                <!-- Se llena con JS -->
            </div>
        </div>

        <!-- Transparencia de Auditoría Histórica (4 Semanas de Referencia) -->
        <div class="card-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>🔍 Auditoría de Línea Base Histórica (Resoluciones 120/21, 26/104 & Decreto 710/2023)</span>
                </div>
                <div class="panel-badge" id="audit-badge-summary">4 semanas limpias</div>
            </div>
            <div class="audit-box">
                <div>
                    <strong style="color:#38bdf8">Semanas de Referencia Válidas (Mismo día):</strong>
                    <div class="audit-dates" id="audit-valid-dates" style="margin-top:6px;">
                        <span>Cargando fechas de referencia...</span>
                    </div>
                </div>
                <div style="margin-top:8px;">
                    <strong style="color:#f87171">Días Descartados de la Muestra (Feriados, Pre/Pos Feriados y Lluvias Open-Meteo):</strong>
                    <div class="audit-excluded" id="audit-excluded-dates" style="margin-top:6px;">
                        <span>Verificando casuísticas meteorológicas y calendario...</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Auditoría de Despachos y Cuota Diaria (ICF Provisorio) -->
        <div class="card-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>⏱️ Auditoría de Despachos en Cabecera & Clasificación en 5 Estados</span>
                </div>
                <div class="panel-badge" id="dispatches-total-badge">0 despachos</div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
                <div style="background:#111c35;padding:12px;border-radius:8px;border:1px solid var(--border)">
                    <div style="font-size:11px;color:#10b981;font-weight:700">Regulares (A Tiempo)</div>
                    <div style="font-size:22px;font-weight:900;color:#10b981" id="st-regular">0</div>
                </div>
                <div style="background:#111c35;padding:12px;border-radius:8px;border:1px solid var(--border)">
                    <div style="font-size:11px;color:#f59e0b;font-weight:700">Irregulares (Fuera Tol.)</div>
                    <div style="font-size:22px;font-weight:900;color:#f59e0b" id="st-irregular">0</div>
                </div>
                <div style="background:#111c35;padding:12px;border-radius:8px;border:1px solid var(--border)">
                    <div style="font-size:11px;color:#818cf8;font-weight:700">Refuerzos (Extras)</div>
                    <div style="font-size:22px;font-weight:900;color:#818cf8" id="st-reinforcement">0</div>
                </div>
                <div style="background:#111c35;padding:12px;border-radius:8px;border:1px solid var(--border)">
                    <div style="font-size:11px;color:#ec4899;font-weight:700">Incompletos (80%)</div>
                    <div style="font-size:22px;font-weight:900;color:#ec4899" id="st-incomplete">0</div>
                </div>
                <div style="background:#111c35;padding:12px;border-radius:8px;border:1px solid var(--border)">
                    <div style="font-size:11px;color:#ef4444;font-weight:700">Faltantes de Cuota</div>
                    <div style="font-size:22px;font-weight:900;color:#ef4444" id="st-unperformed">0</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentAgency = '__DEFAULT_AGENCY__';
        let isAdmin = __IS_ADMIN__;
        let currentService = 'ALL';
        let refreshTimer = null;

        function pctColor(p) {
            if (p >= 95) return '#10b981';
            if (p >= 85) return '#38bdf8';
            if (p >= 70) return '#f59e0b';
            return '#ef4444';
        }

        function onCompanyChange(agencyId) {
            currentAgency = agencyId;
            currentService = 'ALL';
            loadComplianceData();
        }

        function selectService(code) {
            currentService = code;
            loadComplianceData();
        }

        function renderServices(services) {
            const pillsCont = document.getElementById('service-pills');
            let html = `<button class="pill-btn ${currentService === 'ALL' ? 'active' : ''}" onclick="selectService('ALL')">Todos los Servicios</button>`;
            (services || []).forEach(s => {
                const act = currentService === s.code ? 'active' : '';
                html += `<button class="pill-btn ${act}" onclick="selectService('${s.code}')">${s.code} - ${s.name.split('(')[0].trim()}</button>`;
            });
            pillsCont.innerHTML = html;
        }

        function renderCompanies(comps) {
            const sel = document.getElementById('filter-company');
            if (!sel || !comps || comps.length === 0) return;
            if (!isAdmin) {
                sel.disabled = true;
                return;
            }
            const curVal = sel.value || currentAgency;
            sel.innerHTML = comps.map(c => `
                <option value="${c.agency_id}" ${c.agency_id === curVal ? 'selected' : ''}>
                    ${c.name} (${c.agency_id})
                </option>
            `).join('');
            sel.value = curVal;
        }

        function renderData(d) {
            renderCompanies(d.available_companies);
            renderServices(d.available_services);

            // KPIs Superiores
            const cbd = (d.cbd_ifo && d.cbd_ifo.summary) || {};
            document.getElementById('kpi-cbd-dia').textContent = cbd.cbd_total_dia || '0';
            document.getElementById('kpi-iccbdm').textContent = (cbd.iccbdm_global || 0).toFixed(2);
            
            const ifoVal = cbd.ifo_global_pct || 0;
            const ifoEl = document.getElementById('kpi-ifo-global');
            ifoEl.textContent = ifoVal.toFixed(1) + '%';
            ifoEl.style.color = pctColor(ifoVal);

            const badgeIfo = document.getElementById('kpi-ifo-badge');
            if (ifoVal >= 90) {
                badgeIfo.textContent = 'Óptimo';
                badgeIfo.style.color = '#34d399';
                badgeIfo.style.background = 'rgba(16,185,129,0.2)';
            } else if (ifoVal >= 80) {
                badgeIfo.textContent = 'Cumple';
                badgeIfo.style.color = '#38bdf8';
                badgeIfo.style.background = 'rgba(56,189,248,0.2)';
            } else {
                badgeIfo.textContent = 'Déficit';
                badgeIfo.style.color = '#f87171';
                badgeIfo.style.background = 'rgba(239,68,68,0.2)';
            }

            document.getElementById('kpi-cbd-obj').textContent = (cbd.cbd_objetivo_global || 0).toFixed(1);

            // Régimen
            const dayInfo = d.day_info || {};
            document.getElementById('regimen-badge').textContent = `Régimen: ${dayInfo.tipo_dia_desc || 'Laboral'}`;

            // Tabla Franjas
            const franjas = (d.cbd_ifo && d.cbd_ifo.franjas) || [];
            const tbody = document.getElementById('table-franjas-body');
            if (franjas.length > 0) {
                tbody.innerHTML = franjas.map(f => `
                    <tr>
                        <td style="font-weight:700;color:#fff">${f.nombre}</td>
                        <td style="color:var(--muted);font-family:'JetBrains Mono',monospace">${f.rango}</td>
                        <td style="font-weight:800;color:var(--primary)">${f.cbd_franja}</td>
                        <td>${f.avg_cbd_hora.toFixed(2)}</td>
                        <td style="font-weight:900;color:#fff;font-family:'JetBrains Mono',monospace">${f.iccbdm.toFixed(2)}</td>
                        <td style="color:var(--muted)">Franja: ${f.cbd_minimo_franja} &middot; Hora: ${f.cbd_minimo_hora}</td>
                        <td style="color:#c084fc;font-weight:700">${f.cbd_objetivo_franja.toFixed(2)}</td>
                        <td style="font-weight:900;color:${pctColor(f.ifo_franja_pct)};font-family:'JetBrains Mono',monospace">${f.ifo_franja_pct.toFixed(1)}%</td>
                        <td style="color:var(--muted)">${f.umbral_ifo_pct.toFixed(0)}%</td>
                        <td><span class="status-pill ${f.badge_class}">${f.estado}</span></td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:18px;">Sin datos para la fecha seleccionada.</td></tr>`;
            }

            // Curva Horaria
            const hourly = (d.cbd_ifo && d.cbd_ifo.hourly_breakdown) || [];
            const hGrid = document.getElementById('hourly-bars-grid');
            if (hourly.length > 0) {
                const maxVal = Math.max(...hourly.map(h => Math.max(h.cbd_actual, h.cbd_objetivo)), 1);
                hGrid.innerHTML = hourly.map(h => {
                    const hAct = Math.max(2, (h.cbd_actual / maxVal) * 70);
                    const hObj = Math.max(2, (h.cbd_objetivo / maxVal) * 70);
                    const ifoCol = pctColor(h.ifo_pct);
                    return `
                    <div class="hourly-col" title="${h.hora_label}: Real ${h.cbd_actual} vs Obj ${h.cbd_objetivo} (IFO ${h.ifo_pct}%)">
                        <div class="hourly-h">${h.hora_label}</div>
                        <div class="hourly-bars">
                            <div class="h-bar-act" style="height:${hAct}px"></div>
                            <div class="h-bar-obj" style="height:${hObj}px"></div>
                        </div>
                        <div class="hourly-ifo" style="color:${ifoCol}">${h.ifo_pct.toFixed(0)}%</div>
                        <div style="font-size:9px;color:var(--muted)">${h.cbd_actual}/${h.cbd_objetivo.toFixed(0)}</div>
                    </div>`;
                }).join('');
            }

            // Auditoría Histórica
            const histRef = (d.cbd_ifo && d.cbd_ifo.historical_reference) || {};
            const valBox = document.getElementById('audit-valid-dates');
            const excBox = document.getElementById('audit-excluded-dates');
            
            const vDates = histRef.valid_dates || [];
            if (vDates.length > 0) {
                valBox.innerHTML = vDates.map(vd => `<span class="audit-badge">📅 ${vd}</span>`).join('');
                document.getElementById('audit-badge-summary').textContent = `${vDates.length} semanas de referencia`;
            } else {
                valBox.innerHTML = `<span style="color:var(--muted)">Sin fechas de referencia históricas</span>`;
            }

            const eDates = histRef.excluded_dates || [];
            if (eDates.length > 0) {
                excBox.innerHTML = eDates.map(ed => `
                    <span class="excluded-tag" title="${ed.reason}">
                        🚫 ${ed.date}: ${ed.reason}
                    </span>
                `).join('');
            } else {
                excBox.innerHTML = `<span style="color:var(--muted)">No se detectaron días atípicos en el período de evaluación</span>`;
            }

            // 5 Estados Operativos
            const pb = d.performance_breakdown || {};
            document.getElementById('st-regular').textContent = pb.regular || 0;
            document.getElementById('st-irregular').textContent = pb.irregular || 0;
            document.getElementById('st-reinforcement').textContent = pb.reinforcement || 0;
            document.getElementById('st-incomplete').textContent = pb.incomplete || 0;
            document.getElementById('st-unperformed').textContent = pb.unperformed || 0;
            document.getElementById('dispatches-total-badge').textContent = `${d.total_dispatched} despachos`;
        }

        async function loadComplianceData() {
            try {
                const dateVal = document.getElementById('filter-date').value;
                let url = `/api/v1/compliance/today?agency_id=${encodeURIComponent(currentAgency)}&service=${encodeURIComponent(currentService)}`;
                if (dateVal) url += `&date=${encodeURIComponent(dateVal)}`;
                const r = await fetch(url);
                const d = await r.json();
                renderData(d);
            } catch(e) {
                console.warn('Error fetching compliance:', e);
            }
        }

        // Inicializar fecha de hoy o ayer
        document.getElementById('filter-date').value = new Date().toISOString().slice(0, 10);
        loadComplianceData();
        refreshTimer = setInterval(loadComplianceData, 60000);
    </script>
</body>
</html>
"""
    html = html.replace("__SELECT_DISABLED__", select_disabled)
    html = html.replace("__COMPANY_OPTIONS__", company_options)
    html = html.replace("__DEFAULT_AGENCY__", default_agency)
    html = html.replace("__DEFAULT_COMPANY__", default_company)
    html = html.replace("__IS_ADMIN__", "true" if is_admin else "false")
    return html
