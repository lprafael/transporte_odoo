# config_db.py - Carga de configuración de servicios especiales desde la base de datos CID.
# Este script solo LEE datos; el catálogo es un sistema independiente que los carga.

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

# Carga .env si existe
try:
    from dotenv import load_dotenv
    _env_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"),
    ]
    for _env_f in _env_candidates:
        if os.path.exists(_env_f):
            load_dotenv(_env_f, override=False)
    load_dotenv()
except ImportError:
    pass


def get_fecha_base() -> str:
    """Fecha a procesar (YYYY-MM-DD). Por defecto: ayer."""
    base = os.environ.get("FECHA_BASE", "").strip()
    if base:
        return base
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def _parse_agency_ids(agency_ids: Optional[str]) -> list:
    """Convierte agency_ids (texto o CSV) en lista para SQL IN."""
    if not agency_ids or not str(agency_ids).strip():
        return []
    s = str(agency_ids).strip()
    # Permitir "0006", "GRUPO BENE S.A." o 0006, GRUPO BENE S.A.
    out = []
    for part in s.replace("'", "").split(","):
        part = part.strip()
        if part:
            out.append(part)
    return out


def obtener_feriado(engine, fecha_base: str) -> Optional[str]:
    """
    Verifica si una fecha (YYYY-MM-DD) es feriado consultando public.feriados en la BD CID.
    Retorna la descripción del feriado si existe, o None si no es feriado.
    """
    try:
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT descripcion FROM public.feriados WHERE fecha = :fecha LIMIT 1"),
                {"fecha": str(fecha_base)[:10]}
            ).fetchone()
            if res and res[0]:
                return str(res[0]).strip()
    except Exception as e:
        print(f"  [WARN] Error al consultar feriados en BD: {e}")
    return None


def determinar_tipo_dia(engine, fecha_base: str) -> Tuple[int, bool, Optional[str], str]:
    """
    Determina el tipo_dia operativo para fecha_base según el modelo de CID (control_metricas.tipo_dia):
    - 7: Domingo o Feriado (aplica la programación operativa del día domingo)
    - 6: Sábado
    - 5: Laboral (Lunes a Viernes)

    Retorna:
        (tipo_dia, es_feriado, feriado_desc, tipo_dia_desc)
    """
    if isinstance(fecha_base, datetime):
        dt = fecha_base
        f_str = dt.strftime("%Y-%m-%d")
    else:
        f_str = str(fecha_base)[:10]
        dt = datetime.strptime(f_str, "%Y-%m-%d")

    dow = dt.weekday()  # 0=Lunes, ..., 5=Sábado, 6=Domingo
    feriado_desc = obtener_feriado(engine, f_str)
    es_feriado = feriado_desc is not None

    # Regla: Si es feriado o domingo, se considera la programación del día domingo (tipo_dia=7)
    if es_feriado or dow == 6:
        tipo_dia = 7
        tipo_dia_desc = f"Feriado ({feriado_desc})" if es_feriado else "Domingo"
    elif dow == 5:
        tipo_dia = 6
        tipo_dia_desc = "Sábado"
    else:
        tipo_dia = 5
        tipo_dia_desc = "Laboral (L-V)"

    return tipo_dia, es_feriado, feriado_desc, tipo_dia_desc


