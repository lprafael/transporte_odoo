# logica_monitoreo.py - OPTIMIZADO CON CONTROL CRUZADO (GPS + BILLETAJE)
# Lógica optimizada para el conteo de servicios y validaciones.

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import linemerge
import shapely

def first_point_from_geometry(geom):
    if geom.geom_type == "Point":
        return geom
    elif geom.geom_type == "LineString":
        return Point(list(geom.coords)[0])
    elif geom.geom_type == "MultiLineString":
        merged = linemerge(geom)
        if merged.geom_type == "LineString":
            return Point(list(merged.coords)[0])
        return Point(list(merged.geoms[0].coords)[0])
    b = geom.boundary
    if b.geom_type == "MultiPoint":
        return list(b.geoms)[0]
    return b

def preparar_gps_y_geocercas(df_gps, G3, G4, radio_geocerca_m, G5_ida=None, G5_vuelta=None, all_validaciones=None, idSam_mapping=None):
    """
    Optimizado: Integra control cruzado de GPS (AVL) y Billetaje Electrónico.
    Si se proporciona all_validaciones e idSam_mapping, suplementa el dataframe de GPS
    con las coordenadas de validación de los validadores a bordo, asegurando que ante
    cortes o desconexiones del módem AVL, los servicios reales con pasajeros no sean excluidos.
    """
    df_gps = df_gps.copy() if df_gps is not None else pd.DataFrame()

    # --- CONTROL CRUZADO: Suplementar GPS con coordenadas de Billetaje si existen ---
    if all_validaciones is not None and not all_validaciones.empty and idSam_mapping:
        try:
            # Buscar columnas latitude y longitude en validaciones
            cols_val = [c.lower() for c in all_validaciones.columns]
            all_v_norm = all_validaciones.copy()
            all_v_norm.columns = cols_val

            if "latitude" in cols_val and "longitude" in cols_val and "fechahoraevento" in cols_val and "idsam" in cols_val:
                mask_val_gps = (
                    all_v_norm["latitude"].notna() &
                    all_v_norm["longitude"].notna() &
                    (all_v_norm["latitude"] != 0) &
                    (all_v_norm["longitude"] != 0)
                )
                if mask_val_gps.any():
                    val_pts = all_v_norm[mask_val_gps].copy()
                    sam_to_bus = {str(v).strip().upper(): str(k).strip().upper() for k, v in idSam_mapping.items() if v}
                    val_pts["mean_id"] = val_pts["idsam"].astype(str).str.strip().str.upper().map(sam_to_bus)
                    val_pts = val_pts[val_pts["mean_id"].notna()]
                    
                    if not val_pts.empty:
                        v_dt = pd.to_datetime(val_pts["fechahoraevento"])
                        if v_dt.dt.tz is not None:
                            val_pts["fecha_hora"] = v_dt.dt.tz_convert("America/Asuncion").dt.tz_localize(None)
                        else:
                            val_pts["fecha_hora"] = v_dt
                        
                        gps_val = val_pts[["mean_id", "fecha_hora", "latitude", "longitude"]].copy()

                        if not df_gps.empty:
                            df_gps["mean_id"] = df_gps["mean_id"].astype(str).str.strip().str.upper()
                            g_dt = pd.to_datetime(df_gps["fecha_hora"])
                            if g_dt.dt.tz is not None:
                                df_gps["fecha_hora"] = g_dt.dt.tz_convert("America/Asuncion").dt.tz_localize(None)
                            else:
                                df_gps["fecha_hora"] = g_dt
                            df_gps = pd.concat([df_gps, gps_val], ignore_index=True)
                        else:
                            df_gps = gps_val

                        df_gps = df_gps.drop_duplicates(subset=["mean_id", "fecha_hora"]).sort_values(["mean_id", "fecha_hora"]).reset_index(drop=True)
        except Exception as e:
            print(f"  [WARN] Error suplementando GPS con Billetaje: {e}")

    if df_gps.empty:
        return gpd.GeoDataFrame(), pd.DataFrame()

    # Asegurar tipo datetime y normalizar zona horaria Asunción
    if not pd.api.types.is_datetime64_any_dtype(df_gps["fecha_hora"]):
        df_gps["fecha_hora"] = pd.to_datetime(df_gps["fecha_hora"], utc=True)
    if df_gps["fecha_hora"].dt.tz is not None:
        df_gps["fecha_hora"] = df_gps["fecha_hora"].dt.tz_convert("America/Asuncion").dt.tz_localize(None)

    # Crear GeoDataFrame
    gdf_gps = gpd.GeoDataFrame(
        df_gps,
        geometry=gpd.points_from_xy(df_gps.longitude, df_gps.latitude),
        crs="EPSG:4326"
    ).to_crs("EPSG:32721")

    # Puntos de inicio/fin de las rutas
    p1_list = [first_point_from_geometry(g) for g in G3.geometry]
    p2_list = [first_point_from_geometry(g) for g in G4.geometry]

    G1_proj = gpd.GeoDataFrame(geometry=p1_list, crs="EPSG:4326").to_crs("EPSG:32721")
    G2_proj = gpd.GeoDataFrame(geometry=p2_list, crs="EPSG:4326").to_crs("EPSG:32721")

    u_g1 = G1_proj.union_all()
    u_g2 = G2_proj.union_all()

    # Distancias a cabeceras vectorizadas
    gdf_gps["dist_G1"] = gdf_gps.geometry.distance(u_g1)
    gdf_gps["dist_G2"] = gdf_gps.geometry.distance(u_g2)

    gdf_gps["ubicacion"] = "Fuera"
    gdf_gps.loc[gdf_gps["dist_G1"] <= radio_geocerca_m, "ubicacion"] = "G1"
    gdf_gps.loc[gdf_gps["dist_G2"] <= radio_geocerca_m, "ubicacion"] = "G2"

    # --- Flags de punto de retorno (geocerca tipo 5) ---
    gdf_gps["en_retorno_ida"] = False
    gdf_gps["en_retorno_vuelta"] = False

    if G5_ida is not None and not G5_ida.empty:
        try:
            retorno_ida_union = G5_ida.to_crs("EPSG:32721").geometry.union_all()
            shapely.prepare(retorno_ida_union)
            gdf_gps["en_retorno_ida"] = gdf_gps.geometry.intersects(retorno_ida_union)
        except Exception as e:
            print(f"  [WARN] Error calculando retorno ida: {e}")

    if G5_vuelta is not None and not G5_vuelta.empty:
        try:
            retorno_vta_union = G5_vuelta.to_crs("EPSG:32721").geometry.union_all()
            shapely.prepare(retorno_vta_union)
            gdf_gps["en_retorno_vuelta"] = gdf_gps.geometry.intersects(retorno_vta_union)
        except Exception as e:
            print(f"  [WARN] Error calculando retorno vuelta: {e}")

    ds_inicio_fin = gdf_gps[gdf_gps["ubicacion"] != "Fuera"].copy()
    ds_inicio_fin = ds_inicio_fin.sort_values(by=["mean_id", "fecha_hora"], ignore_index=True)

    return gdf_gps, ds_inicio_fin

