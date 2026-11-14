# -*- coding: utf-8 -*-
"""
Módulo de Control de Indicadores Regulatorios VMT: CBD e IFO (Res. GVMT N° 120/2025)
===================================================================================
Implementa en transporte_odoo exactamente el mismo motor de cálculo y análisis de cbd_monitor:
1. Conteo de buses distintos en tránsito por hora y por franja (según res_120/bus_monitor.py):
   - Filtrado espacial fuera de cabeceras de inicio, fin y puntos terminales/patios.
   - Regla de continuidad operativa inteligente (>=15 min y >=30 mensajes, o continuidad H-1 / H+1).
   - Almacenamiento persistente en la BD de transporte_odoo (flota_db) aislado por tenant (concessionaire_id).
2. Cálculo de CBD Mínimo (por hora y por franja) e índice compuesto ICCBDM (70% horario + 30% franja).
3. Cálculo de IFO y CBD Objetivo por hora y por franja:
   - 4 fechas históricas de referencia (con regla de Noviembre para Enero/Marzo/Diciembre y exclusión de atípicos/lluvias/feriados).
   - Factores de ajuste acumulativos (Capa 1 mensual, Capa 2 feriados/pre/post, Capa 3 clima/atípicos).
   - Fórmula oficial: IFO = (CBD_actual / max(CBD_historico * factor, CBD_minimo_hora)) * 100%.
4. Control Operativo de Compensación por Franja y Alertas Preventivas:
   - Si en una hora de una franja (ej. hora 5 de Pico 5-7) el IFO fue bajo (ej. 50%), calcula automáticamente
     el IFO Objetivo Compensado para las siguientes horas de la franja (ej. 110% a las 6 y 110% a las 7 para
     promediar 270/3 = 90% Nivel A) y la cantidad exacta de buses requeridos en calle.
   - Emite alertas preventivas cuando va culminando la hora o la franja si la empresa está en riesgo de incumplir
     el CBD mínimo o caer en infracción de IFO (Nivel B / Nivel C).
"""

import os
import math
import logging
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

import requests
import psycopg2
from psycopg2.extras import RealDictCursor

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Caché en memoria para respuestas de Open-Meteo por fecha: date -> {'mm': float, 'code': int, 'desc': str}
_OPEN_METEO_CACHE: Dict[date, Dict[str, Any]] = {}

WEATHER_CODE_MAP = {
    0: "☀️ Despejado",
    1: "🌤️ Mayormente despejado",
    2: "⛅ Parcialmente nublado",
    3: "☁️ Nublado",
    45: "🌫️ Niebla",
    48: "🌫️ Niebla con escarcha",
    51: "🌦️ Llovizna ligera",
    53: "🌦️ Llovizna moderada",
    55: "🌧️ Llovizna intensa",
    61: "🌧️ Lluvia débil",
    63: "🌧️ Lluvia moderada",
    65: "🌧️💦 Lluvia fuerte",
    80: "🌧️ Chubascos ligeros",
    81: "🌧️💧 Chubascos moderados",
    82: "🌧️💦 Chubascos intensos",
    95: "⛈️ Tormenta eléctrica",
    96: "⛈️🌨️ Tormenta con granizo",
    99: "⛈️🌨️ Tormenta fuerte con granizo",
}


def _fetch_open_meteo_rain_range(start_date: date, end_date: date) -> Dict[date, Dict[str, Any]]:
    """
    Consulta la API de Open-Meteo (Forecast API para los últimos 92 días + Archive ERA5 para históricos)
    en las coordenadas del Departamento Central / Gran Asunción (lat=-25.3, lon=-57.6, America/Asuncion)
    para obtener la precipitación diaria acumulada (mm) y descripción climática.
    """
    missing = [
        start_date + timedelta(days=i)
        for i in range((end_date - start_date).days + 1)
        if (start_date + timedelta(days=i)) not in _OPEN_METEO_CACHE
    ]
    if not missing:
        return {
            start_date + timedelta(days=i): _OPEN_METEO_CACHE[start_date + timedelta(days=i)]
            for i in range((end_date - start_date).days + 1)
        }

    min_miss = min(missing)
    max_miss = max(missing)
    today_py = _get_paraguay_now().date()
    latitud, longitud = -25.3, -57.6

    # 1. Consultar Archive API para fechas históricas hasta hace 2 días
    archive_end = min(max_miss, today_py - timedelta(days=2))
    if min_miss <= archive_end:
        try:
            resp = requests.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": latitud,
                    "longitude": longitud,
                    "start_date": min_miss.strftime("%Y-%m-%d"),
                    "end_date": archive_end.strftime("%Y-%m-%d"),
                    "daily": ["weathercode", "precipitation_sum"],
                    "timezone": "America/Asuncion",
                    "precipitation_unit": "mm",
                },
                timeout=6,
            )
            if resp.status_code == 200:
                daily = resp.json().get("daily", {})
                times = daily.get("time") or []
                precips = daily.get("precipitation_sum") or []
                codes = daily.get("weathercode") or []
                for idx, t_str in enumerate(times):
                    d_obj = date.fromisoformat(t_str)
                    mm_val = float(precips[idx]) if idx < len(precips) and precips[idx] is not None else 0.0
                    c_val = int(codes[idx]) if idx < len(codes) and codes[idx] is not None else 0
                    _OPEN_METEO_CACHE[d_obj] = {
                        "mm": round(mm_val, 2),
                        "code": c_val,
                        "desc": WEATHER_CODE_MAP.get(c_val, "🌡️ Variable"),
                    }
        except Exception as e:
            _logger.debug("Aviso consultando Open-Meteo Archive API: %s", e)

    # 2. Consultar Forecast API para fechas recientes / hoy (últimos 92 días hasta mañana)
    if max_miss >= today_py - timedelta(days=90):
        try:
            days_back = min(92, max(7, (today_py - min_miss).days + 2))
            resp_f = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitud,
                    "longitude": longitud,
                    "daily": ["weathercode", "precipitation_sum"],
                    "timezone": "America/Asuncion",
                    "precipitation_unit": "mm",
                    "past_days": days_back,
                    "forecast_days": 2,
                },
                timeout=6,
            )
            if resp_f.status_code == 200:
                daily = resp_f.json().get("daily", {})
                times = daily.get("time") or []
                precips = daily.get("precipitation_sum") or []
                codes = daily.get("weathercode") or []
                for idx, t_str in enumerate(times):
                    d_obj = date.fromisoformat(t_str)
                    mm_val = float(precips[idx]) if idx < len(precips) and precips[idx] is not None else 0.0
                    c_val = int(codes[idx]) if idx < len(codes) and codes[idx] is not None else 0
                    existing = _OPEN_METEO_CACHE.get(d_obj)
                    if not existing or mm_val > existing["mm"]:
                        _OPEN_METEO_CACHE[d_obj] = {
                            "mm": round(mm_val, 2),
                            "code": c_val,
                            "desc": WEATHER_CODE_MAP.get(c_val, "🌡️ Variable"),
                        }
        except Exception as e:
            _logger.debug("Aviso consultando Open-Meteo Forecast API: %s", e)

    result: Dict[date, Dict[str, Any]] = {}
    for i in range((end_date - start_date).days + 1):
        d_cur = start_date + timedelta(days=i)
        result[d_cur] = _OPEN_METEO_CACHE.get(
            d_cur, {"mm": 0.0, "code": 0, "desc": "☀️ Despejado"}
        )
    return result


def _get_cid_connection():
    """Conexión a base de datos de monitoreo CID (VMT Paraguay)."""
    cid_host = os.getenv("CID_DB_HOST", "168.90.177.232")
    cid_port = int(os.getenv("CID_DB_PORT", 2024))
    cid_db = os.getenv("CID_DB_NAME", "bbdd-monitoreo-cid")
    cid_user = os.getenv("CID_DB_USER", "FPorta")
    cid_pass = os.getenv("CID_DB_PASS", "portaf2024")
    try:
        return psycopg2.connect(
            host=cid_host, port=cid_port, dbname=cid_db,
            user=cid_user, password=cid_pass, connect_timeout=4
        )
    except Exception as e:
        _logger.debug("No se pudo conectar a CID DB (%s): %s", cid_host, e)
        return None


def _get_vmt_live_connection():
    """Conexión directa a la BD transaccional de telemetría en vivo del VMT (monitoreo.vmt.gov.py)."""
    vmt_host = os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py")
    vmt_port = int(os.getenv("VMT_DB_PORT", 5432))
    vmt_db = os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod")
    vmt_user = os.getenv("VMT_DB_USER", "jefe-CID")
    vmt_pass = os.getenv("VMT_DB_PASS", "vmtdmt")
    try:
        return psycopg2.connect(
            host=vmt_host, port=vmt_port, dbname=vmt_db,
            user=vmt_user, password=vmt_pass, sslmode="require", connect_timeout=6
        )
    except Exception as e:
        _logger.debug("No se pudo conectar a VMT Live DB (%s): %s", vmt_host, e)
        return None


def _get_paraguay_now() -> datetime:
    """Retorna la fecha/hora actual en zona horaria de Paraguay (UTC-3)."""
    return datetime.utcnow() - timedelta(hours=3)


