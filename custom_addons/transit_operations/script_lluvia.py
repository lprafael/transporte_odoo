# -*- coding: utf-8 -*-
"""
Script para descarga y almacenamiento de datos de lluvia del Departamento Central, Paraguay (Open-Meteo)
y gestión de Días Atípicos (Lluvias, Feriados, Pre/Pos-Feriados) en la BD de transporte_odoo (flota_db).
========================================================================================================
Trasladado desde cbd_monitor/script_lluvia.py y adaptado a transporte_odoo (flota_db):
  1. Consulta las 19 localidades del Departamento Central en Open-Meteo:
     - Archive ERA5 API (https://archive-api.open-meteo.com/v1/era5) para fechas históricas.
     - Forecast API (https://api.open-meteo.com/v1/forecast) para fechas recientes / hoy.
  2. Registra en la tabla `transit_rain_casuistica` (homóloga a `control_metricas.t_casuisticas_lluvia`):
     - Eventos horarios donde la lluvia máxima en Central supere UMBRAL_REGISTRO (2.5 mm/h),
       marcando `es_lluvia_intensa = True` cuando >= 15.0 mm/h.
     - Resumen acumulado diario por localidad máxima cuando el acumulado diario supere 5.0 mm.
  3. Registra en la tabla `transit_atypical_day` (homóloga a `control_metricas.dias_atipicos`):
     - Días de lluvia (`tipo_atipico = 'LLUVIA'`, `factor_exigencia = 0.50`, `descartar_historico = True`)
       cuando el acumulado diario en el Departamento Central supere 5.0 mm.
     - Días Feriados (`FERIADO_LAB` factor 0.30, `FERIADO_SAB` factor 0.50) y Pre/Pos-Feriados
       (`PRE_POS_FERIADO` factor 0.70, `descartar_historico = True`) sincronizados desde `transit_holiday`
       y `public.feriados` (BD CID).

CÓMO EJECUTAR EL SCRIPT:
------------------------
  # 1. Por defecto (descarga ayer y hoy + sincroniza feriados y días atípicos):
  python script_lluvia.py

  # 2. Fecha específica:
  python script_lluvia.py --fecha 2026-11-05

  # 3. Rango de fechas:
  python script_lluvia.py --inicio 2026-09-01 --fin 2026-11-12
"""

import os
import math
import logging
import argparse
from datetime import datetime, timedelta, date, time
from typing import List, Dict, Any, Optional, Tuple

import requests
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("script_lluvia")

# ==========================
# CONFIGURACIÓN GENERAL
# ==========================

OPENMETEO_ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "America/Asuncion"

# Coordenadas de los 19 distritos del Departamento Central, Paraguay (idéntico a cbd_monitor/script_lluvia.py)
LOCATIONS = [
    {"name": "Areguá",               "lat": -25.3125, "lon": -57.3847},
    {"name": "Capiatá",              "lat": -25.3552, "lon": -57.4454},
    {"name": "Fernando de la Mora",  "lat": -25.3386, "lon": -57.5217},
    {"name": "Guarambaré",           "lat": -25.4910, "lon": -57.4557},
    {"name": "Itá",                  "lat": -25.5005, "lon": -57.3672},
    {"name": "Itauguá",              "lat": -25.3926, "lon": -57.3542},
    {"name": "J. Augusto Saldívar",  "lat": -25.4446, "lon": -57.4344},
    {"name": "Lambaré",              "lat": -25.3468, "lon": -57.6065},
    {"name": "Limpio",               "lat": -25.1661, "lon": -57.4856},
    {"name": "Luque",                "lat": -25.2700, "lon": -57.4872},
    {"name": "Mariano Roque Alonso", "lat": -25.2079, "lon": -57.5320},
    {"name": "Ñemby",                "lat": -25.3949, "lon": -57.5357},
    {"name": "Nueva Italia",         "lat": -25.6108, "lon": -57.4656},
    {"name": "San Antonio",          "lat": -25.4213, "lon": -57.5473},
    {"name": "San Lorenzo",          "lat": -25.3397, "lon": -57.5088},
    {"name": "Villa Elisa",          "lat": -25.3676, "lon": -57.5927},
    {"name": "Villeta",              "lat": -25.4949, "lon": -57.5584},
    {"name": "Ypacaraí",             "lat": -25.4078, "lon": -57.2889},
    {"name": "Ypané",                "lat": -25.4500, "lon": -57.5300},
]