def calcular_servicios_y_validaciones(
    gdf_gps_proj,
    ds_inicio_fin,
    idSam_mapping,
    rango_cumplimiento_pct,
    radio_itinerario_m,
    G3, G4,
    all_validaciones,
):
    servicios = []
    if ds_inicio_fin.empty:
        return pd.DataFrame(), pd.DataFrame()

    it_ida_buffer = G3.to_crs("EPSG:32721").geometry.buffer(radio_itinerario_m).union_all()
    it_vta_buffer = G4.to_crs("EPSG:32721").geometry.buffer(radio_itinerario_m).union_all()
    shapely.prepare(it_ida_buffer)
    shapely.prepare(it_vta_buffer)

    gdf_gps_proj["dentro_itinerario_ida"] = gdf_gps_proj.geometry.intersects(it_ida_buffer)
    gdf_gps_proj["dentro_itinerario_vuelta"] = gdf_gps_proj.geometry.intersects(it_vta_buffer)

    validaciones_dfs = []

    # Normalizar validaciones
    if not all_validaciones.empty:
        all_validaciones.columns = [c.lower() for c in all_validaciones.columns]
        
        # Evaluar flag de transbordo
        if "entidad" in all_validaciones.columns and "númerotransbordos" in all_validaciones.columns and "montoevento" in all_validaciones.columns:
            entidad = all_validaciones["entidad"].astype(str).str.strip().str.zfill(4)
            num_trans = pd.to_numeric(all_validaciones["númerotransbordos"], errors='coerce').fillna(-1).astype(int)
            monto = pd.to_numeric(all_validaciones["montoevento"], errors='coerce').fillna(-1)
            
            is_t1 = (entidad == "0002") & (num_trans.isin([1, 5, 6, 9, 10])) & (monto == 0)
            is_t2 = (entidad == "0003") & (num_trans.isin([1, 2]))
            all_validaciones["is_transbordo"] = is_t1 | is_t2
        else:
            all_validaciones["is_transbordo"] = False
            
        prod = all_validaciones["idproducto"].astype(str).str.strip().str.lower() if "idproducto" in all_validaciones.columns else pd.Series("", index=all_validaciones.index)
        monto = pd.to_numeric(all_validaciones["montoevento"], errors='coerce').fillna(-1) if "montoevento" in all_validaciones.columns else pd.Series(-1, index=all_validaciones.index)

        # Perfil Discapacidad: producto 4553 y monto = 0
        all_validaciones["is_discapacidad"] = (prod == "4553") & (monto == 0)

        # Perfil Estudiante: producto 4553 y monto > 0 (tarifa 50%)
        is_est_prod = (prod == "4553") & (monto > 0)
        if "is_estudiante" in all_validaciones.columns:
            all_validaciones["is_estudiante"] = all_validaciones["is_estudiante"] | is_est_prod
        else:
            all_validaciones["is_estudiante"] = is_est_prod

        # Perfil General: producto 4d4f
        all_validaciones["is_general"] = (prod == "4d4f")
        all_validaciones["idsam_upper"] = all_validaciones["idsam"].astype(str).str.strip().str.upper()

    # Pre-agrupar GPS por bus para rendimiento óptimo
    gps_por_bus = {str(b).strip().upper(): group.sort_values("fecha_hora") for b, group in gdf_gps_proj.groupby("mean_id")}

    for bus, df_bus in ds_inicio_fin.groupby("mean_id"):
        df_bus = df_bus.sort_values("fecha_hora", ignore_index=True)
        bus_str = str(bus).strip().upper()
        idSam = idSam_mapping.get(str(bus)) or idSam_mapping.get(str(bus).upper()) or idSam_mapping.get(str(bus).lower())
        
        # Filtro de validaciones en memoria
        if not all_validaciones.empty and "fechahoraevento" in all_validaciones.columns and "idsam_upper" in all_validaciones.columns:
            idSam_str = str(idSam).strip().upper() if idSam else ""
            bus_validaciones = all_validaciones[all_validaciones["idsam_upper"] == idSam_str] if idSam_str else pd.DataFrame()
        else:
            bus_validaciones = pd.DataFrame(columns=["fechahoraevento", "idsam"])

        df_gps_bus = gps_por_bus.get(bus_str, pd.DataFrame())
        if df_gps_bus.empty:
            continue

        primera_hora = df_bus.iloc[0].fecha_hora
        inicio_cabecera = (primera_hora.tz_localize(None) if primera_hora.tzinfo else primera_hora) - timedelta(minutes=5)
        asignadas_bus = set()

        it_tuples = list(df_bus.itertuples())
        for i in range(len(it_tuples) - 1):
            prev = it_tuples[i]
            curr = it_tuples[i + 1]

            sentido = None
            if prev.ubicacion == "G1" and curr.ubicacion == "G2":
                sentido = "ida"
            elif prev.ubicacion == "G2" and curr.ubicacion == "G1":
                sentido = "vuelta"

            if not sentido:
                # OPTIMIZACIÓN: Si están en la misma geocerca y pasaron menos de 3 min, el bus está detenido en terminal
                sec_diff = (curr.fecha_hora - prev.fecha_hora).total_seconds()
                if sec_diff < 180 and prev.ubicacion == curr.ubicacion:
                    continue

                fuera_entre = df_gps_bus[
                    (df_gps_bus["fecha_hora"] > prev.fecha_hora) &
                    (df_gps_bus["fecha_hora"] < curr.fecha_hora) &
                    (df_gps_bus["ubicacion"] == "Fuera")
                ]
                if not fuera_entre.empty:
                    curr_time = curr.fecha_hora
                    inicio_cabecera = curr_time.tz_localize(None) if curr_time.tzinfo else curr_time

                # --- Detección de retorno al 80% (Punto de Retorno - Rescate de Viaje) ---
                sentido_inferido = "ida" if prev.ubicacion == "G1" else ("vuelta" if prev.ubicacion == "G2" else None)
                col_retorno = "en_retorno_ida" if sentido_inferido == "ida" else "en_retorno_vuelta"

                if sentido_inferido and col_retorno in df_gps_bus.columns:
                    gps_en_retorno = df_gps_bus[
                        (df_gps_bus["fecha_hora"] > prev.fecha_hora) &
                        (df_gps_bus["fecha_hora"] < curr.fecha_hora) &
                        (df_gps_bus[col_retorno] == True)
                    ]
                    if not gps_en_retorno.empty:
                        df_tramo_inc = df_gps_bus[
                            (df_gps_bus["fecha_hora"] >= prev.fecha_hora) &
                            (df_gps_bus["fecha_hora"] <= curr.fecha_hora)
                        ]
                        total_ev_inc = len(df_tramo_inc)
                        col_ref_inc = "dentro_itinerario_ida" if sentido_inferido == "ida" else "dentro_itinerario_vuelta"
                        ev_itin_inc = int(df_tramo_inc[col_ref_inc].sum()) if col_ref_inc in df_tramo_inc.columns else 0
                        pct_inc = round((ev_itin_inc / total_ev_inc) * 100, 2) if total_ev_inc > 0 else 0

                        inc_inicio = prev.fecha_hora
                        inc_fin = curr.fecha_hora
                        inc_inicio_cabecera = inicio_cabecera.replace(tzinfo=None) if hasattr(inicio_cabecera, "tzinfo") else inicio_cabecera
                        fin_v_inc = inc_fin.tz_localize(None) if inc_fin.tzinfo else inc_fin

                        # Asignar validaciones del viaje de retorno
                        val_retorno = bus_validaciones[
                            (bus_validaciones["fechahoraevento"] >= inc_inicio_cabecera) &
                            (bus_validaciones["fechahoraevento"] <= fin_v_inc)
                        ].copy()
                        if not val_retorno.empty and "serialmediopago" in val_retorno.columns:
                            keys = val_retorno["serialmediopago"].astype(str) + "_" + val_retorno["fechahoraevento"].astype(str)
                            mask_dup = keys.isin(asignadas_bus)
                            val_retorno = val_retorno[~mask_dup]
                            asignadas_bus.update(keys[~mask_dup])

                        val_count = len(val_retorno)
                        mask_t = val_retorno["is_transbordo"] == True if "is_transbordo" in val_retorno.columns else pd.Series(False, index=val_retorno.index)
                        mask_disc = val_retorno["is_discapacidad"] == True if "is_discapacidad" in val_retorno.columns else pd.Series(False, index=val_retorno.index)
                        mask_est = val_retorno["is_estudiante"] == True if "is_estudiante" in val_retorno.columns else pd.Series(False, index=val_retorno.index)
                        
                        val_transbordo = len(val_retorno[mask_t])
                        val_discapacidad = len(val_retorno[~mask_t & mask_disc])
                        val_estudiante = len(val_retorno[~mask_t & ~mask_disc & mask_est])
                        val_general = len(val_retorno[~mask_t & ~mask_disc & ~mask_est])

                        observacion_inc = "Válido (Retorno)" if pct_inc >= rango_cumplimiento_pct else "No corresponde"

                        if observacion_inc.startswith("Válido") and not val_retorno.empty:
                            val_retorno["sentido"] = sentido_inferido
                            validaciones_dfs.append(val_retorno)

                        servicios.append({
                            "sentido": sentido_inferido,
                            "mean_id": bus,
                            "idsam": idSam,
                            "inicio_cabecera": inc_inicio_cabecera,
                            "inicio_serv": inc_inicio,
                            "fin_serv": inc_fin,
                            "duración(min)": int((inc_fin - inc_inicio).total_seconds() / 60),
                            "total_eventos": total_ev_inc,
                            "eventos_itinerario": ev_itin_inc,
                            "validaciones": val_count,
                            "validaciones_general": val_general,
                            "validaciones_transbordo": val_transbordo,
                            "validaciones_estudiante": val_estudiante,
                            "validaciones_discapacidad": val_discapacidad,
                            "porcentaje_cumplimiento": pct_inc,
                            "observación": observacion_inc,
                        })
                        inicio_cabecera = fin_v_inc

                continue

            inicio_serv, fin_serv = prev.fecha_hora, curr.fecha_hora
            duracion_min = int((fin_serv - inicio_serv).total_seconds() / 60)
            
            # Filtro GPS del tramo
            df_tramo = df_gps_bus[
                (df_gps_bus["fecha_hora"] >= inicio_serv) & 
                (df_gps_bus["fecha_hora"] <= fin_serv)
            ]
            
            total_eventos = len(df_tramo)
            col_ref = "dentro_itinerario_ida" if sentido == "ida" else "dentro_itinerario_vuelta"
            eventos_itinerario = df_tramo[col_ref].sum() if total_eventos > 0 else 0
            porcentaje_cumplimiento = round((eventos_itinerario / total_eventos) * 100, 2) if total_eventos > 0 else 0
            
            fin_v = (fin_serv.tz_localize(None) if fin_serv.tzinfo else fin_serv)
            
            val_servicio = bus_validaciones[
                (bus_validaciones["fechahoraevento"] >= inicio_cabecera) & 
                (bus_validaciones["fechahoraevento"] <= fin_v)
            ].copy()
            
            # Blindaje 100% contra duplicidades
            if not val_servicio.empty and "serialmediopago" in val_servicio.columns:
                keys = val_servicio["serialmediopago"].astype(str) + "_" + val_servicio["fechahoraevento"].astype(str)
                mask_dup = keys.isin(asignadas_bus)
                if mask_dup.any():
                    val_servicio = val_servicio[~mask_dup]

            val_count = len(val_servicio)

            # Validación estricta según rango_cumplimiento_pct configurado en parametro_monitoreo
            if porcentaje_cumplimiento >= rango_cumplimiento_pct:
                observacion = "Válido"
            else:
                observacion = "No corresponde"

            if observacion.startswith("Válido") and not val_servicio.empty and "serialmediopago" in val_servicio.columns:
                keys = val_servicio["serialmediopago"].astype(str) + "_" + val_servicio["fechahoraevento"].astype(str)
                asignadas_bus.update(keys)

            mask_t = val_servicio["is_transbordo"] == True if "is_transbordo" in val_servicio.columns else pd.Series(False, index=val_servicio.index)
            mask_disc = val_servicio["is_discapacidad"] == True if "is_discapacidad" in val_servicio.columns else pd.Series(False, index=val_servicio.index)
            mask_est = val_servicio["is_estudiante"] == True if "is_estudiante" in val_servicio.columns else pd.Series(False, index=val_servicio.index)
            
            val_transbordo = len(val_servicio[mask_t])
            val_discapacidad = len(val_servicio[~mask_t & mask_disc])
            val_estudiante = len(val_servicio[~mask_t & ~mask_disc & mask_est])
            val_general = len(val_servicio[~mask_t & ~mask_disc & ~mask_est])
                
            if observacion.startswith("Válido") and not val_servicio.empty:
                val_servicio["sentido"] = sentido
                validaciones_dfs.append(val_servicio)

            servicios.append({
                "sentido": sentido, "mean_id": bus, "idsam": idSam,
                "inicio_cabecera": inicio_cabecera.replace(tzinfo=None) if hasattr(inicio_cabecera, "tzinfo") else inicio_cabecera,
                "inicio_serv": inicio_serv, "fin_serv": fin_serv,
                "duración(min)": duracion_min,
                "total_eventos": total_eventos, "eventos_itinerario": eventos_itinerario,
                "validaciones": val_count,
                "validaciones_general": val_general,
                "validaciones_transbordo": val_transbordo,
                "validaciones_estudiante": val_estudiante,
                "validaciones_discapacidad": val_discapacidad,
                "porcentaje_cumplimiento": porcentaje_cumplimiento,
                "observación": observacion,
            })

            if observacion == "No corresponde":
                inicio_cabecera = fin_v - timedelta(minutes=5)
            else:
                inicio_cabecera = fin_v

    ds_servicios = pd.DataFrame(servicios)
    ds_validaciones = pd.concat(validaciones_dfs, ignore_index=True) if validaciones_dfs else pd.DataFrame()
    
    if not ds_validaciones.empty and "idsam_upper" in ds_validaciones.columns:
        ds_validaciones = ds_validaciones.drop(columns=["idsam_upper"])
        
    return ds_servicios, ds_validaciones