# ==============================================================================
# 1. MODELO: CONSOLIDADO POR FRANJA OPERATIVA (transit.cbd.franja)
# ==============================================================================
class TransitCBDFranja(models.Model):
    _name = 'transit.cbd.franja'
    _description = 'Control Operativo por Franja Horaria (CBD, ICCBDM e IFO)'
    _inherit = ['transit.tenant.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date desc, start_hour asc, id desc'

    name = fields.Char(string='Franja Operativa', required=True, tracking=True)
    cid_franja_id = fields.Integer(string='ID Franja Operativa', index=True, help='Identificador de la franja operativa.')
    date = fields.Date(string='Fecha Operativa', required=True, default=fields.Date.context_today, index=True, tracking=True)
    agency_id = fields.Char(string='Código de Empresa (Agency ID)', related='concessionaire_id.agency_id', store=True, index=True)

    start_hour = fields.Integer(string='Hora Inicio', required=True)
    end_hour = fields.Integer(string='Hora Fin', required=True)
    range_label = fields.Char(string='Horario', compute='_compute_range_label', store=True)

    tipo_dia = fields.Selection([
        ('5', 'Laboral (Lunes a Viernes)'),
        ('6', 'Sábado'),
        ('7', 'Domingo / Feriado')
    ], string='Tipo de Día', default='5', required=True)

    is_peak = fields.Boolean(string='Es Franja Pico', compute='_compute_is_peak', store=True)
    is_regulated = fields.Boolean(
        string='Franja Regulada (CBD & IFO)',
        compute='_compute_is_peak',
        store=True,
        help='Todas las franjas activas se controlan en CBD Mínimo, ICCBDM e IFO.'
    )

    # Condiciones de Feriado y Clima (Open-Meteo)
    is_holiday = fields.Boolean(string='Es Feriado', default=False)
    holiday_info = fields.Char(string='Estado Feriado / Calendario', default='Día Normal')
    is_rainy_day = fields.Boolean(string='Día de Lluvia (>= 5mm Open-Meteo)', default=False)
    precipitation_mm = fields.Float(string='Precipitación Open-Meteo (mm)', digits=(6, 2), default=0.0)
    weather_description = fields.Char(string='Clima Open-Meteo', default='☀️ Despejado (0.0 mm)')
    excluded_dates_info = fields.Char(
        string='Fechas Descartadas (Feriados / Lluvia)',
        help='Fechas históricas excluidas de las 4 semanas de referencia por Feriado, Pre/Post-Feriado o Lluvia (>= 5mm en Open-Meteo).'
    )
    ifo_umbral_minimo = fields.Float(
        string='Umbral Mínimo IFO (%)',
        digits=(5, 1),
        default=80.0,
        help='Porcentaje mínimo exigido según parámetros regulatorios de IFO.'
    )

    # Relación con las líneas horarias
    hourly_line_ids = fields.One2many(
        'transit.cbd.hourly',
        'franja_id',
        string='Desglose por Horas de la Franja'
    )

    # Indicadores CBD y Flota Mínima (ICCBDM)
    cbd_franja_distinct = fields.Integer(
        string='CBD Franja Observado (Buses Únicos)',
        default=0,
        tracking=True,
        help='Cantidad de buses distintos detectados en tránsito fuera de terminales durante toda la franja.'
    )
    cbd_minimo_franja = fields.Integer(string='CBD Mínimo Franja', default=0)
    cbd_minimo_hora = fields.Integer(string='CBD Mínimo por Hora', default=0)
    cbd_historico_franja = fields.Float(
        string='CBD Histórico Franja (4 Sem.)',
        digits=(6, 2),
        default=0.0,
        help='Promedio de buses distintos en la franja en las 4 fechas de referencia.'
    )
    adjustment_factor = fields.Float(string='Factor de Ajuste', digits=(4, 2), default=1.0)
    factor_details = fields.Char(string='Detalle de Ajustes', default='Ninguno (1.00)')
    reference_dates_info = fields.Char(string='Fechas de Referencia (4 Sem.)')

    cbd_objetivo_franja = fields.Integer(
        string='CBD Objetivo Franja (100% IFO)',
        compute='_compute_cbd_metrics',
        store=True,
        help='Meta de buses únicos en la franja = ceil(max(CBD_historico_franja * factor, CBD_minimo_franja)).'
    )
    buses_faltantes_franja = fields.Integer(
        string='Buses Faltantes Mínimo Franja',
        compute='_compute_cbd_metrics',
        store=True
    )
    buses_faltantes_ifo_100_franja = fields.Integer(
        string='Faltan p/ 100% IFO Franja',
        compute='_compute_cbd_metrics',
        store=True,
        help='Buses distintos faltantes en toda la franja para alcanzar el CBD Objetivo (100% IFO Franja).'
    )
    iccbdm_pct = fields.Float(
        string='Índice ICCBDM (%)',
        digits=(6, 1),
        compute='_compute_cbd_metrics',
        store=True,
        tracking=True,
        help='Fórmula Res. 120/2025: (Promedio(min(CBD_h / Min_h, 1)) * 0.70 + min(CBD_franja / Min_franja, 1) * 0.30) * 100'
    )
    cbd_compliance_state = fields.Selection([
        ('Cumple', 'Cumple (100%)'),
        ('Leve', 'Falta Leve (95% - 99.9%)'),
        ('Intermedia', 'Falta Intermedia (85% - 94.9%)'),
        ('Grave', 'Falta Grave (< 85%)'),
    ], string='Estado Cumplimiento CBD', compute='_compute_cbd_metrics', store=True)
    cumple_cbd_franja = fields.Boolean(
        string='Cumple Flota Mínima (ICCBDM = 100%)',
        compute='_compute_cbd_metrics',
        store=True
    )

    # Indicadores IFO
    ifo_promedio = fields.Float(
        string='IFO Promedio Franja (%)',
        digits=(6, 1),
        compute='_compute_ifo_metrics',
        store=True,
        tracking=True,
        help='Promedio aritmético de los IFO de cada hora de la franja.'
    )
    ifo_level = fields.Selection([
        ('A', 'Nivel A (>= 90.0% - Cumple)'),
        ('B', 'Nivel B (80.0% - 89.9% - Acumulable)'),
        ('C', 'Nivel C (< 80.0% - Infracción Directa)'),
    ], string='Nivel de Servicio IFO', compute='_compute_ifo_metrics', store=True, tracking=True)

    # Progreso Temporal de la Franja
    total_hours = fields.Integer(string='Total Horas Franja', compute='_compute_progress', store=True)
    elapsed_hours = fields.Integer(string='Horas Cerradas', compute='_compute_progress', store=True)
    remaining_hours = fields.Integer(string='Horas Restantes (Incl. Actual)', compute='_compute_progress', store=True)
    is_ending_soon = fields.Boolean(
        string='Franja por Culminar',
        compute='_compute_progress',
        store=True,
        help='Indica si la franja está en su última hora o últimos minutos de operación.'
    )
    state = fields.Selection([
        ('in_progress', 'En Curso (Operando)'),
        ('future', 'Próxima / Por Iniciar'),
        ('closed', 'Concluida / Cerrada'),
    ], string='Estado de la Franja', compute='_compute_progress', store=True, tracking=True)

    # Compensación Dinámica de IFO (Para no caer en infracción)
    ifo_acumulado_transcurrido = fields.Float(
        string='Suma IFO Horas Cerradas (%)',
        digits=(6, 1),
        compute='_compute_compensation',
        store=True
    )
    ifo_requerido_restante_a = fields.Float(
        string='IFO Objetivo Horas Restantes (Nivel A >= 90%)',
        digits=(6, 1),
        compute='_compute_compensation',
        store=True,
        help='IFO que la empresa debe promediar en las horas restantes de la franja para cerrar con promedio >= 90% (Nivel A).'
    )
    buses_requeridos_restante_a = fields.Integer(
        string='Buses Objetivo / Hora Restante (Nivel A)',
        compute='_compute_compensation',
        store=True,
        help='Cantidad de buses en tránsito por hora requeridos en las horas restantes para alcanzar Nivel A.'
    )
    ifo_requerido_restante_b = fields.Float(
        string='IFO Mínimo Horas Restantes (Nivel B >= 80%)',
        digits=(6, 1),
        compute='_compute_compensation',
        store=True,
        help='IFO mínimo en las horas restantes para evitar caer en Nivel C (< 80%, multa directa de 20 jornales).'
    )
    buses_requeridos_restante_b = fields.Integer(
        string='Buses Mínimos / Hora Restante (Nivel B)',
        compute='_compute_compensation',
        store=True
    )
    ifo_requerido_restante_100 = fields.Float(
        string='IFO Req. Horas Restantes (100%)',
        digits=(6, 1),
        compute='_compute_compensation',
        store=True,
        help='IFO promedio requerido en las horas restantes de la franja para cerrar con promedio = 100%.'
    )
    buses_requeridos_restante_100 = fields.Integer(
        string='Buses Objetivo / Hora Restante (100% IFO)',
        compute='_compute_compensation',
        store=True,
        help='Cantidad de buses en tránsito por hora requeridos en las horas restantes para alcanzar 100% IFO.'
    )

    # Monitoreo instantáneo en calle y faltantes para IFO 100% (Franja en curso)
    active_hour = fields.Integer(
        string='Hora Actual Monitoreada',
        compute='_compute_live_ifo_100',
        store=True
    )
    active_hour_label = fields.Char(
        string='Hora en Curso',
        compute='_compute_live_ifo_100',
        store=True
    )
    buses_en_calle_actual = fields.Integer(
        string='En Calle (Hora Actual)',
        compute='_compute_live_ifo_100',
        store=True,
        help='Buses en tránsito contabilizados en la hora en curso de la franja (base del IFO horario).'
    )
    buses_en_calle_vivo = fields.Integer(
        string='Activos Ahora (Últ. 15 min)',
        default=0,
        help='Buses válidos con transmisión activa fuera de terminales en los últimos 15 minutos.'
    )
    cbd_objetivo_hora_actual = fields.Integer(
        string='Meta 100% IFO (Hora Actual)',
        compute='_compute_live_ifo_100',
        store=True,
        help='Cantidad de buses requerida en la hora en curso para alcanzar IFO = 100%.'
    )
    ifo_hora_actual = fields.Float(
        string='IFO Hora Actual (%)',
        digits=(6, 1),
        compute='_compute_live_ifo_100',
        store=True
    )
    buses_faltantes_hora_100 = fields.Integer(
        string='Faltan p/ 100% IFO (Hora)',
        compute='_compute_live_ifo_100',
        store=True,
        help='Cantidad de buses que falta sacar en la hora en curso para alcanzar IFO = 100%.'
    )
    cbd_objetivo_comp_100_actual = fields.Integer(
        string='Meta 100% Compensada (Hora)',
        compute='_compute_live_ifo_100',
        store=True,
        help='Buses requeridos en la hora actual para compensar horas previas y cerrar la franja en 100% IFO.'
    )
    buses_faltantes_comp_100 = fields.Integer(
        string='Faltan p/ 100% Franja (Comp.)',
        compute='_compute_live_ifo_100',
        store=True,
        help='Buses que falta incorporar en la hora actual para cerrar la franja con promedio de 100% IFO.'
    )
    last_sync_at = fields.Datetime(
        string='Última Sincronización',
        default=fields.Datetime.now
    )

    # Alertas y Sanciones Previstas
    alert_severity = fields.Selection([
        ('ok', 'Óptimo (Cumple)'),
        ('warning', 'Alerta Preventiva / Nivel B'),
        ('danger', 'PELIGRO DE INFRACCIÓN / DÉFICIT'),
        ('closed', 'Franja Cerrada'),
    ], string='Estado de Alerta', compute='_compute_alerts', store=True, tracking=True)

    alert_message = fields.Text(string='Indicación Operativa y Alerta', compute='_compute_alerts', store=True)

    infraccion_prevista = fields.Selection([
        ('none', 'Sin Infracción (Cumple Nivel A y CBD)'),
        ('art_15_2', 'Art. 15.2 - Franja Pico en Nivel B (Acumula p/ 10 Jornales)'),
        ('art_15_3', 'Art. 15.3 - Franja Pico en Nivel C (20 Jornales DIRECTA)'),
        ('art_15_4', 'Art. 15.4 - Franja Pos-Pico en Nivel B (Acumula p/ 10 Jornales)'),
        ('art_15_5', 'Art. 15.5 - Franja Pos-Pico en Nivel C (20 Jornales DIRECTA)'),
        ('art_15_6', 'Art. 15.6 - Incumplimiento CBD Mínimo ICCBDM < 100% (20 Jornales DIRECTA)'),
    ], string='Situación Sancionatoria (Res. 120/2025)', compute='_compute_alerts', store=True)

    _sql_constraints = [
        ('concessionaire_date_franja_unique',
         'unique(concessionaire_id, date, start_hour, end_hour)',
         'Ya existe un registro de esta franja para la empresa y fecha seleccionada.')
    ]

    @api.depends('start_hour', 'end_hour')
    def _compute_range_label(self):
        for rec in self:
            rec.range_label = f"{rec.start_hour:02d}:00 - {rec.end_hour:02d}:59"

    @api.depends('name', 'tipo_dia')
    def _compute_is_peak(self):
        for rec in self:
            name_lower = (rec.name or '').lower()
            rec.is_peak = ('pico' in name_lower) and ('pos' not in name_lower)
            rec.is_regulated = True

    @api.depends('start_hour', 'end_hour', 'date')
    def _compute_progress(self):
        now_py = _get_paraguay_now()
        today = now_py.date()
        current_hour = now_py.hour
        current_min = now_py.minute

        for rec in self:
            total = max(rec.end_hour - rec.start_hour + 1, 1)
            rec.total_hours = total

            if rec.date < today:
                rec.elapsed_hours = total
                rec.remaining_hours = 0
                rec.is_ending_soon = False
                rec.state = 'closed'
            elif rec.date > today:
                rec.elapsed_hours = 0
                rec.remaining_hours = total
                rec.is_ending_soon = False
                rec.state = 'future'
            else:
                if current_hour < rec.start_hour:
                    rec.elapsed_hours = 0
                    rec.remaining_hours = total
                    rec.is_ending_soon = False
                    rec.state = 'future'
                elif current_hour > rec.end_hour:
                    rec.elapsed_hours = total
                    rec.remaining_hours = 0
                    rec.is_ending_soon = False
                    rec.state = 'closed'
                else:
                    elapsed = current_hour - rec.start_hour
                    rem = total - elapsed
                    rec.elapsed_hours = elapsed
                    rec.remaining_hours = rem
                    rec.is_ending_soon = (rem == 1 and current_min >= 25) or (rem == 1)
                    rec.state = 'in_progress'

    @api.depends(
        'hourly_line_ids.distinct_buses_count',
        'hourly_line_ids.cbd_minimo_hora',
        'cbd_franja_distinct',
        'cbd_minimo_franja',
        'cbd_historico_franja',
        'adjustment_factor',
    )
    def _compute_cbd_metrics(self):
        for rec in self:
            base_franja = max(rec.cbd_historico_franja * rec.adjustment_factor, rec.cbd_minimo_franja)
            rec.cbd_objetivo_franja = math.ceil(base_franja) if base_franja > 0 else rec.cbd_minimo_franja
            rec.buses_faltantes_franja = max(0, rec.cbd_minimo_franja - rec.cbd_franja_distinct)
            rec.buses_faltantes_ifo_100_franja = max(0, rec.cbd_objetivo_franja - rec.cbd_franja_distinct)

            lines = rec.hourly_line_ids
            if lines and rec.cbd_minimo_hora > 0:
                sum_ratios = sum(
                    min(l.distinct_buses_count / float(rec.cbd_minimo_hora), 1.0)
                    for l in lines
                )
                promedio_ratio_hora = sum_ratios / len(lines)
            else:
                promedio_ratio_hora = 1.0 if rec.cbd_minimo_hora == 0 else 0.0

            if rec.cbd_minimo_franja > 0:
                ratio_franja = min(rec.cbd_franja_distinct / float(rec.cbd_minimo_franja), 1.0)
            else:
                ratio_franja = 1.0

            indice_cbd = (promedio_ratio_hora * 0.70) + (ratio_franja * 0.30)
            rec.iccbdm_pct = round(indice_cbd * 100.0, 1)

            if indice_cbd >= 1.0:
                rec.cbd_compliance_state = 'Cumple'
                rec.cumple_cbd_franja = True
            elif indice_cbd >= 0.95:
                rec.cbd_compliance_state = 'Leve'
                rec.cumple_cbd_franja = False
            elif indice_cbd >= 0.85:
                rec.cbd_compliance_state = 'Intermedia'
                rec.cumple_cbd_franja = False
            else:
                rec.cbd_compliance_state = 'Grave'
                rec.cumple_cbd_franja = False

    @api.depends('hourly_line_ids.ifo_pct')
    def _compute_ifo_metrics(self):
        for rec in self:
            lines = rec.hourly_line_ids
            if lines:
                ifos = [l.ifo_pct for l in lines]
                avg = sum(ifos) / len(ifos)
                rec.ifo_promedio = round(avg, 1)
                if avg >= 90.0:
                    rec.ifo_level = 'A'
                elif avg >= 80.0:
                    rec.ifo_level = 'B'
                else:
                    rec.ifo_level = 'C'
            else:
                rec.ifo_promedio = 0.0
                rec.ifo_level = 'C'

    @api.depends(
        'ifo_promedio',
        'hourly_line_ids.ifo_pct',
        'hourly_line_ids.cbd_historico',
        'hourly_line_ids.adjustment_factor',
        'hourly_line_ids.cbd_minimo_hora',
        'hourly_line_ids.distinct_buses_count',
        'remaining_hours',
        'state',
    )
    def _compute_compensation(self):
        now_py = _get_paraguay_now()
        current_hour = now_py.hour

        for rec in self:
            lines_sorted = sorted(rec.hourly_line_ids, key=lambda l: l.hour)
            total_n = max(len(lines_sorted) or rec.total_hours, 1)

            if not lines_sorted:
                rec.ifo_acumulado_transcurrido = 0.0
                rec.ifo_requerido_restante_100 = 100.0
                rec.buses_requeridos_restante_100 = rec.cbd_minimo_hora
                rec.ifo_requerido_restante_a = 90.0
                rec.buses_requeridos_restante_a = rec.cbd_minimo_hora
                rec.ifo_requerido_restante_b = 80.0
                rec.buses_requeridos_restante_b = rec.cbd_minimo_hora
                continue

            # Determinar qué horas ya tienen operación registrada vs qué horas faltan compensar:
            # Si la franja está en curso hoy, las horas cerradas son hour < current_hour.
            # Si es una simulación o consulta donde algunas horas tienen buses > 0 y las siguientes están en 0,
            # también detectamos las horas con actividad previa para mostrar la compensación requerida en las siguientes.
            if rec.state == 'in_progress':
                closed_lines = [l for l in lines_sorted if l.hour < current_hour]
                remaining_lines = [l for l in lines_sorted if l.hour >= current_hour]
            else:
                # Si hay horas con déficit al inicio y horas posteriores o si evaluamos la última etapa:
                non_zero = [l for l in lines_sorted if l.distinct_buses_count > 0]
                zero_after = [
                    l for l in lines_sorted
                    if l.distinct_buses_count == 0 and (not non_zero or l.hour > non_zero[-1].hour)
                ]
                if non_zero and zero_after:
                    closed_lines = non_zero
                    remaining_lines = zero_after
                elif len(lines_sorted) > 1 and rec.ifo_promedio < 90.0:
                    # Mostrar cuánto requería en las horas posteriores tras la primera hora deficitaria
                    closed_lines = lines_sorted[:1]
                    remaining_lines = lines_sorted[1:]
                else:
                    closed_lines = lines_sorted
                    remaining_lines = []

            s_closed = sum(l.ifo_pct for l in closed_lines)
            rec.ifo_acumulado_transcurrido = round(s_closed, 1)
            m_remaining = len(remaining_lines)

            if m_remaining > 0:
                # Denominadores ajustados de las horas restantes
                denoms_rem = [
                    max(l.cbd_historico * l.adjustment_factor, l.cbd_minimo_hora, 1.0)
                    for l in remaining_lines
                ]
                avg_denom_rem = sum(denoms_rem) / len(denoms_rem)

                # Meta 100% IFO (Promedio Franja = 100%)
                target_sum_100 = (100.0 * total_n) - s_closed
                req_ifo_100 = max(round(target_sum_100 / m_remaining, 1), 0.0)
                rec.ifo_requerido_restante_100 = req_ifo_100
                rec.buses_requeridos_restante_100 = max(
                    math.ceil((req_ifo_100 / 100.0) * avg_denom_rem),
                    rec.cbd_minimo_hora
                ) if req_ifo_100 > 0 else rec.cbd_minimo_hora

                # Meta Nivel A (Promedio Franja >= 90%)
                target_sum_a = (90.0 * total_n) - s_closed
                req_ifo_a = max(round(target_sum_a / m_remaining, 1), 0.0)
                rec.ifo_requerido_restante_a = req_ifo_a
                rec.buses_requeridos_restante_a = max(
                    math.ceil((req_ifo_a / 100.0) * avg_denom_rem),
                    rec.cbd_minimo_hora
                ) if req_ifo_a > 0 else rec.cbd_minimo_hora

                # Meta Nivel B (Promedio Franja >= 80% para evitar Nivel C)
                target_sum_b = (80.0 * total_n) - s_closed
                req_ifo_b = max(round(target_sum_b / m_remaining, 1), 0.0)
                rec.ifo_requerido_restante_b = req_ifo_b
                rec.buses_requeridos_restante_b = max(
                    math.ceil((req_ifo_b / 100.0) * avg_denom_rem),
                    rec.cbd_minimo_hora
                ) if req_ifo_b > 0 else rec.cbd_minimo_hora
            else:
                rec.ifo_requerido_restante_100 = 0.0
                rec.buses_requeridos_restante_100 = 0
                rec.ifo_requerido_restante_a = 0.0
                rec.buses_requeridos_restante_a = 0
                rec.ifo_requerido_restante_b = 0.0
                rec.buses_requeridos_restante_b = 0

    @api.depends(
        'state',
        'start_hour',
        'end_hour',
        'date',
        'cbd_minimo_hora',
        'hourly_line_ids.hour',
        'hourly_line_ids.distinct_buses_count',
        'hourly_line_ids.cbd_objetivo',
        'hourly_line_ids.ifo_pct',
        'hourly_line_ids.cbd_objetivo_compensado_100',
    )
    def _compute_live_ifo_100(self):
        """Calcula en la hora activa los buses actualmente en calle y los faltantes para IFO = 100%."""
        now_py = _get_paraguay_now()
        today = now_py.date()
        current_hour = now_py.hour

        for rec in self:
            lines_sorted = sorted(rec.hourly_line_ids, key=lambda l: l.hour)
            if not lines_sorted:
                rec.active_hour = rec.start_hour
                rec.active_hour_label = f"{rec.start_hour:02d}:00 - {rec.start_hour:02d}:59"
                rec.buses_en_calle_actual = 0
                rec.cbd_objetivo_hora_actual = rec.cbd_minimo_hora
                rec.ifo_hora_actual = 0.0
                rec.buses_faltantes_hora_100 = rec.cbd_minimo_hora
                rec.cbd_objetivo_comp_100_actual = rec.cbd_minimo_hora
                rec.buses_faltantes_comp_100 = rec.cbd_minimo_hora
                continue

            if rec.state == 'in_progress' or (rec.date == today and rec.start_hour <= current_hour <= rec.end_hour):
                target_line = next((l for l in lines_sorted if l.hour == current_hour), lines_sorted[-1])
            elif rec.state == 'future' or rec.date > today or (rec.date == today and current_hour < rec.start_hour):
                target_line = lines_sorted[0]
            else:
                operated = [l for l in lines_sorted if l.distinct_buses_count > 0]
                target_line = operated[-1] if operated else lines_sorted[-1]

            rec.active_hour = target_line.hour
            rec.active_hour_label = f"{target_line.hour:02d}:00 - {target_line.hour:02d}:59"
            rec.buses_en_calle_actual = target_line.distinct_buses_count
            rec.cbd_objetivo_hora_actual = target_line.cbd_objetivo
            rec.ifo_hora_actual = target_line.ifo_pct
            rec.buses_faltantes_hora_100 = max(0, target_line.cbd_objetivo - target_line.distinct_buses_count)
            comp_100 = target_line.cbd_objetivo_compensado_100 or target_line.cbd_objetivo
            rec.cbd_objetivo_comp_100_actual = comp_100
            rec.buses_faltantes_comp_100 = max(0, comp_100 - target_line.distinct_buses_count)

    @api.depends(
        'state',
        'is_ending_soon',
        'ifo_promedio',
        'ifo_level',
        'ifo_requerido_restante_a',
        'buses_requeridos_restante_a',
        'ifo_requerido_restante_b',
        'buses_requeridos_restante_b',
        'cumple_cbd_franja',
        'cbd_franja_distinct',
        'cbd_minimo_franja',
        'iccbdm_pct',
        'is_peak',
        'is_regulated',
        'remaining_hours',
    )
    def _compute_alerts(self):
        for rec in self:
            msg_parts = []
            severity = 'ok'
            infraccion = 'none'

            # 1. Alerta de CBD Mínimo de la Franja e ICCBDM
            if not rec.cumple_cbd_franja and rec.state != 'future':
                if rec.is_regulated:
                    infraccion = 'art_15_6'
                severity = 'danger'
                faltan_f = max(0, rec.cbd_minimo_franja - rec.cbd_franja_distinct)
                if rec.state == 'in_progress':
                    cierre_txt = " (¡FRANJA POR CULMINAR!)" if rec.is_ending_soon else ""
                    msg_parts.append(
                        f"🚨 ALERTA CBD MÍNIMO FRANJA{cierre_txt}: Índice ICCBDM actual en {rec.iccbdm_pct}% (< 100%). "
                        f"Buses distintos en franja: {rec.cbd_franja_distinct} de {rec.cbd_minimo_franja} requeridos "
                        f"(faltan sacar {faltan_f} unidades distintas para evitar multa de 20 Jornales - Art. 15.6)."
                    )
                else:
                    msg_parts.append(
                        f"❌ INCUMPLIMIENTO CBD MÍNIMO (Art. 15.6 - 20 Jornales): ICCBDM = {rec.iccbdm_pct}%. "
                        f"Buses distintos en franja: {rec.cbd_franja_distinct} / Mínimo: {rec.cbd_minimo_franja}."
                    )

            # 2. Evaluación de IFO y Compensación por Franja
            if rec.state == 'in_progress' or rec.ifo_requerido_restante_a > 0:
                if rec.ifo_requerido_restante_a > 90.0:
                    severity = 'danger' if rec.ifo_requerido_restante_a > 100.0 else 'warning'
                    msg_parts.append(
                        f"⚠️ ALERTA DE COMPENSACIÓN IFO ({rec.name}): Por bajo IFO en hora(s) previa(s) "
                        f"(acumulado {rec.ifo_acumulado_transcurrido}%), la empresa DEBE AUMENTAR su operativa a "
                        f"IFO Objetivo = {rec.ifo_requerido_restante_a}% (~{rec.buses_requeridos_restante_a} buses/hora) "
                        f"en las siguientes horas de la franja para promediar 90% (Nivel A) y no caer en infracción."
                    )
                    if rec.ifo_requerido_restante_b > 80.0:
                        msg_parts.append(
                            f"🚨 RIESGO MULTA DIRECTA NIVEL C (20 Jornales): Requiere como mínimo absoluto "
                            f"IFO = {rec.ifo_requerido_restante_b}% (~{rec.buses_requeridos_restante_b} buses/hora) "
                            f"para superar el 80% en la franja."
                        )
                elif rec.state == 'in_progress':
                    msg_parts.append(
                        f"✅ OPERATIVA EN META: Para cerrar en Nivel A (>= 90%), mantener IFO >= {rec.ifo_requerido_restante_a}% "
                        f"(~{rec.buses_requeridos_restante_a} buses/hora) en las {rec.remaining_hours} hora(s) restante(s)."
                    )

            # 3. Liquidación de Franja Concluida
            if rec.state == 'closed':
                if rec.ifo_level == 'C':
                    severity = 'danger'
                    if rec.is_regulated and infraccion == 'none':
                        infraccion = 'art_15_3' if rec.is_peak else 'art_15_5'
                    msg_parts.append(
                        f"❌ FRANJA CONCLUIDA EN NIVEL C (IFO = {rec.ifo_promedio}% < 80%): "
                        f"Infracción Directa de 20 Jornales ({'Art. 15.3 Pico' if rec.is_peak else 'Art. 15.5 Pos-Pico'})."
                    )
                elif rec.ifo_level == 'B':
                    if severity == 'ok':
                        severity = 'warning'
                    if rec.is_regulated and infraccion == 'none':
                        infraccion = 'art_15_2' if rec.is_peak else 'art_15_4'
                    msg_parts.append(
                        f"⚠️ FRANJA CONCLUIDA EN NIVEL B (IFO = {rec.ifo_promedio}%): "
                        f"Acumula 1 franja en Nivel B en el mes (límite de 5 al mes para sanción de 10 Jornales - "
                        f"{'Art. 15.2' if rec.is_peak else 'Art. 15.4'})."
                    )
                elif rec.cumple_cbd_franja:
                    severity = 'ok'
                    msg_parts.append(
                        f"✅ FRANJA CUMPLIDA EN NIVEL A (IFO = {rec.ifo_promedio}%, ICCBDM = {rec.iccbdm_pct}%): "
                        f"Sin infracciones."
                    )

            rec.alert_severity = severity
            rec.infraccion_prevista = infraccion
            rec.alert_message = "\n".join(msg_parts) if msg_parts else "Operación normal sin alertas."

    def action_recalculate_silent(self):
        """Recalcula silenciosamente las métricas desde telemetría GPS para actualización automática en pantalla."""
        for rec in self:
            if rec.date and rec.concessionaire_id:
                self.env['transit.cbd.hourly'].compute_cbd_for_date_and_company(
                    rec.date, rec.concessionaire_id.id
                )
        return True

    def action_recalculate(self):
        """Recalcula las métricas horarias y de franja desde el GPS para la fecha y empresa de este registro."""
        self.action_recalculate_silent()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Indicadores CBD e IFO Actualizados'),
                'message': _('Se recalcularon los buses en tránsito, IFO Objetivo y alertas desde telemetría GPS.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    def action_sync_today_live(self):
        """Sincroniza el día actual desde telemetría GPS en tiempo real desde la vista."""
        self.env['transit.cbd.hourly'].cron_update_today_cbd_ifo()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


# ==============================================================================
# 2. MODELO: CONTEO HORARIO DE BUSES CBD & IFO (transit.cbd.hourly)
# ==============================================================================
class TransitCBDHourly(models.Model):
    _name = 'transit.cbd.hourly'
    _description = 'Conteo Horario de Buses Distintos (CBD), IFO y Metas por Hora'
    _inherit = ['transit.tenant.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date desc, hour asc, id desc'

    date = fields.Date(string='Fecha Operativa', required=True, default=fields.Date.context_today, index=True)
    hour = fields.Integer(string='Hora del Día (0-23)', required=True, index=True)
    hour_label = fields.Char(string='Horario', compute='_compute_hour_label', store=True)
    agency_id = fields.Char(string='Código de Empresa (Agency ID)', related='concessionaire_id.agency_id', store=True, index=True)

    franja_id = fields.Many2one('transit.cbd.franja', string='Franja Operativa', ondelete='cascade', index=True)
    franja_name = fields.Char(string='Denominación Franja', related='franja_id.name', store=True)

    # Cálculo CBD según bus_monitor.py
    distinct_buses_count = fields.Integer(
        string='CBD Actual (Buses Distintos)',
        default=0,
        tracking=True,
        help='Cantidad de buses distintos que saca la empresa en esta hora (fuera de terminales y con continuidad operativa).'
    )
    bus_codes_summary = fields.Text(string='Internos en Tránsito', help='Lista de internos detectados fuera de terminal en la hora.')
    data_source = fields.Selection([
        ('gps_broker', 'Telemetría GPS en Tiempo Real'),
        ('cid_db', 'Consolidado de Monitoreo'),
        ('manual', 'Simulación / Manual'),
    ], string='Fuente de Datos', default='gps_broker')

    bus_detail_ids = fields.One2many(
        'transit.cbd.bus.detail',
        'hourly_id',
        string='Detalle Individual de Buses en la Hora'
    )

    # Parámetros Regulatorios y Base Histórica (cbd_monitor)
    cbd_minimo_hora = fields.Integer(string='CBD Mínimo Hora', default=0)
    cbd_historico = fields.Float(
        string='CBD Histórico (4 Semanas)',
        digits=(6, 2),
        default=0.0,
        help='Promedio de buses distintos observados en las 4 fechas históricas de referencia.'
    )
    adjustment_factor = fields.Float(
        string='Factor de Ajuste (Res. 120)',
        digits=(4, 2),
        default=1.0,
        help='Factor multiplicativo acumulado: Mes Ene/Dic (0.80), Feriado (0.30/0.50), Pre/Post Feriado (0.70), Lluvia/Atípico (0.50).'
    )
    factor_details = fields.Char(string='Detalle de Ajustes', default='Ninguno (1.00)')
    cbd_denominador_ajustado = fields.Float(
        string='Denominador Ajustado (CBD_hist * factor)',
        digits=(6, 2),
        compute='_compute_targets',
        store=True,
        help='Denominador oficial del IFO = max(CBD_historico * factor, CBD_minimo_hora).'
    )

    # Metas de Buses e IFO Objetivo para la Hora
    cbd_objetivo = fields.Integer(
        string='CBD Objetivo Hora (100% IFO)',
        compute='_compute_targets',
        store=True,
        help='Buses necesarios para alcanzar IFO = 100%: ceil(max(CBD_historico * factor, CBD_minimo_hora)).'
    )
    cbd_objetivo_nivel_a = fields.Integer(
        string='Buses Meta Base Nivel A (90% IFO)',
        compute='_compute_targets',
        store=True,
        help='Buses necesarios para alcanzar 90% de IFO en la hora sin arrastrar deuda.'
    )
    cbd_objetivo_nivel_b = fields.Integer(
        string='Buses Meta Base Nivel B (80% IFO)',
        compute='_compute_targets',
        store=True,
        help='Buses necesarios para alcanzar 80% de IFO en la hora.'
    )

    # IFO Objetivo Compensado (Teniendo en cuenta las horas previas de la misma franja)
    ifo_objetivo_compensado_100 = fields.Float(
        string='IFO Objetivo Comp. 100% (%)',
        digits=(6, 1),
        compute='_compute_compensated_targets',
        store=True,
        help='IFO que debe alcanzar esta hora para cerrar la franja con promedio de 100% IFO, compensando horas previas.'
    )
    cbd_objetivo_compensado_100 = fields.Integer(
        string='Buses Req. Comp. [100% IFO]',
        compute='_compute_compensated_targets',
        store=True,
        help='Cantidad de buses en calle necesaria en esta hora para promediar 100% IFO en toda la franja.'
    )
    ifo_objetivo_compensado_a = fields.Float(
        string='IFO Objetivo Compensado (%) [Nivel A]',
        digits=(6, 1),
        compute='_compute_compensated_targets',
        store=True,
        help='IFO que debe alcanzar esta hora para que el promedio de la franja llegue a 90% (Nivel A), compensando horas previas.'
    )
    cbd_objetivo_compensado_a = fields.Integer(
        string='Buses Requeridos Compensados [Nivel A]',
        compute='_compute_compensated_targets',
        store=True,
        help='Cantidad de buses distintos que debe sacar en esta hora para cumplir el IFO Objetivo Compensado (Nivel A).'
    )
    ifo_objetivo_compensado_b = fields.Float(
        string='IFO Mínimo Compensado (%) [Nivel B]',
        digits=(6, 1),
        compute='_compute_compensated_targets',
        store=True,
        help='IFO mínimo en esta hora para que la franja no caiga en Nivel C (< 80%).'
    )
    cbd_objetivo_compensado_b = fields.Integer(
        string='Buses Mínimos Compensados [Nivel B]',
        compute='_compute_compensated_targets',
        store=True
    )
    buses_faltantes_minimo = fields.Integer(
        string='Faltan p/ CBD Mínimo',
        compute='_compute_compensated_targets',
        store=True
    )
    buses_faltantes_100 = fields.Integer(
        string='Faltan p/ 100% IFO (Hora)',
        compute='_compute_compensated_targets',
        store=True,
        help='Cantidad de buses que falta incorporar respecto al CBD Objetivo (100% IFO) de esta hora.'
    )
    buses_faltantes_comp_100 = fields.Integer(
        string='Faltan p/ 100% IFO (Comp.)',
        compute='_compute_compensated_targets',
        store=True,
        help='Cantidad de buses que falta incorporar respecto a la meta compensada de 100% IFO.'
    )
    buses_faltantes_a = fields.Integer(
        string='Faltan p/ IFO Objetivo (Nivel A)',
        compute='_compute_compensated_targets',
        store=True
    )

    # IFO Calculado y Nivel de Servicio
    ifo_pct = fields.Float(
        string='IFO Actual (%)',
        digits=(6, 1),
        compute='_compute_ifo',
        store=True,
        tracking=True,
        help='Fórmula cbd_monitor: IFO = (CBD_actual / max(CBD_historico * factor, CBD_minimo_hora)) * 100'
    )
    ifo_level = fields.Selection([
        ('A', 'Nivel A (>= 90%)'),
        ('B', 'Nivel B (80% - 89.9%)'),
        ('C', 'Nivel C (< 80%)'),
    ], string='Nivel IFO Hora', compute='_compute_ifo', store=True, tracking=True)

    cumple_cbd_minimo = fields.Boolean(
        string='Cumple CBD Mínimo Hora',
        compute='_compute_ifo',
        store=True
    )

    state = fields.Selection([
        ('compliant', 'Cumple (Nivel A y CBD Mínimo)'),
        ('warning', 'Apercibimiento / Riesgo (Nivel B)'),
        ('breach', 'Incumplimiento / Déficit (Nivel C o < CBD Mín.)'),
    ], string='Estado Horario', compute='_compute_ifo', store=True)

    # Alertas Preventivas al ir culminando la hora
    is_current_hour = fields.Boolean(string='Hora en Curso', compute='_compute_is_current_hour')
    alert_status = fields.Selection([
        ('ok', 'Cumple Meta'),
        ('warning', 'Alerta Preventiva (Subir Operativa)'),
        ('critical', 'Riesgo de Incumplimiento'),
    ], string='Alerta Horaria', compute='_compute_alerts', store=True)

    alert_message = fields.Text(string='Indicación / Alerta de la Hora', compute='_compute_alerts', store=True)

    _sql_constraints = [
        ('concessionaire_date_hour_unique',
         'unique(concessionaire_id, date, hour)',
         'Ya existe un registro horario para esta empresa, fecha y hora.')
    ]

    @api.depends('hour')
    def _compute_hour_label(self):
        for rec in self:
            rec.hour_label = f"{rec.hour:02d}:00 - {rec.hour:02d}:59"

    @api.depends('date', 'hour')
    def _compute_is_current_hour(self):
        now_py = _get_paraguay_now()
        today = now_py.date()
        current_hour = now_py.hour
        for rec in self:
            rec.is_current_hour = (rec.date == today and rec.hour == current_hour)

    @api.depends('cbd_historico', 'adjustment_factor', 'cbd_minimo_hora')
    def _compute_targets(self):
        for rec in self:
            raw_adj = rec.cbd_historico * rec.adjustment_factor
            base_adj = round(max(raw_adj, float(rec.cbd_minimo_hora)), 2)
            rec.cbd_denominador_ajustado = base_adj
            rec.cbd_objetivo = math.ceil(base_adj) if base_adj > 0 else rec.cbd_minimo_hora
            rec.cbd_objetivo_nivel_a = max(math.ceil(0.90 * base_adj), rec.cbd_minimo_hora) if base_adj > 0 else rec.cbd_minimo_hora
            rec.cbd_objetivo_nivel_b = max(math.ceil(0.80 * base_adj), rec.cbd_minimo_hora) if base_adj > 0 else rec.cbd_minimo_hora

    @api.depends('distinct_buses_count', 'cbd_historico', 'adjustment_factor', 'cbd_minimo_hora', 'cbd_denominador_ajustado')
    def _compute_ifo(self):
        for rec in self:
            denominador = rec.cbd_denominador_ajustado or round(max(rec.cbd_historico * rec.adjustment_factor, float(rec.cbd_minimo_hora)), 2)
            if denominador > 0:
                ifo = round((rec.distinct_buses_count / denominador) * 100.0, 1)
            else:
                ifo = 100.0 if rec.distinct_buses_count > 0 else 0.0

            rec.ifo_pct = ifo
            rec.cumple_cbd_minimo = (rec.distinct_buses_count >= rec.cbd_minimo_hora)

            if ifo >= 90.0 and rec.cumple_cbd_minimo:
                rec.ifo_level = 'A'
                rec.state = 'compliant'
            elif ifo >= 80.0 and rec.cumple_cbd_minimo:
                rec.ifo_level = 'B'
                rec.state = 'warning'
            else:
                rec.ifo_level = 'A' if ifo >= 90.0 else ('B' if ifo >= 80.0 else 'C')
                rec.state = 'breach'

    @api.depends(
        'hour',
        'distinct_buses_count',
        'ifo_pct',
        'cbd_denominador_ajustado',
        'cbd_minimo_hora',
        'cbd_objetivo',
        'cbd_objetivo_nivel_a',
        'cbd_objetivo_nivel_b',
        'franja_id.hourly_line_ids.ifo_pct',
        'franja_id.hourly_line_ids.hour',
        'franja_id.start_hour',
        'franja_id.end_hour',
    )
    def _compute_compensated_targets(self):
        """
        Calcula para cada hora h su IFO Objetivo Compensado considerando el IFO obtenido
        en las horas previas de la misma franja.
        Ejemplo: Franja Pico 5 a 7 (3 horas).
        - En h=5: no hay horas previas -> IFO Objetivo = 90%. Si tuvo IFO=50%:
        - En h=6 y h=7: horas previas = {5} (suma=50%), faltan M=2 horas (6 y 7) ->
          IFO Objetivo = (90*3 - 50) / 2 = 220 / 2 = 110.0%!
        """
        for rec in self:
            denom = rec.cbd_denominador_ajustado or max(rec.cbd_historico * rec.adjustment_factor, float(rec.cbd_minimo_hora))
            if rec.franja_id and rec.franja_id.hourly_line_ids:
                siblings = sorted(rec.franja_id.hourly_line_ids, key=lambda x: x.hour)
                total_n = max(len(siblings), 1)
                active_hours = [s.hour for s in siblings if s.distinct_buses_count > 0]
                last_active_h = max(active_hours) if active_hours else -1
                if last_active_h >= 0 and rec.hour > last_active_h:
                    # Para todas las horas futuras/restantes después de la última hora operada,
                    # se reparte equitativamente la meta faltante de la franja (ej. h=6 y h=7 -> 110% cada una)
                    prev_lines = [s for s in siblings if s.hour <= last_active_h]
                else:
                    prev_lines = [s for s in siblings if s.hour < rec.hour]
                rem_count = total_n - len(prev_lines)
                sum_prev_ifo = sum(s.ifo_pct for s in prev_lines)

                if rem_count > 0:
                    req_100 = max(round(((100.0 * total_n) - sum_prev_ifo) / rem_count, 1), 0.0)
                    req_a = max(round(((90.0 * total_n) - sum_prev_ifo) / rem_count, 1), 0.0)
                    req_b = max(round(((80.0 * total_n) - sum_prev_ifo) / rem_count, 1), 0.0)
                else:
                    req_100 = 100.0
                    req_a = 90.0
                    req_b = 80.0
            else:
                req_100 = 100.0
                req_a = 90.0
                req_b = 80.0

            rec.ifo_objetivo_compensado_100 = req_100
            rec.ifo_objetivo_compensado_a = req_a
            rec.ifo_objetivo_compensado_b = req_b

            buses_100 = math.ceil((req_100 / 100.0) * denom) if (denom > 0 and req_100 > 0) else rec.cbd_minimo_hora
            buses_a = math.ceil((req_a / 100.0) * denom) if (denom > 0 and req_a > 0) else rec.cbd_minimo_hora
            buses_b = math.ceil((req_b / 100.0) * denom) if (denom > 0 and req_b > 0) else rec.cbd_minimo_hora

            rec.cbd_objetivo_compensado_100 = max(buses_100, rec.cbd_minimo_hora)
            rec.cbd_objetivo_compensado_a = max(buses_a, rec.cbd_minimo_hora)
            rec.cbd_objetivo_compensado_b = max(buses_b, rec.cbd_minimo_hora)

            rec.buses_faltantes_minimo = max(0, rec.cbd_minimo_hora - rec.distinct_buses_count)
            rec.buses_faltantes_100 = max(0, rec.cbd_objetivo - rec.distinct_buses_count)
            rec.buses_faltantes_comp_100 = max(0, rec.cbd_objetivo_compensado_100 - rec.distinct_buses_count)
            rec.buses_faltantes_a = max(0, rec.cbd_objetivo_compensado_a - rec.distinct_buses_count)

    @api.depends(
        'distinct_buses_count',
        'cbd_minimo_hora',
        'cbd_objetivo_compensado_a',
        'ifo_objetivo_compensado_a',
        'buses_faltantes_minimo',
        'buses_faltantes_a',
        'ifo_pct',
        'ifo_level',
    )
    def _compute_alerts(self):
        now_py = _get_paraguay_now()
        today = now_py.date()
        current_hour = now_py.hour
        minute = now_py.minute

        for rec in self:
            is_curr = (rec.date == today and rec.hour == current_hour)
            msgs = []
            status = 'ok'

            if rec.buses_faltantes_minimo > 0:
                status = 'critical'
                if is_curr:
                    cierre = f" (¡Culminando hora, min {minute:02d}!)" if minute >= 35 else ""
                    msgs.append(
                        f"🚨 INCUMPLIMIENTO CBD MÍNIMO HORARIO{cierre}: "
                        f"Buses actuales: {rec.distinct_buses_count} / Mínimo exigido: {rec.cbd_minimo_hora}. "
                        f"¡Debe sacar {rec.buses_faltantes_minimo} bus(es) más de inmediato!"
                    )
                else:
                    msgs.append(
                        f"❌ Déficit CBD Mínimo Horario: operaron {rec.distinct_buses_count} de {rec.cbd_minimo_hora} buses mínimos."
                    )

            if rec.buses_faltantes_a > 0:
                if status != 'critical':
                    status = 'critical' if rec.ifo_objetivo_compensado_a > 100.0 or (is_curr and minute >= 40) else 'warning'
                if rec.ifo_objetivo_compensado_a > 90.0:
                    msgs.append(
                        f"🎯 COMPENSACIÓN REQUERIDA: Para recuperar el promedio de la franja (Nivel A >= 90%), "
                        f"el IFO Objetivo de esta hora es {rec.ifo_objetivo_compensado_a}% "
                        f"({rec.cbd_objetivo_compensado_a} buses). "
                        f"Actual: {rec.distinct_buses_count} buses (IFO {rec.ifo_pct}%) -> "
                        f"Faltan aumentar {rec.buses_faltantes_a} bus(es)."
                    )
                else:
                    msgs.append(
                        f"⚠️ Meta Nivel A ({rec.ifo_objetivo_compensado_a}% IFO = {rec.cbd_objetivo_compensado_a} buses): "
                        f"Faltan {rec.buses_faltantes_a} bus(es) en circulación."
                    )
            else:
                if status == 'ok':
                    msgs.append(
                        f"✅ Cumple IFO Objetivo ({rec.ifo_pct}% >= {rec.ifo_objetivo_compensado_a}%) "
                        f"y CBD Mínimo ({rec.distinct_buses_count} >= {rec.cbd_minimo_hora} buses)."
                    )

            rec.alert_status = status
            rec.alert_message = " | ".join(msgs)

    def action_recalculate_day(self):
        """Acción desde botón para recalcular todo el día de la empresa."""
        for rec in self:
            self.compute_cbd_for_date_and_company(rec.date, rec.concessionaire_id.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cálculo Completado'),
                'message': _('Se actualizaron los conteos de buses distintos, IFO y alertas del día.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_sync_today_live(self):
        """Sincroniza el día actual desde VMT / CID / GPS Broker desde el botón de cabecera en lista."""
        self.cron_update_today_cbd_ifo()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    # ==========================================================================
    # MOTOR DE CÁLCULO OFICIAL (IDÉNTICO A bus_monitor.py + performance.py)
    # ==========================================================================
    @api.model
    def compute_cbd_for_date_and_company(
        self,
        target_date: date,
        concessionaire_id: Optional[int] = None,
        min_duracion_min: int = 15,
        min_mensajes: int = 30,
    ):
        """
        Ejecuta el cálculo exacto de bus_monitor.py y performance.py para la fecha y empresa,
        guardando los buses distintos por hora y por franja en la BD de transporte_odoo (flota_db).
        """
        if isinstance(target_date, str):
            target_date = fields.Date.from_string(target_date)

        if concessionaire_id:
            concessionaires = self.env['transit.concessionaire'].browse([concessionaire_id])
        else:
            concessionaires = self.env['transit.concessionaire'].search([('active', '=', True)])

        for conc in concessionaires:
            agency_id = (conc.agency_id or conc.code or '').strip()
            if not agency_id:
                continue
            _logger.info(
                "Procesando CBD/IFO para empresa %s (agency_id=%s) en fecha %s",
                conc.name, agency_id, target_date
            )
            self._process_single_company(conc, target_date, min_duracion_min=min_duracion_min, min_mensajes=min_mensajes)

    @api.model
    def _process_single_company(
        self,
        concessionaire,
        target_date: date,
        min_duracion_min: int = 15,
        min_mensajes: int = 30,
    ):
        agency_id = (concessionaire.agency_id or concessionaire.code).strip()
        conc_id = concessionaire.id

        # 1. Determinar tipo de día (5=Laboral, 6=Sábado, 7=Domingo/Feriado)
        td = self._get_tipo_dia(target_date)

        # 2. Obtener TODAS las franjas horarias del tipo de día y parámetros mínimos (CID DB)
        franjas_config = self._get_franjas_and_minimos(td, target_date)

        # 3. Obtener las 4 fechas históricas de referencia, factor de ajuste y datos de Feriados/Open-Meteo
        fechas_ref, factor_ajuste, detalle_ajuste, weather_meta = self._get_historical_dates_and_factors(target_date)
        ref_dates_str = ", ".join(d.strftime("%Y-%m-%d") for d in fechas_ref)

        # 4. Extraer los buses distintos en tránsito fuera de terminales (algoritmo bus_monitor.py)
        # Priorizando GPS de gps_broker (telemetry_ping en flota_db) y complementando con CID DB
        buses_by_hour, buses_detail_by_hour, source_used = self._extract_valid_transit_buses(
            agency_id, target_date, min_duracion_min=min_duracion_min, min_mensajes=min_mensajes
        )

        # 5. Obtener CBD histórico por hora y por franja en las 4 fechas de referencia
        hist_by_hour, hist_by_franja = self._get_historical_cbd(agency_id, fechas_ref, franjas_config)

        # 6. Guardar en las tablas de transporte_odoo: transit_cbd_franja, transit_cbd_hourly y transit_cbd_bus_detail
        for fr_info in franjas_config:
            fr_id_cid = fr_info.get('id_franja', 0)
            fr_name = fr_info['nombre']
            h_start = fr_info['h_start']
            h_end = fr_info['h_end']
            min_f = fr_info['min_franja']
            min_h = fr_info['min_hora']
            ifo_min_pct = float(fr_info.get('ifo_min_pct', 80.0))
            hist_f_avg = hist_by_franja.get((h_start, h_end), 0.0)

            franja_rec = self.env['transit.cbd.franja'].sudo().search([
                ('concessionaire_id', '=', conc_id),
                ('date', '=', target_date),
                ('start_hour', '=', h_start),
                ('end_hour', '=', h_end),
            ], limit=1)

            franja_vals = {
                'concessionaire_id': conc_id,
                'date': target_date,
                'cid_franja_id': fr_id_cid,
                'name': fr_name,
                'start_hour': h_start,
                'end_hour': h_end,
                'tipo_dia': str(td),
                'cbd_minimo_franja': min_f,
                'cbd_minimo_hora': min_h,
                'ifo_umbral_minimo': ifo_min_pct,
                'cbd_historico_franja': hist_f_avg,
                'adjustment_factor': factor_ajuste,
                'factor_details': detalle_ajuste,
                'reference_dates_info': ref_dates_str,
                'is_holiday': weather_meta.get('is_holiday', False),
                'holiday_info': weather_meta.get('holiday_info', 'Día Normal'),
                'is_rainy_day': weather_meta.get('is_rainy_day', False),
                'precipitation_mm': weather_meta.get('precipitation_mm', 0.0),
                'weather_description': weather_meta.get('weather_description', '☀️ Despejado (0.0 mm)'),
                'excluded_dates_info': weather_meta.get('excluded_dates_info', 'Ninguna fecha descartada'),
            }

            if not franja_rec:
                franja_rec = self.env['transit.cbd.franja'].sudo().create(franja_vals)
            else:
                franja_rec.sudo().write(franja_vals)

            all_buses_franja: Set[str] = set()

            for h in range(h_start, h_end + 1):
                buses_hora = buses_by_hour.get(h, [])
                all_buses_franja.update(buses_hora)
                cbd_obs = len(buses_hora)
                cbd_hist_avg = hist_by_hour.get(h, 0.0)

                hourly_rec = self.sudo().search([
                    ('concessionaire_id', '=', conc_id),
                    ('date', '=', target_date),
                    ('hour', '=', h),
                ], limit=1)

                h_vals = {
                    'concessionaire_id': conc_id,
                    'date': target_date,
                    'hour': h,
                    'franja_id': franja_rec.id,
                    'distinct_buses_count': cbd_obs,
                    'bus_codes_summary': ", ".join(sorted(buses_hora)) if buses_hora else "Sin buses en tránsito",
                    'data_source': source_used,
                    'cbd_minimo_hora': min_h,
                    'cbd_historico': cbd_hist_avg,
                    'adjustment_factor': factor_ajuste,
                    'factor_details': detalle_ajuste,
                }

                if hourly_rec:
                    hourly_rec.sudo().write(h_vals)
                else:
                    hourly_rec = self.sudo().create(h_vals)

                # Actualizar detalle individual de buses por hora
                self.env['transit.cbd.bus.detail'].sudo().search([('hourly_id', '=', hourly_rec.id)]).unlink()
                details_to_create = []
                for b_info in buses_detail_by_hour.get(h, []):
                    details_to_create.append({
                        'hourly_id': hourly_rec.id,
                        'concessionaire_id': conc_id,
                        'agency_id': agency_id,
                        'date': target_date,
                        'hour': h,
                        'bus_internal_code': b_info['mean_id'],
                        'first_ping': b_info['primera_posicion_timestamp'],
                        'last_ping': b_info['ultima_posicion_timestamp'],
                        'message_count': b_info['cantidad_mensajes'],
                        'duration_min': b_info['duracion_min'],
                        'is_valid_transit': b_info['is_valid'],
                    })
                if details_to_create:
                    self.env['transit.cbd.bus.detail'].sudo().create(details_to_create)

            now_py_dt = _get_paraguay_now()
            now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            cutoff_15m = now_utc_naive - timedelta(minutes=15)
            active_vivo_buses: Set[str] = set()
            if target_date == now_py_dt.date() and h_start <= now_py_dt.hour <= h_end:
                for h_chk in range(h_start, h_end + 1):
                    for b_info in buses_detail_by_hour.get(h_chk, []):
                        last_p = b_info.get('ultima_posicion_timestamp')
                        if b_info.get('is_valid') and last_p and last_p >= cutoff_15m:
                            active_vivo_buses.add(b_info['mean_id'])

            # Actualizar conteo de buses distintos acumulados en toda la franja y activos en últimos 15 min
            franja_rec.sudo().write({
                'cbd_franja_distinct': len(all_buses_franja),
                'buses_en_calle_vivo': len(active_vivo_buses),
                'last_sync_at': fields.Datetime.now(),
            })
            # Forzar recálculo de objetivos compensados entre hermanos de la franja
            franja_rec.hourly_line_ids._compute_compensated_targets()
            franja_rec.hourly_line_ids._compute_alerts()
            franja_rec._compute_progress()
            franja_rec._compute_cbd_metrics()
            franja_rec._compute_ifo_metrics()
            franja_rec._compute_compensation()
            franja_rec._compute_live_ifo_100()
            franja_rec._compute_alerts()

    @api.model
    def _get_tipo_dia(self, target_date: date) -> int:
        """Determina el id_tipo_dia (5=Laboral, 6=Sábado, 7=Domingo/Feriado) igual que cbd_monitor."""
        dow = target_date.weekday()
        es_feriado = bool(self.env['transit.holiday'].sudo().search([
            ('date', '=', target_date), ('active', '=', True)
        ], limit=1))

        if not es_feriado:
            conn_cid = _get_cid_connection()
            if conn_cid:
                try:
                    cur = conn_cid.cursor()
                    cur.execute("SELECT 1 FROM public.feriados WHERE fecha = %s LIMIT 1;", (target_date,))
                    es_feriado = cur.fetchone() is not None
                    cur.close()
                    conn_cid.close()
                except Exception:
                    pass

        if es_feriado or dow == 6:
            return 7
        elif dow == 5:
            return 6
        return 5

    @api.model
    def _get_franjas_and_minimos(self, tipo_dia: int, target_date: date) -> List[Dict]:
        """
        Obtiene TODAS las franjas operativas vigentes para el tipo_dia y sus parámetros mínimos
        de CBD e IFO desde la BD CID (control_metricas.franjas_operativas, cbd_parametros_minimos, parametros_ifo).
        """
        conn_cid = _get_cid_connection()
        if conn_cid:
            try:
                cur = conn_cid.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT id_franja, denominacion, hora_inicio, hora_fin
                    FROM control_metricas.franjas_operativas
                    WHERE id_tipo_dia = %s
                      AND activo = TRUE
                      AND (inicio_vigencia IS NULL OR inicio_vigencia <= %s)
                      AND (fin_vigencia IS NULL OR fin_vigencia >= %s)
                    ORDER BY hora_inicio;
                """, (tipo_dia, target_date, target_date))
                franjas = cur.fetchall()
                if not franjas:
                    cur.execute("""
                        SELECT id_franja, denominacion, hora_inicio, hora_fin
                        FROM control_metricas.franjas_operativas
                        WHERE id_tipo_dia = %s AND activo = TRUE
                        ORDER BY hora_inicio;
                    """, (tipo_dia,))
                    franjas = cur.fetchall()

                cur.execute("""
                    SELECT id_franja, cbd_minimo_hora, cbd_minimo_franja
                    FROM control_metricas.cbd_parametros_minimos
                    WHERE id_tipo_dia = %s
                    ORDER BY vigencia_desde DESC NULLS LAST;
                """, (tipo_dia,))
                params = {}
                for r in cur.fetchall():
                    if r['id_franja'] not in params:
                        params[r['id_franja']] = r

                cur.execute("""
                    SELECT id_franja_operativa, porc_cumplimiento_minimo
                    FROM control_metricas.parametros_ifo
                    ORDER BY inicio_vigencia DESC NULLS LAST;
                """)
                ifo_params = {}
                for r in cur.fetchall():
                    if r['id_franja_operativa'] not in ifo_params:
                        ifo_params[r['id_franja_operativa']] = float(r['porc_cumplimiento_minimo'] or 80.0)

                cur.close()
                conn_cid.close()

                if franjas:
                    res = []
                    for f in franjas:
                        fid = f['id_franja']
                        p = params.get(fid, {})
                        res.append({
                            'id_franja': fid,
                            'nombre': f['denominacion'],
                            'h_start': f['hora_inicio'].hour,
                            'h_end': f['hora_fin'].hour,
                            'min_franja': int(p.get('cbd_minimo_franja') or 0),
                            'min_hora': int(p.get('cbd_minimo_hora') or 0),
                            'ifo_min_pct': ifo_params.get(fid, 80.0 if ('Pico' in f['denominacion'] and 'Pos' not in f['denominacion']) else 90.0),
                        })
                    return res
            except Exception as e:
                _logger.debug("Aviso consultando franjas en CID DB: %s", e)

        # Respaldo exacto de las 10 franjas activas en la BD CID (control_metricas.franjas_operativas + cbd_parametros_minimos + parametros_ifo)
        if tipo_dia == 5:
            return [
                {'id_franja': 40, 'nombre': 'Madrugada', 'h_start': 4, 'h_end': 4, 'min_franja': 3, 'min_hora': 3, 'ifo_min_pct': 90.0},
                {'id_franja': 30, 'nombre': 'Pico Mañana', 'h_start': 5, 'h_end': 7, 'min_franja': 12, 'min_hora': 4, 'ifo_min_pct': 80.0},
                {'id_franja': 31, 'nombre': 'Pos Pico (entre picos)', 'h_start': 8, 'h_end': 15, 'min_franja': 9, 'min_hora': 3, 'ifo_min_pct': 90.0},
                {'id_franja': 32, 'nombre': 'Pico Tarde', 'h_start': 16, 'h_end': 18, 'min_franja': 12, 'min_hora': 4, 'ifo_min_pct': 80.0},
                {'id_franja': 33, 'nombre': 'Pos Pico Tarde', 'h_start': 19, 'h_end': 20, 'min_franja': 6, 'min_hora': 3, 'ifo_min_pct': 90.0},
                {'id_franja': 34, 'nombre': 'Nocturno Laboral', 'h_start': 21, 'h_end': 22, 'min_franja': 4, 'min_hora': 2, 'ifo_min_pct': 90.0},
            ]
        elif tipo_dia == 6:
            return [
                {'id_franja': 35, 'nombre': 'Pico Sábado', 'h_start': 6, 'h_end': 15, 'min_franja': 12, 'min_hora': 3, 'ifo_min_pct': 90.0},
                {'id_franja': 36, 'nombre': 'Pos Pico Sábado', 'h_start': 16, 'h_end': 20, 'min_franja': 10, 'min_hora': 2, 'ifo_min_pct': 90.0},
                {'id_franja': 37, 'nombre': 'Nocturno Sábado', 'h_start': 21, 'h_end': 22, 'min_franja': 4, 'min_hora': 2, 'ifo_min_pct': 90.0},
            ]
        return [
            {'id_franja': 38, 'nombre': 'Servicio Reducido(Pos pico)', 'h_start': 7, 'h_end': 21, 'min_franja': 9, 'min_hora': 2, 'ifo_min_pct': 90.0},
        ]

    @api.model
    def _get_historical_dates_and_factors(self, target_date: date) -> Tuple[List[date], float, str, Dict[str, Any]]:
        """
        Replica get_fechas_referencia y get_factores_ajuste_acumulados de cbd_monitor,
        integrando directamente:
          1. Feriados nacionales y asuetos (public.feriados en CID DB + sincronización con transit.holiday en flota_db),
             incluyendo Pre-Feriados y Post-Feriados.
          2. Días de Lluvia obtenidos directamente de la API de Open-Meteo (Archive ERA5 + Forecast API para Central)
             y complementados con control_metricas.t_casuisticas_lluvia / dias_atipicos en CID DB.
        """
        factor_total = 1.0
        ajustes = []
        month = target_date.month
        year = target_date.year
        weekday = target_date.weekday()

        # 1. Factores Mensuales (Capa 1)
        if month == 1:
            factor_total *= 0.80
            ajustes.append("Mes Enero (0.80)")
        elif month == 12:
            factor_total *= 0.80
            ajustes.append("Mes Diciembre (0.80)")

        # Conjuntos de fechas de feriados y motivos de descarte
        feriados_map: Dict[date, str] = {}
        atipicos_reasons: Dict[date, str] = {}
        atipicos_hoy: List[Dict] = []
        lluvia_cid_by_date: Dict[date, float] = {}

        # 0. Consultar tablas locales en flota_db: transit.holiday, transit.atypical.day y transit.rain.casuistica
        for h in self.env['transit.holiday'].sudo().search([('active', '=', True)]):
            if h.date:
                feriados_map[h.date] = h.name or "Feriado"

        try:
            local_atipicos = self.env['transit.atypical.day'].sudo().search([('active', '=', True)])
            for at_rec in local_atipicos:
                f_at = at_rec.fecha
                if not f_at:
                    continue
                if at_rec.descartar_historico or at_rec.tipo_atipico == 'LLUVIA':
                    atipicos_reasons[f_at] = f"{at_rec.tipo_atipico}: {at_rec.observacion or ''}".strip(": ")
                if f_at == target_date:
                    atipicos_hoy.append({
                        'tipo_atipico': at_rec.tipo_atipico,
                        'factor_exigencia': at_rec.factor_exigencia,
                        'observacion': at_rec.observacion or '',
                    })
                if at_rec.tipo_atipico == 'LLUVIA' and (at_rec.mm_caidos or 0.0) > 0:
                    lluvia_cid_by_date[f_at] = max(lluvia_cid_by_date.get(f_at, 0.0), float(at_rec.mm_caidos))

            self.env.cr.execute("""
                SELECT fecha_evento, MAX(mm_caidos) AS max_mm
                FROM transit_rain_casuistica
                WHERE fecha_evento >= %s AND fecha_evento <= %s
                GROUP BY fecha_evento;
            """, (target_date - timedelta(days=380), target_date))
            for r in self.env.cr.dictfetchall():
                if r.get('max_mm') is not None:
                    f_ev = r['fecha_evento']
                    lluvia_cid_by_date[f_ev] = max(lluvia_cid_by_date.get(f_ev, 0.0), float(r['max_mm']))
        except Exception as e_loc:
            _logger.debug("Aviso consultando transit_atypical_day / transit_rain_casuistica local: %s", e_loc)

        # Consultar CID DB para feriados, dias_atipicos y t_casuisticas_lluvia (y sincronizar en flota_db)
        conn_cid = _get_cid_connection()
        if conn_cid:
            try:
                cur = conn_cid.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT fecha, descripcion FROM public.feriados WHERE fecha IS NOT NULL;")
                for r in cur.fetchall():
                    f_dt = r['fecha']
                    f_desc = r.get('descripcion') or 'Feriado Oficial'
                    if f_dt not in feriados_map:
                        feriados_map[f_dt] = f_desc
                        if 2024 <= f_dt.year <= 2030:
                            try:
                                existing_h = self.env['transit.holiday'].sudo().search([('date', '=', f_dt)], limit=1)
                                if not existing_h:
                                    self.env['transit.holiday'].sudo().create({
                                        'name': f_desc,
                                        'date': f_dt,
                                        'active': True,
                                    })
                            except Exception:
                                pass

                cur.execute("""
                    SELECT fecha, tipo_atipico, observacion
                    FROM control_metricas.dias_atipicos
                    WHERE NOT (tipo_atipico = 'DISRUPTIVO' AND COALESCE(descartar_historico, false) = false);
                """)
                for r in cur.fetchall():
                    atipicos_reasons[r['fecha']] = f"{r.get('tipo_atipico')}: {r.get('observacion') or ''}".strip(": ")

                cur.execute("""
                    SELECT tipo_atipico, factor_exigencia, observacion
                    FROM control_metricas.dias_atipicos
                    WHERE fecha = %s;
                """, (target_date,))
                for r in cur.fetchall():
                    if not any(x.get('tipo_atipico') == r.get('tipo_atipico') for x in atipicos_hoy):
                        atipicos_hoy.append(r)

                cur.execute("""
                    SELECT fecha_evento, MAX(mm_caidos) as max_mm
                    FROM control_metricas.t_casuisticas_lluvia
                    WHERE fecha_evento >= %s AND fecha_evento <= %s
                    GROUP BY fecha_evento;
                """, (target_date - timedelta(days=380), target_date))
                for r in cur.fetchall():
                    if r['max_mm'] is not None:
                        f_ev = r['fecha_evento']
                        lluvia_cid_by_date[f_ev] = max(lluvia_cid_by_date.get(f_ev, 0.0), float(r['max_mm']))

                cur.close()
                conn_cid.close()
            except Exception as e:
                _logger.debug("Aviso consultando factores en CID DB: %s", e)

        feriados_set = set(feriados_map.keys())
        for f_dt, f_desc in feriados_map.items():
            atipicos_reasons[f_dt] = f"Feriado ({f_desc})"
            pre_d = f_dt - timedelta(days=1)
            pos_d = f_dt + timedelta(days=1)
            if pre_d not in atipicos_reasons:
                atipicos_reasons[pre_d] = f"Pre-Feriado ({f_desc})"
            if pos_d not in atipicos_reasons:
                atipicos_reasons[pos_d] = f"Post-Feriado ({f_desc})"

        # Consultar Open-Meteo para ventana histórica (últimas 18 semanas + fecha actual)
        om_start = target_date - timedelta(weeks=18)
        open_meteo_map = _fetch_open_meteo_rain_range(om_start, target_date)
        for d_om, info_om in open_meteo_map.items():
            mm_om = float(info_om.get("mm") or 0.0)
            mm_cid = lluvia_cid_by_date.get(d_om, 0.0)
            mm_eff = max(mm_om, mm_cid)
            if mm_eff >= 5.0:
                atipicos_reasons[d_om] = f"Lluvia Open-Meteo ({mm_eff:.1f} mm)"

        # Clima de hoy (target_date) según Open-Meteo + transit_rain_casuistica / CID DB
        om_today = open_meteo_map.get(target_date, {"mm": 0.0, "desc": "☀️ Despejado"})
        mm_today_om = float(om_today.get("mm") or 0.0)
        mm_today_cid = lluvia_cid_by_date.get(target_date, 0.0)
        mm_today_final = round(max(mm_today_om, mm_today_cid), 2)
        is_rainy_today = (mm_today_final >= 5.0)
        weather_desc_today = f"{om_today.get('desc', '🌡️ Clima')} ({mm_today_final:.1f} mm - Open-Meteo)"

        # Si target_date es día de lluvia (>= 5mm), asegurar su persistencia en transit_atypical_day (flota_db)
        if is_rainy_today:
            try:
                existing_at = self.env['transit.atypical.day'].sudo().search([
                    ('fecha', '=', target_date), ('tipo_atipico', '=', 'LLUVIA')
                ], limit=1)
                if not existing_at:
                    self.env['transit.atypical.day'].sudo().create({
                        'fecha': target_date,
                        'tipo_atipico': 'LLUVIA',
                        'factor_exigencia': 0.50,
                        'descartar_historico': True,
                        'fuente_dato': 'Open-Meteo',
                        'mm_caidos': mm_today_final,
                        'observacion': f"Lluvia acumulada > 5mm ({mm_today_final:.2f} mm en Central)",
                    })
            except Exception:
                pass

        # 2. Factores Diarios (Capa 2: Feriados y Pre/Post Feriado)
        is_holiday_today = (target_date in feriados_set)
        holiday_info_str = "Día Normal"
        if is_holiday_today:
            h_desc = feriados_map.get(target_date, "Feriado")
            if weekday == 5:
                factor_total *= 0.50
                ajustes.append(f"Feriado Sábado: {h_desc} (0.50)")
                holiday_info_str = f"Feriado Sábado: {h_desc} (Factor 0.50)"
            else:
                factor_total *= 0.30
                ajustes.append(f"Feriado Laboral: {h_desc} (0.30)")
                holiday_info_str = f"Feriado Laboral: {h_desc} (Factor 0.30)"
        else:
            hol_parts = []
            if (target_date - timedelta(days=1)) in feriados_set:
                factor_total *= 0.70
                h_ant = feriados_map.get(target_date - timedelta(days=1), "Feriado")
                ajustes.append(f"Post-Feriado de {h_ant} (0.70)")
                hol_parts.append(f"Post-Feriado ({h_ant})")
            if (target_date + timedelta(days=1)) in feriados_set:
                factor_total *= 0.70
                h_sig = feriados_map.get(target_date + timedelta(days=1), "Feriado")
                ajustes.append(f"Pre-Feriado de {h_sig} (0.70)")
                hol_parts.append(f"Pre-Feriado ({h_sig})")
            if hol_parts:
                holiday_info_str = " / ".join(hol_parts)

        # 3. Factor Climático Open-Meteo y Días Atípicos (Capa 3)
        lluvia_aplicada = False
        for at in atipicos_hoy:
            tipo = at.get('tipo_atipico') or ''
            # Evitar duplicar el factor de feriado o pre/pos-feriado si ya se aplicó en Capa 2
            if tipo in ('FERIADO_LAB', 'FERIADO_SAB', 'PRE_POS_FERIADO'):
                continue
            fac = float(at.get('factor_exigencia') or 1.0)
            obs = at.get('observacion') or ''
            factor_total *= fac
            if tipo == 'LLUVIA':
                ajustes.append(f"Lluvia ({obs}) ({fac})")
                lluvia_aplicada = True
                is_rainy_today = True
            else:
                ajustes.append(f"{tipo} ({fac})")

        if not lluvia_aplicada and is_rainy_today:
            factor_total *= 0.50
            ajustes.append(f"Lluvia Open-Meteo {mm_today_final:.1f}mm (0.50)")

        # 4. Selección de las 4 Fechas de Referencia (descartando Feriados, Pre/Post-Feriados y Lluvias Open-Meteo >= 5mm)
        discarded_log: List[str] = []

        def _es_atipica(d: date) -> bool:
            if d in atipicos_reasons:
                return True
            if d in feriados_set:
                return True
            # Si cae fuera de la ventana inicial de Open-Meteo (ej. Noviembre del año anterior), consultar puntualmente
            if d not in open_meteo_map:
                extra_om = _fetch_open_meteo_rain_range(d, d)
                open_meteo_map.update(extra_om)
                mm_d = max(float(extra_om.get(d, {}).get("mm") or 0.0), lluvia_cid_by_date.get(d, 0.0))
                if mm_d >= 5.0:
                    atipicos_reasons[d] = f"Lluvia Open-Meteo ({mm_d:.1f} mm)"
                    return True
            return False

        def _ajustar_fecha(d: date, usadas: Set[date]) -> date:
            ajustada = d
            guard = 0
            while (_es_atipica(ajustada) or ajustada in usadas) and guard < 26:
                if ajustada in atipicos_reasons:
                    entry_str = f"{ajustada.strftime('%Y-%m-%d')} ({atipicos_reasons[ajustada]})"
                    if entry_str not in discarded_log:
                        discarded_log.append(entry_str)
                ajustada -= timedelta(weeks=1)
                guard += 1
            return ajustada

        ref_month = None
        ref_year = year
        if month == 1:
            ref_month, ref_year = 11, year - 1
        elif month == 12:
            ref_month, ref_year = 11, year
        elif month == 3:
            ref_month, ref_year = 11, year - 1

        fechas_base: List[date] = []
        if ref_month:
            d_iter = date(ref_year, ref_month, 1)
            while d_iter.weekday() != weekday:
                d_iter += timedelta(days=1)
            while len(fechas_base) < 4 and d_iter.month == ref_month:
                fechas_base.append(d_iter)
                d_iter += timedelta(weeks=1)

        if len(fechas_base) < 4:
            fechas_base = [target_date - timedelta(weeks=i) for i in range(1, 5)]

        fechas_ajustadas: List[date] = []
        fechas_usadas: Set[date] = set()
        for f_ref in fechas_base[:4]:
            f_adj = _ajustar_fecha(f_ref, fechas_usadas)
            fechas_ajustadas.append(f_adj)
            fechas_usadas.add(f_adj)

        detalle_str = ", ".join(ajustes) if ajustes else "Ninguno (1.00)"
        weather_meta = {
            "is_holiday": is_holiday_today,
            "holiday_info": holiday_info_str,
            "is_rainy_day": is_rainy_today,
            "precipitation_mm": mm_today_final,
            "weather_description": weather_desc_today,
            "excluded_dates_info": "; ".join(discarded_log) if discarded_log else "Ninguna (4 semanas limpias)",
        }
        return fechas_ajustadas, round(factor_total, 2), detalle_str, weather_meta

    @api.model
    def _get_company_terminal_geoms_wkt(self, agency_id: str, target_date: date) -> List[str]:
        """
        Obtiene las geometrías WKT de geocercas de inicio (tipo 1), fin (tipo 2) y terminales (tipo 6)
        desde CID DB (igual que bus_monitor.py) para excluir buses estacionados en cabecera/patio.
        """
        wkts: List[str] = []
        conn_cid = _get_cid_connection()
        if conn_cid:
            try:
                cur = conn_cid.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT ST_AsText(pt.geom_geocerca) as geom_wkt
                    FROM geometria.puntos_terminales pt
                    WHERE pt.id_eot_vmt_hex = %s AND pt.geom_geocerca IS NOT NULL
                    UNION ALL
                    SELECT ST_AsText(gc.geom) as geom_wkt
                    FROM public.eots e
                    JOIN public.catalogo_rutas cr ON cr.id_eot_catalogo = e.cod_catalogo
                    JOIN geometria.historico_itinerario hi ON cr.ruta_hex = hi.ruta_hex
                    JOIN geometria.geocercas gc ON hi.id_itinerario = gc.id_itinerario
                    WHERE e.id_eot_vmt_hex = %s
                      AND cr.estado = TRUE
                      AND hi.vigente = TRUE
                      AND gc.id_tipo IN (1, 2, 6)
                      AND (hi.fecha_fin_vigencia IS NULL OR hi.fecha_fin_vigencia > %s)
                      AND gc.geom IS NOT NULL;
                """, (agency_id, agency_id, target_date))
                for r in cur.fetchall():
                    if r.get('geom_wkt'):
                        wkts.append(r['geom_wkt'])
                cur.close()
                conn_cid.close()
            except Exception as e:
                _logger.debug("Aviso obteniendo geocercas de CID DB: %s", e)
        return wkts

    @api.model
    def _extract_valid_transit_buses(
        self,
        agency_id: str,
        target_date: date,
        min_duracion_min: int = 15,
        min_mensajes: int = 30,
    ) -> Tuple[Dict[int, List[str]], Dict[int, List[Dict]], str]:
        """
        Calcula los buses distintos en tránsito por hora ejecutando el mismo análisis de
        cbd_monitor/res_120/bus_monitor.py y fusionando por hora las 3 fuentes oficiales:
        1. CID DB (control_metricas.cbd_detalle_buses) para las horas ya consolidadas por el VMT.
        2. VMT Live DB (app_monitoreo_mensajeoperativo en monitoreo.vmt.gov.py) para las horas
           en curso o aún no consolidadas en CID DB (filtrando terminales con PostGIS y aplicando
           la regla de continuidad operativa inteligente de bus_monitor.py).
        3. Telemetría local (telemetry_ping en flota_db).
        """
        buses_by_hour: Dict[int, List[str]] = {}
        buses_detail_by_hour: Dict[int, List[Dict]] = {}
        primary_source = 'cid_db'

        def _merge_hour_results(
            src_buses_by_hour: Dict[int, List[str]],
            src_detail_by_hour: Dict[int, List[Dict]],
        ):
            for h, b_list in src_buses_by_hour.items():
                existing_set = set(buses_by_hour.get(h, []))
                for b_code in b_list:
                    if b_code not in existing_set:
                        buses_by_hour.setdefault(h, []).append(b_code)
                        existing_set.add(b_code)
            for h, d_list in src_detail_by_hour.items():
                existing_map = {d['mean_id']: d for d in buses_detail_by_hour.get(h, [])}
                for d_item in d_list:
                    mid = d_item['mean_id']
                    if mid not in existing_map:
                        buses_detail_by_hour.setdefault(h, []).append(d_item)
                        existing_map[mid] = d_item
                    else:
                        ex = existing_map[mid]
                        if d_item.get('is_valid') and not ex.get('is_valid'):
                            ex['is_valid'] = True
                        if int(d_item.get('cantidad_mensajes') or 0) > int(ex.get('cantidad_mensajes') or 0):
                            ex['cantidad_mensajes'] = d_item['cantidad_mensajes']
                            ex['duracion_min'] = d_item['duracion_min']
                            ex['primera_posicion_timestamp'] = d_item['primera_posicion_timestamp']
                            ex['ultima_posicion_timestamp'] = d_item['ultima_posicion_timestamp']

        def _evaluate_raw_rows(raw_rows: List[Dict]) -> Tuple[Dict[int, List[str]], Dict[int, List[Dict]]]:
            out_buses: Dict[int, List[str]] = {}
            out_details: Dict[int, List[Dict]] = {}
            if not raw_rows:
                return out_buses, out_details

            now_py = _get_paraguay_now()
            is_today = (target_date == now_py.date())
            current_hour = now_py.hour if is_today else -1
            max_hour_in_data = max(int(r['hora']) for r in raw_rows)

            # Incluir también continuidad desde horas ya cargadas en buses_by_hour (ej. desde CID DB)
            buses_horas = set((str(r['mean_id']), int(r['hora'])) for r in raw_rows)
            for prev_h, prev_list in buses_by_hour.items():
                for prev_b in prev_list:
                    buses_horas.add((str(prev_b), int(prev_h)))

            for r in raw_rows:
                h = int(r['hora'])
                b = str(r['mean_id'])
                msgs = int(r['cantidad_mensajes'] or 0)
                active_route_msgs = int(r.get('mensajes_en_ruta', msgs) or 0)
                dur = 0.0
                first_ts = r['primera_posicion_timestamp']
                last_ts = r['ultima_posicion_timestamp']
                if first_ts and last_ts:
                    dur = (last_ts - first_ts).total_seconds() / 60.0
                    if hasattr(first_ts, 'tzinfo') and first_ts.tzinfo:
                        first_ts = first_ts.astimezone(timezone.utc).replace(tzinfo=None)
                    if hasattr(last_ts, 'tzinfo') and last_ts.tzinfo:
                        last_ts = last_ts.astimezone(timezone.utc).replace(tzinfo=None)

                continua_sig = (b, h + 1) in buses_horas
                viene_ant = (b, h - 1) in buses_horas
                is_live_edge = (h == current_hour) or (h == max_hour_in_data and not continua_sig)

                # Regla de _consolidar_detalles_buses en bus_monitor.py + continuidad en hora actual en curso:
                es_operativo = False
                if dur >= min_duracion_min and msgs >= min_mensajes:
                    es_operativo = True
                elif viene_ant and continua_sig:
                    es_operativo = True
                elif continua_sig and not viene_ant and msgs >= 15:
                    es_operativo = True
                elif is_live_edge and (
                    (viene_ant and msgs >= 2)
                    or (dur >= 8.0 and msgs >= 8)
                    or (active_route_msgs >= 3 and dur >= 2.0)
                ):
                    es_operativo = True

                out_details.setdefault(h, []).append({
                    'mean_id': b,
                    'primera_posicion_timestamp': first_ts,
                    'ultima_posicion_timestamp': last_ts,
                    'cantidad_mensajes': msgs,
                    'duracion_min': round(dur, 1),
                    'is_valid': es_operativo,
                })
                if es_operativo:
                    out_buses.setdefault(h, []).append(b)
            return out_buses, out_details

        # ------------------------------------------------------------------
        # 1. Consultar CID DB (control_metricas.cbd_detalle_buses)
        # ------------------------------------------------------------------
        max_cid_hour = -1
        conn_cid = _get_cid_connection()
        if conn_cid:
            try:
                cur = conn_cid.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT hora, mean_id, primera_posicion_timestamp, ultima_posicion_timestamp, cantidad_mensajes
                    FROM control_metricas.cbd_detalle_buses
                    WHERE id_eot_vmt_hex = %s AND fecha = %s
                    ORDER BY hora, mean_id;
                """, (agency_id, target_date))
                rows = cur.fetchall()
                cur.close()
                conn_cid.close()

                cid_buses: Dict[int, List[str]] = {}
                cid_details: Dict[int, List[Dict]] = {}
                for r in rows:
                    h = int(r['hora'])
                    if h > max_cid_hour:
                        max_cid_hour = h
                    mid = str(r['mean_id'])
                    cid_buses.setdefault(h, []).append(mid)
                    dur = 0.0
                    first_ts = r['primera_posicion_timestamp']
                    last_ts = r['ultima_posicion_timestamp']
                    if first_ts and last_ts:
                        dur = (last_ts - first_ts).total_seconds() / 60.0
                        if hasattr(first_ts, 'tzinfo') and first_ts.tzinfo:
                            first_ts = first_ts.astimezone(timezone.utc).replace(tzinfo=None)
                        if hasattr(last_ts, 'tzinfo') and last_ts.tzinfo:
                            last_ts = last_ts.astimezone(timezone.utc).replace(tzinfo=None)

                    cid_details.setdefault(h, []).append({
                        'mean_id': mid,
                        'primera_posicion_timestamp': first_ts,
                        'ultima_posicion_timestamp': last_ts,
                        'cantidad_mensajes': int(r['cantidad_mensajes'] or 1),
                        'duracion_min': round(dur, 1),
                        'is_valid': True,
                    })
                _merge_hour_results(cid_buses, cid_details)
            except Exception as e:
                _logger.debug("Aviso consultando cbd_detalle_buses en CID DB: %s", e)

        # ------------------------------------------------------------------
        # 2. Consultar VMT Live DB (app_monitoreo_mensajeoperativo) para horas
        #    aún no consolidadas en CID DB (ej. hoy desde max_cid_hour hasta hora actual)
        # ------------------------------------------------------------------
        now_py = _get_paraguay_now()
        days_diff = (now_py.date() - target_date).days
        max_expected_hour = now_py.hour if target_date == now_py.date() else 23
        terminal_wkts = None

        if days_diff <= 2 and max_cid_hour < max_expected_hour and agency_id in ('0008', '002A', '004B'):
            start_live_hour = max(0, max_cid_hour)  # incluye max_cid_hour para evaluar continuidad H-1
            start_local_dt = datetime.combine(target_date, time(start_live_hour, 0, 0))
            end_local_dt = datetime.combine(target_date, time(23, 59, 59))

            conn_vmt = _get_vmt_live_connection()
            if conn_vmt:
                try:
                    terminal_wkts = self._get_company_terminal_geoms_wkt(agency_id, target_date)
                    # Agregar también las terminales locales de transit_stop como WKT
                    self.env.cr.execute("""
                        SELECT ST_AsText(ST_Buffer(geom::geography, COALESCE(radius_meters, 100))::geometry) AS wkt
                        FROM transit_stop
                        WHERE stop_type IN ('origin', 'destination') AND geom IS NOT NULL;
                    """)
                    for r_stop in self.env.cr.dictfetchall():
                        if r_stop.get('wkt'):
                            terminal_wkts.append(r_stop['wkt'])

                    cur_vmt = conn_vmt.cursor(cursor_factory=RealDictCursor)
                    if terminal_wkts:
                        cur_vmt.execute("""
                            WITH terminal_geoms AS (
                                SELECT ST_SetSRID(ST_GeomFromText(wkt), 4326) AS geom
                                FROM unnest(%s::text[]) AS wkt
                            ),
                            consolidated_terminals AS (
                                SELECT ST_Union(geom) AS geom FROM terminal_geoms
                            )
                            SELECT
                                EXTRACT(HOUR FROM m.fecha_hora_procesamiento AT TIME ZONE 'America/Asuncion')::int AS hora,
                                m.mean_id::text AS mean_id,
                                MIN(m.fecha_hora_procesamiento AT TIME ZONE 'UTC') AS primera_posicion_timestamp,
                                MAX(m.fecha_hora_procesamiento AT TIME ZONE 'UTC') AS ultima_posicion_timestamp,
                                COUNT(*) AS cantidad_mensajes,
                                COUNT(*) FILTER (WHERE m.route_id IS NOT NULL AND m.route_id NOT IN ('0000', '', 'None')) AS mensajes_en_ruta
                            FROM public.app_monitoreo_mensajeoperativo m
                            CROSS JOIN consolidated_terminals ct
                            WHERE m.agency_id = %s
                              AND m.fecha_hora_procesamiento >= (%s::timestamp AT TIME ZONE 'America/Asuncion')
                              AND m.fecha_hora_procesamiento <= (%s::timestamp AT TIME ZONE 'America/Asuncion')
                              AND DATE(m.fecha_hora_procesamiento AT TIME ZONE 'America/Asuncion') = %s
                              AND m.latitude IS NOT NULL AND m.longitude IS NOT NULL
                              AND NOT (m.latitude = 0 AND m.longitude = 0)
                              AND (
                                  ct.geom IS NULL
                                  OR NOT ST_Within(ST_SetSRID(ST_MakePoint(m.longitude, m.latitude), 4326), ct.geom)
                              )
                            GROUP BY 1, 2
                            ORDER BY 1, 2;
                        """, (terminal_wkts, agency_id, start_local_dt, end_local_dt, target_date))
                    else:
                        cur_vmt.execute("""
                            SELECT
                                EXTRACT(HOUR FROM m.fecha_hora_procesamiento AT TIME ZONE 'America/Asuncion')::int AS hora,
                                m.mean_id::text AS mean_id,
                                MIN(m.fecha_hora_procesamiento AT TIME ZONE 'UTC') AS primera_posicion_timestamp,
                                MAX(m.fecha_hora_procesamiento AT TIME ZONE 'UTC') AS ultima_posicion_timestamp,
                                COUNT(*) AS cantidad_mensajes,
                                COUNT(*) FILTER (WHERE m.route_id IS NOT NULL AND m.route_id NOT IN ('0000', '', 'None')) AS mensajes_en_ruta
                            FROM public.app_monitoreo_mensajeoperativo m
                            WHERE m.agency_id = %s
                              AND m.fecha_hora_procesamiento >= (%s::timestamp AT TIME ZONE 'America/Asuncion')
                              AND m.fecha_hora_procesamiento <= (%s::timestamp AT TIME ZONE 'America/Asuncion')
                              AND DATE(m.fecha_hora_procesamiento AT TIME ZONE 'America/Asuncion') = %s
                              AND m.latitude IS NOT NULL AND m.longitude IS NOT NULL
                              AND NOT (m.latitude = 0 AND m.longitude = 0)
                            GROUP BY 1, 2
                            ORDER BY 1, 2;
                        """, (agency_id, start_local_dt, end_local_dt, target_date))

                    vmt_raw_rows = cur_vmt.fetchall()
                    cur_vmt.close()
                    conn_vmt.close()

                    if vmt_raw_rows:
                        vmt_buses, vmt_details = _evaluate_raw_rows(vmt_raw_rows)
                        _merge_hour_results(vmt_buses, vmt_details)
                        primary_source = 'gps_broker'
                except Exception as e:
                    _logger.warning("Aviso consultando app_monitoreo_mensajeoperativo en VMT Live DB: %s", e)
                    try:
                        conn_vmt.close()
                    except Exception:
                        pass

        # ------------------------------------------------------------------
        # 3. Complementar con telemetry_ping en flota_db (si tiene datos adicionales)
        # ------------------------------------------------------------------
        self.env.cr.execute("""
            SELECT COUNT(*)
            FROM telemetry_ping
            WHERE DATE(recorded_at AT TIME ZONE 'America/Asuncion') = %s
              AND agency_id = %s;
        """, (target_date, agency_id))
        local_ping_count = self.env.cr.fetchone()[0] or 0

        if local_ping_count > 0:
            if terminal_wkts is None:
                terminal_wkts = self._get_company_terminal_geoms_wkt(agency_id, target_date)
            if terminal_wkts:
                self.env.cr.execute("""
                    WITH local_terminals AS (
                        SELECT ST_Buffer(geom::geography, COALESCE(radius_meters, 100))::geometry AS geom
                        FROM transit_stop
                        WHERE stop_type IN ('origin', 'destination') AND geom IS NOT NULL
                        UNION ALL
                        SELECT ST_SetSRID(ST_GeomFromText(wkt), 4326) AS geom
                        FROM unnest(%s::text[]) AS wkt
                    ),
                    consolidated_terminals AS (
                        SELECT ST_Union(geom) AS geom FROM local_terminals
                    )
                    SELECT
                        EXTRACT(HOUR FROM tp.recorded_at AT TIME ZONE 'America/Asuncion')::int AS hora,
                        tp.bus_internal_code AS mean_id,
                        MIN(tp.recorded_at AT TIME ZONE 'UTC') AS primera_posicion_timestamp,
                        MAX(tp.recorded_at AT TIME ZONE 'UTC') AS ultima_posicion_timestamp,
                        COUNT(*) AS cantidad_mensajes,
                        COUNT(*) FILTER (WHERE tp.route_id IS NOT NULL AND tp.route_id NOT IN ('0000', '', 'None')) AS mensajes_en_ruta
                    FROM telemetry_ping tp
                    CROSS JOIN consolidated_terminals ct
                    WHERE DATE(tp.recorded_at AT TIME ZONE 'America/Asuncion') = %s
                      AND tp.agency_id = %s
                      AND tp.latitude IS NOT NULL AND tp.longitude IS NOT NULL
                      AND (ct.geom IS NULL OR NOT ST_Within(tp.geom, ct.geom))
                    GROUP BY 1, 2
                    ORDER BY 1, 2;
                """, (terminal_wkts, target_date, agency_id))
            else:
                self.env.cr.execute("""
                    WITH consolidated_terminals AS (
                        SELECT ST_Union(ST_Buffer(geom::geography, COALESCE(radius_meters, 100))::geometry) AS geom
                        FROM transit_stop
                        WHERE stop_type IN ('origin', 'destination') AND geom IS NOT NULL
                    )
                    SELECT
                        EXTRACT(HOUR FROM tp.recorded_at AT TIME ZONE 'America/Asuncion')::int AS hora,
                        tp.bus_internal_code AS mean_id,
                        MIN(tp.recorded_at AT TIME ZONE 'UTC') AS primera_posicion_timestamp,
                        MAX(tp.recorded_at AT TIME ZONE 'UTC') AS ultima_posicion_timestamp,
                        COUNT(*) AS cantidad_mensajes,
                        COUNT(*) FILTER (WHERE tp.route_id IS NOT NULL AND tp.route_id NOT IN ('0000', '', 'None')) AS mensajes_en_ruta
                    FROM telemetry_ping tp
                    CROSS JOIN consolidated_terminals ct
                    WHERE DATE(tp.recorded_at AT TIME ZONE 'America/Asuncion') = %s
                      AND tp.agency_id = %s
                      AND tp.latitude IS NOT NULL AND tp.longitude IS NOT NULL
                      AND (ct.geom IS NULL OR NOT ST_Within(tp.geom, ct.geom))
                    GROUP BY 1, 2
                    ORDER BY 1, 2;
                """, (target_date, agency_id))

            raw_rows = self.env.cr.dictfetchall()
            if raw_rows:
                loc_buses, loc_details = _evaluate_raw_rows(raw_rows)
                _merge_hour_results(loc_buses, loc_details)
                primary_source = 'gps_broker'

        return buses_by_hour, buses_detail_by_hour, primary_source

    @api.model
    def _get_historical_cbd(
        self,
        agency_id: str,
        fechas_ref: List[date],
        franjas_config: List[Dict],
    ) -> Tuple[Dict[int, float], Dict[Tuple[int, int], float]]:
        """
        Calcula el CBD histórico promedio por hora y por franja en las 4 fechas de referencia,
        tomando el máximo entre billetaje (servicios_diarios) y GPS (cbd_detalle_buses / flota_db)
        exactamente como get_cbd_for_hour y cbd_objetivo.py en cbd_monitor.
        """
        hist_hour_avg: Dict[int, float] = {}
        hist_franja_avg: Dict[Tuple[int, int], float] = {}
        if not fechas_ref:
            return hist_hour_avg, hist_franja_avg

        n_ref = len(fechas_ref)
        cache_gps: Dict[Tuple[date, int], int] = {}
        cache_val: Dict[Tuple[date, int], int] = {}
        franja_dist_gps: Dict[Tuple[date, int, int], int] = {}
        franja_dist_val: Dict[Tuple[date, int, int], int] = {}

        # 1. Consultar CID DB (servicios_diarios + cbd_detalle_buses)
        conn_cid = _get_cid_connection()
        if conn_cid:
            try:
                cur = conn_cid.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT cod_catalogo FROM public.eots WHERE id_eot_vmt_hex = %s LIMIT 1;", (agency_id,))
                eot_row = cur.fetchone()
                cod_catalogo = eot_row['cod_catalogo'] if eot_row else None

                # GPS por hora
                cur.execute("""
                    SELECT fecha, hora, COUNT(DISTINCT mean_id) as cbd
                    FROM control_metricas.cbd_detalle_buses
                    WHERE id_eot_vmt_hex = %s AND fecha = ANY(%s)
                    GROUP BY fecha, hora;
                """, (agency_id, fechas_ref))
                for r in cur.fetchall():
                    cache_gps[(r['fecha'], int(r['hora']))] = int(r['cbd'])

                # Validaciones por hora
                if cod_catalogo is not None:
                    cur.execute("""
                        SELECT fecha, hora, COUNT(DISTINCT idsam) as cbd
                        FROM public.servicios_diarios
                        WHERE id_eot_catalogo = %s AND fecha = ANY(%s)
                        GROUP BY fecha, hora;
                    """, (cod_catalogo, fechas_ref))
                    for r in cur.fetchall():
                        cache_val[(r['fecha'], int(r['hora']))] = int(r['cbd'])

                # Buses distintos por franja en las fechas de referencia
                for fr in franjas_config:
                    h0, h1 = fr['h_start'], fr['h_end']
                    cur.execute("""
                        SELECT fecha, COUNT(DISTINCT mean_id) as cbd
                        FROM control_metricas.cbd_detalle_buses
                        WHERE id_eot_vmt_hex = %s AND fecha = ANY(%s) AND hora >= %s AND hora <= %s
                        GROUP BY fecha;
                    """, (agency_id, fechas_ref, h0, h1))
                    for r in cur.fetchall():
                        franja_dist_gps[(r['fecha'], h0, h1)] = int(r['cbd'])

                    if cod_catalogo is not None:
                        cur.execute("""
                            SELECT fecha, COUNT(DISTINCT idsam) as cbd
                            FROM public.servicios_diarios
                            WHERE id_eot_catalogo = %s AND fecha = ANY(%s) AND hora >= %s AND hora <= %s
                            GROUP BY fecha;
                        """, (cod_catalogo, fechas_ref, h0, h1))
                        for r in cur.fetchall():
                            franja_dist_val[(r['fecha'], h0, h1)] = int(r['cbd'])

                cur.close()
                conn_cid.close()
            except Exception as e:
                _logger.debug("Aviso consultando histórico en CID DB: %s", e)

        # 2. Complementar con registros locales en transit_cbd_hourly / telemetry_ping (flota_db)
        try:
            self.env.cr.execute("""
                SELECT date AS fecha, hour AS hora, distinct_buses_count AS cbd
                FROM transit_cbd_hourly
                WHERE agency_id = %s AND date = ANY(%s);
            """, (agency_id, fechas_ref))
            for r in self.env.cr.dictfetchall():
                key = (r['fecha'], int(r['hora']))
                if int(r['cbd'] or 0) > cache_gps.get(key, 0):
                    cache_gps[key] = int(r['cbd'])
        except Exception:
            pass

        # 3. Calcular promedios por hora (0..23)
        for h in range(24):
            total_h = 0
            for fh in fechas_ref:
                c_val = cache_val.get((fh, h), 0)
                c_gps = cache_gps.get((fh, h), 0)
                total_h += max(c_val, c_gps)
            hist_hour_avg[h] = round(total_h / float(n_ref), 2)

        # 4. Calcular promedios por franja
        for fr in franjas_config:
            h0, h1 = fr['h_start'], fr['h_end']
            total_f = 0
            for fh in fechas_ref:
                f_val = franja_dist_val.get((fh, h0, h1), 0)
                f_gps = franja_dist_gps.get((fh, h0, h1), 0)
                total_f += max(f_val, f_gps)
            hist_franja_avg[(h0, h1)] = round(total_f / float(n_ref), 2)

        return hist_hour_avg, hist_franja_avg

    @api.model
    def cron_update_today_cbd_ifo(self):
        """Cron automático cada 5 minutos para actualizar el conteo horario de buses, IFO y alertas."""
        today = _get_paraguay_now().date()
        _logger.info("Cron CBD/IFO: actualizando métricas en tiempo real para %s", today)
        concessionaires = self.env['transit.concessionaire'].sudo().search([('active', '=', True)])
        for conc in concessionaires:
            try:
                self.compute_cbd_for_date_and_company(today, conc.id)
            except Exception as e:
                _logger.error("Error en cron CBD/IFO para %s: %s", conc.name, e)
        # Asegurar transición limpia a cerrada de franjas vencidas si quedó alguna abierta
        stale_open = self.env['transit.cbd.franja'].sudo().search([
            ('state', '=', 'in_progress'),
        ])
        if stale_open:
            stale_open._compute_progress()
            stale_open._compute_live_ifo_100()
            stale_open._compute_compensation()
            stale_open._compute_alerts()


# ==============================================================================
# 3. MODELO: DETALLE INDIVIDUAL DE BUSES (transit.cbd.bus.detail)
# ==============================================================================
class TransitCBDBusDetail(models.Model):
    _name = 'transit.cbd.bus.detail'
    _description = 'Detalle de Bus en Tránsito por Hora (Tabla Homóloga a cbd_detalle_buses)'
    _inherit = ['transit.tenant.mixin', 'mail.thread']
    _order = 'date desc, hour desc, bus_internal_code asc'

    hourly_id = fields.Many2one('transit.cbd.hourly', string='Registro Horario', ondelete='cascade', index=True)
    agency_id = fields.Char(string='Agency ID', index=True)
    date = fields.Date(string='Fecha', required=True, index=True)
    hour = fields.Integer(string='Hora', required=True, index=True)
    bus_internal_code = fields.Char(string='Interno / Mean ID', required=True, index=True)

    first_ping = fields.Datetime(string='Primera Posición (UTC)')
    last_ping = fields.Datetime(string='Última Posición (UTC)')
    message_count = fields.Integer(string='Cantidad de Mensajes GPS', default=0)
    duration_min = fields.Float(string='Duración en Tránsito (min)', digits=(6, 1), default=0.0)
    is_valid_transit = fields.Boolean(
        string='Operativo Válido (bus_monitor.py)',
        default=True,
        help='True si superó el filtro de permanencia (>=15 min y >=30 msgs) o continuidad horaria (H-1 / H+1).'
    )


# ==============================================================================
# COORDENADAS DE LOS 19 DISTRITOS DEL DEPARTAMENTO CENTRAL (script_lluvia.py)
# ==============================================================================
CENTRAL_LOCATIONS = [
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


# ==============================================================================
# 4. MODELO: CASUÍSTICAS DE LLUVIA OPEN-METEO (transit.rain.casuistica)
#    (Tabla homóloga a control_metricas.t_casuisticas_lluvia de cbd_monitor)
# ==============================================================================
class TransitRainCasuistica(models.Model):
    _name = 'transit.rain.casuistica'
    _description = 'Casuísticas de Lluvia Open-Meteo (19 Distritos de Central)'
    _order = 'fecha_evento desc, es_resumen_diario desc, hora_inicio asc'
    _rec_name = 'notas'

    fecha_evento = fields.Date(string='Fecha del Evento', required=True, index=True, default=fields.Date.context_today)
    hora_inicio = fields.Char(string='Hora Inicio', required=True, default='00:00:00')
    hora_fin = fields.Char(string='Hora Fin', required=True, default='23:59:59')
    es_resumen_diario = fields.Boolean(
        string='Es Acumulado Diario',
        default=False,
        help='True cuando representa el acumulado diario máximo en un distrito de Central (> 5.0 mm).'
    )
    distrito_max = fields.Char(string='Distrito Máx. Lluvia (Central)')
    latitud = fields.Float(string='Latitud', digits=(10, 4))
    longitud = fields.Float(string='Longitud', digits=(10, 4))
    mm_caidos = fields.Float(string='Precipitación (mm)', digits=(8, 2), required=True, default=0.0)
    es_lluvia_intensa = fields.Boolean(
        string='Es Lluvia Intensa (>= 15 mm)',
        default=False,
        help='True cuando la lluvia supera el umbral de lluvia intensa (15 mm).'
    )
    registro_comprobado = fields.Boolean(string='Registro Comprobado', default=False)
    factor_ajuste = fields.Float(string='Factor de Ajuste', digits=(4, 2), default=0.50)
    fuente_registro = fields.Char(string='Fuente de Registro', default='Open-Meteo')
    notas = fields.Text(string='Notas / Detalle')

    _sql_constraints = [
        ('fecha_hora_unique',
         'unique(fecha_evento, hora_inicio, hora_fin)',
         'Ya existe un registro de lluvia para esta fecha y rango horario.')
    ]

    @api.model
    def sync_open_meteo_range(self, start_date: date, end_date: date) -> Dict[str, int]:
        """
        Ejecuta la misma lógica de script_lluvia.py:
        Consulta en Open-Meteo (ERA5 Archive + Forecast API) los 19 distritos del Departamento Central,
        calcula el máximo por hora (> 2.5 mm/h) y el acumulado diario máximo por distrito (> 5.0 mm/día),
        y almacena tanto las casuísticas en `transit_rain_casuistica` como los días de lluvia en `transit_atypical_day`.
        """
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)

        today = _get_paraguay_now().date()
        era5_cutoff = today - timedelta(days=5)
        lats = ",".join(str(loc["lat"]) for loc in CENTRAL_LOCATIONS)
        lons = ",".join(str(loc["lon"]) for loc in CENTRAL_LOCATIONS)

        hourly_by_iso: Dict[str, Dict[str, Any]] = {}
        daily_by_date_loc: Dict[Tuple[date, int], float] = {}

        def _process_payload(data_list: List[Dict[str, Any]]):
            if not data_list or "hourly" not in data_list[0]:
                return
            times = data_list[0]["hourly"].get("time") or []
            num_hours = len(times)
            rains_by_loc = []
            for d in data_list:
                h_obj = d.get("hourly", {})
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

                loc_info = CENTRAL_LOCATIONS[max_loc_idx] if max_loc_idx < len(CENTRAL_LOCATIONS) else CENTRAL_LOCATIONS[0]
                existing = hourly_by_iso.get(t_str)
                if not existing or max_rain > existing["rain_mm"]:
                    hourly_by_iso[t_str] = {
                        "dt": dt,
                        "rain_mm": round(max_rain, 2),
                        "location_name": loc_info["name"],
                        "lat": loc_info["lat"],
                        "lon": loc_info["lon"],
                    }

        def _fetch_chunk(c_start: date, c_end: date):
            if c_start <= era5_cutoff:
                e_end = min(c_end, era5_cutoff)
                try:
                    resp = requests.get(
                        "https://archive-api.open-meteo.com/v1/era5",
                        params={
                            "latitude": lats,
                            "longitude": lons,
                            "start_date": c_start.strftime("%Y-%m-%d"),
                            "end_date": e_end.strftime("%Y-%m-%d"),
                            "hourly": "rain,precipitation",
                            "timezone": "America/Asuncion",
                        },
                        timeout=25,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        _process_payload(data if isinstance(data, list) else [data])
                except Exception as e:
                    _logger.debug("Aviso ERA5 Open-Meteo (%s a %s): %s", c_start, e_end, e)

            if c_end > era5_cutoff:
                f_start = max(c_start, era5_cutoff + timedelta(days=1))
                if f_start <= c_end:
                    try:
                        resp_f = requests.get(
                            "https://api.open-meteo.com/v1/forecast",
                            params={
                                "latitude": lats,
                                "longitude": lons,
                                "start_date": f_start.strftime("%Y-%m-%d"),
                                "end_date": c_end.strftime("%Y-%m-%d"),
                                "hourly": "rain,precipitation",
                                "timezone": "America/Asuncion",
                            },
                            timeout=25,
                        )
                        if resp_f.status_code == 200:
                            data_f = resp_f.json()
                            _process_payload(data_f if isinstance(data_f, list) else [data_f])
                    except Exception as e:
                        _logger.debug("Aviso Forecast Open-Meteo (%s a %s): %s", f_start, c_end, e)

        cur_chunk = start_date
        while cur_chunk <= end_date:
            nxt_chunk = min(cur_chunk + timedelta(days=30), end_date)
            _fetch_chunk(cur_chunk, nxt_chunk)
            cur_chunk = nxt_chunk + timedelta(days=1)

        count_hourly = 0
        count_daily = 0
        count_atypical = 0

        # 1. Guardar eventos horarios (> 2.5 mm/h)
        for rec in sorted(hourly_by_iso.values(), key=lambda x: x["dt"]):
            rain_mm = float(rec["rain_mm"])
            if rain_mm <= 2.5:
                continue
            dt = rec["dt"]
            f_ev = dt.date()
            h_ini = dt.strftime("%H:%M:%S")
            h_fin = (dt + timedelta(hours=1)).strftime("%H:%M:%S")
            loc_name = rec["location_name"]
            notas = f"Lluvia MAX Central: {rain_mm:.2f} mm ({loc_name})"

            existing_rec = self.sudo().search([
                ('fecha_evento', '=', f_ev),
                ('hora_inicio', '=', h_ini),
                ('hora_fin', '=', h_fin),
            ], limit=1)
            vals = {
                'fecha_evento': f_ev,
                'hora_inicio': h_ini,
                'hora_fin': h_fin,
                'es_resumen_diario': False,
                'distrito_max': loc_name,
                'latitud': rec["lat"],
                'longitud': rec["lon"],
                'mm_caidos': rain_mm,
                'es_lluvia_intensa': (rain_mm >= 15.0),
                'registro_comprobado': False,
                'factor_ajuste': 0.50,
                'fuente_registro': 'Open-Meteo',
                'notas': notas,
            }
            if existing_rec:
                existing_rec.sudo().write(vals)
            else:
                self.sudo().create(vals)
            count_hourly += 1

        # 2. Guardar acumulado diario por distrito (> 5.0 mm/día) y Día Atípico de Lluvia
        cur_d = start_date
        while cur_d <= end_date:
            best_mm = 0.0
            best_loc = CENTRAL_LOCATIONS[0]
            for loc_idx, loc in enumerate(CENTRAL_LOCATIONS):
                tot_mm = daily_by_date_loc.get((cur_d, loc_idx), 0.0)
                if tot_mm > best_mm:
                    best_mm = tot_mm
                    best_loc = loc
            best_mm = round(best_mm, 2)
            if best_mm > 5.0:
                loc_name = best_loc["name"]
                lat = best_loc["lat"]
                lon = best_loc["lon"]
                notas_dia = (
                    f"Acumulado diario ERA5: {best_mm:.2f} mm en {loc_name} "
                    f"(lat {lat}, lon {lon}). Referencia para días atípicos."
                )
                ex_daily = self.sudo().search([
                    ('fecha_evento', '=', cur_d),
                    ('hora_inicio', '=', '00:00:00'),
                    ('hora_fin', '=', '23:59:59'),
                ], limit=1)
                d_vals = {
                    'fecha_evento': cur_d,
                    'hora_inicio': '00:00:00',
                    'hora_fin': '23:59:59',
                    'es_resumen_diario': True,
                    'distrito_max': loc_name,
                    'latitud': lat,
                    'longitud': lon,
                    'mm_caidos': best_mm,
                    'es_lluvia_intensa': (best_mm >= 15.0),
                    'registro_comprobado': True,
                    'factor_ajuste': 0.50,
                    'fuente_registro': 'Open-Meteo',
                    'notas': notas_dia,
                }
                if ex_daily:
                    ex_daily.sudo().write(d_vals)
                else:
                    self.sudo().create(d_vals)
                count_daily += 1

                # Guardar también en transit.atypical.day
                ex_atyp = self.env['transit.atypical.day'].sudo().search([
                    ('fecha', '=', cur_d),
                    ('tipo_atipico', '=', 'LLUVIA'),
                ], limit=1)
                at_vals = {
                    'fecha': cur_d,
                    'tipo_atipico': 'LLUVIA',
                    'factor_exigencia': 0.50,
                    'descartar_historico': True,
                    'fuente_dato': 'Open-Meteo',
                    'distrito_max': loc_name,
                    'mm_caidos': best_mm,
                    'observacion': f"Lluvia acumulada > 5mm ({best_mm:.2f} mm en {loc_name})",
                    'active': True,
                }
                if ex_atyp:
                    ex_atyp.sudo().write(at_vals)
                else:
                    self.env['transit.atypical.day'].sudo().create(at_vals)
                count_atypical += 1

            cur_d += timedelta(days=1)

        return {
            'hourly': count_hourly,
            'daily': count_daily,
            'atypical': count_atypical,
        }

    def action_sync_recent_rain(self):
        """Botón en Odoo para descargar lluvia de los últimos 30 días desde Open-Meteo (19 distritos Central)."""
        today = _get_paraguay_now().date()
        start = today - timedelta(days=30)
        res = self.sync_open_meteo_range(start, today)
        self.env['transit.atypical.day'].sync_holidays_and_cid_atypical()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización Open-Meteo Completada'),
                'message': _(
                    'Se procesaron los 19 distritos de Central (%s a %s): %d eventos horarios (>2.5mm), '
                    '%d acumulados diarios (>5mm) y %d días atípicos de lluvia registrados en flota_db.'
                ) % (start, today, res['hourly'], res['daily'], res['atypical']),
                'type': 'success',
                'sticky': False,
            }
        }


# ==============================================================================
# 5. MODELO: DÍAS ATÍPICOS Y FERIADOS (transit.atypical.day)
#    (Tabla homóloga a control_metricas.dias_atipicos de cbd_monitor)
# ==============================================================================
class TransitAtypicalDay(models.Model):
    _name = 'transit.atypical.day'
    _description = 'Días Atípicos, Lluvias y Feriados (Res. GVMT N° 120/2025)'
    _order = 'fecha desc, tipo_atipico asc'
    _rec_name = 'observacion'

    fecha = fields.Date(string='Fecha', required=True, index=True, default=fields.Date.context_today)
    tipo_atipico = fields.Selection([
        ('LLUVIA', 'Lluvia (> 5.0 mm Open-Meteo)'),
        ('FERIADO_LAB', 'Feriado Laboral (L-V)'),
        ('FERIADO_SAB', 'Feriado Sábado'),
        ('PRE_POS_FERIADO', 'Pre-Feriado / Pos-Feriado'),
        ('DISRUPTIVO', 'Evento Disruptivo / Paro'),
        ('OTRO', 'Otro Día Atípico'),
    ], string='Tipo de Día Atípico', required=True, default='LLUVIA', index=True)

    factor_exigencia = fields.Float(
        string='Factor de Exigencia',
        digits=(4, 2),
        required=True,
        default=0.50,
        help='Factor multiplicativo aplicado al CBD Histórico: Lluvia=0.50, Feriado L-V=0.30, Feriado Sáb=0.50, Pre/Pos-Feriado=0.70.'
    )
    descartar_historico = fields.Boolean(
        string='Descartar de las 4 Semanas Históricas',
        default=True,
        help='Si está activo, esta fecha se excluye al buscar las 4 semanas históricas de referencia del IFO.'
    )
    fuente_dato = fields.Char(string='Fuente del Dato', default='Open-Meteo')
    distrito_max = fields.Char(string='Distrito Máx. Precipitación')
    mm_caidos = fields.Float(string='Precipitación Acumulada (mm)', digits=(8, 2), default=0.0)
    observacion = fields.Text(string='Observación / Detalle')
    id_tipo_dia_aplicable = fields.Integer(string='ID Tipo Día Aplicable (5/6/7)')
    active = fields.Boolean(string='Activo', default=True)

    _sql_constraints = [
        ('fecha_tipo_unique',
         'unique(fecha, tipo_atipico)',
         'Ya existe un registro para esta fecha y tipo de día atípico.')
    ]

    @api.model
    def sync_holidays_and_cid_atypical(self) -> Dict[str, int]:
        """
        Sincroniza feriados locales (`transit.holiday`), feriados oficiales VMT (`public.feriados`),
        pre/pos-feriados y días atípicos/lluvias de `control_metricas.dias_atipicos` y `t_casuisticas_lluvia`
        dentro de las tablas locales `transit_atypical_day` y `transit_rain_casuistica` de `flota_db`.
        """
        feriados_map: Dict[date, str] = {}
        for h in self.env['transit.holiday'].sudo().search([('active', '=', True)]):
            if h.date:
                feriados_map[h.date] = h.name or "Feriado Nacional"

        synced_cid_atyp = 0
        synced_cid_rain = 0

        conn_cid = _get_cid_connection()
        if conn_cid:
            try:
                cur = conn_cid.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT fecha, descripcion FROM public.feriados WHERE fecha IS NOT NULL;")
                for r in cur.fetchall():
                    f_dt = r['fecha']
                    f_desc = r.get('descripcion') or 'Feriado Oficial'
                    feriados_map[f_dt] = f_desc
                    if 2024 <= f_dt.year <= 2030:
                        ex_h = self.env['transit.holiday'].sudo().search([('date', '=', f_dt)], limit=1)
                        if not ex_h:
                            self.env['transit.holiday'].sudo().create({
                                'name': f_desc,
                                'date': f_dt,
                                'active': True,
                            })

                cur.execute("""
                    SELECT fecha, tipo_atipico, factor_exigencia, descartar_historico,
                           fuente_dato, observacion, id_tipo_dia_aplicable
                    FROM control_metricas.dias_atipicos
                    WHERE fecha >= '2025-01-01' AND fecha <= '2030-12-31';
                """)
                for r in cur.fetchall():
                    f_dt = r['fecha']
                    tipo = r.get('tipo_atipico') or 'OTRO'
                    if tipo not in ('LLUVIA', 'FERIADO_LAB', 'FERIADO_SAB', 'PRE_POS_FERIADO', 'DISRUPTIVO', 'OTRO'):
                        tipo = 'OTRO'
                    descartar = True if tipo == 'LLUVIA' else bool(r.get('descartar_historico', True))
                    raw_fuente = (r.get('fuente_dato') or '').strip()
                    clean_fuente = 'Monitoreo Operativo' if raw_fuente.upper() in ('', 'CID', 'CID DB', 'VMT', 'CCM') else raw_fuente
                    ex_at = self.sudo().search([('fecha', '=', f_dt), ('tipo_atipico', '=', tipo)], limit=1)
                    vals = {
                        'fecha': f_dt,
                        'tipo_atipico': tipo,
                        'factor_exigencia': float(r.get('factor_exigencia') or 0.50),
                        'descartar_historico': descartar,
                        'fuente_dato': clean_fuente,
                        'observacion': r.get('observacion') or tipo,
                        'id_tipo_dia_aplicable': r.get('id_tipo_dia_aplicable'),
                        'active': True,
                    }
                    if ex_at:
                        ex_at.sudo().write(vals)
                    else:
                        self.sudo().create(vals)
                    synced_cid_atyp += 1

                cur.execute("""
                    SELECT fecha_evento, hora_inicio, hora_fin, es_lluvia_intensa,
                           registro_comprobado, factor_ajuste, fuente_registro, notas, mm_caidos
                    FROM control_metricas.t_casuisticas_lluvia
                    WHERE fecha_evento >= '2025-01-01';
                """)
                RainModel = self.env['transit.rain.casuistica'].sudo()
                for r in cur.fetchall():
                    f_ev = r['fecha_evento']
                    h_ini = r['hora_inicio'].strftime('%H:%M:%S') if r.get('hora_inicio') else '00:00:00'
                    h_fin = r['hora_fin'].strftime('%H:%M:%S') if r.get('hora_fin') else '23:59:59'
                    es_res = (h_ini == '00:00:00' and h_fin in ('23:59:59', '23:59:00'))
                    mm_v = float(r.get('mm_caidos') or 0.0)
                    ex_r = RainModel.search([
                        ('fecha_evento', '=', f_ev),
                        ('hora_inicio', '=', h_ini),
                        ('hora_fin', '=', h_fin),
                    ], limit=1)
                    r_vals = {
                        'fecha_evento': f_ev,
                        'hora_inicio': h_ini,
                        'hora_fin': h_fin,
                        'es_resumen_diario': es_res,
                        'mm_caidos': mm_v,
                        'es_lluvia_intensa': bool(r.get('es_lluvia_intensa', False)),
                        'registro_comprobado': bool(r.get('registro_comprobado', False)),
                        'factor_ajuste': float(r.get('factor_ajuste') or 0.50),
                        'fuente_registro': r.get('fuente_registro') or 'Open-Meteo',
                        'notas': r.get('notas') or f"Lluvia: {mm_v:.2f} mm",
                    }
                    if not ex_r:
                        RainModel.create(r_vals)
                        synced_cid_rain += 1

                cur.close()
                conn_cid.close()
            except Exception as e:
                _logger.debug("Aviso sincronizando dias_atipicos desde CID DB: %s", e)

        # Generar registros para todos los feriados y sus pre/pos-feriados
        count_hol = 0
        for f_dt, f_desc in feriados_map.items():
            if not (2024 <= f_dt.year <= 2030):
                continue
            es_sab = (f_dt.weekday() == 5)
            tipo_f = 'FERIADO_SAB' if es_sab else 'FERIADO_LAB'
            fac_f = 0.50 if es_sab else 0.30
            ex_f = self.sudo().search([('fecha', '=', f_dt), ('tipo_atipico', '=', tipo_f)], limit=1)
            f_vals = {
                'fecha': f_dt,
                'tipo_atipico': tipo_f,
                'factor_exigencia': fac_f,
                'descartar_historico': True,
                'fuente_dato': 'Sincronización Consolidada',
                'observacion': f_desc,
                'id_tipo_dia_aplicable': 7,
                'active': True,
            }
            if ex_f:
                ex_f.sudo().write(f_vals)
            else:
                self.sudo().create(f_vals)
            count_hol += 1

            for delta_d, prefix in [(-1, "Pre-feriado de"), (1, "Pos-feriado de")]:
                adj_dt = f_dt + timedelta(days=delta_d)
                if adj_dt not in feriados_map:
                    ex_pp = self.sudo().search([
                        ('fecha', '=', adj_dt), ('tipo_atipico', '=', 'PRE_POS_FERIADO')
                    ], limit=1)
                    pp_vals = {
                        'fecha': adj_dt,
                        'tipo_atipico': 'PRE_POS_FERIADO',
                        'factor_exigencia': 0.70,
                        'descartar_historico': True,
                        'fuente_dato': 'Sincronización Consolidada',
                        'observacion': f"{prefix}: {f_desc}",
                        'active': True,
                    }
                    if ex_pp:
                        ex_pp.sudo().write(pp_vals)
                    else:
                        self.sudo().create(pp_vals)
                    count_hol += 1

        return {
            'holidays_atypical': count_hol,
            'cid_atypical': synced_cid_atyp,
            'cid_rain': synced_cid_rain,
        }

    def action_sync_all_atypical_days(self):
        """Botón en Odoo para sincronizar Feriados, Pre/Pos-Feriados y Lluvias Open-Meteo."""
        today = _get_paraguay_now().date()
        res_hol = self.sync_holidays_and_cid_atypical()
        res_rain = self.env['transit.rain.casuistica'].sync_open_meteo_range(today - timedelta(days=30), today)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Días Atípicos y Lluvias Sincronizados'),
                'message': _(
                    'Feriados/Pre-Pos: %d | Días Atípicos: %d | Lluvias Open-Meteo (últimos 30 días): %d días con lluvia > 5mm.'
                ) % (res_hol['holidays_atypical'], res_hol['cid_atypical'], res_rain['atypical']),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cron_sync_rain_and_atypical_days(self):
        """Cron diario que ejecuta script_lluvia dentro de Odoo (últimos 7 días + hoy) y sincroniza feriados."""
        today = _get_paraguay_now().date()
        self.sync_holidays_and_cid_atypical()
        self.env['transit.rain.casuistica'].sync_open_meteo_range(today - timedelta(days=7), today)

