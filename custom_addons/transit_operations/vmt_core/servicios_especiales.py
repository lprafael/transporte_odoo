#!/usr/bin/env python3
# servicios_especiales.py - Script principal: lee configuración desde BD, procesa cada servicio especial,
# genera reportes Excel, opcionalmente graba en BD y envía correo de resumen a la empresa.
#
# OPCIONES DE EJECUCIÓN:
# =====================
#
# 1. Todos los servicios (fecha por defecto - ayer):
#    python servicios_especiales.py
#
# 2. Servicio específico (fecha por defecto - ayer):
#    python servicios_especiales.py -s B1
#    python servicios_especiales.py --servicio B1
#
# 3. Todos los servicios en fecha específica:
#    python servicios_especiales.py -f 2024-05-20
#    python servicios_especiales.py --fecha 2024-05-20
#
# 4. Servicio específico en fecha específica:
#    python servicios_especiales.py -s B1 -f 2024-05-20
#    python servicios_especiales.py --servicio B1 --fecha 2024-05-20
#
# 5. Todos los servicios en rango de fechas:
#    python servicios_especiales.py --desde 2024-05-20 --hasta 2024-05-25
#    python servicios_especiales.py -d 2024-05-20 -t 2024-05-25
#
# 6. Servicio específico en rango de fechas:
#    python servicios_especiales.py -s B1 --desde 2024-05-20 --hasta 2024-05-25
#    python servicios_especiales.py --servicio B1 -d 2024-05-20 -t 2024-05-25
#
# PARÁMETROS:
# ===========
# -s, --servicio    : Código del servicio (ej. B1, E1, E2, etc.)
# -f, --fecha       : Fecha específica en formato YYYY-MM-DD
# -d, --desde       : Fecha inicio del rango en formato YYYY-MM-DD
# -t, --hasta       : Fecha fin del rango en formato YYYY-MM-DD
#
# VARIABLES DE ENTORNO (opcional):
# ===============================
# DB_CID_URL       : URL de base de datos CID
# DB_MONITOREO_URL : URL de base de datos de monitoreo
# DB_AZURE_URL     : URL de base de datos Azure
# FECHA_BASE       : Fecha por defecto si no se especifica (YYYY-MM-DD)
# REPORT_DIR       : Directorio para reportes (default: "Reportes")
# LOG_DIR          : Directorio para logs (default: "Logs")
# GRABAR_EN_BD     : "true"/"false" para guardar resultados en BD
# MAIL_ENABLED     : "true"/"false" para enviar correos
# GENERATE_PDFS    : "true"/"false" para generar PDFs
#
# EJEMPLOS PRÁCTICOS:
# ==================
# Procesar todos los servicios de ayer:
#    python servicios_especiales.py
#
# Procesar servicio E1 de hoy:
#    python servicios_especiales.py -s E1 -f 2026-03-12
#
# Procesar todos los servicios de la última semana:
#    python servicios_especiales.py --desde 2026-03-06 --hasta 2026-03-12
#
# Procesar servicio B2 del mes completo:
#    python servicios_especiales.py -s B2 --desde 2026-03-01 --hasta 2026-03-31

import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import create_engine, text

from config_db import (
    get_fecha_base,
    cargar_configuraciones,
    obtener_geometrias_rutas,
)
from openpyxl.worksheet.table import Table, TableStyleInfo
from logica_monitoreo import procesar_servicio

# Cargar .env
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Variables globales para control de ejecución
HAS_ERROR = False
ID_SCRIPT = 6

def registrar_alerta(engine, descripcion, id_tipo_alerta=1):
    """Registra una alerta en la tabla alertas.control_alertas."""
    global HAS_ERROR
    # Solo marcamos error de ejecución si es de tipo 1 (técnico/script)
    if id_tipo_alerta == 1:
        HAS_ERROR = True
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO alertas.control_alertas 
                (fuente, fechahora_alerta, id_tipo_alerta, verificado, corregido, descripcion_incidente)
                VALUES (:fuente, NOW(), :tipo, false, false, :desc)
            """), {
                "fuente": "servicios_especiales.py",
                "tipo": id_tipo_alerta,
                "desc": descripcion[:1000] # Truncar si es muy largo
            })
        print(f"  [INFO] Alerta registrada en control_alertas")
    except Exception as e:
        print(f"  [WARN] Error al registrar alerta en BD: {e}")

def registrar_ejecucion_correcta(engine):
    """Registra una ejecución correcta en la tabla alertas.registro_ejecuciones."""
    if HAS_ERROR:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO alertas.registro_ejecuciones 
                (id_script, fecha_proceso, fecha_ejecucion, estado, detalles)
                VALUES (:id, CURRENT_DATE, NOW(), 'OK', 'Ejecución completada correctamente')
            """), {"id": ID_SCRIPT})
        print("  [INFO] Ejecución registrada en alertas.registro_ejecuciones")
    except Exception as e:
        print(f"  [WARN] Error al registrar ejecución en BD: {e}")