def validaciones_por_hora(ds_validaciones):
    if ds_validaciones.empty:
        return pd.DataFrame(columns=["sentido", "rango", "cantidad_validaciones"])

    ds = ds_validaciones.copy()
    ds["hora_dt"] = ds["fechahoraevento"].dt.floor("h")
    
    res = ds.groupby(["sentido", "hora_dt"]).size().reset_index(name="cantidad_validaciones")
    res = res.sort_values(by=["sentido", "hora_dt"])
    res["rango"] = res["hora_dt"].dt.strftime("%H:%M")
    
    final_blocks = []
    for sentido, df_sentido in res.groupby("sentido", sort=False):
        final_blocks.append(df_sentido[["sentido", "rango", "cantidad_validaciones"]])
        subtotal = df_sentido["cantidad_validaciones"].sum()
        final_blocks.append(pd.DataFrame([{
            "sentido": f"SUBTOTAL {sentido.upper()}",
            "rango": "--:--",
            "cantidad_validaciones": subtotal
        }]))
    
    total_gral = ds.shape[0]
    final_blocks.append(pd.DataFrame([{
        "sentido": "TOTAL GENERAL",
        "rango": "--:--",
        "cantidad_validaciones": total_gral
    }]))
    
    return pd.concat(final_blocks, ignore_index=True)