# Umbral horario para registrar evento en transit_rain_casuistica (mm/h)
UMBRAL_REGISTRO_HORA = 2.5
# Umbral horario para considerar "lluvia intensa" (mm/h)
UMBRAL_LLUVIA_INTENSA = 15.0
# Umbral acumulado diario para considerar Día Atípico de Lluvia con factor 0.50 (mm/día)
UMBRAL_DIA_ATIPICO_LLUVIA = 5.0

# Configuración Base de Datos Local (flota_db en transporte_odoo)
PG_CONFIG = {
    "host": os.getenv("PG_HOST", os.getenv("HOST", "db")),
    "port": int(os.getenv("PG_PORT", os.getenv("PORT", 5432))),
    "dbname": os.getenv("PG_DB", os.getenv("DB_NAME", "flota_db")),
    "user": os.getenv("PG_USER", os.getenv("USER", "odoo")),
    "password": os.getenv("PG_PASS", os.getenv("PASSWORD", "odoo_password")),
}

# Configuración Base de Datos CID (VMT Paraguay) para respaldo/sincronización
CID_CONFIG = {
    "host": os.getenv("CID_DB_HOST", "168.90.177.232"),
    "port": int(os.getenv("CID_DB_PORT", 2024)),
    "dbname": os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid"),
    "user": os.getenv("CID_DB_USER", "FPorta"),
    "password": os.getenv("CID_DB_PASS", "portaf2024"),
}


def get_pg_connection():
    """Conexión a la BD de transporte_odoo (flota_db)."""
    hosts_to_try = [PG_CONFIG["host"], "db", "localhost", "127.0.0.1"]
    last_err = None
    for h in dict.fromkeys(hosts_to_try):
        try:
            return psycopg2.connect(
                host=h,
                port=PG_CONFIG["port"],
                dbname=PG_CONFIG["dbname"],
                user=PG_CONFIG["user"],
                password=PG_CONFIG["password"],
                connect_timeout=4,
            )
        except Exception as e:
            last_err = e
    raise last_err


def get_cid_connection():
    """Conexión opcional a la BD CID (VMT) para sincronizar feriados y días atípicos históricos."""
    try:
        return psycopg2.connect(
            host=CID_CONFIG["host"],
            port=CID_CONFIG["port"],
            dbname=CID_CONFIG["dbname"],
            user=CID_CONFIG["user"],
            password=CID_CONFIG["password"],
            connect_timeout=4,
        )
    except Exception as e:
        logger.debug("Aviso: no se pudo conectar a CID DB: %s", e)
        return None


