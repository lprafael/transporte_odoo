#!/usr/bin/env python3
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import calendar
import concurrent.futures
from sqlalchemy import create_engine, text
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# Cargar configuraciones y lógica desde los archivos existentes
from config_db import cargar_configuraciones, obtener_geometrias_rutas, determinar_tipo_dia
from logica_monitoreo import procesar_servicio

# Cargar .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Variables globales para los motores de base de datos en los workers
_worker_engine_cid = None
_worker_engine_monitoreo = None
_worker_engine_azure = None

def _init_worker(db_cid, db_monitoreo, db_azure):
    """Inicializador por cada proceso worker: genera conexiones independientes seguras."""
    global _worker_engine_cid, _worker_engine_monitoreo, _worker_engine_azure
    _worker_engine_cid = create_engine(db_cid, pool_pre_ping=True)
    _worker_engine_monitoreo = create_engine(db_monitoreo, pool_pre_ping=True)
    _worker_engine_azure = create_engine(db_azure, pool_pre_ping=True)

def _procesar_un_dia(d_str, cfg, set_estudiantes):
    """
    Función ejecutada por un worker para procesar un único día de un servicio en paralelo.
    Retorna (d_str, day_results, error_str).
    """
    global _worker_engine_cid, _worker_engine_monitoreo, _worker_engine_azure
    try:
        # 1. Geometría para este día
        res_geom = obtener_geometrias_rutas(_worker_engine_cid, cfg["ruta_hex_ida"], cfg["ruta_hex_vuelta"], d_str)
        if len(res_geom) == 4:
            G3, G4, G5_ida, G5_vuelta = res_geom
        else:
            G3, G4 = res_geom[0], res_geom[1]
            G5_ida, G5_vuelta = None, None

        if G3 is None or G4 is None:
            return d_str, [], f"No se pudo cargar geometría para {d_str}"

        # 2. Franja horaria para el día d
        if isinstance(d_str, datetime):
            d = d_str
            d_str = d.strftime("%Y-%m-%d")
        else:
            d = datetime.strptime(d_str, "%Y-%m-%d")
        h_ini_str = cfg["franja_hora_inicio"].replace(".", ":")
        h_fin_str = cfg["franja_hora_fin"].replace(".", ":")
        h_ini = int(h_ini_str.split(":")[0])
        h_fin = int(h_fin_str.split(":")[0])
        
        fecha_inicio = f"{d_str} {h_ini_str}"
        if cfg["pasa_al_dia_siguiente"] or h_fin < h_ini:
            fecha_fin_dt = d + timedelta(days=1)
        else:
            fecha_fin_dt = d
            
        parts = h_fin_str.split(":")
        h, m, s = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, int(parts[2]) if len(parts) > 2 else 0
        fecha_fin = fecha_fin_dt.replace(hour=h, minute=m, second=s).strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. Query GPS con Reintentos
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
                AND fecha_hora BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
                AND mean_id IN ({bus_list_sql})
        """
        
        df_gps = pd.DataFrame()
        for attempt in range(3):
            try:
                with _worker_engine_monitoreo.connect() as conn:
                    df_gps = pd.read_sql(text(query_gps), conn)
                if not df_gps.empty:
                    df_gps["mean_id"] = df_gps["mean_id"].astype(str).str.strip().str.upper()
                break 
            except Exception as e:
                if attempt < 2:
                    import time
                    time.sleep(5)
                    continue
                return d_str, [], f"Error GPS día {d_str} tras 3 intentos: {e}"

        # 4. Query Validaciones con Reintentos
        idsams_filt = [str(i) for i in cfg["idSam_mapping"].values() if i]
        all_validaciones = pd.DataFrame()
        if idsams_filt:
            idsam_str = ", ".join(f"'{i}'" for i in idsams_filt)
            min_v = datetime.strptime(fecha_inicio, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=15)
            max_v = datetime.strptime(fecha_fin, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=15)
            
            query_v = f"""
                SELECT idsam, fechahoraevento, serialmediopago, entidad, latitude, longitude, idrutaestacion, tipotransporte, númerotransbordos, montoevento, idproducto
                FROM c_transacciones
                WHERE fechahoraevento BETWEEN '{min_v}' AND '{max_v}'
                  AND idproducto IN ('4d4f', '4553') AND tipoevento = 4
                  AND idsam IN ({idsam_str})
            """
            for attempt in range(3):
                try:
                    with _worker_engine_azure.connect() as conn_az:
                        all_validaciones = pd.read_sql(text(query_v), conn_az)
                        if not all_validaciones.empty:
                            all_validaciones["fechahoraevento"] = pd.to_datetime(all_validaciones["fechahoraevento"])
                            is_est = pd.Series(False, index=all_validaciones.index)
                            if "serialmediopago" in all_validaciones.columns and set_estudiantes:
                                seriales = all_validaciones["serialmediopago"].astype(str).str.strip().str.upper()
                                is_est = is_est | seriales.isin(set_estudiantes)
                            all_validaciones["is_estudiante"] = is_est
                    break
                except Exception as e:
                    if attempt < 2:
                        import time
                        time.sleep(5)
                        continue
                    return d_str, [], f"Error Azure día {d_str} tras 3 intentos: {e}"

        if df_gps.empty and all_validaciones.empty:
            return d_str, [], None

        # 5. Procesar lógica de monitoreo maestro (GPS + Control Cruzado Billetaje)
        resultados = procesar_servicio(cfg, df_gps, G3, G4, all_validaciones, G5_ida=G5_ida, G5_vuelta=G5_vuelta)
        ds_servicios = resultados["ds_servicios"]
        resumen_dia = resultados.get("resumen_operativa", {})
        
        day_results = []
        if not ds_servicios.empty:
            validos = ds_servicios[ds_servicios["observación"].str.startswith("Válido")]
            for (sentido, bus), group in validos.groupby(['sentido', 'mean_id']):
                day_results.append({
                    'sentido': sentido,
                    'bus': bus,
                    'servicios': len(group),
                    'Total': int(group['validaciones'].sum()) if 'validaciones' in group.columns else 0,
                    'General': int(group['validaciones_general'].sum()) if 'validaciones_general' in group.columns else 0,
                    'Transbordo': int(group['validaciones_transbordo'].sum()) if 'validaciones_transbordo' in group.columns else 0,
                    'Estudiante': int(group['validaciones_estudiante'].sum()) if 'validaciones_estudiante' in group.columns else 0,
                    'Discapacidad': int(group['validaciones_discapacidad'].sum()) if 'validaciones_discapacidad' in group.columns else 0,
                })

        return d_str, day_results, resumen_dia, None

    except Exception as e:
        return d_str, [], {}, str(e)

def get_month_dates(reporting_year, reporting_month, pasa_al_dia_siguiente, fecha_inicio_personalizada=None):
    first_day_m1 = datetime(reporting_year, reporting_month, 1)
    last_day_m1 = datetime(reporting_year, reporting_month, calendar.monthrange(reporting_year, reporting_month)[1])
    
    if fecha_inicio_personalizada:
        start_date = datetime.strptime(fecha_inicio_personalizada, "%Y-%m-%d")
    else:
        if pasa_al_dia_siguiente:
            start_date = first_day_m1 - timedelta(days=1)
        else:
            start_date = first_day_m1
    
    if pasa_al_dia_siguiente:
        end_date = last_day_m1 - timedelta(days=1)
    else:
        end_date = last_day_m1
    
    return pd.date_range(start_date, end_date, freq='D')

def apply_payment_logic(summation):
    if summation == 9: return 8
    if summation == 8: return 7
    if summation == 7: return 6
    if summation == 5: return 0
    return summation

import locale
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
    except:
        pass

# =====================================================================
# CONFIGURACIÓN DE DISTANCIAS FIJAS OFICIALES Y FORMATEADOR EXCEL
# =====================================================================

DISTANCIAS_OFICIALES = {
    "E1": {
        "ida": 18.0,
        "vuelta": 17.7,
        "redondo": 35.7,
        "nota": "** Según Pliego de Bases y Condiciones del llamado",
        "descripcion": "Línea E1 (Asunción – San Lorenzo por Av. Eusebio Ayala / Ruta PY02)",
    },
    "E2": {
        "ida": 19.0,
        "vuelta": 19.2,
        "redondo": 38.2,
        "nota": "** Según Pliego de Bases y Condiciones del llamado",
        "descripcion": "Línea E2 (Asunción – San Lorenzo por Av. Mariscal López / Ruta D027)",
    },
    "E3": {
        "ida": 18.3,
        "vuelta": 18.9,
        "redondo": 37.2,
        "nota": "** Según Convenio Modificatorio Nº 01",
        "descripcion": "Línea E3 (Puerto de Asunción – Aeropuerto Silvio Pettirossi)",
    },
    "B1": {
        "ida": 25.3,
        "vuelta": 23.5,
        "redondo": 48.8,
        "nota": "** Según Geometría Oficial de Itinerario",
        "descripcion": "Línea B1 (Servicio Búho 1)",
    },
    "B2": {
        "ida": 24.1,
        "vuelta": 24.8,
        "redondo": 48.9,
        "nota": "** Según Geometría Oficial de Itinerario",
        "descripcion": "Línea B2 (Servicio Búho 2)",
    },
    "B3": {
        "ida": 23.3,
        "vuelta": 24.4,
        "redondo": 47.7,
        "nota": "** Según Geometría Oficial de Itinerario",
        "descripcion": "Línea B3 (Servicio Búho 3)",
    },
    "B4": {
        "ida": 20.7,
        "vuelta": 21.1,
        "redondo": 41.8,
        "nota": "** Según Geometría Oficial de Itinerario",
        "descripcion": "Línea B4 (Servicio Búho 4)",
    },
}

def obtener_info_distancia(codigo):
    cod = str(codigo).strip().upper()
    if cod in DISTANCIAS_OFICIALES:
        return DISTANCIAS_OFICIALES[cod]
    return {
        "ida": 0.0,
        "vuelta": 0.0,
        "redondo": 0.0,
        "nota": "** Según Pliego de Bases y Condiciones del llamado",
        "descripcion": f"Línea {cod}",
    }

def obtener_programacion_servicios_por_dia(engine, id_servicio: int, dates: list) -> dict:
    """
    Retorna un diccionario {fecha_str: cantidad_servicios_programados_por_sentido}
    para cada fecha en dates consultando servicios_especiales.programacion_operativa
    y determinando el tipo de día (Laboral=5, Sábado=6, Domingo/Feriado=7).
    """
    prog_por_dia = {}
    cache_prog = {}
    for dt in dates:
        f_str = dt.strftime("%Y-%m-%d")
        tipo_dia, es_feriado, feriado_desc, tipo_dia_desc = determinar_tipo_dia(engine, f_str)
        cache_key = (tipo_dia, f_str)
        if cache_key not in cache_prog:
            query = text("""
                SELECT count(*) as cant
                FROM servicios_especiales.programacion_operativa
                WHERE id_servicio_especial = :id
                  AND tipo_dia = :tipo_dia
                  AND LOWER(TRIM(sentido)) = 'ida'
                  AND fecha_inicio_vigencia <= :fecha
                  AND (fecha_fin_vigencia IS NULL OR fecha_fin_vigencia >= :fecha)
            """)
            try:
                with engine.connect() as conn:
                    res = conn.execute(query, {"id": id_servicio, "tipo_dia": tipo_dia, "fecha": f_str}).scalar()
                    cache_prog[cache_key] = int(res) if res else 0
            except Exception as e:
                print(f"  [WARN] Error consultando programacion_operativa para {f_str}: {e}")
                cache_prog[cache_key] = 0
        prog_por_dia[f_str] = cache_prog[cache_key]
    return prog_por_dia

# Fills
NAVY_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
LIGHT_GRAY_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
MEDIUM_GRAY_FILL = PatternFill(start_color="BFBFBF", end_color="BFBFBF", fill_type="solid")

# Bordes
THIN_SIDE = Side(style='thin', color='000000')
THIN_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
BOTTOM_THIN_BORDER = Border(bottom=THIN_SIDE)

# Fuentes
FONT_TITLE_WHITE_18 = Font(name="Calibri", size=18, bold=True, color="FFFFFF")
FONT_TITLE_BLACK_16 = Font(name="Calibri", size=16, bold=True, color="000000")
FONT_SECTION_BLACK_16 = Font(name="Calibri", size=16, bold=True, color="000000")
FONT_HEADER_WHITE_12 = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
FONT_META_BOLD_14 = Font(name="Calibri", size=14, bold=True, color="000000")
FONT_META_REG_12 = Font(name="Calibri", size=12, bold=False, color="000000")
FONT_DATA_REG_12 = Font(name="Calibri", size=12, bold=False, color="000000")
FONT_DATA_REG_11 = Font(name="Calibri", size=11, bold=False, color="000000")
FONT_DATA_BOLD_11 = Font(name="Calibri", size=11, bold=True, color="000000")
FONT_DATA_BOLD_12 = Font(name="Calibri", size=12, bold=True, color="000000")
FONT_DATA_BOLD_14 = Font(name="Calibri", size=14, bold=True, color="000000")
FONT_FOOTNOTE_11 = Font(name="Calibri", size=11, bold=False, color="000000")

# Alineaciones
ALIGN_CENTER = Alignment(horizontal='center', vertical='center')
ALIGN_LEFT = Alignment(horizontal='left', vertical='center')
ALIGN_RIGHT = Alignment(horizontal='right', vertical='center')
ALIGN_ROTATED_90 = Alignment(horizontal='center', vertical='center', text_rotation=90)

def _style_range(ws, min_col, min_row, max_col, max_row, font=None, fill=None, border=None, alignment=None, number_format=None):
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            cell = ws.cell(row=r, column=c)
            if font: cell.font = font
            if fill: cell.fill = fill
            if border: cell.border = border
            if alignment: cell.alignment = alignment
            if number_format: cell.number_format = number_format

def generar_hoja_informe_km(wb, df_serv, cfg, dates):
    ws = wb.create_sheet(title="Informe KM")
    ws.views.sheetView[0].showGridLines = False

    buses = cfg["mean_ids"]
    num_buses = len(buses)
    num_days = len(dates)
    last_col = 5 + num_days
    last_day_letter = get_column_letter(last_col)

    # Column dimensions
    ws.column_dimensions['A'].width = 42.6
    ws.column_dimensions['B'].width = 10.7
    ws.column_dimensions['C'].width = 13.0
    ws.column_dimensions['D'].width = 13.0
    ws.column_dimensions['E'].width = 4.14
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        ws.column_dimensions[col_letter].width = 8.5

    # 1. Title box A1:E2
    ws.merge_cells("A1:E2")
    ws.cell(1, 1, f"{cfg.get('eot_nombre', 'Empresa')} - Servicio {cfg.get('nombre', '')}")
    _style_range(ws, 1, 1, 5, 2, font=FONT_TITLE_WHITE_18, fill=NAVY_FILL, border=THIN_BORDER, alignment=ALIGN_CENTER)
    ws.row_dimensions[1].height = 23.25
    ws.row_dimensions[2].height = 18.75

    # Row 3: Empty
    ws.row_dimensions[3].height = 4.5

    # Row 4: Subtitle
    periodo_str = f"{dates[0].strftime('%d/%m/%Y')} AL {dates[-1].strftime('%d/%m/%Y')}"
    nom = str(cfg.get('nombre', '')).strip().upper()
    if nom.startswith('SERVICIO '):
        nom = nom.replace('SERVICIO ', '', 1).strip()
    ws.cell(4, 1, f"PLANILLA DE DATOS SERVICIO {nom} - OPERATIVOS DEL PERIODO {periodo_str}").font = FONT_TITLE_BLACK_16
    ws.cell(4, 1).border = BOTTOM_THIN_BORDER
    ws.row_dimensions[4].height = 18.0

    # Row 5: Fecha de inicio de operativa
    ws.merge_cells("A5:E5")
    ws.cell(5, 1, "Fecha de inicio de operativa")
    _style_range(ws, 1, 5, 5, 5, font=FONT_META_BOLD_14, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for idx, dt in enumerate(dates):
        c = 6 + idx
        py_dt = dt.to_pydatetime() if hasattr(dt, 'to_pydatetime') else dt
        cell = ws.cell(5, c, py_dt)
        cell.font = FONT_META_REG_12
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_ROTATED_90
        cell.number_format = 'ddd", "d/m/yyyy'
    ws.row_dimensions[5].height = 91.5

    # Row 6: Servicios a realizar
    ws.merge_cells("A6:E6")
    ws.cell(6, 1, "Servicios a realizar")
    _style_range(ws, 1, 6, 5, 6, font=FONT_META_BOLD_14, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    prog_map = cfg.get("prog_servicios_por_dia", {})
    for idx, dt in enumerate(dates):
        c = 6 + idx
        d_str = dt.strftime("%Y-%m-%d")
        cant_prog = prog_map.get(d_str, 0)
        cell = ws.cell(6, c, cant_prog)
        cell.font = FONT_DATA_REG_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[6].height = 16.5

    # Row 7: Empty
    ws.row_dimensions[7].height = 5.25

    # Row 8: SENTIDO IDA
    ws.cell(8, 1, "SENTIDO IDA").font = FONT_SECTION_BLACK_16
    ws.cell(8, 1).border = BOTTOM_THIN_BORDER
    ws.row_dimensions[8].height = 15.75

    # Row 9: Table Header IDA
    headers_ida = ["Nº COCHE", "ITV ANT.", "ITV ACT", "ITV VEN", "SIT."]
    for c, h in enumerate(headers_ida, start=1):
        cell = ws.cell(9, c, h)
        cell.font = FONT_HEADER_WHITE_12
        cell.fill = NAVY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(9, c, f"=CONCATENATE(DAY({col_letter}5))")
        cell.font = FONT_HEADER_WHITE_12
        cell.fill = NAVY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[9].height = 15.75

    # IDA Buses (Rows 10 to 10 + num_buses - 1)
    ida_start_row = 10
    ida_end_row = ida_start_row + num_buses - 1

    for idx, bus in enumerate(buses):
        r = ida_start_row + idx
        ws.row_dimensions[r].height = 15.0
        idsam = cfg["idSam_mapping"].get(bus, "")
        ws.cell(r, 1, f"IdSam: {idsam} - mean_id: {str(bus).lower()}").font = FONT_DATA_REG_12
        ws.cell(r, 1).border = THIN_BORDER

        for c, txt in [(2, "---"), (3, "---"), (4, "---"), (5, "ITV")]:
            cell = ws.cell(r, c, txt)
            cell.font = FONT_DATA_REG_11
            cell.border = THIN_BORDER
            cell.alignment = ALIGN_CENTER
            if c in (2, 3, 4):
                cell.number_format = 'dd/mm/yyyy'

        mask = (df_serv['sentido'].str.lower() == 'ida') & (df_serv['mean_id'].astype(str).str.upper() == str(bus).upper())
        for c_idx, dt in enumerate(dates):
            c = 6 + c_idx
            d_str = dt.strftime("%Y-%m-%d")
            val = 0
            if not df_serv[mask].empty and d_str in df_serv.columns:
                val = int(df_serv.loc[mask, d_str].values[0])
            cell = ws.cell(r, c, val)
            cell.font = FONT_DATA_REG_11
            cell.border = THIN_BORDER
            cell.alignment = ALIGN_CENTER

    # IDA Summary Rows
    r_contab = ida_end_row + 1
    r_excl = r_contab + 1
    r_val = r_excl + 1
    r_pago = r_val + 1

    # Servicios contabilizados
    ws.merge_cells(f"A{r_contab}:E{r_contab}")
    ws.cell(r_contab, 1, "Servicios contabilizados")
    _style_range(ws, 1, r_contab, 5, r_contab, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(r_contab, c, f"=SUM({col_letter}{ida_start_row}:{col_letter}{ida_end_row})")
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[r_contab].height = 15.75

    # Servicios EXCLUIDO P/ITV (*)
    ws.merge_cells(f"A{r_excl}:E{r_excl}")
    ws.cell(r_excl, 1, "Servicios EXCLUIDO P/ITV (*)")
    _style_range(ws, 1, r_excl, 5, r_excl, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        cell = ws.cell(r_excl, c, 0)
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[r_excl].height = 15.75

    # Servicios VÁLIDOS REALIZADOS (**)
    ws.merge_cells(f"A{r_val}:E{r_val}")
    ws.cell(r_val, 1, "Servicios VÁLIDOS REALIZADOS (**)")
    _style_range(ws, 1, r_val, 5, r_val, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(r_val, c, f"=+{col_letter}{r_contab}-{col_letter}{r_excl}")
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[r_val].height = 15.75

    # Servicios CONTABILIZADOS PARA PAGO (**)
    ws.merge_cells(f"A{r_pago}:E{r_pago}")
    ws.cell(r_pago, 1, "Servicios CONTABILIZADOS PARA PAGO (**)")
    _style_range(ws, 1, r_pago, 5, r_pago, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(r_pago, c, f"={col_letter}{r_val}")
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[r_pago].height = 15.0

    # Spacer between IDA and VUELTA
    sp1 = r_pago + 1
    ws.row_dimensions[sp1].height = 6.0

    # SENTIDO VUELTA
    r_vta_title = sp1 + 1
    ws.cell(r_vta_title, 1, "SENTIDO VUELTA").font = FONT_SECTION_BLACK_16
    ws.cell(r_vta_title, 1).border = BOTTOM_THIN_BORDER
    ws.row_dimensions[r_vta_title].height = 17.25

    # VUELTA Header
    r_vta_hdr = r_vta_title + 1
    for c, h in enumerate(headers_ida, start=1):
        cell = ws.cell(r_vta_hdr, c, h)
        cell.font = FONT_HEADER_WHITE_12
        cell.fill = NAVY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(r_vta_hdr, c, f"=CONCATENATE(DAY({col_letter}5))")
        cell.font = FONT_HEADER_WHITE_12
        cell.fill = NAVY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[r_vta_hdr].height = 15.75

    # VUELTA Buses
    vta_start_row = r_vta_hdr + 1
    vta_end_row = vta_start_row + num_buses - 1

    for idx, bus in enumerate(buses):
        r = vta_start_row + idx
        ws.row_dimensions[r].height = 15.0
        idsam = cfg["idSam_mapping"].get(bus, "")
        ws.cell(r, 1, f"IdSam: {idsam} - mean_id: {str(bus).lower()}").font = FONT_DATA_REG_12
        ws.cell(r, 1).border = THIN_BORDER

        for c, txt in [(2, "---"), (3, "---"), (4, "---"), (5, "ITV")]:
            cell = ws.cell(r, c, txt)
            cell.font = FONT_DATA_REG_11
            cell.border = THIN_BORDER
            cell.alignment = ALIGN_CENTER
            if c in (2, 3, 4):
                cell.number_format = 'dd/mm/yyyy'

        mask = (df_serv['sentido'].str.lower() == 'vuelta') & (df_serv['mean_id'].astype(str).str.upper() == str(bus).upper())
        for c_idx, dt in enumerate(dates):
            c = 6 + c_idx
            d_str = dt.strftime("%Y-%m-%d")
            val = 0
            if not df_serv[mask].empty and d_str in df_serv.columns:
                val = int(df_serv.loc[mask, d_str].values[0])
            cell = ws.cell(r, c, val)
            cell.font = FONT_DATA_REG_11
            cell.border = THIN_BORDER
            cell.alignment = ALIGN_CENTER

    # VUELTA Summary Rows
    vr_contab = vta_end_row + 1
    vr_excl = vr_contab + 1
    vr_val = vr_excl + 1
    vr_pago = vr_val + 1

    ws.merge_cells(f"A{vr_contab}:E{vr_contab}")
    ws.cell(vr_contab, 1, "Servicios contabilizados")
    _style_range(ws, 1, vr_contab, 5, vr_contab, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(vr_contab, c, f"=SUM({col_letter}{vta_start_row}:{col_letter}{vta_end_row})")
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[vr_contab].height = 15.75

    ws.merge_cells(f"A{vr_excl}:E{vr_excl}")
    ws.cell(vr_excl, 1, "Servicios EXCLUIDO P/ITV (*)")
    _style_range(ws, 1, vr_excl, 5, vr_excl, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        cell = ws.cell(vr_excl, c, 0)
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[vr_excl].height = 15.75

    ws.merge_cells(f"A{vr_val}:E{vr_val}")
    ws.cell(vr_val, 1, "Servicios VÁLIDOS REALIZADOS (**)")
    _style_range(ws, 1, vr_val, 5, vr_val, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(vr_val, c, f"=+{col_letter}{vr_contab}-{col_letter}{vr_excl}")
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[vr_val].height = 15.75

    ws.merge_cells(f"A{vr_pago}:E{vr_pago}")
    ws.cell(vr_pago, 1, "Servicios CONTABILIZADOS PARA PAGO (**)")
    _style_range(ws, 1, vr_pago, 5, vr_pago, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c in range(6, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(vr_pago, c, f"={col_letter}{vr_val}")
        cell.font = FONT_DATA_BOLD_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[vr_pago].height = 13.5

    # Spacer before CANTIDADES MENSUALES
    sp2 = vr_pago + 1
    ws.row_dimensions[sp2].height = 11.25

    # CANTIDADES MENSUALES
    m_title = sp2 + 1
    m_buses = m_title + 1
    m_contab = m_buses + 1
    m_excl = m_contab + 1
    m_val = m_excl + 1
    m_pbc = m_val + 1
    m_pago = m_pbc + 1
    m_km = m_pago + 1
    m_sub = m_km + 1
    m_sp3 = m_sub + 1
    fn1 = m_sp3 + 1
    fn2 = fn1 + 1

    dist_info = obtener_info_distancia(cfg.get("codigo", "")).copy()
    if cfg.get("km_computo_ida") is not None:
        v_ida = float(cfg["km_computo_ida"])
        dist_info["ida"] = int(v_ida) if v_ida.is_integer() else v_ida
    if cfg.get("km_computo_vuelta") is not None:
        v_vta = float(cfg["km_computo_vuelta"])
        dist_info["vuelta"] = int(v_vta) if v_vta.is_integer() else v_vta
    r_tot = dist_info["ida"] + dist_info["vuelta"]
    dist_info["redondo"] = int(r_tot) if isinstance(r_tot, (int, float)) and float(r_tot).is_integer() else round(r_tot, 2)

    # m_title
    ws.merge_cells(f"A{m_title}:E{m_title}")
    ws.cell(m_title, 1, "CANTIDADES MENSUALES")
    _style_range(ws, 1, m_title, 5, m_title, font=FONT_META_BOLD_14, fill=MEDIUM_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_CENTER)
    ws.cell(m_title, 6, "IDA")
    _style_range(ws, 6, m_title, 6, m_title, font=FONT_META_BOLD_14, fill=MEDIUM_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_CENTER)
    ws.cell(m_title, 7, "VUE")
    _style_range(ws, 7, m_title, 7, m_title, font=FONT_META_BOLD_14, fill=MEDIUM_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_CENTER)
    ws.cell(m_title, 8, None).border = THIN_BORDER
    ws.row_dimensions[m_title].height = 16.5

    # m_buses
    ws.merge_cells(f"A{m_buses}:E{m_buses}")
    ws.cell(m_buses, 1, "Cantidad de buses")
    _style_range(ws, 1, m_buses, 5, m_buses, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    ws.cell(m_buses, 6, None).border = THIN_BORDER
    ws.cell(m_buses, 7, None).border = THIN_BORDER
    cell_b = ws.cell(m_buses, 8, num_buses)
    cell_b.font = FONT_DATA_BOLD_12
    cell_b.border = THIN_BORDER
    cell_b.alignment = ALIGN_CENTER
    ws.row_dimensions[m_buses].height = 18.75

    # m_contab
    ws.merge_cells(f"A{m_contab}:E{m_contab}")
    ws.cell(m_contab, 1, f"=+A{r_contab}")
    _style_range(ws, 1, m_contab, 5, m_contab, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c, form in [(6, f"=SUM(F{r_contab}:{last_day_letter}{r_contab})"), (7, f"=SUM(F{vr_contab}:{last_day_letter}{vr_contab})"), (8, f"=F{m_contab}+G{m_contab}")]:
        cell = ws.cell(m_contab, c, form)
        cell.font = FONT_DATA_BOLD_14
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_RIGHT
    ws.row_dimensions[m_contab].height = 18.75

    # m_excl
    ws.merge_cells(f"A{m_excl}:E{m_excl}")
    ws.cell(m_excl, 1, f"=+A{r_excl}")
    _style_range(ws, 1, m_excl, 5, m_excl, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c, form in [(6, 0), (7, 0), (8, f"=F{m_excl}+G{m_excl}")]:
        cell = ws.cell(m_excl, c, form)
        cell.font = FONT_DATA_BOLD_14
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_RIGHT
    ws.row_dimensions[m_excl].height = 18.75

    # m_val
    ws.merge_cells(f"A{m_val}:E{m_val}")
    ws.cell(m_val, 1, f"=+A{r_val}")
    _style_range(ws, 1, m_val, 5, m_val, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c, form in [(6, f"=SUM(F{r_val}:{last_day_letter}{r_val})"), (7, f"=SUM(F{vr_val}:{last_day_letter}{vr_val})"), (8, f"=F{m_val}+G{m_val}")]:
        cell = ws.cell(m_val, c, form)
        cell.font = FONT_DATA_BOLD_14
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_RIGHT
    ws.row_dimensions[m_val].height = 18.75

    # m_pbc
    ws.merge_cells(f"A{m_pbc}:E{m_pbc}")
    ws.cell(m_pbc, 1, "Exclusion s/PBC - Anexo 2 - Numeral 7.1.1 ")
    _style_range(ws, 1, m_pbc, 5, m_pbc, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c, form in [(6, 0), (7, 0), (8, f"=F{m_pbc}+G{m_pbc}")]:
        cell = ws.cell(m_pbc, c, form)
        cell.font = FONT_DATA_BOLD_14
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_RIGHT
    ws.row_dimensions[m_pbc].height = 18.75

    # m_pago
    ws.merge_cells(f"A{m_pago}:E{m_pago}")
    ws.cell(m_pago, 1, "Servicios CONTABILIZADOS PARA PAGO (**)")
    _style_range(ws, 1, m_pago, 5, m_pago, font=FONT_DATA_BOLD_12, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for c, form in [(6, f"=SUM(F{r_pago}:{last_day_letter}{r_pago})"), (7, f"=SUM(F{vr_pago}:{last_day_letter}{vr_pago})"), (8, f"=F{m_pago}+G{m_pago}")]:
        cell = ws.cell(m_pago, c, form)
        cell.font = FONT_DATA_BOLD_12
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_RIGHT
    ws.row_dimensions[m_pago].height = 15.75

    # m_km (Distancia por servicio según Apéndice / Convenio)
    ws.merge_cells(f"A{m_km}:E{m_km}")
    ws.cell(m_km, 1, "km por servicio (**)")
    _style_range(ws, 1, m_km, 5, m_km, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    cell_ida = ws.cell(m_km, 6, dist_info["ida"])
    cell_ida.font = FONT_DATA_REG_11
    cell_ida.border = THIN_BORDER
    cell_ida.alignment = ALIGN_RIGHT

    cell_vta = ws.cell(m_km, 7, dist_info["vuelta"])
    cell_vta.font = FONT_DATA_REG_11
    cell_vta.border = THIN_BORDER
    cell_vta.alignment = ALIGN_RIGHT

    cell_tot = ws.cell(m_km, 8, f"=F{m_km}+G{m_km}")
    cell_tot.font = FONT_DATA_BOLD_11
    cell_tot.border = THIN_BORDER
    cell_tot.alignment = ALIGN_RIGHT
    ws.row_dimensions[m_km].height = 18.75

    # m_sub (Kilómetros para el pago de subsidio)
    ws.merge_cells(f"A{m_sub}:E{m_sub}")
    ws.cell(m_sub, 1, "Kilómetros para el pago de subsidio (**)")
    _style_range(ws, 1, m_sub, 5, m_sub, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    num_fmt_km = '_ * #,##0_ ;_ * \\-#,##0_ ;_ * \\-_ ;_ @_ '
    cell_s_ida = ws.cell(m_sub, 6, f"=F{m_pago}*F{m_km}")
    cell_s_ida.font = FONT_DATA_REG_12
    cell_s_ida.border = THIN_BORDER
    cell_s_ida.alignment = ALIGN_RIGHT
    cell_s_ida.number_format = num_fmt_km

    cell_s_vta = ws.cell(m_sub, 7, f"=G{m_pago}*G{m_km}")
    cell_s_vta.font = FONT_DATA_REG_12
    cell_s_vta.border = THIN_BORDER
    cell_s_vta.alignment = ALIGN_RIGHT
    cell_s_vta.number_format = num_fmt_km

    cell_s_tot = ws.cell(m_sub, 8, f"=F{m_sub}+G{m_sub}")
    cell_s_tot.font = FONT_DATA_BOLD_12
    cell_s_tot.border = THIN_BORDER
    cell_s_tot.alignment = ALIGN_RIGHT
    cell_s_tot.number_format = num_fmt_km
    ws.row_dimensions[m_sub].height = 17.45

    # Spacer
    ws.merge_cells(f"A{m_sp3}:E{m_sp3}")
    ws.row_dimensions[m_sp3].height = 7.5

    # Footnotes
    ws.cell(fn1, 1, "* Según Resolución GVMT Nº 207/2023").font = FONT_FOOTNOTE_11
    ws.row_dimensions[fn1].height = 15.75

    ws.cell(fn2, 1, dist_info["nota"]).font = FONT_FOOTNOTE_11
    ws.row_dimensions[fn2].height = 15.75


def generar_hoja_resumen_operativa(wb, resumen_dias, cfg, dates):
    ws = wb.create_sheet(title="Resumen Operativa")
    ws.views.sheetView[0].showGridLines = True

    # Title box A1:U2
    ws.merge_cells("A1:U2")
    ws.cell(1, 1, f"{cfg.get('eot_nombre', 'Empresa')} - Servicio {cfg.get('nombre', '')} | AUDITORÍA OPERATIVA MENSUAL VMT")
    _style_range(ws, 1, 1, 21, 2, font=FONT_TITLE_WHITE_18, fill=NAVY_FILL, border=THIN_BORDER, alignment=ALIGN_CENTER)
    ws.row_dimensions[1].height = 22.0
    ws.row_dimensions[2].height = 20.0

    # Period
    periodo_str = f"{dates[0].strftime('%d/%m/%Y')} AL {dates[-1].strftime('%d/%m/%Y')}"
    ws.cell(3, 1, f"DETALLE DE CUMPLIMIENTO OPERATIVO Y SERVICIOS FALTANTES - {periodo_str}").font = FONT_TITLE_BLACK_16
    ws.row_dimensions[3].height = 20.0

    headers = [
        "Fecha", "Día", "Tipo de Día",
        "Prog. Ida", "Prog. Vta", "Total Prog.",
        "Según Operativa Ida", "Según Operativa Vta", "Total Según Operativa",
        "Fuera Operativa Ida", "Fuera Operativa Vta", "Total Fuera Operativa",
        "No Realizados Ida", "No Realizados Vta", "Total No Realizados",
        "% Cumplimiento",
        "Val. General", "Val. Transbordo", "Val. Estudiante", "Val. Discapacidad", "Total Pasajeros"
    ]
    # Header row at row 5
    header_row = 5
    ws.row_dimensions[header_row].height = 28.0
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(header_row, col_idx, h)
        cell.font = FONT_HEADER_WHITE_12
        cell.fill = NAVY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER

    start_data_row = 6
    for idx, dt in enumerate(dates):
        r = start_data_row + idx
        d_str = dt.strftime("%Y-%m-%d")
        rd = resumen_dias.get(d_str, {})
        ws.row_dimensions[r].height = 18.0

        p_ida = rd.get("prog_ida", 0)
        p_vta = rd.get("prog_vuelta", 0)
        p_tot = rd.get("total_programados", p_ida + p_vta)

        s_ida = rd.get("segun_operativa_ida", 0)
        s_vta = rd.get("segun_operativa_vuelta", 0)
        s_tot = rd.get("total_segun_operativa", s_ida + s_vta)

        f_ida = rd.get("fuera_operativa_ida", 0)
        f_vta = rd.get("fuera_operativa_vuelta", 0)
        f_tot = rd.get("total_fuera_operativa", f_ida + f_vta)

        n_ida = rd.get("no_realizados_ida", 0)
        n_vta = rd.get("no_realizados_vuelta", 0)
        n_tot = rd.get("total_no_realizados", n_ida + n_vta)

        pct = rd.get("porcentaje_cumplimiento_operativa", round((s_tot / p_tot * 100), 2) if p_tot > 0 else 0.0)

        v_gen = rd.get("validaciones_general", 0)
        v_tra = rd.get("validaciones_transbordo", 0)
        v_est = rd.get("validaciones_estudiante", 0)
        v_dis = rd.get("validaciones_discapacidad", 0)
        v_tot = rd.get("total_validaciones", v_gen + v_tra + v_est + v_dis)

        dow_name = dt.strftime("%A").capitalize()
        tipo_desc = rd.get("tipo_dia_desc", "Laboral" if dt.weekday() < 5 else ("Sábado" if dt.weekday() == 5 else "Domingo"))

        row_vals = [
            dt.strftime("%d/%m/%Y"), dow_name, tipo_desc,
            p_ida, p_vta, p_tot,
            s_ida, s_vta, s_tot,
            f_ida, f_vta, f_tot,
            n_ida, n_vta, n_tot,
            f"{pct:.1f}%",
            v_gen, v_tra, v_est, v_dis, v_tot
        ]

        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(r, c_idx, val)
            cell.font = FONT_DATA_REG_11
            cell.border = THIN_BORDER
            cell.alignment = ALIGN_CENTER if c_idx in [1, 2, 3, 16] else ALIGN_RIGHT
            if c_idx == 15 and n_tot > 0:
                cell.fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
                cell.font = Font(name="Calibri", size=11, bold=True, color="C00000")
            elif c_idx == 9:
                cell.font = Font(name="Calibri", size=11, bold=True, color="385723")

    # Totals row
    tot_row = start_data_row + len(dates)
    ws.row_dimensions[tot_row].height = 22.0
    ws.cell(tot_row, 1, "TOTALES").font = FONT_DATA_BOLD_12
    ws.cell(tot_row, 1).border = THIN_BORDER
    ws.cell(tot_row, 2, "").border = THIN_BORDER
    ws.cell(tot_row, 3, "").border = THIN_BORDER
    _style_range(ws, 1, tot_row, 3, tot_row, fill=MEDIUM_GRAY_FILL)

    for c_idx in range(4, 22):
        col_let = get_column_letter(c_idx)
        cell = ws.cell(tot_row, c_idx)
        if c_idx == 16:  # % cumplimiento
            cell.value = f"=AVERAGE({col_let}{start_data_row}:{col_let}{tot_row-1})"
            cell.number_format = '0.0%'
        else:
            cell.value = f"=SUM({col_let}{start_data_row}:{col_let}{tot_row-1})"
            cell.number_format = '#,##0'
        cell.font = FONT_DATA_BOLD_12
        cell.fill = MEDIUM_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_RIGHT

    # Adjust widths
    for col_idx in range(1, len(headers) + 1):
        col_let = get_column_letter(col_idx)
        max_len = max(len(str(headers[col_idx-1])), 12)
        ws.column_dimensions[col_let].width = max_len + 4


def generar_hoja_informe_validaciones(wb, df_val, cfg, dates):
    ws = wb.create_sheet(title="Informe Validaciones")
    ws.views.sheetView[0].showGridLines = False

    buses = cfg["mean_ids"]
    num_buses = len(buses)
    num_days = len(dates)
    last_col = 6 + num_days

    # Column dimensions
    ws.column_dimensions['A'].width = 16.5
    ws.column_dimensions['B'].width = 21.6
    ws.column_dimensions['C'].width = 10.3
    ws.column_dimensions['D'].width = 9.0
    ws.column_dimensions['E'].width = 9.7
    ws.column_dimensions['F'].width = 4.14
    for c in range(7, last_col + 1):
        col_letter = get_column_letter(c)
        ws.column_dimensions[col_letter].width = 8.5

    # Row 1: Empty
    # Row 2 & 3: Title box A2:F3
    ws.merge_cells("A2:F3")
    ws.cell(2, 1, f"{cfg.get('eot_nombre', 'Empresa')} - Servicio {cfg.get('nombre', '')}")
    _style_range(ws, 1, 2, 6, 3, font=FONT_TITLE_WHITE_18, fill=NAVY_FILL, border=THIN_BORDER, alignment=ALIGN_CENTER)
    ws.row_dimensions[2].height = 23.25
    ws.row_dimensions[3].height = 23.25

    # Row 4: Empty
    ws.row_dimensions[4].height = 12.75

    # Row 5: Subtitle
    periodo_str = f"{dates[0].strftime('%d/%m/%Y')} AL {dates[-1].strftime('%d/%m/%Y')}"
    nom = str(cfg.get('nombre', '')).strip().upper()
    if nom.startswith('SERVICIO '):
        nom = nom.replace('SERVICIO ', '', 1).strip()
    ws.cell(5, 1, f"PLANILLA DE DATOS SERVICIO {nom} - OPERATIVOS DEL PERIODO {periodo_str}").font = FONT_TITLE_BLACK_16
    ws.cell(5, 1).border = BOTTOM_THIN_BORDER
    ws.row_dimensions[5].height = 18.75

    # Row 6: Fecha de inicio de operativa
    ws.merge_cells("A6:F6")
    ws.cell(6, 1, "Fecha de inicio de operativa")
    _style_range(ws, 1, 6, 6, 6, font=FONT_META_BOLD_14, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    for idx, dt in enumerate(dates):
        c = 7 + idx
        if idx == 0:
            py_dt = dt.to_pydatetime() if hasattr(dt, 'to_pydatetime') else dt
            cell = ws.cell(6, c, py_dt)
        else:
            prev_col_letter = get_column_letter(c - 1)
            cell = ws.cell(6, c, f"=+{prev_col_letter}6+1")
        cell.font = FONT_META_REG_12
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_ROTATED_90
        cell.number_format = 'ddd", "d/m/yyyy'
    ws.row_dimensions[6].height = 107.25

    # Row 7: Servicios a realizar
    ws.merge_cells("A7:F7")
    ws.cell(7, 1, "Servicios a realizar")
    _style_range(ws, 1, 7, 6, 7, font=FONT_META_BOLD_14, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
    prog_map = cfg.get("prog_servicios_por_dia", {})
    for idx, dt in enumerate(dates):
        c = 7 + idx
        d_str = dt.strftime("%Y-%m-%d")
        cant_prog = prog_map.get(d_str, 0)
        cell = ws.cell(7, c, cant_prog)
        cell.font = FONT_DATA_REG_11
        cell.fill = LIGHT_GRAY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[7].height = 18.0

    # Row 8: Empty
    ws.row_dimensions[8].height = 17.25

    # Row 9: VALIDACIONES
    ws.cell(9, 1, "VALIDACIONES").font = FONT_SECTION_BLACK_16
    ws.cell(9, 1).border = BOTTOM_THIN_BORDER
    ws.row_dimensions[9].height = 20.25

    # Row 10: Table Header
    headers_val = ["Nº COCHE", "NUMERO DE COCHE", "ITV ANT.", "ITV ACT", "ITV VEN", "SIT."]
    for c, h in enumerate(headers_val, start=1):
        cell = ws.cell(10, c, h)
        cell.font = FONT_HEADER_WHITE_12
        cell.fill = NAVY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    for c in range(7, last_col + 1):
        col_letter = get_column_letter(c)
        cell = ws.cell(10, c, f"=CONCATENATE(DAY({col_letter}6))")
        cell.font = FONT_HEADER_WHITE_12
        cell.fill = NAVY_FILL
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_CENTER
    ws.row_dimensions[10].height = 15.75

    # Data rows (5 rows per bus)
    val_start_row = 11
    val_end_row = val_start_row + (5 * num_buses) - 1
    current_row = val_start_row

    tipos = ["Total", "General", "Transbordo", "Estudiante", "Discapacidad"]

    for bus in buses:
        idsam = cfg["idSam_mapping"].get(bus, "")
        for tipo in tipos:
            ws.row_dimensions[current_row].height = 15.75
            ws.cell(current_row, 1, str(idsam).lower()).font = FONT_DATA_REG_11
            ws.cell(current_row, 1).border = THIN_BORDER

            ws.cell(current_row, 2, f"{bus} ({tipo})").font = FONT_DATA_REG_11
            ws.cell(current_row, 2).border = THIN_BORDER

            for c, txt in [(3, "---"), (4, "---"), (5, "---"), (6, "ITV")]:
                cell = ws.cell(current_row, c, txt)
                cell.font = FONT_DATA_REG_11
                cell.border = THIN_BORDER
                cell.alignment = ALIGN_CENTER
                if c in (3, 4, 5):
                    cell.number_format = 'dd/mm/yyyy'

            mask = (df_val['bus_orig'].astype(str).str.upper() == str(bus).upper()) & (df_val['tipo'] == tipo)
            for c_idx, dt in enumerate(dates):
                c = 7 + c_idx
                d_str = dt.strftime("%Y-%m-%d")
                val = 0
                if not df_val[mask].empty and d_str in df_val.columns:
                    val = int(df_val.loc[mask, d_str].sum())
                cell = ws.cell(current_row, c, val)
                cell.font = FONT_DATA_REG_11
                cell.border = THIN_BORDER
                cell.alignment = ALIGN_CENTER

            current_row += 1

    # Sumatorias
    sum_row_map = {}
    for tipo in tipos:
        sr = current_row
        sum_row_map[tipo] = sr
        ws.row_dimensions[sr].height = 18.75 if tipo == "Discapacidad" else 15.75
        ws.merge_cells(f"A{sr}:F{sr}")
        ws.cell(sr, 1, f"SUMATORIA ({tipo})")
        _style_range(ws, 1, sr, 6, sr, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
        for c in range(7, last_col + 1):
            col_letter = get_column_letter(c)
            cell = ws.cell(sr, c, f'=SUMIF($B${val_start_row}:$B${val_end_row}, "*({tipo})*", {col_letter}{val_start_row}:{col_letter}{val_end_row})')
            cell.font = FONT_DATA_REG_11
            cell.border = THIN_BORDER
            cell.alignment = ALIGN_RIGHT
        current_row += 1

    # Spacer
    ws.merge_cells(f"A{current_row}:F{current_row}")
    ws.row_dimensions[current_row].height = 11.25
    current_row += 1

    # CANTIDADES MENSUALES
    vm_title = current_row
    ws.merge_cells(f"A{vm_title}:G{vm_title}")
    ws.cell(vm_title, 1, "CANTIDADES MENSUALES")
    _style_range(ws, 1, vm_title, 7, vm_title, font=FONT_META_BOLD_14, fill=MEDIUM_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_CENTER)
    ws.row_dimensions[vm_title].height = 18.75
    current_row += 1

    vm_buses = current_row
    ws.merge_cells(f"A{vm_buses}:F{vm_buses}")
    ws.cell(vm_buses, 1, "Cantidad de buses")
    _style_range(ws, 1, vm_buses, 6, vm_buses, font=FONT_DATA_BOLD_14, border=THIN_BORDER, alignment=ALIGN_LEFT)
    cell_b = ws.cell(vm_buses, 7, num_buses)
    cell_b.font = FONT_DATA_REG_12
    cell_b.border = THIN_BORDER
    cell_b.alignment = ALIGN_RIGHT
    ws.row_dimensions[vm_buses].height = 18.75
    current_row += 1

    last_day_letter = get_column_letter(last_col)
    for tipo in tipos:
        sr_target = sum_row_map[tipo]
        vm_r = current_row
        ws.merge_cells(f"A{vm_r}:F{vm_r}")
        ws.cell(vm_r, 1, f"SUMATORIA ({tipo})")
        _style_range(ws, 1, vm_r, 6, vm_r, font=FONT_DATA_BOLD_12, fill=LIGHT_GRAY_FILL, border=THIN_BORDER, alignment=ALIGN_LEFT)
        cell = ws.cell(vm_r, 7, f"=SUM(G{sr_target}:{last_day_letter}{sr_target})")
        cell.font = FONT_DATA_REG_12
        cell.border = THIN_BORDER
        cell.alignment = ALIGN_RIGHT
        cell.number_format = '#,##0'
        ws.row_dimensions[vm_r].height = 15.75
        current_row += 1

    # Spacer
    ws.row_dimensions[current_row].height = 8.25
    current_row += 1

    # Footnotes
    ws.cell(current_row, 1, "* Según Resolución GVMT Nº 207/2023").font = FONT_FOOTNOTE_11
    ws.row_dimensions[current_row].height = 15.75
    current_row += 1

    ws.cell(current_row, 1, "** Según Pliego de Bases y Condiciones del llamado").font = FONT_FOOTNOTE_11
    ws.row_dimensions[current_row].height = 15.75

def _enviar_correo_mensual(nombre_archivo, codigo_servicio, nombre_servicio, mes_analisis):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    mail_from = os.environ.get("EMAIL_FROM", os.environ.get("MAIL_FROM", "")).strip()
    mail_pass = os.environ.get("EMAIL_PASSWORD", os.environ.get("MAIL_APP_PASSWORD", "")).strip()
    mail_user = os.environ.get("EMAIL_USERNAME", mail_from).strip()
    mail_host = os.environ.get("EMAIL_HOST", "smtp.gmail.com").strip()
    try:
        mail_port = int(os.environ.get("EMAIL_PORT", "465"))
    except:
        mail_port = 465

    mail_to = os.environ.get("MAIL_MENSUAL", "").strip()
    
    if not mail_from or not mail_pass:
        print("  Correo omitido: configure EMAIL_FROM y EMAIL_PASSWORD en .env")
        return
    if not mail_to:
        print("  Correo omitido: configure MAIL_MENSUAL en .env")
        return
    if not os.path.exists(nombre_archivo):
        print(f"  No se envía correo: archivo {nombre_archivo} no existe.")
        return

    html = f"""
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: sans-serif; line-height: 1.5; color: #333; }}
  .container {{ max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 8px; }}
  h2 {{ color: #004a99; }}
  .footer {{ font-size: 12px; color: #777; margin-top: 20px; border-top: 1px solid #eee; padding-top: 10px; }}
</style>
</head>
<body>
  <div class="container">
    <h2>Informe Mensual de Servicios Especiales</h2>
    <p>Estimados,</p>
    <p>Se adjunta el reporte mensual correspondiente al servicio <strong>{nombre_servicio} ({codigo_servicio})</strong>.</p>
    <p><strong>Mes de análisis:</strong> {mes_analisis}</p>
    <p>Este informe centraliza la cantidad de servicios y validaciones registradas durante el periodo indicado.</p>
    <div class="footer">
      Centro de Control y Monitoreo de Transporte<br>
      Sistema de Gestión de Flota
    </div>
  </div>
</body>
</html>
"""

    msg = MIMEMultipart()
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = f"Reporte Mensual {codigo_servicio} - {mes_analisis}"
    msg.attach(MIMEText(html, "html"))

    with open(nombre_archivo, "rb") as f:
        part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(nombre_archivo))
        msg.attach(part)

    try:
        if mail_port == 465:
            with smtplib.SMTP_SSL(mail_host, mail_port) as session:
                session.login(mail_user, mail_pass)
                session.sendmail(mail_from, [mail_to], msg.as_string())
        else:
            with smtplib.SMTP(mail_host, mail_port) as session:
                session.starttls()
                session.login(mail_user, mail_pass)
                session.sendmail(mail_from, [mail_to], msg.as_string())
        print(f"  Correo mensual enviado exitosamente a {mail_to}")
    except Exception as e:
        print(f"  Error al enviar correo mensual: {e}")

def main():
    import argparse
    from argparse import RawTextHelpFormatter

    examples = """
Ejemplos de comando:
  1. Procesar el mes anterior (automático con workers):
     python reporte_mensual_excel.py

  2. Procesar con 8 workers en paralelo:
     python reporte_mensual_excel.py -w 8

  3. Procesar un servicio específico (ej. B1) para el mes anterior:
     python reporte_mensual_excel.py -s B1

  4. Procesar un mes y año específicos (ej. Enero 2026):
     python reporte_mensual_excel.py -m 1 -y 2026

  5. Combinación (ej. Servicio B1 en Enero 2026 con 6 workers):
     python reporte_mensual_excel.py -s B1 -m 1 -y 2026 -w 6
"""

    parser = argparse.ArgumentParser(
        description="Generador de Reporte Mensual de Servicios Especiales (Optimizado con Workers)",
        epilog=examples,
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument("-s", "--servicio", help="Código del servicio (ej: B1, B3, etc.)")
    parser.add_argument("-m", "--mes", type=int, help="Mes de análisis (1-12)")
    parser.add_argument("-y", "--year", type=int, help="Año de análisis (ej: 2026)")
    parser.add_argument("-fi", "--fecha_inicio", help="Fecha de inicio (YYYY-MM-DD)")
    parser.add_argument("-ff", "--fecha_fin", help="Fecha de fin (YYYY-MM-DD)")
    parser.add_argument("-w", "--workers", type=int, default=None, 
                        help="Número de workers en paralelo (por defecto: automático según CPU)")
    parser.add_argument("--no-email", action="store_true", help="No enviar correo electrónico al finalizar")
    args = parser.parse_args()

    today = datetime.now()
    if args.fecha_inicio and args.fecha_fin:
        dt_inicio = datetime.strptime(args.fecha_inicio, "%Y-%m-%d")
        reporting_month = dt_inicio.month
        reporting_year = dt_inicio.year
    elif args.mes and args.year:
        reporting_month = args.mes
        reporting_year = args.year
    else:
        first_of_this_month = today.replace(day=1)
        prev_month_date = first_of_this_month - timedelta(days=1)
        reporting_month = prev_month_date.month
        reporting_year = prev_month_date.year

    db_cid = os.environ.get("DB_CID_URL")
    db_monitoreo = os.environ.get("DB_MONITOREO_URL")
    db_azure = os.environ.get("DB_AZURE_URL")
    
    if not all([db_cid, db_monitoreo, db_azure]):
        print("Faltan variables de entorno (DB_CID_URL, DB_MONITOREO_URL, DB_AZURE_URL)")
        sys.exit(1)

    engine_cid = create_engine(db_cid, pool_pre_ping=True)

    # Determinar número de workers
    num_workers = args.workers if args.workers else min(8, max(1, (os.cpu_count() or 4)))
    print(f"\n[CONFIG] Modo paralelo activado: {num_workers} workers concurrentes.")

    configs = []
    last_day_month = calendar.monthrange(reporting_year, reporting_month)[1]
    
    for day in range(1, last_day_month + 1):
        ref_date = datetime(reporting_year, reporting_month, day).strftime("%Y-%m-%d")
        daily_configs = cargar_configuraciones(engine_cid, ref_date)
        
        existing_codes = {c["codigo"] for c in configs}
        new_configs = [c for c in daily_configs if c["codigo"] not in existing_codes]
        
        for cfg in new_configs:
            cfg["fecha_adjudicacion_encontrada"] = ref_date
        
        configs.extend(new_configs)
        
        if args.servicio:
            servicios_pedidos = {s.strip().upper() for s in args.servicio.split(",") if s.strip()}
            if servicios_pedidos.issubset({c["codigo"].upper() for c in configs}):
                break
    
    if args.servicio:
        servicios_pedidos = {s.strip().upper() for s in args.servicio.split(",") if s.strip()}
        configs = [c for c in configs if c["codigo"].upper() in servicios_pedidos]

    if not configs:
        print(f"No hay servicios configurados para ningún día de {calendar.month_name[reporting_month]} {reporting_year}")
        sys.exit(0)

    report_dir = "Reportes_Mensuales"
    os.makedirs(report_dir, exist_ok=True)

    if args.fecha_inicio and args.fecha_fin:
        analysis_month_str = f"Personalizado ({args.fecha_inicio} a {args.fecha_fin})"
    else:
        analysis_month_name = calendar.month_name[reporting_month].upper()
        analysis_month_str = f"{analysis_month_name} {reporting_year}"

    for cfg in configs:
        codigo = cfg["codigo"]
        print(f"\n=======================================================")
        print(f"Procesando reporte mensual para: {codigo}")
        print(f"=======================================================")
        
        with engine_cid.connect() as conn:
            res_eot = conn.execute(text("SELECT eot_nombre FROM eots WHERE eot_id = :id"), {"id": cfg["id_eot"]}).fetchone()
            cfg["eot_nombre"] = res_eot[0] if res_eot else "Empresa Desconocida"

        first_day_month = datetime(reporting_year, reporting_month, 1)
        if cfg["pasa_al_dia_siguiente"]:
            natural_start = first_day_month - timedelta(days=1)
        else:
            natural_start = first_day_month

        fecha_inicio_personalizada = None
        fecha_inicio_adj = cfg.get("fecha_inicio_adjudicacion")
        if fecha_inicio_adj:
            adj_dt = datetime.strptime(fecha_inicio_adj[:10], "%Y-%m-%d")
            if adj_dt >= first_day_month and adj_dt > natural_start:
                fecha_inicio_personalizada = adj_dt.strftime("%Y-%m-%d")

        if args.fecha_inicio and args.fecha_fin:
            dates = pd.date_range(args.fecha_inicio, args.fecha_fin, freq='D')
        else:
            dates = get_month_dates(reporting_year, reporting_month, cfg["pasa_al_dia_siguiente"], fecha_inicio_personalizada)
        
        print(f"  Periodo: {dates[0].strftime('%Y-%m-%d')} al {dates[-1].strftime('%Y-%m-%d')} ({len(dates)} días)")
        cfg["prog_servicios_por_dia"] = obtener_programacion_servicios_por_dia(engine_cid, cfg["id_servicio_especial"], dates)
        
        set_estudiantes = set()
        try:
            with engine_cid.connect() as conn_cid:
                query_estudiantes = "SELECT serial_mdp FROM public.perfiles_especiales WHERE serial_mdp IS NOT NULL AND id_tipo_perfil=3"
                df_est = pd.read_sql(text(query_estudiantes), conn_cid)
                if not df_est.empty:
                    set_estudiantes = set(df_est["serial_mdp"].astype(str).str.strip().str.upper())
            print(f"  [INFO] Se cargaron {len(set_estudiantes)} seriales de estudiantes.")
        except Exception as e:
            print(f"  [WARN] No se pudo cargar la lista de estudiantes: {e}")
            
        buses = cfg["mean_ids"]
        df_servicios_mensual = []
        df_validaciones_mensual = []
        
        for s in ['ida', 'vuelta']:
            for b in buses:
                idsam_val = cfg["idSam_mapping"].get(b, "")
                row_serv = {'sentido': s, 'mean_id': b, 'id_Sam': idsam_val}
                for d in dates:
                    d_str = d.strftime("%Y-%m-%d")
                    row_serv[d_str] = 0
                df_servicios_mensual.append(row_serv)
                
                for tipo in ['Total', 'General', 'Transbordo', 'Estudiante', 'Discapacidad']:
                    row_val = {'sentido': s, 'mean_id': f"{b} ({tipo})", 'id_Sam': idsam_val, 'bus_orig': b, 'tipo': tipo}
                    for d in dates:
                        d_str = d.strftime("%Y-%m-%d")
                        row_val[d_str] = 0
                    df_validaciones_mensual.append(row_val)
        
        df_serv = pd.DataFrame(df_servicios_mensual)
        df_val = pd.DataFrame(df_validaciones_mensual)

        # Procesar días en paralelo con ProcessPoolExecutor
        print(f"  Ejecutando procesamiento distribuido en {num_workers} workers...")
        total_days = len(dates)
        completed = 0

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=num_workers,
            initializer=_init_worker,
            initargs=(db_cid, db_monitoreo, db_azure)
        ) as executor:
            futures = {
                executor.submit(_procesar_un_dia, d.strftime("%Y-%m-%d"), cfg, set_estudiantes): d.strftime("%Y-%m-%d")
                for d in dates
            }

            resumen_dias = {}
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                d_str, day_results, resumen_dia, err = future.result()
                resumen_dias[d_str] = resumen_dia or {}
                
                if err:
                    print(f"  [{completed}/{total_days}] {d_str} [WARN]  {err}")
                else:
                    serv_count = sum(r['servicios'] for r in day_results)
                    print(f"  [{completed}/{total_days}] {d_str} [OK] {serv_count} servicios detectados")

                for res in day_results:
                    sentido = res['sentido']
                    bus = res['bus']
                    
                    mask = (df_serv['sentido'].astype(str).str.lower() == sentido.lower()) & (df_serv['mean_id'].astype(str).str.upper() == str(bus).upper())
                    df_serv.loc[mask, d_str] = res['servicios']
                    
                    mask_val_tot = (df_val['sentido'].astype(str).str.lower() == sentido.lower()) & (df_val['bus_orig'].astype(str).str.upper() == str(bus).upper()) & (df_val['tipo'] == 'Total')
                    df_val.loc[mask_val_tot, d_str] = res['Total']
                    
                    if 'General' in res:
                        mask_val_gral = (df_val['sentido'].astype(str).str.lower() == sentido.lower()) & (df_val['bus_orig'].astype(str).str.upper() == str(bus).upper()) & (df_val['tipo'] == 'General')
                        df_val.loc[mask_val_gral, d_str] = res['General']
                    
                    if 'Transbordo' in res:
                        mask_val_trans = (df_val['sentido'].astype(str).str.lower() == sentido.lower()) & (df_val['bus_orig'].astype(str).str.upper() == str(bus).upper()) & (df_val['tipo'] == 'Transbordo')
                        df_val.loc[mask_val_trans, d_str] = res['Transbordo']
                        
                    if 'Estudiante' in res:
                        mask_val_estud = (df_val['sentido'].astype(str).str.lower() == sentido.lower()) & (df_val['bus_orig'].astype(str).str.upper() == str(bus).upper()) & (df_val['tipo'] == 'Estudiante')
                        df_val.loc[mask_val_estud, d_str] = res['Estudiante']

                    if 'Discapacidad' in res:
                        mask_val_disc = (df_val['sentido'].astype(str).str.lower() == sentido.lower()) & (df_val['bus_orig'].astype(str).str.upper() == str(bus).upper()) & (df_val['tipo'] == 'Discapacidad')
                        df_val.loc[mask_val_disc, d_str] = res['Discapacidad']

        print(f"\n  Generando archivo Excel para {codigo} con formato de Planilla Oficial...")
        timestamp = datetime.now().strftime("%H%M%S")
        nombre_excel_canonical = os.path.join(report_dir, f"Planilla_Mensual_{codigo}_{reporting_year}_{reporting_month:02d}.xlsx")
        nombre_excel_ts = os.path.join(report_dir, f"Planilla_Mensual_{codigo}_{reporting_year}_{reporting_month:02d}_{timestamp}.xlsx")
        
        wb = Workbook()
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
            
        generar_hoja_informe_km(wb, df_serv, cfg, dates)
        generar_hoja_informe_validaciones(wb, df_val, cfg, dates)
        generar_hoja_resumen_operativa(wb, resumen_dias, cfg, dates)
        
        nombre_excel_final = nombre_excel_canonical
        try:
            wb.save(nombre_excel_canonical)
            print(f"  Reporte guardado en: {nombre_excel_canonical}")
        except PermissionError:
            print(f"  [WARN] {nombre_excel_canonical} abierto por otro programa, guardando con timestamp...")
            wb.save(nombre_excel_ts)
            print(f"  Reporte guardado en: {nombre_excel_ts}")
            nombre_excel_final = nombre_excel_ts
            
        if not args.no_email:
            _enviar_correo_mensual(nombre_excel_final, codigo, cfg["nombre"], analysis_month_str)

    engine_cid.dispose()
    print("\nProceso finalizado correctamente.")

if __name__ == "__main__":
    main()