def cantidad_servicios_y_validaciones(ds_servicios):
    if ds_servicios.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    validos = ds_servicios[ds_servicios["observación"].str.startswith("Válido")]
    if validos.empty:
        return pd.DataFrame(), pd.DataFrame()

    ds_cant = validos.groupby(["sentido", "mean_id"]).size().reset_index(name="cantidad_servicios")
    
    total_ida = ds_cant[ds_cant["sentido"] == "ida"]["cantidad_servicios"].sum()
    total_vta = ds_cant[ds_cant["sentido"] == "vuelta"]["cantidad_servicios"].sum()
    
    totales_df = pd.DataFrame([
        {"sentido": "Total ida", "mean_id": "--", "cantidad_servicios": total_ida},
        {"sentido": "Total vuelta", "mean_id": "--", "cantidad_servicios": total_vta}
    ])
    ds_cant = pd.concat([ds_cant, totales_df], ignore_index=True)
    
    ds_cant_val = validos.groupby("mean_id")["validaciones"].sum().reset_index()
    ds_cant_val = pd.concat([ds_cant_val, pd.DataFrame([{"mean_id": "TOTAL", "validaciones": ds_cant_val["validaciones"].sum()}])], ignore_index=True)
    
    return ds_cant, ds_cant_val

def clasificar_operativa(ds_servicios, config):
    """
    Clasifica detalladamente los servicios detectados y programados en tres categorías:
    1. ds_segun_operativa: Servicios realizados según su operativa (Cumplieron itinerario oficial
       y salieron dentro del margen de tolerancia horaria: Regular).
    2. ds_fuera_operativa: Servicios realizados fuera de su operativa:
       - Salidas irregulares (adelantadas o atrasadas fuera de tolerancia horaria).
       - Salidas no programadas / refuerzos extra (sin turno en el cuadro de marcha oficial).
       - Desvíos o incumplimiento de itinerario (< umbral o 'No corresponde').
       - Retornos incompletos (rescate al 80%).
    3. ds_no_realizados: Salidas programadas en la operativa que NO se realizaron (Faltantes / Canceladas).

    Retorna un diccionario con DataFrames y métricas consolidadas.
    """
    programacion = config.get("programacion", [])
    t_antes = config.get("tolerancia_antes_min", 5)
    t_despues = config.get("tolerancia_despues_min", 5)

    cols_operativa = [
        "sentido", "mean_id", "idsam", "nro_servicio_prog", "horario_programado",
        "inicio_serv", "fin_serv", "duración(min)", "desvio_minutos",
        "porcentaje_cumplimiento", "validaciones", "validaciones_general",
        "validaciones_transbordo", "validaciones_estudiante", "validaciones_discapacidad",
        "clasificacion_operativa", "motivo"
    ]
    cols_no_realizados = [
        "sentido", "nro_servicio_prog", "horario_programado", "tipo_dia",
        "clasificacion_operativa", "motivo"
    ]

    if ds_servicios is None or ds_servicios.empty:
        # No se detectó ningún servicio: todas las programadas son no realizadas
        no_realizados = []
        for p in programacion:
            no_realizados.append({
                "sentido": str(p.get("sentido", "")).strip().lower(),
                "nro_servicio_prog": p.get("nro_servicio", 0),
                "horario_programado": str(p.get("horario_salida", "")),
                "tipo_dia": p.get("tipo", config.get("tipo_dia", 5)),
                "clasificacion_operativa": "No realizado (Faltante)",
                "motivo": "Salida programada no realizada / sin detección GPS-Billetaje"
            })
        df_no_real = pd.DataFrame(no_realizados) if no_realizados else pd.DataFrame(columns=cols_no_realizados)
        resumen = {
            "codigo": config.get("codigo", ""),
            "total_programados": len(programacion),
            "total_detectados": 0,
            "total_validos": 0,
            "total_segun_operativa": 0,
            "total_fuera_operativa": 0,
            "total_no_realizados": len(df_no_real),
            "porcentaje_cumplimiento_operativa": 0.0,
            "total_validaciones": 0,
        }
        return {
            "ds_segun_operativa": pd.DataFrame(columns=cols_operativa),
            "ds_fuera_operativa": pd.DataFrame(columns=cols_operativa),
            "ds_no_realizados": df_no_real,
            "resumen_operativa": resumen
        }

    df_servicios = ds_servicios.copy()
    segun_operativa_list = []
    fuera_operativa_list = []
    no_realizados_list = []

    # Separar por sentidos para análisis riguroso
    sentidos = ["ida", "vuelta"]

    for sentido in sentidos:
        prog_sentido = [p for p in programacion if str(p.get("sentido", "")).strip().lower() == sentido]
        serv_sentido = df_servicios[df_servicios["sentido"] == sentido].copy()

        # Identificar viajes con desvío o retorno incompleto directamente como fuera de operativa
        mask_valido = serv_sentido["observación"].str.startswith("Válido")
        mask_retorno = serv_sentido["observación"].str.contains("Retorno")
        
        # Viajes no válidos o retornos
        no_validos = serv_sentido[~mask_valido].copy()
        for _, row in no_validos.iterrows():
            pct = row.get("porcentaje_cumplimiento", 0)
            fuera_operativa_list.append({
                "sentido": sentido,
                "mean_id": row.get("mean_id"),
                "idsam": row.get("idsam"),
                "nro_servicio_prog": "N/A",
                "horario_programado": "N/A",
                "inicio_serv": row.get("inicio_serv"),
                "fin_serv": row.get("fin_serv"),
                "duración(min)": row.get("duración(min)"),
                "desvio_minutos": None,
                "porcentaje_cumplimiento": pct,
                "validaciones": row.get("validaciones", 0),
                "validaciones_general": row.get("validaciones_general", 0),
                "validaciones_transbordo": row.get("validaciones_transbordo", 0),
                "validaciones_estudiante": row.get("validaciones_estudiante", 0),
                "validaciones_discapacidad": row.get("validaciones_discapacidad", 0),
                "clasificacion_operativa": "Realizado fuera de operativa",
                "motivo": f"Desvío de Itinerario (Cumplimiento: {pct}%)"
            })

        retornos = serv_sentido[mask_valido & mask_retorno].copy()
        for _, row in retornos.iterrows():
            fuera_operativa_list.append({
                "sentido": sentido,
                "mean_id": row.get("mean_id"),
                "idsam": row.get("idsam"),
                "nro_servicio_prog": "N/A",
                "horario_programado": "N/A",
                "inicio_serv": row.get("inicio_serv"),
                "fin_serv": row.get("fin_serv"),
                "duración(min)": row.get("duración(min)"),
                "desvio_minutos": None,
                "porcentaje_cumplimiento": row.get("porcentaje_cumplimiento", 0),
                "validaciones": row.get("validaciones", 0),
                "validaciones_general": row.get("validaciones_general", 0),
                "validaciones_transbordo": row.get("validaciones_transbordo", 0),
                "validaciones_estudiante": row.get("validaciones_estudiante", 0),
                "validaciones_discapacidad": row.get("validaciones_discapacidad", 0),
                "clasificacion_operativa": "Realizado fuera de operativa",
                "motivo": "Retorno Incompleto (Rescate de Viaje al 80%)"
            })

        # Viajes válidos completos a emparejar con la programación
        validos_completos = serv_sentido[mask_valido & ~mask_retorno].copy()

        if not prog_sentido:
            # Si no hay programación para este sentido, todos los válidos son no programados (refuerzos)
            for _, row in validos_completos.iterrows():
                fuera_operativa_list.append({
                    "sentido": sentido,
                    "mean_id": row.get("mean_id"),
                    "idsam": row.get("idsam"),
                    "nro_servicio_prog": "N/A",
                    "horario_programado": "N/A",
                    "inicio_serv": row.get("inicio_serv"),
                    "fin_serv": row.get("fin_serv"),
                    "duración(min)": row.get("duración(min)"),
                    "desvio_minutos": None,
                    "porcentaje_cumplimiento": row.get("porcentaje_cumplimiento", 0),
                    "validaciones": row.get("validaciones", 0),
                    "validaciones_general": row.get("validaciones_general", 0),
                    "validaciones_transbordo": row.get("validaciones_transbordo", 0),
                    "validaciones_estudiante": row.get("validaciones_estudiante", 0),
                    "validaciones_discapacidad": row.get("validaciones_discapacidad", 0),
                    "clasificacion_operativa": "Realizado fuera de operativa",
                    "motivo": "Salida No Programada / Sin Cuadro de Marcha"
                })
            continue

        # Crear lista de programados con timestamps de referencia
        df_p = pd.DataFrame(prog_sentido).copy()
        
        # Fecha de referencia tomada de los viajes válidos o de config
        fecha_ref = None
        if not validos_completos.empty:
            primer_inicio = validos_completos.iloc[0]["inicio_serv"]
            fecha_ref = primer_inicio.date() if hasattr(primer_inicio, "date") else datetime.strptime(str(primer_inicio)[:10], "%Y-%m-%d").date()
        elif config.get("fecha_base"):
            fecha_ref = datetime.strptime(str(config["fecha_base"])[:10], "%Y-%m-%d").date()
        else:
            fecha_ref = datetime.now().date()

        def parse_prog_dt(h_str):
            try:
                t = datetime.strptime(str(h_str).strip(), "%H:%M:%S").time()
            except Exception:
                t = datetime.strptime(str(h_str).strip(), "%H:%M").time()
            dt = datetime.combine(fecha_ref, t)
            # Manejo de jornada operativa: salidas de madrugada (00:00 a 04:00) corresponden a +1 día
            if t.hour < 4:
                dt += timedelta(days=1)
            return dt

        df_p["dt_prog"] = df_p["horario_salida"].apply(parse_prog_dt)
        df_p["matched"] = False

        # Emparejamiento óptimo greedy
        # Calculamos todas las diferencias válidos vs programados
        pairs = []
        for v_idx, v_row in validos_completos.iterrows():
            t_real = v_row["inicio_serv"]
            if hasattr(t_real, "tzinfo") and t_real.tzinfo:
                t_real_naive = t_real.replace(tzinfo=None)
            else:
                t_real_naive = t_real

            for p_idx, p_row in df_p.iterrows():
                t_prog = p_row["dt_prog"]
                diff_sec = (t_real_naive - t_prog).total_seconds()
                diff_min = diff_sec / 60.0
                abs_diff = abs(diff_min)
                if abs_diff <= 90.0:  # ventana máxima razonable de asociación
                    pairs.append((abs_diff, diff_min, v_idx, p_idx))

        # Ordenar por cercanía temporal
        pairs.sort(key=lambda x: x[0])

        v_matched = set()
        p_matched = set()

        for abs_diff, diff_min, v_idx, p_idx in pairs:
            if v_idx in v_matched or p_idx in p_matched:
                continue
            v_matched.add(v_idx)
            p_matched.add(p_idx)
            
            v_row = validos_completos.loc[v_idx]
            p_row = df_p.loc[p_idx]
            nro_prog = int(p_row["nro_servicio"])
            h_prog = str(p_row["horario_salida"])
            d_min = round(diff_min, 1)

            if -t_antes <= diff_min <= t_despues:
                segun_operativa_list.append({
                    "sentido": sentido,
                    "mean_id": v_row.get("mean_id"),
                    "idsam": v_row.get("idsam"),
                    "nro_servicio_prog": nro_prog,
                    "horario_programado": h_prog,
                    "inicio_serv": v_row.get("inicio_serv"),
                    "fin_serv": v_row.get("fin_serv"),
                    "duración(min)": v_row.get("duración(min)"),
                    "desvio_minutos": d_min,
                    "porcentaje_cumplimiento": v_row.get("porcentaje_cumplimiento", 0),
                    "validaciones": v_row.get("validaciones", 0),
                    "validaciones_general": v_row.get("validaciones_general", 0),
                    "validaciones_transbordo": v_row.get("validaciones_transbordo", 0),
                    "validaciones_estudiante": v_row.get("validaciones_estudiante", 0),
                    "validaciones_discapacidad": v_row.get("validaciones_discapacidad", 0),
                    "clasificacion_operativa": "Realizado según operativa",
                    "motivo": "Cumplió horario y trazado oficial (Regular)"
                })
            else:
                motivo_irr = f"Salida Adelantada ({int(abs(d_min))} min antes)" if d_min < 0 else f"Salida Atrasada (+{int(d_min)} min después)"
                fuera_operativa_list.append({
                    "sentido": sentido,
                    "mean_id": v_row.get("mean_id"),
                    "idsam": v_row.get("idsam"),
                    "nro_servicio_prog": nro_prog,
                    "horario_programado": h_prog,
                    "inicio_serv": v_row.get("inicio_serv"),
                    "fin_serv": v_row.get("fin_serv"),
                    "duración(min)": v_row.get("duración(min)"),
                    "desvio_minutos": d_min,
                    "porcentaje_cumplimiento": v_row.get("porcentaje_cumplimiento", 0),
                    "validaciones": v_row.get("validaciones", 0),
                    "validaciones_general": v_row.get("validaciones_general", 0),
                    "validaciones_transbordo": v_row.get("validaciones_transbordo", 0),
                    "validaciones_estudiante": v_row.get("validaciones_estudiante", 0),
                    "validaciones_discapacidad": v_row.get("validaciones_discapacidad", 0),
                    "clasificacion_operativa": "Realizado fuera de operativa",
                    "motivo": f"{motivo_irr} (Irregular)"
                })

        # Válidos que no coincidieron con ninguna programada -> Refuerzos no programados
        for v_idx, v_row in validos_completos.iterrows():
            if v_idx not in v_matched:
                fuera_operativa_list.append({
                    "sentido": sentido,
                    "mean_id": v_row.get("mean_id"),
                    "idsam": v_row.get("idsam"),
                    "nro_servicio_prog": "N/A",
                    "horario_programado": "N/A",
                    "inicio_serv": v_row.get("inicio_serv"),
                    "fin_serv": v_row.get("fin_serv"),
                    "duración(min)": v_row.get("duración(min)"),
                    "desvio_minutos": None,
                    "porcentaje_cumplimiento": v_row.get("porcentaje_cumplimiento", 0),
                    "validaciones": v_row.get("validaciones", 0),
                    "validaciones_general": v_row.get("validaciones_general", 0),
                    "validaciones_transbordo": v_row.get("validaciones_transbordo", 0),
                    "validaciones_estudiante": v_row.get("validaciones_estudiante", 0),
                    "validaciones_discapacidad": v_row.get("validaciones_discapacidad", 0),
                    "clasificacion_operativa": "Realizado fuera de operativa",
                    "motivo": "Salida No Programada / Refuerzo Extra"
                })

        # Salidas programadas no emparejadas -> No realizados (Faltantes)
        for p_idx, p_row in df_p.iterrows():
            if p_idx not in p_matched:
                no_realizados_list.append({
                    "sentido": sentido,
                    "nro_servicio_prog": int(p_row["nro_servicio"]),
                    "horario_programado": str(p_row["horario_salida"]),
                    "tipo_dia": p_row.get("tipo_dia", config.get("tipo_dia", 5)),
                    "clasificacion_operativa": "No realizado (Faltante)",
                    "motivo": "Salida programada no realizada / sin cobertura de bus"
                })

    df_segun = pd.DataFrame(segun_operativa_list) if segun_operativa_list else pd.DataFrame(columns=cols_operativa)
    df_fuera = pd.DataFrame(fuera_operativa_list) if fuera_operativa_list else pd.DataFrame(columns=cols_operativa)
    df_no_real = pd.DataFrame(no_realizados_list) if no_realizados_list else pd.DataFrame(columns=cols_no_realizados)

    total_prog = len(programacion)
    total_det = len(df_servicios)
    val_tot = int(df_servicios["validaciones"].sum()) if not df_servicios.empty and "validaciones" in df_servicios.columns else 0

    resumen = {
        "codigo": config.get("codigo", ""),
        "fecha_base": str(config.get("fecha_base", "")),
        "tipo_dia": config.get("tipo_dia", 5),
        "tipo_dia_desc": config.get("tipo_dia_desc", ""),
        "total_programados": total_prog,
        "prog_ida": len([p for p in programacion if str(p.get("sentido", "")).strip().lower() == "ida"]),
        "prog_vuelta": len([p for p in programacion if str(p.get("sentido", "")).strip().lower() == "vuelta"]),
        "total_detectados": total_det,
        "total_segun_operativa": len(df_segun),
        "segun_operativa_ida": len(df_segun[df_segun["sentido"] == "ida"]) if not df_segun.empty else 0,
        "segun_operativa_vuelta": len(df_segun[df_segun["sentido"] == "vuelta"]) if not df_segun.empty else 0,
        "total_fuera_operativa": len(df_fuera),
        "fuera_operativa_ida": len(df_fuera[df_fuera["sentido"] == "ida"]) if not df_fuera.empty else 0,
        "fuera_operativa_vuelta": len(df_fuera[df_fuera["sentido"] == "vuelta"]) if not df_fuera.empty else 0,
        "total_no_realizados": len(df_no_real),
        "no_realizados_ida": len(df_no_real[df_no_real["sentido"] == "ida"]) if not df_no_real.empty else 0,
        "no_realizados_vuelta": len(df_no_real[df_no_real["sentido"] == "vuelta"]) if not df_no_real.empty else 0,
        "porcentaje_cumplimiento_operativa": round((len(df_segun) / total_prog) * 100, 2) if total_prog > 0 else 0.0,
        "total_validaciones": val_tot,
        "validaciones_general": int(df_servicios["validaciones_general"].sum()) if not df_servicios.empty and "validaciones_general" in df_servicios.columns else 0,
        "validaciones_transbordo": int(df_servicios["validaciones_transbordo"].sum()) if not df_servicios.empty and "validaciones_transbordo" in df_servicios.columns else 0,
        "validaciones_estudiante": int(df_servicios["validaciones_estudiante"].sum()) if not df_servicios.empty and "validaciones_estudiante" in df_servicios.columns else 0,
        "validaciones_discapacidad": int(df_servicios["validaciones_discapacidad"].sum()) if not df_servicios.empty and "validaciones_discapacidad" in df_servicios.columns else 0,
    }

    return {
        "ds_segun_operativa": df_segun,
        "ds_fuera_operativa": df_fuera,
        "ds_no_realizados": df_no_real,
        "resumen_operativa": resumen
    }