def cargar_configuraciones(engine, fecha_base: str):
    """
    Carga desde la BD CID todos los servicios especiales que tengan:
    - parametro_monitoreo activo
    - al menos una adjudicación vigente en fecha_base
    - buses (mean_id, idsam) en esa adjudicación
    - rutas ida y vuelta asignadas (ruta_hex) vigentes
    - programación operativa vigente en fecha_base filtrada por tipo_dia (5=Laboral, 6=Sábado, 7=Dom/Feriado)

    Retorna lista de dicts, uno por servicio listo para procesar.
    """
    tipo_dia, es_feriado, feriado_desc, tipo_dia_desc = determinar_tipo_dia(engine, fecha_base)

    # Servicios con parámetro de monitoreo activo
    df_servicios = pd.read_sql(text("""
        SELECT DISTINCT s.id_servicio_especial, s.codigo, s.nombre
        FROM servicios_especiales.servicio_especial s
        INNER JOIN servicios_especiales.parametro_monitoreo p
            ON p.id_servicio_especial = s.id_servicio_especial AND p.activo = true
        WHERE s.activo = true
        ORDER BY s.codigo
    """), engine)

    if df_servicios.empty:
        return []

    configs = []
    for _, row in df_servicios.iterrows():
        id_servicio = row["id_servicio_especial"]
        codigo = row["codigo"]
        nombre = row["nombre"]

        # Parámetro de monitoreo (el primero activo)
        df_param = pd.read_sql(text("""
            SELECT id_parametro, radio_geocerca_m, radio_itinerario_m, rango_cumplimiento_pct,
                   franja_hora_inicio, franja_hora_fin,
                   tolerancia_antes_min, tolerancia_despues_min,
                   emisor_id, pasa_al_dia_siguiente,
                   km_computo_ida, km_computo_vuelta
            FROM servicios_especiales.parametro_monitoreo
            WHERE id_servicio_especial = :id AND activo = true
            LIMIT 1
        """), engine, params={"id": id_servicio})
        if df_param.empty:
            continue
        param = df_param.iloc[0]

        # Adjudicación vigente en fecha_base (primera que cumpla)
        df_adj = pd.read_sql(text("""
            SELECT id_adjudicacion, id_eot, link_dashboard, fecha_inicio_servicio
            FROM servicios_especiales.adjudicacion_servicio
            WHERE id_servicio_especial = :id
              AND fecha_inicio_servicio <= :fecha
              AND (fecha_fin_servicio IS NULL OR fecha_fin_servicio >= :fecha)
            ORDER BY fecha_inicio_servicio DESC
            LIMIT 1
        """), engine, params={"id": id_servicio, "fecha": fecha_base})
        if df_adj.empty:
            continue
        id_adjudicacion = int(df_adj.iloc[0]["id_adjudicacion"])
        id_eot = int(df_adj.iloc[0]["id_eot"])
        link_dashboard = str(df_adj.iloc[0]["link_dashboard"]).strip() if pd.notna(df_adj.iloc[0]["link_dashboard"]) else None
        fecha_inicio_adj_raw = df_adj.iloc[0]["fecha_inicio_servicio"]
        fecha_inicio_adjudicacion = str(fecha_inicio_adj_raw)[:10] if pd.notna(fecha_inicio_adj_raw) else None
        
        # Email y agency_id de la EOT operadora (según la concesión vigente en fecha_base)
        df_eot = pd.read_sql(text("SELECT e_mail, id_eot_vmt_hex FROM eots WHERE eot_id = :eid"), engine, params={"eid": id_eot})
        eot_email = None
        agency_id_from_eot = None
        if not df_eot.empty:
            val = df_eot.iloc[0].get("e_mail")
            if val is not None and str(val).strip():
                eot_email = str(val).strip()
            hex_val = df_eot.iloc[0].get("id_eot_vmt_hex")
            if hex_val is not None and str(hex_val).strip():
                agency_id_from_eot = str(hex_val).strip()

        # Buses de esa adjudicación
        df_buses = pd.read_sql(text("""
            SELECT numero_orden, idsam, mean_id
            FROM servicios_especiales.bus_adjudicacion
            WHERE id_adjudicacion = :id
            ORDER BY numero_orden
        """), engine, params={"id": id_adjudicacion})
        if df_buses.empty:
            continue
        
        idSam_mapping = {}
        mean_ids = []
        for _, b in df_buses.iterrows():
            mid = b["mean_id"]
            if pd.isna(mid) or str(mid).strip() == "":
                mid = str(b["idsam"])  # fallback
            else:
                mid = str(mid).strip().upper()
            mean_ids.append(mid)
            idSam_mapping[mid] = str(b["idsam"]).strip()

        # Rutas ida y vuelta vigentes (pueden ser múltiples)
        df_rutas = pd.read_sql(text("""
            SELECT ruta_hex, sentido
            FROM servicios_especiales.ruta_servicio_especial
            WHERE id_servicio_especial = :id
              AND (vigente_desde IS NULL OR vigente_desde <= :fecha)
              AND (vigente_hasta IS NULL OR vigente_hasta >= :fecha)
              AND sentido IN ('ida', 'vuelta')
        """), engine, params={"id": id_servicio, "fecha": fecha_base})
        
        ruta_hex_ida = df_rutas[df_rutas["sentido"] == "ida"]["ruta_hex"].tolist()
        ruta_hex_vuelta = df_rutas[df_rutas["sentido"] == "vuelta"]["ruta_hex"].tolist()
        
        if not ruta_hex_ida or not ruta_hex_vuelta:
            continue

        # Programación vigente filtrada por tipo de día (Laboral=5, Sábado=6, Domingo/Feriado=7)
        df_prog = pd.read_sql(text("""
            SELECT numero_servicio, sentido, horario_salida, tipo_dia
            FROM servicios_especiales.programacion_operativa
            WHERE id_servicio_especial = :id
              AND tipo_dia = :tipo_dia
              AND fecha_inicio_vigencia <= :fecha
              AND (fecha_fin_vigencia IS NULL OR fecha_fin_vigencia >= :fecha)
            ORDER BY sentido, numero_servicio
        """), engine, params={"id": id_servicio, "fecha": fecha_base, "tipo_dia": tipo_dia})
        
        programacion_list = []
        if not df_prog.empty:
            for _, p in df_prog.iterrows():
                h = p["horario_salida"]
                if hasattr(h, "strftime"):
                    h_str = h.strftime("%H:%M:%S")
                else:
                    h_str = str(h)
                programacion_list.append({
                    "tipo": int(p["tipo_dia"]) if pd.notna(p["tipo_dia"]) else 1,
                    "nro_servicio": int(p["numero_servicio"]),
                    "sentido": str(p["sentido"]).strip().lower(),
                    "horario_salida": h_str,
                })

        franja_inicio = str(param["franja_hora_inicio"]) if pd.notna(param["franja_hora_inicio"]) else "21:30:00"
        franja_fin = str(param["franja_hora_fin"]) if pd.notna(param["franja_hora_fin"]) else "07:30:00"
        
        f_ini_clean = franja_inicio.replace(".", ":")
        f_fin_clean = franja_fin.replace(".", ":")
        
        h_ini = int(f_ini_clean.split(":")[0])
        h_fin = int(f_fin_clean.split(":")[0])
        
        fecha_inicio = f"{fecha_base} {f_ini_clean}"
        
        if bool(param.get("pasa_al_dia_siguiente")) or h_fin < h_ini:
            fecha_fin_dt = datetime.strptime(fecha_base, "%Y-%m-%d") + timedelta(days=1)
        else:
            fecha_fin_dt = datetime.strptime(fecha_base, "%Y-%m-%d")
        
        parts = f_fin_clean.split(":")
        h, m, s = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, int(parts[2]) if len(parts) > 2 else 0
        fecha_fin = fecha_fin_dt.replace(hour=h, minute=m, second=s).strftime("%Y-%m-%d %H:%M:%S")

        # agency_ids: siempre se deriva de la EOT adjudicada en la fecha de cálculo.
        # La fuente es eots.id_eot_vmt_hex, que corresponde a agency_id en app_monitoreo_mensajeoperativo.
        agency_list = [agency_id_from_eot] if agency_id_from_eot else []
        emisor_id = int(param["emisor_id"]) if pd.notna(param["emisor_id"]) else None

        configs.append({
            "codigo": codigo,
            "nombre": nombre,
            "id_servicio_especial": id_servicio,
            "id_eot": id_eot,
            "eot_email": eot_email,
            "radio_geocerca_m": int(param["radio_geocerca_m"]),
            "radio_itinerario_m": int(param["radio_itinerario_m"]),
            "rango_cumplimiento_pct": int(param["rango_cumplimiento_pct"]),
            "franja_hora_inicio": franja_inicio,
            "franja_hora_fin": franja_fin,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "tolerancia_antes_min": int(param["tolerancia_antes_min"]),
            "tolerancia_despues_min": int(param["tolerancia_despues_min"]),
            "emisor_id": emisor_id,
            "km_computo_ida": float(param["km_computo_ida"]) if pd.notna(param.get("km_computo_ida")) and float(param.get("km_computo_ida", 0)) > 0 else None,
            "km_computo_vuelta": float(param["km_computo_vuelta"]) if pd.notna(param.get("km_computo_vuelta")) and float(param.get("km_computo_vuelta", 0)) > 0 else None,
            "agency_ids": agency_list,
            "idSam_mapping": idSam_mapping,
            "mean_ids": mean_ids,
            "ruta_hex_ida": ruta_hex_ida,
            "ruta_hex_vuelta": ruta_hex_vuelta,
            "programacion": programacion_list,
            "pasa_al_dia_siguiente": bool(param.get("pasa_al_dia_siguiente")),
            "link_dashboard": link_dashboard,
            "fecha_inicio_adjudicacion": fecha_inicio_adjudicacion,
            "tipo_dia": tipo_dia,
            "tipo_dia_desc": tipo_dia_desc,
            "es_feriado": es_feriado,
            "feriado_desc": feriado_desc,
        })

    return configs