def ensure_tables_exist(conn):
    """
    Asegura que las tablas `transit_rain_casuistica` y `transit_atypical_day` existan en `flota_db`
    incluso si el script se ejecuta por CLI antes de actualizar el módulo de Odoo.
    """
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transit_rain_casuistica (
            id SERIAL PRIMARY KEY,
            fecha_evento DATE NOT NULL,
            hora_inicio VARCHAR(16) NOT NULL,
            hora_fin VARCHAR(16) NOT NULL,
            es_resumen_diario BOOLEAN DEFAULT FALSE,
            distrito_max VARCHAR(128),
            latitud DOUBLE PRECISION,
            longitud DOUBLE PRECISION,
            mm_caidos NUMERIC(8, 2) NOT NULL DEFAULT 0.0,
            es_lluvia_intensa BOOLEAN DEFAULT FALSE,
            registro_comprobado BOOLEAN DEFAULT FALSE,
            factor_ajuste NUMERIC(4, 2) DEFAULT 0.50,
            fuente_registro VARCHAR(64) DEFAULT 'Open-Meteo',
            notas TEXT,
            create_uid INTEGER,
            create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            write_uid INTEGER,
            write_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            UNIQUE(fecha_evento, hora_inicio, hora_fin)
        );
        CREATE INDEX IF NOT EXISTS idx_transit_rain_casuistica_fecha ON transit_rain_casuistica(fecha_evento);

        CREATE TABLE IF NOT EXISTS transit_atypical_day (
            id SERIAL PRIMARY KEY,
            fecha DATE NOT NULL,
            tipo_atipico VARCHAR(32) NOT NULL,
            factor_exigencia NUMERIC(4, 2) NOT NULL DEFAULT 0.50,
            descartar_historico BOOLEAN DEFAULT TRUE,
            fuente_dato VARCHAR(64) DEFAULT 'Open-Meteo',
            distrito_max VARCHAR(128),
            mm_caidos NUMERIC(8, 2) DEFAULT 0.0,
            observacion TEXT,
            id_tipo_dia_aplicable INTEGER,
            active BOOLEAN DEFAULT TRUE,
            create_uid INTEGER,
            create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            write_uid INTEGER,
            write_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            UNIQUE(fecha, tipo_atipico)
        );
        CREATE INDEX IF NOT EXISTS idx_transit_atypical_day_fecha ON transit_atypical_day(fecha);
    """)
    conn.commit()
    cur.close()


# ==========================
# CONSULTA OPEN-METEO (19 DISTRITOS DE CENTRAL)
# ==========================

def _call_openmeteo_endpoint(url: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
    lats = ",".join(str(loc["lat"]) for loc in LOCATIONS)
    lons = ",".join(str(loc["lon"]) for loc in LOCATIONS)
    params = {
        "latitude": lats,
        "longitude": lons,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "hourly": "rain,precipitation",
        "timezone": TIMEZONE,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def fetch_rain_data(start_date: date, end_date: date) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Llama a la API de Open-Meteo para el rango [start_date, end_date] en los 19 distritos de Central.
    Utiliza ERA5 Archive para fechas históricas y Forecast API para fechas recientes (últimos 5 días / hoy).
    Retorna:
      - hourly_records: lista de dicts por cada hora con {dt, rain_mm, location_name, lat, lon}
      - daily_summaries: lista de dicts por cada día con {date, max_daily_mm, location_name, lat, lon}
    """
    today = date.today()
    era5_cutoff = today - timedelta(days=5)

    hourly_by_iso: Dict[str, Dict[str, Any]] = {}
    daily_by_date_loc: Dict[Tuple[date, int], float] = {}

    def _process_api_response(data_list: List[Dict[str, Any]]):
        if not data_list or "hourly" not in data_list[0]:
            return
        times = data_list[0]["hourly"].get("time") or []
        num_hours = len(times)

        rains_by_loc = []
        for d in data_list:
            h_obj = d.get("hourly", {})
            # Preferimos 'rain', y si es None usamos 'precipitation'
            r_arr = h_obj.get("rain") or []
            p_arr = h_obj.get("precipitation") or []
            merged = []
            for idx in range(num_hours):
                val_r = r_arr[idx] if idx < len(r_arr) else None
                val_p = p_arr[idx] if idx < len(p_arr) else None
                val = val_r if val_r is not None else (val_p if val_p is not None else 0.0)
                merged.append(float(val))
            rains_by_loc.append(merged)

        for i, t_str in enumerate(times):
            dt = datetime.fromisoformat(t_str)
            d_ev = dt.date()
            max_rain = 0.0
            max_loc_idx = 0
            for loc_idx, r_list in enumerate(rains_by_loc):
                if i < len(r_list):
                    val = r_list[i]
                    daily_by_date_loc[(d_ev, loc_idx)] = daily_by_date_loc.get((d_ev, loc_idx), 0.0) + val
                    if val > max_rain:
                        max_rain = val
                        max_loc_idx = loc_idx

            loc_info = LOCATIONS[max_loc_idx] if max_loc_idx < len(LOCATIONS) else LOCATIONS[0]
            existing = hourly_by_iso.get(t_str)
            if not existing or max_rain > existing["rain_mm"]:
                hourly_by_iso[t_str] = {
                    "dt": dt,
                    "rain_mm": round(max_rain, 2),
                    "location_name": loc_info["name"],
                    "lat": loc_info["lat"],
                    "lon": loc_info["lon"],
                }

    # 1. Tramo histórico con ERA5
    if start_date <= era5_cutoff:
        era5_end = min(end_date, era5_cutoff)
        try:
            data_era5 = _call_openmeteo_endpoint(OPENMETEO_ERA5_URL, start_date, era5_end)
            _process_api_response(data_era5)
        except Exception as e:
            logger.warning("Aviso en consulta ERA5 (%s a %s): %s. Intentando Forecast API...", start_date, era5_end, e)
            try:
                data_fc = _call_openmeteo_endpoint(OPENMETEO_FORECAST_URL, start_date, era5_end)
                _process_api_response(data_fc)
            except Exception as e2:
                logger.error("Error en respaldo Forecast API: %s", e2)

    # 2. Tramo reciente con Forecast API
    if end_date > era5_cutoff:
        fc_start = max(start_date, era5_cutoff + timedelta(days=1))
        if fc_start <= end_date:
            try:
                data_fc = _call_openmeteo_endpoint(OPENMETEO_FORECAST_URL, fc_start, end_date)
                _process_api_response(data_fc)
            except Exception as e:
                logger.error("Error consultando Open-Meteo Forecast (%s a %s): %s", fc_start, end_date, e)

    hourly_records = sorted(hourly_by_iso.values(), key=lambda x: x["dt"])

    # Consolidar el acumulado diario máximo entre los 19 distritos
    daily_summaries = []
    cur_d = start_date
    while cur_d <= end_date:
        best_mm = 0.0
        best_loc = LOCATIONS[0]
        for loc_idx, loc in enumerate(LOCATIONS):
            tot_mm = daily_by_date_loc.get((cur_d, loc_idx), 0.0)
            if tot_mm > best_mm:
                best_mm = tot_mm
                best_loc = loc
        daily_summaries.append({
            "date": cur_d,
            "max_daily_mm": round(best_mm, 2),
            "location_name": best_loc["name"],
            "lat": best_loc["lat"],
            "lon": best_loc["lon"],
        })
        cur_d += timedelta(days=1)

    return hourly_records, daily_summaries