def regularidad_servicios(ds_servicios, config):
    if ds_servicios.empty: return pd.DataFrame()
    validos = ds_servicios[ds_servicios["observación"].str.startswith("Válido")].copy()
    if validos.empty: return pd.DataFrame()
    
    programacion = config.get("programacion", [])
    t_antes = config.get("tolerancia_antes_min", 5)
    t_despues = config.get("tolerancia_despues_min", 5)
    
    if not programacion:
        validos = validos.sort_values(by=["sentido", "inicio_serv"])
        validos["nro_servicio"] = validos.groupby("sentido").cumcount() + 1
        validos["nro_servicio_prog"] = "N/A"
        validos["regularidad"] = "N/A"
        return validos

    df_prog = pd.DataFrame(programacion)
    validos = validos.sort_values(by=["sentido", "inicio_serv"])
    validos["regularidad"] = "No Programado"
    validos["nro_servicio_prog"] = 0
    
    for idx, row in validos.iterrows():
        inicio_real = row["inicio_serv"]
        sentido = row["sentido"]
        
        prog_sentido = df_prog[df_prog["sentido"] == sentido].copy()
        if prog_sentido.empty: continue
        
        prog_sentido["dt_prog"] = prog_sentido["horario_salida"].apply(
            lambda x: datetime.combine(inicio_real.date(), datetime.strptime(x, "%H:%M:%S").time()).replace(tzinfo=inicio_real.tzinfo)
        )
        
        def ajustar_dia(dt_p):
            diff = (dt_p - inicio_real).total_seconds() / 3600
            if diff > 12: return dt_p - timedelta(days=1)
            if diff < -12: return dt_p + timedelta(days=1)
            return dt_p
        
        prog_sentido["dt_prog"] = prog_sentido["dt_prog"].apply(ajustar_dia)
        prog_sentido["desvio"] = (inicio_real - prog_sentido["dt_prog"]).dt.total_seconds() / 60
        prog_sentido["abs_desvio"] = prog_sentido["desvio"].abs()
        cercano = prog_sentido.sort_values("abs_desvio").iloc[0]
        
        desvio_min = int(cercano["desvio"])
        
        if -t_antes <= desvio_min <= t_despues:
            estado = "Regular"
        else:
            estado = "Irregular"
            
        validos.loc[idx, "regularidad"] = estado
        validos.loc[idx, "nro_servicio"] = cercano["nro_servicio"]
        validos.loc[idx, "nro_servicio_prog"] = cercano["nro_servicio"]

    return validos