def diagnosticar_carga(engine, fecha_base: str) -> dict:
    """
    Ejecuta los mismos pasos que cargar_configuraciones pero devuelve conteos y
    el motivo por el que cada servicio no llegó a config (para depuración).
    """
    tipo_dia, es_feriado, feriado_desc, tipo_dia_desc = determinar_tipo_dia(engine, fecha_base)
    detalle_servicios = []

    df_servicios = pd.read_sql(text("""
        SELECT DISTINCT s.id_servicio_especial, s.codigo, s.nombre
        FROM servicios_especiales.servicio_especial s
        INNER JOIN servicios_especiales.parametro_monitoreo p
            ON p.id_servicio_especial = s.id_servicio_especial AND p.activo = true
        WHERE s.activo = true
        ORDER BY s.codigo
    """), engine)

    if df_servicios.empty:
        return {
            "fecha_base": fecha_base,
            "tipo_dia": tipo_dia,
            "tipo_dia_desc": tipo_dia_desc,
            "es_feriado": es_feriado,
            "feriado_desc": feriado_desc,
            "total_con_parametro": 0,
            "con_adjudicacion": 0,
            "con_buses": 0,
            "con_rutas": 0,
            "con_programacion": 0,
            "configs_finales": 0,
            "detalle": [],
            "error_conexion": False,
        }

    total = len(df_servicios)
    con_adj = con_buses = con_rutas = con_prog = 0

    for _, row in df_servicios.iterrows():
        id_servicio = row["id_servicio_especial"]
        codigo = row["codigo"]
        nombre = row["nombre"]
        fallo = None

        df_param = pd.read_sql(text("""
            SELECT id_parametro, pasa_al_dia_siguiente FROM servicios_especiales.parametro_monitoreo
            WHERE id_servicio_especial = :id AND activo = true LIMIT 1
        """), engine, params={"id": id_servicio})
        if df_param.empty:
            fallo = "parametro_monitoreo"
            detalle_servicios.append({"codigo": codigo, "nombre": nombre, "fallo_en": fallo})
            continue
        
        pasa_dia = bool(df_param.iloc[0]["pasa_al_dia_siguiente"])

        df_adj = pd.read_sql(text("""
            SELECT id_adjudicacion, id_eot
            FROM servicios_especiales.adjudicacion_servicio
            WHERE id_servicio_especial = :id
              AND fecha_inicio_servicio <= :fecha
              AND (fecha_fin_servicio IS NULL OR fecha_fin_servicio >= :fecha)
            ORDER BY fecha_inicio_servicio DESC LIMIT 1
        """), engine, params={"id": id_servicio, "fecha": fecha_base})
        if df_adj.empty:
            fallo = "adjudicacion_vigente"
            detalle_servicios.append({"codigo": codigo, "nombre": nombre, "fallo_en": fallo})
            continue
        con_adj += 1
        id_adjudicacion = int(df_adj.iloc[0]["id_adjudicacion"])

        df_buses = pd.read_sql(text("""
            SELECT numero_orden, idsam, mean_id
            FROM servicios_especiales.bus_adjudicacion
            WHERE id_adjudicacion = :id ORDER BY numero_orden
        """), engine, params={"id": id_adjudicacion})
        if df_buses.empty:
            fallo = "buses_adjudicacion"
            detalle_servicios.append({"codigo": codigo, "nombre": nombre, "fallo_en": fallo})
            continue
        con_buses += 1

        df_rutas = pd.read_sql(text("""
            SELECT ruta_hex, sentido
            FROM servicios_especiales.ruta_servicio_especial
            WHERE id_servicio_especial = :id
              AND (vigente_desde IS NULL OR vigente_desde <= :fecha)
              AND (vigente_hasta IS NULL OR vigente_hasta >= :fecha)
              AND sentido IN ('ida', 'vuelta')
        """), engine, params={"id": id_servicio, "fecha": fecha_base})
        
        ruta_hex_ida = df_rutas[df_rutas["sentido"] == "ida"]["ruta_hex"].tolist()
        ruta_hex_vuelta = df_rutas[df_rutas["sentido"] == "vuelta"]["ruta_hex"].tolist()
        
        if not ruta_hex_ida or not ruta_hex_vuelta:
            fallo = "rutas_ida_vuelta"
            detalle_servicios.append({"codigo": codigo, "nombre": nombre, "fallo_en": fallo})
            continue
        con_rutas += 1

        df_prog = pd.read_sql(text("""
            SELECT numero_servicio, sentido, horario_salida, tipo_dia
            FROM servicios_especiales.programacion_operativa
            WHERE id_servicio_especial = :id
              AND tipo_dia = :tipo_dia
              AND fecha_inicio_vigencia <= :fecha
              AND (fecha_fin_vigencia IS NULL OR fecha_fin_vigencia >= :fecha)
            ORDER BY sentido, numero_servicio
        """), engine, params={"id": id_servicio, "fecha": fecha_base, "tipo_dia": tipo_dia})
        
        if not df_prog.empty:
            con_prog += 1
            detalle_servicios.append({"codigo": codigo, "nombre": nombre, "fallo_en": None, "pasa_al_dia_siguiente": pasa_dia})
        else:
            detalle_servicios.append({"codigo": codigo, "nombre": nombre, "fallo_en": None, "nota": "Sin programación", "pasa_al_dia_siguiente": pasa_dia})

    configs_finales = sum(1 for d in detalle_servicios if d.get("fallo_en") is None)
    return {
        "fecha_base": fecha_base,
        "tipo_dia": tipo_dia,
        "tipo_dia_desc": tipo_dia_desc,
        "es_feriado": es_feriado,
        "feriado_desc": feriado_desc,
        "total_con_parametro": total,
        "con_adjudicacion": con_adj,
        "con_buses": con_buses,
        "con_rutas": con_rutas,
        "con_programacion": con_prog,
        "configs_finales": configs_finales,
        "detalle": detalle_servicios,
        "error_conexion": False,
    }