# ==========================
# PERSISTENCIA EN FLOTA_DB (transporte_odoo)
# ==========================

def insert_rain_and_atypical_into_db(
    hourly_records: List[Dict[str, Any]],
    daily_summaries: List[Dict[str, Any]],
    conn=None,
) -> Dict[str, int]:
    """
    Inserta/actualiza en `flota_db`:
      1. `transit_rain_casuistica`:
         - Un registro por cada hora con lluvia > UMBRAL_REGISTRO_HORA (2.5 mm/h).
         - Un registro resumen diario (00:00 a 23:59:59) cuando el acumulado diario > 5.0 mm.
      2. `transit_atypical_day`:
         - Un registro `LLUVIA` con `factor_exigencia = 0.50` y `descartar_historico = True`
           por cada fecha cuyo acumulado diario en Central supere 5.0 mm.
    """
    own_conn = False
    if conn is None:
        conn = get_pg_connection()
        own_conn = True

    ensure_tables_exist(conn)
    cur = conn.cursor()

    count_hourly = 0
    count_daily_rain = 0
    count_atypical = 0

    upsert_rain_sql = """
        INSERT INTO transit_rain_casuistica (
            fecha_evento, hora_inicio, hora_fin, es_resumen_diario,
            distrito_max, latitud, longitud, mm_caidos,
            es_lluvia_intensa, registro_comprobado, factor_ajuste,
            fuente_registro, notas, write_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (fecha_evento, hora_inicio, hora_fin)
        DO UPDATE SET
            es_resumen_diario = EXCLUDED.es_resumen_diario,
            distrito_max = EXCLUDED.distrito_max,
            latitud = EXCLUDED.latitud,
            longitud = EXCLUDED.longitud,
            mm_caidos = EXCLUDED.mm_caidos,
            es_lluvia_intensa = EXCLUDED.es_lluvia_intensa,
            factor_ajuste = EXCLUDED.factor_ajuste,
            notas = EXCLUDED.notas,
            write_date = NOW();
    """

    upsert_atypical_sql = """
        INSERT INTO transit_atypical_day (
            fecha, tipo_atipico, factor_exigencia, descartar_historico,
            fuente_dato, distrito_max, mm_caidos, observacion, active, write_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
        ON CONFLICT (fecha, tipo_atipico)
        DO UPDATE SET
            factor_exigencia = EXCLUDED.factor_exigencia,
            descartar_historico = EXCLUDED.descartar_historico,
            fuente_dato = EXCLUDED.fuente_dato,
            distrito_max = EXCLUDED.distrito_max,
            mm_caidos = EXCLUDED.mm_caidos,
            observacion = EXCLUDED.observacion,
            active = TRUE,
            write_date = NOW();
    """

    # 1. Insertar registros horarios que superen UMBRAL_REGISTRO_HORA (2.5 mm/h)
    for rec in hourly_records:
        rain_mm = float(rec["rain_mm"])
        if rain_mm <= UMBRAL_REGISTRO_HORA:
            continue

        dt = rec["dt"]
        fecha_evento = dt.date()
        hora_inicio = dt.strftime("%H:%M:%S")
        hora_fin = (dt + timedelta(hours=1)).strftime("%H:%M:%S")
        es_intensa = rain_mm >= UMBRAL_LLUVIA_INTENSA
        loc_name = rec.get("location_name") or "Central"
        notas = f"Lluvia MAX Central: {rain_mm:.2f} mm ({loc_name})"

        cur.execute(
            upsert_rain_sql,
            (
                fecha_evento,
                hora_inicio,
                hora_fin,
                False,
                loc_name,
                rec.get("lat"),
                rec.get("lon"),
                rain_mm,
                es_intensa,
                False,
                0.50,
                "Open-Meteo",
                notas,
            ),
        )
        count_hourly += 1

    # 2. Insertar resumen diario y Día Atípico cuando el acumulado diario supere 5.0 mm
    for d_sum in daily_summaries:
        max_mm = float(d_sum["max_daily_mm"])
        if max_mm <= UMBRAL_DIA_ATIPICO_LLUVIA:
            continue

        fecha_ev = d_sum["date"]
        loc_name = d_sum["location_name"]
        lat = d_sum["lat"]
        lon = d_sum["lon"]
        es_intensa_dia = max_mm >= UMBRAL_LLUVIA_INTENSA
        notas_dia = (
            f"Acumulado diario ERA5: {max_mm:.2f} mm en {loc_name} "
            f"(lat {lat}, lon {lon}). Referencia para días atípicos."
        )

        cur.execute(
            upsert_rain_sql,
            (
                fecha_ev,
                "00:00:00",
                "23:59:59",
                True,
                loc_name,
                lat,
                lon,
                max_mm,
                es_intensa_dia,
                True,
                0.50,
                "Open-Meteo",
                notas_dia,
            ),
        )
        count_daily_rain += 1

        obs_atipico = f"Lluvia acumulada > 5mm ({max_mm:.2f} mm en {loc_name})"
        cur.execute(
            upsert_atypical_sql,
            (
                fecha_ev,
                "LLUVIA",
                0.50,
                True,
                "Open-Meteo",
                loc_name,
                max_mm,
                obs_atipico,
            ),
        )
        count_atypical += 1

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

    logger.info(
        "Almacenados en flota_db: %d eventos horarios en transit_rain_casuistica, "
        "%d acumulados diarios (>5mm) y %d días atípicos de lluvia en transit_atypical_day.",
        count_hourly, count_daily_rain, count_atypical
    )
    return {
        "hourly_inserted": count_hourly,
        "daily_rain_inserted": count_daily_rain,
        "atypical_rain_inserted": count_atypical,
    }


