# -*- coding: utf-8 -*-
import os
import sys
import io
import base64
import logging
from datetime import datetime, date, timedelta, time
import calendar
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
try:
    import pandas as pd
except ImportError:
    pd = None

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Rutas de búsqueda de módulos de monitoreo VMT
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(CURRENT_DIR)
VMT_CORE_DIR = os.path.join(ADDON_DIR, "vmt_core")
MONITOREO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(ADDON_DIR)),
    "monitoreo_servicios_especiales"
)
ALT_MONITOREO_DIR = r"c:\Users\lpraf\OneDrive\Documentos\Poliverso\monitoreo_servicios_especiales"

for d in [VMT_CORE_DIR, MONITOREO_DIR, ALT_MONITOREO_DIR]:
    if os.path.exists(d) and d not in sys.path:
        sys.path.insert(0, d)


class TransitMonitoringAudit(models.Model):
    _name = 'transit.monitoring.audit'
    _description = 'Auditoría y Monitoreo Operativo VMT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Referencia / Título', compute='_compute_name', store=True, readonly=False)

    service_id = fields.Many2one(
        'transit.service',
        string='Servicio Especial / Concesión',
        required=True,
        tracking=True,
        index=True
    )
    service_code = fields.Char(string='Código de Línea', related='service_id.code', store=True, index=True)

    mode = fields.Selection([
        ('daily', 'Monitoreo Diario (Fecha Específica)'),
        ('monthly', 'Planilla Mensual (Mes Completo)'),
    ], string='Alcance de Monitoreo', default='daily', required=True, tracking=True)

    date = fields.Date(
        string='Fecha Operativa',
        default=lambda self: fields.Date.today() - timedelta(days=1),
        help='Fecha del servicio a auditar (por defecto: ayer)'
    )
    year = fields.Integer(
        string='Año Operativo',
        default=lambda self: fields.Date.today().year,
        required=True
    )
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ], string='Mes Operativo', default=lambda self: str(fields.Date.today().month), required=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('running', 'Procesando...'),
        ('done', 'Auditado / Concluido'),
        ('error', 'Error en Ejecución'),
    ], string='Estado', default='draft', tracking=True)

    tipo_dia_desc = fields.Char(string='Tipo de Día Operativo', readonly=True)

    # -------------------------------------------------------------------------
    # KPIs / METRICAS DE OPERATIVA
    # -------------------------------------------------------------------------
    total_programados = fields.Integer(string='Salidas Programadas', default=0, readonly=True)
    prog_ida = fields.Integer(string='Prog. Ida', default=0, readonly=True)
    prog_vuelta = fields.Integer(string='Prog. Vuelta', default=0, readonly=True)

    total_detectados = fields.Integer(string='Total Viajes Físicos', default=0, readonly=True)

    total_segun_operativa = fields.Integer(
        string='Realizados según Operativa',
        default=0,
        readonly=True,
        help='Servicios que cumplieron itinerario oficial (>=80%) y salieron dentro de la tolerancia de horario (Regulares)'
    )
    segun_operativa_ida = fields.Integer(string='Según Op. Ida', default=0, readonly=True)
    segun_operativa_vuelta = fields.Integer(string='Según Op. Vuelta', default=0, readonly=True)

    total_fuera_operativa = fields.Integer(
        string='Realizados fuera de Operativa',
        default=0,
        readonly=True,
        help='Servicios ejecutados que salieron fuera de tolerancia horaria (irregulares), refuerzos no programados o desvíos'
    )
    fuera_operativa_ida = fields.Integer(string='Fuera Op. Ida', default=0, readonly=True)
    fuera_operativa_vuelta = fields.Integer(string='Fuera Op. Vuelta', default=0, readonly=True)

    total_no_realizados = fields.Integer(
        string='Servicios No Realizados',
        default=0,
        readonly=True,
        help='Salidas que figuraban en la programación operativa pero ningún bus las realizó (Faltantes / Canceladas)'
    )
    no_realizados_ida = fields.Integer(string='No Realiz. Ida', default=0, readonly=True)
    no_realizados_vuelta = fields.Integer(string='No Realiz. Vuelta', default=0, readonly=True)

    compliance_pct = fields.Float(
        string='% Cumplimiento Operativo',
        digits=(5, 2),
        default=0.0,
        readonly=True,
        help='(Servicios según Operativa / Total Programados) * 100'
    )
    coverage_pct = fields.Float(
        string='% Cobertura Total de Salidas',
        digits=(5, 2),
        default=0.0,
        readonly=True,
        help='((Según Operativa + Fuera de Operativa) / Total Programados) * 100'
    )

    # Validaciones Billetaje
    total_validaciones = fields.Integer(string='Total Pasajeros / Validaciones', default=0, readonly=True)
    validaciones_general = fields.Integer(string='General (Tarifa Completa)', default=0, readonly=True)
    validaciones_transbordo = fields.Integer(string='Transbordos', default=0, readonly=True)
    validaciones_estudiante = fields.Integer(string='Estudiantes (Medio Boleto)', default=0, readonly=True)
    validaciones_discapacidad = fields.Integer(string='Discapacidad (Gratuito)', default=0, readonly=True)

    km_oficiales = fields.Float(string='Km Oficiales Liquidados', digits=(10, 1), default=0.0, readonly=True)

    execution_time_seconds = fields.Float(string='Tiempo de Cálculo (s)', digits=(6, 1), readonly=True)
    log_output = fields.Text(string='Registro de Auditoría y Trazas', readonly=True)

    # -------------------------------------------------------------------------
    # CONTRASTE CON PLANILLA DEL OPERADOR (ARAPOTÍ / EMPRESA)
    # -------------------------------------------------------------------------
    operator_excel_file = fields.Binary(
        string='Planilla del Operador (Excel)',
        attachment=True,
        help='Planilla de despacho diario/mensual del operador (ej. Arapotí) para contrastar contra el monitoreo satelital VMT'
    )
    operator_excel_filename = fields.Char(string='Nombre Archivo Planilla')

    operator_declared_trips = fields.Integer(string='Servicios Declarados por Operador', readonly=True)
    contrast_matched_trips = fields.Integer(string='Coincidentes con GPS', readonly=True)
    contrast_discrepancy_trips = fields.Integer(string='Con Discrepancia Horaria', readonly=True)
    contrast_missing_gps_trips = fields.Integer(string='Declarados sin Señal GPS', readonly=True)
    contrast_unreported_reinforcements = fields.Integer(string='Refuerzos GPS no Declarados', readonly=True)
    contrast_concordance_pct = fields.Float(string='% Concordancia Operador / VMT', digits=(5, 2), readonly=True)

    contrast_excel_file = fields.Binary(string='Informe de Contraste (Excel)', readonly=True, attachment=True)
    contrast_excel_filename = fields.Char(string='Nombre Informe Contraste', readonly=True)

    contrast_line_ids = fields.One2many(
        'transit.monitoring.contrast.line',
        'audit_id',
        string='Detalle de Contraste Operador vs VMT'
    )

    # -------------------------------------------------------------------------
    # LINEAS DE DETALLE (ONE2MANY)
    # -------------------------------------------------------------------------
    line_ids = fields.One2many('transit.monitoring.audit.line', 'audit_id', string='Todas las Líneas')

    line_segun_operativa_ids = fields.One2many(
        'transit.monitoring.audit.line', 'audit_id',
        string='Servicios Realizados según Operativa',
        domain=[('category', '=', 'segun_operativa')]
    )
    line_fuera_operativa_ids = fields.One2many(
        'transit.monitoring.audit.line', 'audit_id',
        string='Servicios Realizados fuera de Operativa',
        domain=[('category', '=', 'fuera_operativa')]
    )
    line_no_realizados_ids = fields.One2many(
        'transit.monitoring.audit.line', 'audit_id',
        string='Servicios NO Realizados (Faltantes)',
        domain=[('category', '=', 'no_realizados')]
    )

    # -------------------------------------------------------------------------
    # ARCHIVOS EXCEL GENERADOS
    # -------------------------------------------------------------------------
    excel_daily_file = fields.Binary(string='Reporte Diario Excel (.xlsx)', attachment=True, readonly=True)
    excel_daily_filename = fields.Char(string='Nombre Archivo Diario')

    excel_monthly_file = fields.Binary(string='Planilla Mensual Excel (.xlsx)', attachment=True, readonly=True)
    excel_monthly_filename = fields.Char(string='Nombre Archivo Mensual')

    @api.depends('service_code', 'mode', 'date', 'year', 'month')
    def _compute_name(self):
        for rec in self:
            code = rec.service_code or (rec.service_id.code if rec.service_id else 'S/C')
            if rec.mode == 'daily':
                f_str = rec.date.strftime("%d/%m/%Y") if rec.date else ""
                rec.name = f"[{code}] Auditoría Diaria VMT - {f_str}"
            else:
                meses = dict(self._fields['month'].selection)
                m_nom = meses.get(rec.month, rec.month)
                rec.name = f"[{code}] Planilla Mensual VMT - {m_nom} {rec.year}"

    # -------------------------------------------------------------------------
    # EJECUCION DE MONITOREO
    # -------------------------------------------------------------------------
    def action_run_monitoring(self):
        """Ejecuta el monitoreo en vivo aplicando la lógica de monitoreo VMT."""
        self.ensure_one()
        self.write({'state': 'running'})
        self.env.cr.commit()

        start_time = datetime.now()
        logs = []

        try:
            from sqlalchemy import create_engine, text
            from config_db import (
                cargar_configuraciones,
                obtener_geometrias_rutas,
                determinar_tipo_dia,
            )
            from reporte_mensual_excel import (
                DISTANCIAS_OFICIALES,
                obtener_info_distancia,
                obtener_programacion_servicios_por_dia,
            )
            from logica_monitoreo import procesar_servicio, clasificar_operativa

            db_cid = os.environ.get("DB_CID_URL", "postgresql://FPorta:portaf2024@168.90.177.232:2024/bbdd-monitoreo-cid")
            db_mon = os.environ.get("DB_MONITOREO_URL", "postgresql://jefe-CID:vmtdmt@168.90.177.231:5432/bbdd-monitoreo-prod")
            db_az = os.environ.get("DB_AZURE_URL", "postgresql://vmtuser:$$Tr4nsp0rt3$$@192.168.174.21:5432/opentransit-prod")

            engine_cid = create_engine(db_cid, pool_pre_ping=True)
            engine_mon = create_engine(db_mon, pool_pre_ping=True)

            code = (self.service_code or self.service_id.code or "").strip().upper()

            if self.mode == 'daily':
                f_str = self.date.strftime("%Y-%m-%d")
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando auditoría diaria para servicio {code} en fecha {f_str}...")

                configs = cargar_configuraciones(engine_cid, f_str)
                cfg = next((c for c in configs if str(c.get("codigo", "")).strip().upper() == code), None)
                if not cfg:
                    raise UserError(_("No se encontró configuración activa de adjudicación, rutas o programación para el servicio '%s' en fecha %s.") % (code, f_str))

                logs.append(f"  Parámetros: Geocerca={cfg['radio_geocerca_m']}m, Buffer Itinerario={cfg['radio_itinerario_m']}m, Umbral Cumplimiento={cfg['rango_cumplimiento_pct']}%.")
                logs.append(f"  Tipo de día: {cfg.get('tipo_dia_desc', 'N/A')}. Salidas programadas: {len(cfg.get('programacion', []))}.")

                # Geometría y geocercas tipo 5
                res_geom = obtener_geometrias_rutas(engine_cid, cfg["ruta_hex_ida"], cfg["ruta_hex_vuelta"], f_str)
                if len(res_geom) == 4:
                    G3, G4, G5_ida, G5_vuelta = res_geom
                else:
                    G3, G4 = res_geom[0], res_geom[1]
                    G5_ida, G5_vuelta = None, None

                # Query GPS
                buses = cfg["mean_ids"]
                bus_variants = list(set([b for b in buses] + [b.lower() for b in buses] + [b.upper() for b in buses]))
                bus_list_sql = ", ".join(f"'{b}'" for b in bus_variants)
                emisor_cond = f" AND emisor_id = {cfg['emisor_id']}" if cfg.get("emisor_id") is not None else ""
                agency_cond = ""
                if cfg.get("agency_ids"):
                    agency_list = ", ".join(f"'{a}'" for a in cfg["agency_ids"])
                    agency_cond = f" AND agency_id IN ({agency_list})"

                tabla_monitoreo = os.environ.get("TABLA_MONITOREO_GPS", "app_monitoreo_mensajeoperativo")
                query_gps = f"""
                    SELECT mean_id, fecha_hora, latitude, longitude
                    FROM {tabla_monitoreo}
                    WHERE 1=1 {emisor_cond} {agency_cond}
                      AND fecha_hora BETWEEN '{cfg['fecha_inicio']}' AND '{cfg['fecha_fin']}'
                      AND mean_id IN ({bus_list_sql})
                """
                with engine_mon.connect() as conn:
                    df_gps = pd.read_sql(text(query_gps), conn)
                logs.append(f"  Puntos GPS AVL recuperados: {len(df_gps):,}")

                # Query Billetaje
                idsams_filt = [str(i) for i in cfg["idSam_mapping"].values() if i]
                all_validaciones = pd.DataFrame()
                if idsams_filt:
                    try:
                        engine_az = create_engine(db_az, pool_pre_ping=True, connect_args={"connect_timeout": 5})
                        idsam_str = ", ".join(f"'{i}'" for i in idsams_filt)
                        min_v = datetime.strptime(cfg["fecha_inicio"], "%Y-%m-%d %H:%M:%S") - timedelta(minutes=15)
                        max_v = datetime.strptime(cfg["fecha_fin"], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=15)
                        query_v = f"""
                            SELECT idsam, fechahoraevento, serialmediopago, entidad, latitude, longitude,
                                   idrutaestacion, tipotransporte, númerotransbordos, montoevento, idproducto
                            FROM c_transacciones
                            WHERE fechahoraevento BETWEEN '{min_v}' AND '{max_v}'
                              AND idproducto IN ('4d4f', '4553') AND tipoevento = 4
                              AND idsam IN ({idsam_str})
                        """
                        with engine_az.connect() as conn_az:
                            all_validaciones = pd.read_sql(text(query_v), conn_az)
                        logs.append(f"  Transacciones billetaje electrónico recuperadas: {len(all_validaciones):,}")
                    except Exception as e_az:
                        logs.append(f"  [AVISO] Billetaje externo no accesible ({e_az}), continuando con AVL puro.")

                # Procesar lógica unificada de monitoreo
                resultados = procesar_servicio(cfg, df_gps, G3, G4, all_validaciones, G5_ida=G5_ida, G5_vuelta=G5_vuelta)
                ds_servicios = resultados["ds_servicios"]
                ds_servicios_validos = resultados["ds_servicios_validos"]
                ds_cant_servicios = resultados["ds_cant_servicios"]
                ds_cant_validaciones = resultados["ds_cant_validaciones"]
                ds_valid_por_hora = resultados["ds_valid_por_hora"]
                ds_segun = resultados.get("ds_segun_operativa", pd.DataFrame())
                ds_fuera = resultados.get("ds_fuera_operativa", pd.DataFrame())
                ds_no_real = resultados.get("ds_no_realizados", pd.DataFrame())
                resumen = resultados.get("resumen_operativa", {})

                logs.append(f"  Monitoreo concluido: {len(ds_segun)} según operativa, {len(ds_fuera)} fuera de operativa, {len(ds_no_real)} no realizados.")

                # Limpiar líneas previas
                self.line_ids.unlink()

                lines_to_create = []

                # 1. Según Operativa
                for idx, r in ds_segun.iterrows():
                    lines_to_create.append((0, 0, {
                        'category': 'segun_operativa',
                        'date': self.date,
                        'direction': r.get('sentido'),
                        'mean_id': r.get('mean_id'),
                        'idsam': r.get('idsam'),
                        'service_number_prog': int(r.get('nro_servicio_prog', 0)) if pd.notna(r.get('nro_servicio_prog')) and r.get('nro_servicio_prog') != 'N/A' else 0,
                        'scheduled_time': str(r.get('horario_programado', '')),
                        'actual_start': r.get('inicio_serv'),
                        'actual_end': r.get('fin_serv'),
                        'duration_minutes': int(r.get('duración(min)', 0)),
                        'deviation_minutes': float(r.get('desvio_minutos', 0.0)) if pd.notna(r.get('desvio_minutos')) else 0.0,
                        'compliance_pct': float(r.get('porcentaje_cumplimiento', 0.0)),
                        'validations_total': int(r.get('validaciones', 0)),
                        'validations_general': int(r.get('validaciones_general', 0)),
                        'validations_transfer': int(r.get('validaciones_transbordo', 0)),
                        'validations_student': int(r.get('validaciones_estudiante', 0)),
                        'validations_disability': int(r.get('validaciones_discapacidad', 0)),
                        'status_reason': str(r.get('motivo', 'Regular')),
                    }))

                # 2. Fuera de Operativa
                for idx, r in ds_fuera.iterrows():
                    lines_to_create.append((0, 0, {
                        'category': 'fuera_operativa',
                        'date': self.date,
                        'direction': r.get('sentido'),
                        'mean_id': r.get('mean_id'),
                        'idsam': r.get('idsam'),
                        'service_number_prog': int(r.get('nro_servicio_prog', 0)) if pd.notna(r.get('nro_servicio_prog')) and r.get('nro_servicio_prog') != 'N/A' else 0,
                        'scheduled_time': str(r.get('horario_programado', '')),
                        'actual_start': r.get('inicio_serv'),
                        'actual_end': r.get('fin_serv'),
                        'duration_minutes': int(r.get('duración(min)', 0)),
                        'deviation_minutes': float(r.get('desvio_minutos', 0.0)) if pd.notna(r.get('desvio_minutos')) else 0.0,
                        'compliance_pct': float(r.get('porcentaje_cumplimiento', 0.0)),
                        'validations_total': int(r.get('validaciones', 0)),
                        'validations_general': int(r.get('validaciones_general', 0)),
                        'validations_transfer': int(r.get('validaciones_transbordo', 0)),
                        'validations_student': int(r.get('validaciones_estudiante', 0)),
                        'validations_disability': int(r.get('validaciones_discapacidad', 0)),
                        'status_reason': str(r.get('motivo', 'Irregular / Refuerzo')),
                    }))

                # 3. No Realizados
                for idx, r in ds_no_real.iterrows():
                    lines_to_create.append((0, 0, {
                        'category': 'no_realizados',
                        'date': self.date,
                        'direction': r.get('sentido'),
                        'service_number_prog': int(r.get('nro_servicio_prog', 0)),
                        'scheduled_time': str(r.get('horario_programado', '')),
                        'status_reason': str(r.get('motivo', 'No Realizado / Faltante')),
                    }))

                # Generar Excel diario idéntico a servicios_especiales.py
                output_stream = io.BytesIO()
                dict_dfs = {
                    "Resumen_Operativa": pd.DataFrame([resumen]),
                    "Segun_Operativa": ds_segun,
                    "Fuera_Operativa": ds_fuera,
                    "No_Realizados": ds_no_real,
                    "Servicios": ds_servicios,
                    "Serv_y_regularidad": ds_servicios_validos,
                    "Cant_Servicios": ds_cant_servicios,
                    "Validaciones_bus": ds_cant_validaciones,
                    "Validaciones_hora": ds_valid_por_hora,
                    "Validaciones": resultados.get("ds_validaciones", pd.DataFrame())
                }

                with pd.ExcelWriter(output_stream, engine="openpyxl") as writer:
                    for sheet_name, df_sheet in dict_dfs.items():
                        if df_sheet is None or df_sheet.empty:
                            continue
                        df_to_write = df_sheet.copy()
                        for col in df_to_write.columns:
                            if pd.api.types.is_datetime64_any_dtype(df_to_write[col]):
                                if getattr(df_to_write[col].dtype, "tz", None) is not None:
                                    df_to_write[col] = df_to_write[col].dt.tz_convert("America/Asuncion").dt.tz_localize(None)
                        df_to_write.to_excel(writer, sheet_name=sheet_name, index=False)
                        ws = writer.sheets[sheet_name]
                        r_cnt, c_cnt = df_to_write.shape
                        if r_cnt > 0 and c_cnt > 0:
                            last_c = get_column_letter(c_cnt)
                            tab = Table(displayName=f"Tab_{sheet_name[:20]}_{code}", ref=f"A1:{last_c}{r_cnt+1}")
                            tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
                            ws.add_table(tab)
                            for i, col in enumerate(df_to_write.columns):
                                col_vals = [len(str(val)) for val in df_to_write[col].dropna()]
                                max_v = max(col_vals) if col_vals else 0
                                max_len = max(max_v, len(str(col))) + 2
                                ws.column_dimensions[get_column_letter(i + 1)].width = min(max_len, 45)

                excel_bytes = output_stream.getvalue()
                filename_daily = f"Reporte_servicios_y_validaciones_{code}_{f_str}.xlsx"

                dist_info = obtener_info_distancia(code)
                km_est = len(ds_segun) * (dist_info.get("redondo", 40.0) / 2.0)

                self.write({
                    'line_ids': lines_to_create,
                    'tipo_dia_desc': cfg.get('tipo_dia_desc', ''),
                    'total_programados': resumen.get("total_programados", 0),
                    'prog_ida': resumen.get("prog_ida", 0),
                    'prog_vuelta': resumen.get("prog_vuelta", 0),
                    'total_detectados': resumen.get("total_detectados", 0),
                    'total_segun_operativa': resumen.get("total_segun_operativa", 0),
                    'segun_operativa_ida': resumen.get("segun_operativa_ida", 0),
                    'segun_operativa_vuelta': resumen.get("segun_operativa_vuelta", 0),
                    'total_fuera_operativa': resumen.get("total_fuera_operativa", 0),
                    'fuera_operativa_ida': resumen.get("fuera_operativa_ida", 0),
                    'fuera_operativa_vuelta': resumen.get("fuera_operativa_vuelta", 0),
                    'total_no_realizados': resumen.get("total_no_realizados", 0),
                    'no_realizados_ida': resumen.get("no_realizados_ida", 0),
                    'no_realizados_vuelta': resumen.get("no_realizados_vuelta", 0),
                    'compliance_pct': resumen.get("porcentaje_cumplimiento_operativa", 0.0),
                    'coverage_pct': round(((len(ds_segun) + len(ds_fuera)) / max(len(cfg.get('programacion', [])), 1)) * 100, 2),
                    'total_validaciones': resumen.get("total_validaciones", 0),
                    'validaciones_general': resumen.get("validaciones_general", 0),
                    'validaciones_transbordo': resumen.get("validaciones_transbordo", 0),
                    'validaciones_estudiante': resumen.get("validaciones_estudiante", 0),
                    'validaciones_discapacidad': resumen.get("validaciones_discapacidad", 0),
                    'km_oficiales': km_est,
                    'excel_daily_file': base64.b64encode(excel_bytes),
                    'excel_daily_filename': filename_daily,
                    'state': 'done',
                })

            else:
                # -------------------------------------------------------------
                # MODO MENSUAL
                # -------------------------------------------------------------
                rep_year = self.year
                rep_month = int(self.month)
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando generación de planilla mensual para {code} - Mes {rep_month}/{rep_year}...")

                from reporte_mensual_excel import (
                    get_month_dates,
                    generar_hoja_informe_km,
                    generar_hoja_informe_validaciones,
                    generar_hoja_resumen_operativa
                )

                first_day_m1 = datetime(rep_year, rep_month, 1)
                last_day_m1 = datetime(rep_year, rep_month, calendar.monthrange(rep_year, rep_month)[1])
                dates = pd.date_range(first_day_m1, last_day_m1, freq='D')

                sample_date = dates[0].strftime("%Y-%m-%d")
                configs = cargar_configuraciones(engine_cid, sample_date)
                cfg = next((c for c in configs if str(c.get("codigo", "")).strip().upper() == code), None)
                if not cfg:
                    raise UserError(_("No se encontró configuración para el servicio %s.") % code)

                cfg["prog_servicios_por_dia"] = obtener_programacion_servicios_por_dia(engine_cid, cfg["id_servicio_especial"], dates)

                buses = cfg["mean_ids"]
                df_servicios_mensual = []
                df_validaciones_mensual = []

                for s in ['ida', 'vuelta']:
                    for b in buses:
                        idsam_val = cfg["idSam_mapping"].get(b, "")
                        row_serv = {'sentido': s, 'mean_id': b, 'id_Sam': idsam_val}
                        for d in dates:
                            row_serv[d.strftime("%Y-%m-%d")] = 0
                        df_servicios_mensual.append(row_serv)

                        for tipo in ['Total', 'General', 'Transbordo', 'Estudiante', 'Discapacidad']:
                            row_val = {'sentido': s, 'mean_id': f"{b} ({tipo})", 'id_Sam': idsam_val, 'bus_orig': b, 'tipo': tipo}
                            for d in dates:
                                row_val[d.strftime("%Y-%m-%d")] = 0
                            df_validaciones_mensual.append(row_val)

                df_serv = pd.DataFrame(df_servicios_mensual)
                df_val = pd.DataFrame(df_validaciones_mensual)

                resumen_dias = {}
                tot_prog = 0
                tot_segun = 0
                tot_fuera = 0
                tot_no_real = 0
                tot_val = 0

                self.line_ids.unlink()
                lines_to_create = []

                for d in dates:
                    d_str = d.strftime("%Y-%m-%d")
                    logs.append(f"  Procesando día {d_str}...")

                    # Geometría
                    res_geom = obtener_geometrias_rutas(engine_cid, cfg["ruta_hex_ida"], cfg["ruta_hex_vuelta"], d_str)
                    if len(res_geom) == 4:
                        G3, G4, G5_ida, G5_vuelta = res_geom
                    else:
                        G3, G4 = res_geom[0], res_geom[1]
                        G5_ida, G5_vuelta = None, None

                    # GPS
                    bus_list_sql = ", ".join(f"'{b}'" for b in buses)
                    query_gps = f"""
                        SELECT mean_id, fecha_hora, latitude, longitude
                        FROM {tabla_monitoreo}
                        WHERE fecha_hora BETWEEN '{d_str} 04:00:00' AND '{d_str} 23:59:59'
                          AND mean_id IN ({bus_list_sql})
                    """
                    with engine_mon.connect() as conn:
                        df_gps = pd.read_sql(text(query_gps), conn)

                    all_v = pd.DataFrame()
                    res_dia = procesar_servicio(cfg, df_gps, G3, G4, all_v, G5_ida=G5_ida, G5_vuelta=G5_vuelta)
                    rd = res_dia.get("resumen_operativa", {})
                    resumen_dias[d_str] = rd

                    tot_prog += rd.get("total_programados", 0)
                    tot_segun += rd.get("total_segun_operativa", 0)
                    tot_fuera += rd.get("total_fuera_operativa", 0)
                    tot_no_real += rd.get("total_no_realizados", 0)
                    tot_val += rd.get("total_validaciones", 0)

                    # Actualizar df_serv
                    ds_s = res_dia["ds_servicios"]
                    if not ds_s.empty:
                        validos = ds_s[ds_s["observación"].str.startswith("Válido")]
                        for (sent, bus), grp in validos.groupby(['sentido', 'mean_id']):
                            m = (df_serv['sentido'].str.lower() == sent.lower()) & (df_serv['mean_id'].str.upper() == str(bus).upper())
                            df_serv.loc[m, d_str] = len(grp)

                # Construir Workbook Oficial
                wb = Workbook()
                if 'Sheet' in wb.sheetnames:
                    del wb['Sheet']

                generar_hoja_informe_km(wb, df_serv, cfg, dates)
                generar_hoja_informe_validaciones(wb, df_val, cfg, dates)
                generar_hoja_resumen_operativa(wb, resumen_dias, cfg, dates)

                out_monthly = io.BytesIO()
                wb.save(out_monthly)
                monthly_bytes = out_monthly.getvalue()
                filename_monthly = f"Planilla_Mensual_{code}_{rep_year}_{rep_month:02d}.xlsx"

                dist_info = obtener_info_distancia(code)
                km_tot = tot_segun * (dist_info.get("redondo", 40.0) / 2.0)

                self.write({
                    'total_programados': tot_prog,
                    'total_segun_operativa': tot_segun,
                    'total_fuera_operativa': tot_fuera,
                    'total_no_realizados': tot_no_real,
                    'compliance_pct': round((tot_segun / tot_prog) * 100, 2) if tot_prog > 0 else 0.0,
                    'total_validaciones': tot_val,
                    'km_oficiales': km_tot,
                    'excel_monthly_file': base64.b64encode(monthly_bytes),
                    'excel_monthly_filename': filename_monthly,
                    'state': 'done',
                })

            dur = (datetime.now() - start_time).total_seconds()
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Proceso finalizado exitosamente en {dur:.1f} segundos.")
            self.write({
                'execution_time_seconds': dur,
                'log_output': "\n".join(logs)
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Auditoría VMT Concluida'),
                    'message': _('Se procesó la telemetría y se clasificaron los servicios (Según Operativa, Fuera de Operativa y No Realizados). Reportes Excel listos para descargar.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.exception("Error ejecutando auditoría VMT: %s", e)
            dur = (datetime.now() - start_time).total_seconds()
            logs.append(f"[ERROR] {str(e)}")
            self.write({
                'state': 'error',
                'execution_time_seconds': dur,
                'log_output': "\n".join(logs)
            })
            raise UserError(_("Error durante la auditoría de monitoreo VMT:\n\n%s") % str(e))

    def action_contrast_operator_sheet(self):
        """
        Contrasta la planilla de despacho del operador (ej. Arapotí) contra la auditoría
        satelital de telemetría y billetaje VMT, generando diagnósticos viaje a viaje.
        """
        self.ensure_one()
        if not self.operator_excel_file:
            raise UserError(_("Por favor cargue primero el archivo Excel de la planilla del operador."))

        try:
            file_bytes = base64.b64decode(self.operator_excel_file)
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)

            target_sheet = str(self.date.day)
            if target_sheet not in wb.sheetnames:
                target_sheet = next((s for s in wb.sheetnames if s.strip() == target_sheet or s.strip() == str(self.date)), wb.sheetnames[0])

            ws = wb[target_sheet]

            # Extraer viajes declarados por el operador
            declared_trips = []
            for r in range(2, ws.max_row + 1):
                bus_val = ws.cell(r, 1).value
                if bus_val is None or not str(bus_val).strip().isdigit():
                    continue
                bus_str = str(bus_val).strip().zfill(5)

                t_ida = ws.cell(r, 2).value
                tarj_ida = ws.cell(r, 6).value or 0
                t_vta = ws.cell(r, 8).value
                tarj_vta = ws.cell(r, 12).value or 0

                if t_ida:
                    declared_trips.append({
                        'bus': bus_str,
                        'sentido': 'ida',
                        'hora_salida': str(t_ida)[:8],
                        'validaciones': int(tarj_ida) if isinstance(tarj_ida, (int, float)) else 0,
                        'fila_excel': r
                    })
                if t_vta:
                    declared_trips.append({
                        'bus': bus_str,
                        'sentido': 'vuelta',
                        'hora_salida': str(t_vta)[:8],
                        'validaciones': int(tarj_vta) if isinstance(tarj_vta, (int, float)) else 0,
                        'fila_excel': r
                    })

            self.contrast_line_ids.unlink()
            contrast_lines = []
            matched_mon_ids = set()

            coincidentes = 0
            discrepancias_h = 0
            sin_gps_val = 0
            sin_gps_sin_val = 0

            for dec in declared_trips:
                b = dec['bus']
                s = dec['sentido']
                h_str = dec['hora_salida']
                v_dec = dec['validaciones']

                cands = self.line_ids.filtered(
                    lambda l: l.category in ('segun_operativa', 'fuera_operativa') and 
                              l.mean_id and l.mean_id.strip().upper() == b.upper() and 
                              l.direction == s
                )

                best_cand = None
                best_diff = 9999.0

                try:
                    h_dec_t = datetime.strptime(h_str, "%H:%M:%S").time() if len(h_str) == 8 else datetime.strptime(h_str, "%H:%M").time()
                    for cand in cands:
                        if cand.actual_start:
                            t_diff = abs((datetime.combine(self.date, cand.actual_start.time()) - datetime.combine(self.date, h_dec_t)).total_seconds()) / 60.0
                            if t_diff < best_diff:
                                best_diff = t_diff
                                best_cand = cand
                except Exception:
                    pass

                if best_cand and best_diff <= 20.0:
                    matched_mon_ids.add(best_cand.id)
                    coincidentes += 1
                    status = 'matched'
                    diag = f"Coincidencia plena (Desfase: {best_diff:.1f} min, Cumpl: {best_cand.compliance_pct}%)"
                    mon_start = best_cand.actual_start
                    mon_val = best_cand.validations_total
                    comp_pct = best_cand.compliance_pct
                    diff_m = best_diff
                elif best_cand:
                    matched_mon_ids.add(best_cand.id)
                    discrepancias_h += 1
                    status = 'time_diff'
                    diag = f"Desfase de horario notable ({best_diff:.1f} min fuera de tolerancia)"
                    mon_start = best_cand.actual_start
                    mon_val = best_cand.validations_total
                    comp_pct = best_cand.compliance_pct
                    diff_m = best_diff
                else:
                    diff_m = 0.0
                    mon_start = False
                    mon_val = 0
                    comp_pct = 0.0
                    if v_dec > 0:
                        sin_gps_val += 1
                        status = 'no_gps_with_val'
                        diag = f"⚠️ Sin señal GPS continua pero registró {v_dec} validaciones (Avería de equipo AVL o pérdida de enlace satelital)"
                    else:
                        sin_gps_sin_val += 1
                        status = 'no_gps_no_val'
                        diag = "❌ Despacho en grilla teórica no prestado en calle (Sin GPS ni validaciones)"

                contrast_lines.append((0, 0, {
                    'date': self.date,
                    'bus': b,
                    'direction': s,
                    'declared_departure': h_str,
                    'monitored_departure': mon_start,
                    'time_diff_minutes': diff_m,
                    'declared_validations': v_dec,
                    'monitored_validations': mon_val,
                    'compliance_pct': comp_pct,
                    'status': status,
                    'diagnosis': diag,
                }))

            # Refuerzos en pista no declarados en planilla
            unreported_cnt = 0
            for mon_l in self.line_ids.filtered(lambda l: l.category in ('segun_operativa', 'fuera_operativa') and l.id not in matched_mon_ids):
                unreported_cnt += 1
                contrast_lines.append((0, 0, {
                    'date': self.date,
                    'bus': mon_l.mean_id,
                    'direction': mon_l.direction,
                    'declared_departure': 'No Asentado',
                    'monitored_departure': mon_l.actual_start,
                    'time_diff_minutes': 0.0,
                    'declared_validations': 0,
                    'monitored_validations': mon_l.validations_total,
                    'compliance_pct': mon_l.compliance_pct,
                    'status': 'unreported_reinforcement',
                    'diagnosis': '🚌 Refuerzo operativo en calle detectado con telemetría no asentado en la planilla del operador',
                }))

            tot_decl = len(declared_trips)
            concordance = (coincidentes / tot_decl * 100.0) if tot_decl > 0 else 0.0

            # Generar Excel de Contraste
            wb_out = openpyxl.Workbook()
            ws_out = wb_out.active
            ws_out.title = "Contraste Operador vs VMT"

            headers = ["Fecha", "Bus", "Sentido", "Hora Declarada", "Salida GPS Real", "Desfase (min)", "Tarjetas Declaradas", "Validaciones VMT", "% Cumplimiento", "Estado Contraste", "Diagnóstico Técnico"]
            ws_out.append(headers)

            for col_idx, header in enumerate(headers, 1):
                cell = ws_out.cell(1, col_idx)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for cl in contrast_lines:
                data = cl[2]
                row_vals = [
                    str(data['date']),
                    data['bus'],
                    data['direction'].upper() if data.get('direction') else '',
                    data['declared_departure'],
                    data['monitored_departure'].strftime("%H:%M:%S") if data.get('monitored_departure') else 'Sin GPS',
                    round(data['time_diff_minutes'], 1),
                    data['declared_validations'],
                    data['monitored_validations'],
                    f"{data['compliance_pct']:.1f}%",
                    dict([
                        ('matched', 'Coincidente Pleno'),
                        ('time_diff', 'Discrepancia Horaria'),
                        ('no_gps_with_val', 'Sin GPS (Con Billetaje)'),
                        ('no_gps_no_val', 'No Prestado'),
                        ('unreported_reinforcement', 'Refuerzo no Asentado')
                    ]).get(data['status'], data['status']),
                    data['diagnosis']
                ]
                ws_out.append(row_vals)

            for col in ws_out.columns:
                col_lens = [len(str(cell.value)) for cell in col if cell.value is not None]
                max_len = max(col_lens) if col_lens else 10
                col_letter = get_column_letter(col[0].column)
                ws_out.column_dimensions[col_letter].width = min(max_len + 3, 50)

            out_stream = io.BytesIO()
            wb_out.save(out_stream)
            out_bytes = out_stream.getvalue()
            code_str = (self.service_code or 'SRV').upper()
            f_str = self.date.strftime("%Y-%m-%d")
            contrast_filename = f"Reporte_Contraste_Operador_VMT_{code_str}_{f_str}.xlsx"

            self.write({
                'operator_declared_trips': tot_decl,
                'contrast_matched_trips': coincidentes,
                'contrast_discrepancy_trips': discrepancias_h,
                'contrast_missing_gps_trips': sin_gps_val + sin_gps_sin_val,
                'contrast_unreported_reinforcements': unreported_cnt,
                'contrast_concordance_pct': concordance,
                'contrast_excel_file': base64.b64encode(out_bytes),
                'contrast_excel_filename': contrast_filename,
                'contrast_line_ids': contrast_lines,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Contraste Operador vs VMT Concluido'),
                    'message': _('Se procesó la planilla de %(op)s: %(tot)d declarados, %(match)d coincidentes (%(pct).1f%%). Informe listo.',
                                 op=self.operator_excel_filename or 'Operador', tot=tot_decl, match=coincidentes, pct=concordance),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.exception("Error en contraste de planilla de operador: %s", e)
            raise UserError(_("Error procesando el contraste de planilla del operador:\n\n%s") % str(e))


class TransitMonitoringAuditLine(models.Model):
    _name = 'transit.monitoring.audit.line'
    _description = 'Detalle de Servicio Auditado VMT'
    _order = 'category asc, actual_start asc, scheduled_time asc'

    audit_id = fields.Many2one('transit.monitoring.audit', string='Auditoría VMT', required=True, ondelete='cascade')

    category = fields.Selection([
        ('segun_operativa', 'Realizado según Operativa'),
        ('fuera_operativa', 'Realizado fuera de Operativa'),
        ('no_realizados', 'No Realizado (Faltante)'),
    ], string='Categoría Operativa', required=True, index=True)

    date = fields.Date(string='Fecha')
    direction = fields.Selection([
        ('ida', 'Ida'),
        ('vuelta', 'Vuelta'),
    ], string='Sentido')

    mean_id = fields.Char(string='Unidad / Bus')
    idsam = fields.Char(string='Validador')

    service_number_prog = fields.Integer(string='Nº Salida Prog')
    scheduled_time = fields.Char(string='Horario Programado')

    actual_start = fields.Datetime(string='Salida Real')
    actual_end = fields.Datetime(string='Llegada Real')
    duration_minutes = fields.Integer(string='Duración (min)')
    deviation_minutes = fields.Float(string='Desvío (min)', digits=(6, 1))

    compliance_pct = fields.Float(string='Cumplimiento (%)', digits=(5, 2))

    validations_total = fields.Integer(string='Total Pasajeros')
    validations_general = fields.Integer(string='General')
    validations_transfer = fields.Integer(string='Transbordo')
    validations_student = fields.Integer(string='Estudiante')
    validations_disability = fields.Integer(string='Discapacidad')

    status_reason = fields.Char(string='Diagnóstico / Motivo')


class TransitMonitoringContrastLine(models.Model):
    _name = 'transit.monitoring.contrast.line'
    _description = 'Línea de Contraste Operador vs Monitoreo VMT'
    _order = 'direction asc, declared_departure asc, id asc'

    audit_id = fields.Many2one('transit.monitoring.audit', string='Auditoría VMT', required=True, ondelete='cascade')
    date = fields.Date(string='Fecha')
    bus = fields.Char(string='Unidad / Bus', required=True)
    direction = fields.Selection([('ida', 'Ida'), ('vuelta', 'Vuelta')], string='Sentido')
    declared_departure = fields.Char(string='Salida Declarada Planilla')
    monitored_departure = fields.Datetime(string='Salida Detectada GPS')
    time_diff_minutes = fields.Float(string='Desfase Horario (min)', digits=(6, 1))
    declared_validations = fields.Integer(string='Tarjetas Planilla')
    monitored_validations = fields.Integer(string='Validaciones VMT')
    compliance_pct = fields.Float(string='% Trazado GPS', digits=(5, 2))
    status = fields.Selection([
        ('matched', 'Coincidente Pleno (GPS y Horario)'),
        ('time_diff', 'Discrepancia Horaria (> 20 min)'),
        ('no_gps_with_val', 'Sin Señal GPS (Con Validaciones Billetaje)'),
        ('no_gps_no_val', 'No Detectado / Despacho No Prestado'),
        ('unreported_reinforcement', 'Refuerzo en Pista (No Asentado)'),
    ], string='Diagnóstico Comparativo', required=True, index=True)
    diagnosis = fields.Char(string='Detalle Técnico')