def obtener_geometrias_rutas(engine, ruta_hex_ida, ruta_hex_vuelta, fecha_base: str):
    """
    Obtiene las geometrías de ida y vuelta desde la tabla geometria.historico_itinerario
    filtrando por la vigencia en la fecha_base. Soporta múltiples rutas e itinerarios vigentes.

    Además carga las geocercas de tipo 5 (Punto de retorno al 80%) asociadas a cada itinerario.

    Retorna:
        G3        : GeoDataFrame con geometría de rutas de ida
        G4        : GeoDataFrame con geometría de rutas de vuelta
        G5_ida    : GeoDataFrame con geocercas tipo 5 de los itinerarios de ida (puede ser vacío)
        G5_vuelta : GeoDataFrame con geocercas tipo 5 de los itinerarios de vuelta (puede ser vacío)
    """
    import geopandas as gpd

    # Asegurar que sean listas
    if isinstance(ruta_hex_ida, str): ruta_hex_ida = [ruta_hex_ida]
    if isinstance(ruta_hex_vuelta, str): ruta_hex_vuelta = [ruta_hex_vuelta]

    with engine.connect() as conn:
        all_hex = list(set(ruta_hex_ida + ruta_hex_vuelta))
        placeholders = ", ".join(f"'{h}'" for h in all_hex)

        sql = f"""
            SELECT geom, ruta_hex, id_itinerario
            FROM geometria.historico_itinerario
            WHERE ruta_hex IN ({placeholders})
              AND fecha_inicio_vigencia <= :fecha
              AND (fecha_fin_vigencia IS NULL OR fecha_fin_vigencia >= :fecha)
        """

        try:
            rutas = gpd.read_postgis(text(sql), conn, geom_col="geom", params={"fecha": fecha_base})
        except Exception:
            sql_alt = sql.replace("geometria.historico_itinerario", "historico_itinerario")
            rutas = gpd.read_postgis(text(sql_alt), conn, geom_col="geom", params={"fecha": fecha_base})

        if rutas.empty:
            raise RuntimeError(f"No se encontró itinerario vigente para {ruta_hex_ida}/{ruta_hex_vuelta} en la fecha {fecha_base}")

        G3 = rutas[rutas["ruta_hex"].isin(ruta_hex_ida)].copy()
        G4 = rutas[rutas["ruta_hex"].isin(ruta_hex_vuelta)].copy()

        if G3.empty or G4.empty:
            raise RuntimeError(f"Falta una de las geometrías (Ida: {len(G3)}, Vta: {len(G4)}) para la fecha {fecha_base}")

        if G3.crs is None:
            G3.set_crs("EPSG:4326", inplace=True)
        if G4.crs is None:
            G4.set_crs("EPSG:4326", inplace=True)

        # --- Geocercas tipo 5: Punto de retorno al 80% ---
        ids_ida = [int(i) for i in G3["id_itinerario"].dropna().unique()]
        ids_vuelta = [int(i) for i in G4["id_itinerario"].dropna().unique()]
        ids_all = list(set(ids_ida + ids_vuelta))

        G5_ida = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        G5_vuelta = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        if ids_all:
            ids_ph = ", ".join(str(i) for i in ids_all)
            sql_g5 = f"""
                SELECT g.id_geocerca, g.id_itinerario, g.geom
                FROM geometria.geocercas g
                WHERE g.id_itinerario IN ({ids_ph})
                  AND g.id_tipo = 5
            """
            try:
                gdf_g5 = gpd.read_postgis(text(sql_g5), conn, geom_col="geom")
                if gdf_g5.crs is None:
                    gdf_g5.set_crs("EPSG:4326", inplace=True)
                if not gdf_g5.empty:
                    G5_ida = gdf_g5[gdf_g5["id_itinerario"].isin(ids_ida)].copy()
                    G5_vuelta = gdf_g5[gdf_g5["id_itinerario"].isin(ids_vuelta)].copy()
            except Exception as e:
                print(f"  [WARN] No se pudieron cargar geocercas tipo 5: {e}")

    return G3, G4, G5_ida, G5_vuelta