def sync_holidays_and_cid_atypical_days(conn=None) -> Dict[str, int]:
    """
    Sincroniza en `flota_db` (`transit_holiday`, `transit_atypical_day` y `transit_rain_casuistica`):
      1. Feriados nacionales desde `public.feriados` (CID DB) y `transit_holiday` (flota_db),
         generando automáticamente los registros en `transit_atypical_day` para:
           - `FERIADO_LAB` (factor 0.30) o `FERIADO_SAB` (factor 0.50)
           - `PRE_POS_FERIADO` (factor 0.70, día anterior y día posterior)
      2. Registros existentes de `control_metricas.dias_atipicos` y `control_metricas.t_casuisticas_lluvia`
         desde la BD CID para mantener paridad 100% con `cbd_monitor`.
    """
    own_conn = False
    if conn is None:
        conn = get_pg_connection()
        own_conn = True

    ensure_tables_exist(conn)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    feriados_map: Dict[date, str] = {}
    synced_cid_atypical = 0
    synced_cid_rain = 0

    # 1. Leer feriados locales en transit_holiday
    try:
        cur.execute("SELECT date, name FROM transit_holiday WHERE active = TRUE;")
        for r in cur.fetchall():
            if r["date"]:
                feriados_map[r["date"]] = r["name"] or "Feriado Nacional"
    except Exception as e:
        logger.debug("Aviso leyendo transit_holiday: %s", e)
        conn.rollback()

    # 2. Sincronizar desde BD CID si está disponible
    conn_cid = get_cid_connection()
    if conn_cid:
        try:
            cur_cid = conn_cid.cursor(cursor_factory=RealDictCursor)

            # 2a. Feriados de public.feriados
            cur_cid.execute("SELECT fecha, descripcion FROM public.feriados WHERE fecha IS NOT NULL;")
            for r in cur_cid.fetchall():
                f_dt = r["fecha"]
                f_desc = r.get("descripcion") or "Feriado Oficial"
                feriados_map[f_dt] = f_desc
                if 2024 <= f_dt.year <= 2030:
                    cur.execute("SELECT id FROM transit_holiday WHERE date = %s LIMIT 1;", (f_dt,))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO transit_holiday (name, date, is_national, active, create_date, write_date)
                            VALUES (%s, %s, TRUE, TRUE, NOW(), NOW());
                        """, (f_desc, f_dt))

            # 2b. Días atípicos de control_metricas.dias_atipicos
            cur_cid.execute("""
                SELECT fecha, tipo_atipico, factor_exigencia, descartar_historico,
                       fuente_dato, observacion, id_tipo_dia_aplicable
                FROM control_metricas.dias_atipicos
                WHERE fecha >= '2025-01-01' AND fecha <= '2030-12-31';
            """)
            for r in cur_cid.fetchall():
                obs = r.get("observacion") or ""
                tipo = r.get("tipo_atipico") or "OTRO"
                # Para lluvias > 5mm, siempre descartar del histórico de las 4 semanas de referencia
                descartar = True if tipo == "LLUVIA" else bool(r.get("descartar_historico", True))
                raw_fuente = (r.get("fuente_dato") or "").strip()
                clean_fuente = "Monitoreo Operativo" if raw_fuente.upper() in ("", "CID", "CID DB", "VMT", "CCM") else raw_fuente
                cur.execute("""
                    INSERT INTO transit_atypical_day (
                        fecha, tipo_atipico, factor_exigencia, descartar_historico,
                        fuente_dato, observacion, id_tipo_dia_aplicable, active, write_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
                    ON CONFLICT (fecha, tipo_atipico)
                    DO UPDATE SET
                        factor_exigencia = EXCLUDED.factor_exigencia,
                        descartar_historico = EXCLUDED.descartar_historico,
                        fuente_dato = EXCLUDED.fuente_dato,
                        observacion = EXCLUDED.observacion,
                        id_tipo_dia_aplicable = EXCLUDED.id_tipo_dia_aplicable,
                        write_date = NOW();
                """, (
                    r["fecha"],
                    tipo,
                    float(r.get("factor_exigencia") or 0.50),
                    descartar,
                    clean_fuente,
                    obs,
                    r.get("id_tipo_dia_aplicable"),
                ))
                synced_cid_atypical += 1

            # 2c. Casuísticas de lluvia de control_metricas.t_casuisticas_lluvia
            cur_cid.execute("""
                SELECT fecha_evento, hora_inicio, hora_fin, es_lluvia_intensa,
                       registro_comprobado, factor_ajuste, fuente_registro, notas, mm_caidos
                FROM control_metricas.t_casuisticas_lluvia
                WHERE fecha_evento >= '2025-01-01';
            """)
            for r in cur_cid.fetchall():
                h_ini = r["hora_inicio"].strftime("%H:%M:%S") if r.get("hora_inicio") else "00:00:00"
                h_fin = r["hora_fin"].strftime("%H:%M:%S") if r.get("hora_fin") else "23:59:59"
                es_resumen = (h_ini == "00:00:00" and h_fin in ("23:59:59", "23:59:00"))
                mm_val = float(r.get("mm_caidos") or 0.0)
                cur.execute("""
                    INSERT INTO transit_rain_casuistica (
                        fecha_evento, hora_inicio, hora_fin, es_resumen_diario,
                        mm_caidos, es_lluvia_intensa, registro_comprobado,
                        factor_ajuste, fuente_registro, notas, write_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (fecha_evento, hora_inicio, hora_fin)
                    DO UPDATE SET
                        mm_caidos = GREATEST(transit_rain_casuistica.mm_caidos, EXCLUDED.mm_caidos),
                        notas = COALESCE(transit_rain_casuistica.notas, EXCLUDED.notas),
                        write_date = NOW();
                """, (
                    r["fecha_evento"],
                    h_ini,
                    h_fin,
                    es_resumen,
                    mm_val,
                    bool(r.get("es_lluvia_intensa", False)),
                    bool(r.get("registro_comprobado", False)),
                    float(r.get("factor_ajuste") or 0.50),
                    r.get("fuente_registro") or "Open-Meteo",
                    r.get("notas") or f"Lluvia: {mm_val:.2f} mm",
                ))
                synced_cid_rain += 1

            cur_cid.close()
            conn_cid.close()
            conn.commit()
        except Exception as e:
            logger.warning("Aviso durante sincronización con CID DB: %s", e)
            conn.rollback()

    # 3. Generar días atípicos por Feriados, Pre-Feriados y Pos-Feriados en transit_atypical_day
    count_hol_atypical = 0
    for f_dt, f_desc in feriados_map.items():
        if not (2024 <= f_dt.year <= 2030):
            continue
        es_sab = (f_dt.weekday() == 5)
        tipo_f = "FERIADO_SAB" if es_sab else "FERIADO_LAB"
        fac_f = 0.50 if es_sab else 0.30
        cur.execute("""
            INSERT INTO transit_atypical_day (
                fecha, tipo_atipico, factor_exigencia, descartar_historico,
                fuente_dato, observacion, id_tipo_dia_aplicable, active, write_date
            )
            VALUES (%s, %s, %s, TRUE, 'Sincronización Consolidada', %s, 7, TRUE, NOW())
            ON CONFLICT (fecha, tipo_atipico)
            DO UPDATE SET
                factor_exigencia = EXCLUDED.factor_exigencia,
                observacion = EXCLUDED.observacion,
                write_date = NOW();
        """, (f_dt, tipo_f, fac_f, f_desc))
        count_hol_atypical += 1

        # Pre-feriado y Pos-feriado (solo si no son feriados por sí mismos)
        for delta_d, prefix in [(-1, "Pre-feriado de"), (1, "Pos-feriado de")]:
            adj_dt = f_dt + timedelta(days=delta_d)
            if adj_dt not in feriados_map:
                cur.execute("""
                    INSERT INTO transit_atypical_day (
                        fecha, tipo_atipico, factor_exigencia, descartar_historico,
                        fuente_dato, observacion, active, write_date
                    )
                    VALUES (%s, 'PRE_POS_FERIADO', 0.70, TRUE, 'Sincronización Consolidada', %s, TRUE, NOW())
                    ON CONFLICT (fecha, tipo_atipico)
                    DO UPDATE SET
                        factor_exigencia = EXCLUDED.factor_exigencia,
                        observacion = EXCLUDED.observacion,
                        write_date = NOW();
                """, (adj_dt, f"{prefix}: {f_desc}"))
                count_hol_atypical += 1

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

    logger.info(
        "Sincronizados en flota_db: %d días atípicos de feriados/pre/pos, "
        "%d días atípicos CID y %d registros de lluvia CID.",
        count_hol_atypical, synced_cid_atypical, synced_cid_rain
    )
    return {
        "holidays_atypical": count_hol_atypical,
        "cid_atypical": synced_cid_atypical,
        "cid_rain": synced_cid_rain,
    }


# ==========================
# FUNCIONES PÚBLICAS (COMPATIBLES CON script_lluvia.py ORIGINAL)
# ==========================

def cargar_por_fecha(fecha: date, conn=None) -> Dict[str, int]:
    """
    Caso 1: Una fecha específica (ej: 2026-11-05).
    Llama a la API de Open-Meteo para los 19 distritos de Central y guarda en flota_db.
    """
    logger.info("Cargando datos de lluvia Open-Meteo (19 distritos Central) para el día %s...", fecha)
    hourly_records, daily_summaries = fetch_rain_data(fecha, fecha)
    return insert_rain_and_atypical_into_db(hourly_records, daily_summaries, conn=conn)


def cargar_rango_fechas(fecha_inicio: date, fecha_fin: date, conn=None) -> Dict[str, int]:
    """
    Caso 2: Desde una fecha a otra (ej: 2026-09-01 a 2026-11-12).
    Procesa en bloques de hasta 31 días para máxima velocidad sin saturar Open-Meteo.
    """
    if fecha_fin < fecha_inicio:
        raise ValueError("fecha_fin no puede ser anterior a fecha_inicio.")

    logger.info("Cargando datos de lluvia Open-Meteo desde %s hasta %s...", fecha_inicio, fecha_fin)
    totals = {"hourly_inserted": 0, "daily_rain_inserted": 0, "atypical_rain_inserted": 0}

    chunk_start = fecha_inicio
    while chunk_start <= fecha_fin:
        chunk_end = min(chunk_start + timedelta(days=30), fecha_fin)
        logger.info("  - Consultando bloque %s a %s...", chunk_start, chunk_end)
        hourly_records, daily_summaries = fetch_rain_data(chunk_start, chunk_end)
        res = insert_rain_and_atypical_into_db(hourly_records, daily_summaries, conn=conn)
        for k in totals:
            totals[k] += res.get(k, 0)
        chunk_start = chunk_end + timedelta(days=1)

    return totals


def cargar_por_defecto_ayer():
    """
    Caso 3: Sin parámetro -> sincroniza feriados/atípicos y carga datos de lluvia de los últimos 7 días hasta hoy.
    """
    hoy = date.today()
    inicio = hoy - timedelta(days=7)
    logger.info("Sincronizando feriados, días atípicos y lluvias de los últimos 7 días (%s a %s)...", inicio, hoy)
    conn = get_pg_connection()
    try:
        sync_holidays_and_cid_atypical_days(conn=conn)
        cargar_rango_fechas(inicio, hoy, conn=conn)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script para descarga de datos de lluvia (Open-Meteo, 19 distritos de Central) y almacenamiento de Días Atípicos en transporte_odoo (flota_db)."
    )
    parser.add_argument("--fecha", type=str, help="Fecha específica a cargar (Formato: YYYY-MM-DD)")
    parser.add_argument("--inicio", type=str, help="Fecha de inicio para rango (Formato: YYYY-MM-DD)")
    parser.add_argument("--fin", type=str, help="Fecha de fin para rango (Formato: YYYY-MM-DD)")
    parser.add_argument("--sync-feriados", action="store_true", help="Sincronizar también feriados y días atípicos")

    args = parser.parse_args()

    if args.sync_feriados:
        sync_holidays_and_cid_atypical_days()

    if args.fecha:
        fecha_obj = datetime.strptime(args.fecha, "%Y-%m-%d").date()
        cargar_por_fecha(fecha_obj)
    elif args.inicio and args.fin:
        f_inicio = datetime.strptime(args.inicio, "%Y-%m-%d").date()
        f_fin = datetime.strptime(args.fin, "%Y-%m-%d").date()
        cargar_rango_fechas(f_inicio, f_fin)
    else:
        logger.info("No se especificaron parámetros de fecha. Ejecutando sincronización por defecto...")
        cargar_por_defecto_ayer()