def main():
    import argparse
    from argparse import RawTextHelpFormatter

    examples = """
Ejemplos de comando:
  1. Procesar para todos los servicios (ayer):
     python servicios_especiales.py

  2. Procesar un servicio específico (ej. B1):
     python servicios_especiales.py -s B1

  3. Procesar una fecha específica:
     python servicios_especiales.py -f 2026-03-01

  4. Procesar un RANGO de fechas:
     python servicios_especiales.py --desde 2026-03-01 --hasta 2026-03-10

  5. Combinar servicio y rango:
     python servicios_especiales.py -s B1 --desde 2026-03-01 --hasta 2026-03-10
"""

    parser = argparse.ArgumentParser(
        description="Monitoreo de Servicios Especiales",
        epilog=examples,
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument("-s", "--servicio", help="Código del servicio o lista separada por comas (ej. B1 o E1,E2,E3)")
    parser.add_argument("-f", "--fecha", help="Fecha a procesar (YYYY-MM-DD)")
    parser.add_argument("-d", "--desde", help="Fecha inicio del rango (YYYY-MM-DD)")
    parser.add_argument("-t", "--hasta", help="Fecha fin del rango (YYYY-MM-DD)")
    parser.add_argument("-o", "--output", help="Directorio donde guardar los reportes (ej. C:/Reportes)")
    args = parser.parse_args()

    hora_inicio = datetime.now()
    db_cid = os.environ.get("DB_CID_URL", "").strip()
    db_monitoreo = os.environ.get("DB_MONITOREO_URL", "").strip()
    db_azure = os.environ.get("DB_AZURE_URL", "").strip()
    
    if not db_cid or not db_monitoreo or not db_azure:
        print("Configure DB_CID_URL, DB_MONITOREO_URL y DB_AZURE_URL en el archivo .env")
        sys.exit(1)

    # Construir lista de fechas a procesar
    lista_fechas = []
    if args.desde and args.hasta:
        try:
            d_ini = datetime.strptime(args.desde, "%Y-%m-%d")
            d_fin = datetime.strptime(args.hasta, "%Y-%m-%d")
            curr = d_ini
            while curr <= d_fin:
                lista_fechas.append(curr.strftime("%Y-%m-%d"))
                curr += timedelta(days=1)
        except ValueError:
            print("Error: El formato de fecha debe ser YYYY-MM-DD para --desde y --hasta")
            sys.exit(1)
    elif args.fecha:
        lista_fechas = [args.fecha]
    else:
        lista_fechas = [get_fecha_base()]

    report_dir = args.output if args.output else os.environ.get("REPORT_DIR", "Reportes")
    log_dir = os.environ.get("LOG_DIR", "Logs")
    grabar_en_bd = os.environ.get("GRABAR_EN_BD", "false").strip().lower() in ("1", "true", "yes")
    mail_enabled = os.environ.get("MAIL_ENABLED", "false").strip().lower() in ("1", "true", "yes")
    generate_pdfs = os.environ.get("GENERATE_PDFS", "true").strip().lower() in ("1", "true", "yes")

    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    engine_cid = create_engine(db_cid, pool_pre_ping=True)
    engine_monitoreo = create_engine(db_monitoreo, pool_pre_ping=True)
    engine_azure = create_engine(db_azure, pool_pre_ping=True)

    try:
        for fecha_base in lista_fechas:
            print(f"\n{'='*60}")
            print(f" PROCESANDO FECHA: {fecha_base}")
            print(f"{'='*60}")
            
            configs = cargar_configuraciones(engine_cid, fecha_base)
            if configs:
                info_dia = configs[0].get("tipo_dia_desc", "")
                tipo_d_val = configs[0].get("tipo_dia")
                print(f" Régimen operativo: {info_dia} (tipo_dia={tipo_d_val})")
            
            # Filtrar por servicio si se pasó el argumento (permite uno o varios separados por coma, ej: E1,E2,E3)
            if args.servicio:
                servicios_pedidos = [s.strip().upper() for s in args.servicio.split(",") if s.strip()]
                configs = [c for c in configs if c["codigo"].upper() in servicios_pedidos]
                if not configs:
                    print(f"No se encontró configuración para el servicio {args.servicio} en la fecha {fecha_base}")
                    continue

            if not configs:
                print(f"No hay servicios especiales configurados para la fecha {fecha_base}.")
                continue

            for cfg in configs:
                inicio_servicio_dt = datetime.now()
                codigo = cfg["codigo"]
                nombre = cfg["nombre"]
                print(f"\n--- Servicio: {codigo} – {nombre} ---")

                bus_numbers = cfg["mean_ids"]
                if not bus_numbers:
                    print(f"  Sin buses asignados, se omite.")
                    continue
                bus_variants = list(set([b for b in bus_numbers] + [b.lower() for b in bus_numbers] + [b.upper() for b in bus_numbers]))
                bus_list_sql = ", ".join(f"'{b}'" for b in bus_variants)

                emisor_cond = ""
                if cfg.get("emisor_id") is not None:
                    emisor_cond = f" AND emisor_id = {cfg['emisor_id']}"
                agency_cond = ""
                if cfg.get("agency_ids"):
                    agency_list = ", ".join(f"'{a}'" for a in cfg["agency_ids"])
                    agency_cond = f" AND agency_id IN ({agency_list})"

                tabla_monitoreo = os.environ.get("TABLA_MONITOREO_GPS", "app_monitoreo_mensajeoperativo")
                query_gps = f"""
                    SELECT mean_id, fecha_hora, latitude, longitude
                    FROM {tabla_monitoreo}
                    WHERE 1=1
                        {emisor_cond}
                        {agency_cond}
                        AND fecha_hora BETWEEN '{cfg["fecha_inicio"]}' AND '{cfg["fecha_fin"]}'
                        AND mean_id IN ({bus_list_sql})
                """
                df_gps = pd.DataFrame()
                for attempt in range(3):
                    try:
                        with engine_monitoreo.connect() as conn:
                            df_gps = pd.read_sql(text(query_gps), conn)
                            if not df_gps.empty:
                                df_gps["mean_id"] = df_gps["mean_id"].astype(str).str.strip().str.upper()
                        break
                    except Exception as e:
                        if attempt < 2:
                            time.sleep(5)
                            continue
                        print(f"  Error al leer monitoreo GPS: {e}")

                if df_gps.empty:
                    print(f"  No hay datos GPS para los buses de este servicio en la franja indicada.")
                    continue

                try:
                    G3, G4, G5_ida, G5_vuelta = obtener_geometrias_rutas(
                        engine_cid,
                        cfg["ruta_hex_ida"],
                        cfg["ruta_hex_vuelta"],
                        fecha_base,
                    )
                except Exception as e:
                    print(f"  Error al cargar geometrías de rutas: {e}")
                    continue

                # 3. Consulta de VALIDACIONES para este servicio (Azure)
                all_validaciones = pd.DataFrame()
                
                idsams_filt = [str(i) for i in cfg["idSam_mapping"].values() if i]
                if idsams_filt:
                    idsam_str = ", ".join(f"'{i}'" for i in idsams_filt)
                    # Margen de 15 min para capturar validaciones justo antes o después del servicio
                    min_v = datetime.strptime(cfg["fecha_inicio"], "%Y-%m-%d %H:%M:%S") - timedelta(minutes=15)
                    max_v = datetime.strptime(cfg["fecha_fin"], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=15)
                    
                    query_v = f"""
                        SELECT idsam, fechahoraevento, serialmediopago, entidad, latitude, longitude, idrutaestacion, tipotransporte, númerotransbordos, montoevento, idproducto
                        FROM c_transacciones
                        WHERE fechahoraevento BETWEEN '{min_v}' AND '{max_v}'
                          AND idproducto IN ('4d4f', '4553') AND tipoevento = 4
                          AND idsam IN ({idsam_str})
                    """
                    for attempt in range(3):
                        try:
                            with engine_azure.connect() as conn_az:
                                df_res = pd.read_sql(text(query_v), conn_az)
                                if not df_res.empty:
                                    all_validaciones = df_res
                                    all_validaciones["fechahoraevento"] = pd.to_datetime(all_validaciones["fechahoraevento"])
                            break
                        except Exception as e:
                            if attempt < 2:
                                time.sleep(5)
                                continue
                            print(f"  Error al leer validaciones Azure: {e}")
                
                try:
                    resultados = procesar_servicio(cfg, df_gps, G3, G4, all_validaciones, G5_ida=G5_ida, G5_vuelta=G5_vuelta)
                    ds_servicios = resultados["ds_servicios"]
                    if not ds_servicios.empty:
                        print(f"  Servicios detectados para {codigo}: {len(ds_servicios)}")
                        print(f"  Umbral de cumplimiento: {cfg['rango_cumplimiento_pct']}%")
                        print(f"  Distribución por bus y observación:\n{ds_servicios.groupby(['mean_id', 'observación']).size()}")
                        print(f"  Cumplimiento promedio por bus:\n{ds_servicios.groupby('mean_id')['porcentaje_cumplimiento'].mean()}")
                    else:
                        print(f"  No se detectaron servicios para {codigo}")
                except Exception as e:
                    print(f"  Error en lógica de monitoreo: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

                ds_servicios = resultados["ds_servicios"]
                ds_servicios_validos = resultados["ds_servicios_validos"]
                ds_cant_servicios = resultados["ds_cant_servicios"]
                ds_cant_validaciones = resultados["ds_cant_validaciones"]
                ds_valid_por_hora = resultados["ds_valid_por_hora"]
                ds_validaciones = resultados["ds_validaciones"]
                ds_gdf_gps = resultados["ds_gdf_gps"]
                gdf_gps_proj = resultados.get("gdf_gps_proj")
                ds_segun_operativa = resultados.get("ds_segun_operativa", pd.DataFrame())
                ds_fuera_operativa = resultados.get("ds_fuera_operativa", pd.DataFrame())
                ds_no_realizados = resultados.get("ds_no_realizados", pd.DataFrame())
                resumen_operativa = resultados.get("resumen_operativa", {})

                if ds_servicios is None: ds_servicios = pd.DataFrame()

                # Quitar zona horaria de todas las columnas datetime para Excel en todos los DataFrames
                for df in (ds_servicios, ds_servicios_validos, ds_cant_servicios, 
                           ds_cant_validaciones, ds_valid_por_hora, ds_gdf_gps, ds_validaciones,
                           ds_segun_operativa, ds_fuera_operativa, ds_no_realizados):
                    if df is None or df.empty:
                        continue
                    for col in df.columns:
                        if pd.api.types.is_datetime64_any_dtype(df[col]):
                            if getattr(df[col].dtype, "tz", None) is not None:
                                df[col] = df[col].dt.tz_convert("America/Asuncion").dt.tz_localize(None)

                # Alerta por incumplimiento de cantidad de servicios
                tipo_desc_str = f" ({cfg.get('tipo_dia_desc', '')})" if cfg.get('tipo_dia_desc') else ""
                if cfg.get("programacion"):
                    prog_total = len(cfg["programacion"])
                    detect_total = len(ds_servicios[ds_servicios["observación"].str.startswith("Válido")]) if not ds_servicios.empty else 0
                    incompletos = len(ds_servicios[ds_servicios["observación"].str.contains("Retorno")]) if not ds_servicios.empty else 0

                    if detect_total < prog_total:
                        faltantes = prog_total - detect_total
                        inc_str = f" ({incompletos} llegaron al 80% punto de retorno)" if incompletos > 0 else ""
                        msg_alerta = (
                            f"Servicio {codigo}: Se detectaron solo {detect_total} servicios válidos de {prog_total} programados "
                            f"para la fecha {fecha_base}{tipo_desc_str}. Faltan {faltantes} servicios por cumplir{inc_str}."
                        )
                        print(f"  [WARN] Generando alerta operacional (id_tipo_alerta=2): {msg_alerta}")
                        registrar_alerta(engine_cid, msg_alerta, id_tipo_alerta=2)
                else:
                    detect_total = len(ds_servicios[ds_servicios["observación"].str.startswith("Válido")]) if not ds_servicios.empty else 0
                    if detect_total == 0:
                        msg_alerta = f"Servicio {codigo}: No se detectaron servicios válidos para la fecha {fecha_base}{tipo_desc_str}."
                        print(f"  [WARN] Generando alerta operacional (id_tipo_alerta=2): {msg_alerta}")
                        registrar_alerta(engine_cid, msg_alerta, id_tipo_alerta=2)

                nombre_archivo = os.path.join(report_dir, f"Reporte_servicios_y_validaciones_{codigo}_{fecha_base}.xlsx")
                if os.path.exists(nombre_archivo):
                    nombre_archivo = os.path.join(report_dir, f"Reporte_servicios_y_validaciones_{codigo}_{fecha_base}_{datetime.now().strftime('%H%M%S')}.xlsx")

                df_resumen = pd.DataFrame([resumen_operativa]) if resumen_operativa else pd.DataFrame()
                dict_dfs = {
                    "Resumen_Operativa": df_resumen,
                    "Segun_Operativa": ds_segun_operativa,
                    "Fuera_Operativa": ds_fuera_operativa,
                    "No_Realizados": ds_no_realizados,
                    "Servicios": ds_servicios,
                    "Serv_y_regularidad": (ds_servicios_validos if not ds_servicios_validos.empty else pd.DataFrame()),
                    "Cant_Servicios": ds_cant_servicios,
                    "Validaciones_bus": ds_cant_validaciones,
                    "Validaciones_hora": ds_valid_por_hora,
                    "Validaciones": ds_validaciones
                }
                
                hay_datos = any(df is not None and not df.empty for df in dict_dfs.values())

                with pd.ExcelWriter(nombre_archivo, engine="openpyxl") as writer:
                    if not hay_datos:
                        dict_dfs = {"Sin_Datos": pd.DataFrame({"Información": [f"No se detectaron datos para {codigo}"]})}

                    for sheet_name, df_sheet in dict_dfs.items():
                        if df_sheet is None or df_sheet.empty: continue
                        if len(df_sheet) > 1048575:
                            df_sheet = df_sheet.head(1000000)
                        df_sheet.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        if not df_sheet.empty:
                            ws = writer.sheets[sheet_name]
                            row_count, col_count = df_sheet.shape
                            from openpyxl.utils import get_column_letter
                            last_col = get_column_letter(col_count)
                            tab_range = f"A1:{last_col}{row_count + 1}"
                            tab_name = f"Tabla_{sheet_name.replace(' ', '_')}_{codigo}"
                            tab = Table(displayName=tab_name, ref=tab_range)
                            tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
                            ws.add_table(tab)
                            for i, col in enumerate(df_sheet.columns):
                                col_vals = [len(str(val)) for val in df_sheet[col].dropna()]
                                max_v = max(col_vals) if col_vals else 0
                                max_len = max(max_v, len(str(col))) + 2
                                ws.column_dimensions[get_column_letter(i + 1)].width = min(max_len, 50)

                print(f"  Reporte guardado: {nombre_archivo}")

                if grabar_en_bd:
                    try:
                        _grabar_en_cid(
                            engine_cid, codigo, fecha_base,
                            ds_servicios, ds_servicios_validos,
                            ds_cant_servicios, ds_cant_validaciones,
                            ds_validaciones, ds_valid_por_hora,
                        )
                    except Exception as e:
                        print(f"  Error al grabar en BD ({codigo}): {e}")

                tiempo_str = ""
                mail_to = ""
                if mail_enabled:
                    tiempo_str = f"{(datetime.now() - hora_inicio).seconds // 60} min {(datetime.now() - hora_inicio).seconds % 60} seg"
                    mail_to = (cfg.get("eot_email") or "").strip() or os.environ.get("MAIL_TO", "").strip()

                archivos_pdf = []
                if generate_pdfs:
                    try:
                        print(f"  Analizando posibles desvíos para generar PDFs en {codigo}...")
                        archivos_pdf = _generar_pdfs_desvios(ds_servicios, gdf_gps_proj, fecha_base, report_dir, codigo)
                    except Exception as e:
                        print(f"  Error al generar PDFs de desvíos ({codigo}): {e}")
                else:
                    print(f"  Generación de PDFs desactivada por configuración para {codigo}.")

                if mail_enabled:
                    try:
                        print(f"  Enviando reporte por correo para {codigo}...")
                        _enviar_correo_resumen(
                            nombre_archivo, codigo, nombre, fecha_base,
                            hora_inicio.strftime("%Y-%m-%d %H:%M:%S"), tiempo_str,
                            mail_to=mail_to, archivos_pdf=archivos_pdf,
                            link_panel_custom=cfg.get("link_dashboard"),
                            tipo_dia_desc=cfg.get("tipo_dia_desc")
                        )
                    except Exception as e:
                        print(f"  Error al enviar correo ({codigo}): {e}")

                duracion_serv = datetime.now() - inicio_servicio_dt
                print(f"  Tiempo de ejecución para {codigo}: {duracion_serv.seconds // 60} min {duracion_serv.seconds % 60} seg")
        
        # Registrar ejecución correcta si nada falló a nivel crítico
        registrar_ejecucion_correcta(engine_cid)

    except Exception as e:
        error_msg = f"Error crítico en ejecución: {str(e)}"
        print(f"\n[ERROR] {error_msg}")
        registrar_alerta(engine_cid, error_msg)
    finally:
        engine_cid.dispose()
        engine_monitoreo.dispose()
        engine_azure.dispose()
    
    duracion_total = datetime.now() - hora_inicio
    print(f"\nFinalizado. Tiempo total de ejecución: {duracion_total.seconds // 60} min {duracion_total.seconds % 60} seg")


def _generar_pdfs_desvios(ds_servicios, gdf_gps_proj, fecha_base, report_dir, codigo):
    """Genera PDFs de recorridos con desvíos significativos (cumplimiento < 90%)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd
    import contextily as ctx

    if ds_servicios is None or ds_servicios.empty:
        return []

    # Considerar solo servicios VÁLIDOS que tengan algún desvío (menos del 100%)
    ds_fallidos = ds_servicios[
        (ds_servicios["porcentaje_cumplimiento"] < 100) & 
        (ds_servicios["observación"].str.startswith("Válido"))
    ].sort_values("porcentaje_cumplimiento")
    
    if ds_fallidos.empty:
        return []

    gdf = gdf_gps_proj.copy()
    if "fecha_hora" in gdf.columns and getattr(gdf["fecha_hora"].dtype, "tz", None) is not None:
        gdf["fecha_hora"] = gdf["fecha_hora"].dt.tz_localize(None)
    carpeta = os.path.join(report_dir, "graficos_servicios")
    os.makedirs(carpeta, exist_ok=True)
    archivos = []
    for idx, (idx_row, servicio) in enumerate(ds_fallidos.iterrows()):
        mean_id = servicio["mean_id"]
        inicio_serv = servicio["inicio_serv"]
        fin_serv = servicio["fin_serv"]
        sentido = servicio["sentido"]
        # Usamos nro_servicio si existe, sino el índice de la fila para evitar caracteres inválidos como '?'
        nro_s = servicio.get("nro_servicio")
        nro_label = str(nro_s) if nro_s and str(nro_s) != "?" else f"tramo_{idx_row}"
        
        recorrido = gdf[
            (gdf["mean_id"] == mean_id)
            & (gdf["fecha_hora"] >= pd.to_datetime(inicio_serv))
            & (gdf["fecha_hora"] <= pd.to_datetime(fin_serv))
        ]
        if recorrido.empty:
            continue
        recorrido = recorrido.copy()
        recorrido["en_itinerario"] = (
            recorrido["dentro_itinerario_ida"] if sentido == "ida" else recorrido["dentro_itinerario_vuelta"]
        )
        if not isinstance(recorrido, gpd.GeoDataFrame):
            recorrido = gpd.GeoDataFrame(recorrido, geometry=recorrido.geometry, crs=gdf.crs)
        try:
            recorrido_3857 = recorrido.to_crs(epsg=3857)
        except Exception:
            recorrido_3857 = recorrido.to_crs("EPSG:3857")
        fig, ax = plt.subplots(figsize=(8, 6))
        recorrido_3857[recorrido_3857["en_itinerario"]].plot(ax=ax, color="green", label="Dentro del itinerario", markersize=5)
        recorrido_3857[~recorrido_3857["en_itinerario"]].plot(ax=ax, color="red", label="Fuera del itinerario", markersize=5)
        ax.set_xlim(recorrido_3857.total_bounds[[0, 2]])
        ax.set_ylim(recorrido_3857.total_bounds[[1, 3]])
        ax.set_aspect("equal")
        try:
            # Usamos zoom='auto' para que contextily decida el mejor zoom según el área
            ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom='auto')
        except Exception as e:
            print(f"    [WARN] Error agregando mapa base para {mean_id}: {e}")
            pass
        
        ax.set_title(f"Recorrido Bus {mean_id} (Fecha: {fecha_base}, Sentido: {sentido}, serv: {nro_label})\nDesvío detectado")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.legend()
        # Nombre de archivo seguro para Windows
        safe_filename = f"recorrido_{codigo}_{mean_id}_{fecha_base}_{nro_label}.pdf"
        file_path = os.path.join(carpeta, safe_filename)
        plt.savefig(file_path, dpi=100, bbox_inches="tight", format="pdf")
        plt.close()
        archivos.append(file_path)
        print(f"    - PDF generado: {safe_filename}")
    if archivos:
        print(f"  Generados {len(archivos)} PDF(s) de desvíos.")
    return archivos


def _enviar_correo_resumen(nombre_archivo, codigo_servicio, nombre_servicio, fecha_base, hora_inicio_str, tiempo_ejecucion_str, mail_to=None, archivos_pdf=None, link_panel_custom=None, tipo_dia_desc=None):
    """Envía por correo el informe de monitoreo. Destinatario principal: mail_to (e_mail de la EOT) o MAIL_TO de .env."""
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

    mail_to = (mail_to or "").strip() or os.environ.get("MAIL_TO", "").strip()
    mail_cc = os.environ.get("MAIL_CC", "").strip()
    
    # Prioridad: 1. Link de la DB, 2. Link .env
    link_panel = (link_panel_custom or "").strip() or os.environ.get("MAIL_LINK_PANEL", "").strip()
    
    link_html = ""
    if link_panel:
        link_html = f'''
    <p>En caso de requerir información adicional o complementaria, puede consultar el siguiente enlace:<br>
    <a href="{link_panel}" target="_blank">
      📊 Panel de Monitoreo Operativo
    </a></p>
    '''
    
    archivos_pdf = archivos_pdf or []

    if not mail_from or not mail_pass:
        print("  Correo omitido: configure EMAIL_FROM y EMAIL_PASSWORD en .env")
        return
    if not mail_to:
        print("  Correo omitido: configure MAIL_TO en .env o registre e_mail en la tabla eots para la EOT del servicio.")
        return
    if not os.path.exists(nombre_archivo):
        print(f"  No se envía correo: archivo {nombre_archivo} no existe.")
        return

    correos_cc = [e.strip() for e in mail_cc.split(",") if e.strip()]

    info_dia_html = f" &ndash; {tipo_dia_desc}" if tipo_dia_desc else ""

    html = f'''
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #333;
    background-color: #f7f9fb;
    line-height: 1.5;
    padding: 20px;
  }}
  .container {{
    max-width: 720px;
    margin: auto;
    background: #fff;
    border-radius: 12px;
    padding: 30px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  }}
  h2 {{
    color: #004a99;
    margin-top: 0;
  }}
  ul {{
    margin-top: 10px;
  }}
  li {{
    margin-bottom: 8px;
  }}
  .highlight {{
    background: #e9f2ff;
    padding: 10px 15px;
    border-left: 4px solid #004a99;
    border-radius: 6px;
    margin-bottom: 16px;
  }}
  .footer {{
    font-size: 13px;
    color: #666;
    margin-top: 24px;
    border-top: 1px solid #eee;
    padding-top: 12px;
  }}
  a {{
    color: #0056b3;
    text-decoration: none;
  }}
</style>
</head>
<body>
  <div class="container">
    <h2>Informe de Monitoreo Automático – “{nombre_servicio}”</h2>

    <div class="highlight">
      <p><strong>Fecha analizada:</strong> {fecha_base}{info_dia_html}<br>
      <strong>Inicio de ejecución:</strong> {hora_inicio_str}<br>
      <strong>Duración:</strong> {tiempo_ejecucion_str}</p>
    </div>

    <p>Estimados,</p>
    <p>Por medio del presente, se remite el <strong>informe de monitoreo</strong> correspondiente a los servicios y validaciones registrados en el sistema de control operativo <strong>“{nombre_servicio}”</strong>.</p>

    <p>El informe adjunto incluye:</p>
    <ul>
      <li>✔ <strong>Registro de servicios detectados</strong>, con detalle de inicio y fin de cada viaje, tiempos de duración y cumplimiento de itinerario.</li>
      <li>✔ <strong>Listado de servicios válidos y no válidos</strong>, según los criterios establecidos en la normativa vigente.</li>
      <li>✔ <strong>Cantidad de validaciones</strong> por servicio y por unidad, según los registros transaccionales de las Empresas Prestadoras del Servicio de Billetaje Electrónico.</li>
      <li>✔ <strong>Información georreferenciada</strong> de los eventos operativos, con datos de ubicación y tiempos de tránsito de cada unidad monitoreada.</li>
    </ul>

    <p>Estos análisis son ejecutados de forma automática, por lo que cualquier <strong>desvío, cambio de itinerario o retraso</strong> será procesado posteriormente en caso de detectarse. La identificación de los servicios se basa en los datos de georreferenciación reportados por las <strong>Empresas Operadoras de Transporte (EOT)</strong> y las validaciones registradas en el <strong>Sistema Nacional de Billetaje Electrónico (SNBE)</strong>.</p>

    <p>Por lo tanto, cualquier <strong>retraso o inconsistencia en la transmisión de datos</strong> de geoposicionamiento o de validación podría afectar los resultados del monitoreo.</p>

    {link_html}

    <p>Así también, se solicita informar —como respuesta a este correo— cualquier evento que haya influido en la operativa normal del servicio a fin de considerarlo en los informes correspondientes.</p>

    <p>Quedamos atentos a cualquier consulta adicional.</p>

    <div class="footer">
      <strong>Centro de Control y Monitoreo de Transporte</strong><br>
      Sistema Integrado de Monitoreo y Gestión de Flota<br>
    </div>
  </div>
</body>
</html>
'''

    msg = MIMEMultipart()
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = f"Reporte de Servicios y Validaciones – {codigo_servicio} – {fecha_base}"
    if correos_cc:
        msg["Cc"] = ", ".join(correos_cc)
    msg.attach(MIMEText(html, "html"))

    with open(nombre_archivo, "rb") as f:
        part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(nombre_archivo))
        msg.attach(part)

    for file_path in archivos_pdf:
        if os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    part_pdf = MIMEBase("application", "pdf")
                    part_pdf.set_payload(f.read())
                    encoders.encode_base64(part_pdf)
                    part_pdf.add_header("Content-Disposition", "attachment", filename=os.path.basename(file_path))
                    msg.attach(part_pdf)
            except Exception as e:
                print(f"  No se pudo adjuntar PDF {file_path}: {e}")

    destinos = [mail_to] + correos_cc
    try:
        if mail_port == 465:
            with smtplib.SMTP_SSL(mail_host, mail_port) as session:
                session.login(mail_user, mail_pass)
                session.sendmail(mail_from, destinos, msg.as_string())
        else:
            with smtplib.SMTP(mail_host, mail_port) as session:
                session.starttls()
                session.login(mail_user, mail_pass)
                session.sendmail(mail_from, destinos, msg.as_string())
        print(f"  Correo de resumen enviado a {mail_to}")
    except Exception as e:
        print(f"  Error al conectar con el servidor SMTP: {e}")
        raise e


def _grabar_en_cid(
    engine,
    codigo_servicio,
    fecha_base,
    ds_servicios,
    ds_servicios_validos,
    ds_cant_servicios,
    ds_cant_validaciones,
    ds_validaciones,
    ds_valid_por_hora,
):
    """Insertar resultados en tablas nservicios, ncant_servicios, etc. (como Monitoreo_B1.py). servicio = codigo (B1, E1, ...)."""
    from sqlalchemy import text

    def _insertar(table, df, column_map, fecha_col="fecha_operativa", delete_first=True):
        if delete_first:
            with engine.begin() as conn:
                conn.execute(text(f"DELETE FROM {table} WHERE fecha_operativa = :f AND servicio = :s"), {"f": fecha_base, "s": codigo_servicio})
        
        if df is None or df.empty:
            return
            
        df = df.copy()
        df[fecha_col] = fecha_base
        df["servicio"] = codigo_servicio
        df = df.rename(columns=column_map)
        # Asegurar que se inserte solo las columnas que existen en el mapeo + fijas
        cols_to_keep = list(column_map.values()) + [fecha_col, "servicio"]
        # Filtrar solo si el mapeo no está vacío (para casos como nvalidaciones_bus donde column_map es {})
        if column_map:
            df = df[[c for c in df.columns if c in cols_to_keep]]
            
        df.to_sql(table, con=engine, if_exists="append", index=False)

    # nservicios: Guardar SOLO los servicios válidos (ds_servicios_validos ya está filtrado y ordenado)
    map_reg = {
        "sentido": "sentido",
        "mean_id": "mean_id",
        "idsam": "idsam",
        "inicio_cabecera": "inicio_cabec",
        "inicio_serv": "inicio_serv",
        "fin_serv": "fin_serv",
        "duración(min)": "duración_min",
        "total_eventos": "total_eventos",
        "eventos_itinerario": "eventos_itinerario",
        "validaciones": "validaciones",
        "porcentaje_cumplimiento": "porcentaje_cumplimiento",
        "observación": "observación",
        "nro_servicio": "nro_servicio",
        "regularidad": "regularidad"
    }
    
    # Insertar servicios válidos (ya vienen ordenados por sentido e inicio_serv desde logica_monitoreo.py)
    _insertar("nservicios", ds_servicios_validos, map_reg, delete_first=True)
    
    _insertar("ncant_servicios", ds_cant_servicios, {"sentido": "sentido", "mean_id": "mean_id", "cantidad_servicios": "cantidad_servicios"})
    _insertar("nvalidaciones_bus", ds_cant_validaciones, {"mean_id": "mean_id", "validaciones": "validaciones"})
    
    if ds_validaciones is not None and not ds_validaciones.empty:
        # Agregar columna rango a validaciones para que coincida con la tabla (HH:00)
        ds_val_copy = ds_validaciones.copy()
        ds_val_copy["rango"] = ds_val_copy["fechahoraevento"].dt.strftime("%H:00")
        map_val_datos = {
            "idsam": "idsam",
            "serialmediopago": "serialmediopago",
            "fechahoraevento": "fechahoraevento",
            "entidad": "entidad",
            "latitude": "latitude",
            "longitude": "longitude",
            "idrutaestacion": "idrutaestacion",
            "tipotransporte": "tipotransporte",
            "sentido": "sentido",
            "rango": "rango"
        }
        _insertar("nvalidaciones_bus_datos", ds_val_copy, map_val_datos)
        
    _insertar("nvalidaciones_hora", ds_valid_por_hora, {"sentido": "sentido", "rango": "rango", "cantidad_validaciones": "cantidad_validaciones"})
    print(f"  Datos grabados en BD (servicio={codigo_servicio}).")


if __name__ == "__main__":
    main()