def procesar_servicio(config, df_gps, G3, G4, all_validaciones, G5_ida=None, G5_vuelta=None):
    """
    Función maestra unificada de monitoreo para servicios especiales.
    Utilizada tanto por servicios_especiales.py (diario) como por reporte_mensual_excel.py (mensual).
    """
    gdf_gps_proj, ds_inicio_fin = preparar_gps_y_geocercas(
        df_gps, G3, G4, config["radio_geocerca_m"],
        G5_ida=G5_ida, G5_vuelta=G5_vuelta,
        all_validaciones=all_validaciones,
        idSam_mapping=config.get("idSam_mapping")
    )

    ds_servicios, ds_validaciones = calcular_servicios_y_validaciones(
        gdf_gps_proj, ds_inicio_fin, config["idSam_mapping"],
        config["rango_cumplimiento_pct"], config["radio_itinerario_m"],
        G3, G4, all_validaciones
    )

    ds_cant_servicios, ds_cant_validaciones = cantidad_servicios_y_validaciones(ds_servicios)
    ds_servicios_validos = regularidad_servicios(ds_servicios, config)
    ds_valid_por_hora = validaciones_por_hora(ds_validaciones)

    # Clasificación operativa integral: según operativa, fuera de operativa, no realizados
    clasificacion = clasificar_operativa(ds_servicios, config)

    return {
        "ds_servicios": ds_servicios,
        "ds_servicios_validos": ds_servicios_validos,
        "ds_cant_servicios": ds_cant_servicios,
        "ds_cant_validaciones": ds_cant_validaciones,
        "ds_valid_por_hora": ds_valid_por_hora,
        "ds_validaciones": ds_validaciones,
        "ds_gdf_gps": pd.DataFrame(gdf_gps_proj.drop(columns='geometry')) if 'geometry' in gdf_gps_proj.columns else gdf_gps_proj,
        "gdf_gps_proj": gdf_gps_proj,
        "ds_segun_operativa": clasificacion["ds_segun_operativa"],
        "ds_fuera_operativa": clasificacion["ds_fuera_operativa"],
        "ds_no_realizados": clasificacion["ds_no_realizados"],
        "resumen_operativa": clasificacion["resumen_operativa"],
    }
