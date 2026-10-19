import psycopg2
from datetime import datetime, timedelta, date
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv
import sys
import traceback
from enviar_informe import enviar_informe_incumplimientos
from typing import Dict, List, Optional, Tuple, Any

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos desde .env
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

# Variable global para almacenar incumplimientos
datos_incumplimientos = []

def get_db_connection():
    """Establece conexión con la base de datos"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"✗ Error al conectar a la base de datos: {e}")
        sys.exit(1)

def get_tipo_dia_id(fecha, feriados, conn):
    """
    Determina el ID del tipo de día según la fecha
    Retorna el id_tipo_dia de la tabla tipo_dia
    """
    # Si es feriado
    if fecha in feriados:
        codigo_tipo = 'NO LABORAL'
    else:
        dia_semana = fecha.weekday()  # 0=Lunes, 6=Domingo
        if dia_semana == 5:  # Sábado
            codigo_tipo = 'SABADO'
        elif dia_semana == 6:  # Domingo
            codigo_tipo = 'NO LABORAL'
        else:  # Lunes a Viernes
            codigo_tipo = 'LABORAL'
    
    # Usar un nuevo cursor para esta operación
    with conn.cursor() as cur:
        try:
            # Intentar obtener el ID del tipo de día
            cur.execute("""
                SELECT id_tipo_dia FROM control_metricas.tipo_dia 
                WHERE codigo = %s
            """, (codigo_tipo,))
            
            result = cur.fetchone()
            if result:
                return result[0]
            else:
                # Si no se encuentra, buscar por descripción
                cur.execute("""
                    SELECT id_tipo_dia FROM control_metricas.tipo_dia 
                    WHERE descripcion ILIKE %s
                """, (f'%{codigo_tipo}%',))
                result = cur.fetchone()
                if result:
                    return result[0]
        
        except psycopg2.Error as e:
            print(f"⚠ Advertencia: No se pudo acceder a la tabla tipo_dia: {e}")
    
    # Si no se encuentra el tipo de día, usar valores por defecto
    tipo_por_defecto = {
        'NO LABORAL': 7,
        'SABADO': 6,
        'LABORAL': 5
    }
    
    return tipo_por_defecto.get(codigo_tipo, 5)

def obtener_nivel_infraccion(conn, id_infraccion: int, jornales_acumulados: int) -> Dict[str, Any]:
    """
    Obtiene el nivel de infracción según los jornales acumulados.
    
    Args:
        conn: Conexión a la base de datos
        id_infraccion: ID de la infracción desde parametros_ifo
        jornales_acumulados: Número de días de incumplimiento acumulados
    
    Returns:
        Dict con la información del nivel de infracción
    """
    with conn.cursor() as cur:
        try:
            cur.execute("""
                SELECT 
                    id_infraccion,
                    descripcion,
                    jornales
                FROM control_metricas.niveles_infraccion
                WHERE id_infraccion <= %s
                ORDER BY jornales DESC
                LIMIT 1
            """, (id_infraccion,))
            
            resultado = cur.fetchone()
            if resultado:
                return {
                    'id_infraccion': resultado[0],
                    'descripcion': resultado[1],
                    'jornales': resultado[2]
                }
            
            # Si no se encuentra, retornar infracción leve por defecto
            return {
                'id_infraccion': 1,
                'descripcion': 'Falta leve',
                'jornales': 10
            }
        
        except Exception as e:
            print(f"✗ Error al obtener nivel de infracción: {e}")
            return {
                'id_infraccion': 1,
                'descripcion': 'Falta leve',
                'jornales': 10
            }

def contar_incumplimientos_acumulados(conn, id_eot: str, id_franja: int, fecha_actual: date, dias_atras: int = 30) -> int:
    """
    Cuenta los días de incumplimiento acumulados en los últimos N días.
    
    Args:
        conn: Conexión a la base de datos
        id_eot: ID de la EOT
        id_franja: ID de la franja horaria
        fecha_actual: Fecha actual de referencia
        dias_atras: Número de días hacia atrás a considerar (por defecto 30)
    
    Returns:
        int: Número de días con incumplimiento
    """
    with conn.cursor() as cur:
        try:
            fecha_inicio = fecha_actual - timedelta(days=dias_atras)
            
            cur.execute("""
                SELECT COUNT(*)
                FROM control_metricas.ifo_historico
                WHERE id_eot_vmt_hex = %s
                    AND id_franja = %s
                    AND fecha BETWEEN %s AND %s
                    AND cumple_parametros = FALSE
            """, (id_eot, id_franja, fecha_inicio, fecha_actual))
            
            resultado = cur.fetchone()
            return resultado[0] if resultado else 0
        
        except Exception as e:
            print(f"✗ Error al contar incumplimientos acumulados: {e}")
            return 0

def get_fechas_mismas_semanas_anteriores(fecha_referencia, feriados, semanas=4):
    """
    Devuelve una lista con las mismas fechas de las semanas anteriores.
    """
    fechas = []

    for semana in range(1, semanas + 1):
        candidata = fecha_referencia - timedelta(weeks=semana)

        # Si la candidata es feriado, buscar retrocediendo por semanas hasta encontrar no feriado
        intentos = 0
        while candidata in feriados and intentos < 8:
            # Mover una semana más atrás (manteniendo el mismo weekday)
            candidata = candidata - timedelta(weeks=1)
            intentos += 1

        # Evitar incluir la fecha si sigue siendo feriado o ya está en la lista
        if candidata not in feriados and candidata not in fechas:
            fechas.append(candidata)

    return fechas

def get_db_connection_with_autocommit():
    """Establece conexión con la base de datos con autocommit habilitado"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except psycopg2.Error as e:
        print(f"✗ Error al conectar a la base de datos: {e}")
        sys.exit(1)

def obtener_parametros_ifo(conn, id_franja: int, fecha: date) -> Optional[Dict[str, Any]]:
    """
    Obtiene los parámetros de IFO para una franja horaria específica en una fecha dada.
    """
    with conn.cursor() as cur:
        try:
            cur.execute("""
                SELECT 
                    p.id_parametro,
                    p.descripcion,
                    p.normativa,
                    p.id_franja_operativa,
                    p.porc_cumplimiento_minimo / 100.0,
                    p.muestreo_meses,
                    p.id_infraccion,
                    f.denominacion as nombre_franja
                FROM control_metricas.parametros_ifo p
                JOIN control_metricas.franjas_operativas f ON p.id_franja_operativa = f.id_franja
                WHERE p.id_franja_operativa = %s
                    AND p.inicio_vigencia <= %s 
                    AND (p.fin_vigencia IS NULL OR p.fin_vigencia >= %s)
                ORDER BY p.inicio_vigencia DESC
                LIMIT 1
            """, (id_franja, fecha, fecha))
            
            resultado = cur.fetchone()
            if resultado:
                return {
                    'id_parametro': resultado[0],
                    'descripcion': resultado[1],
                    'normativa': resultado[2],
                    'id_franja_operativa': resultado[3],
                    'porc_cumplimiento_minimo': float(resultado[4]),
                    'muestreo_meses': resultado[5],
                    'id_infraccion': resultado[6],
                    'nombre_franja': resultado[7]
                }
            return None
        
        except Exception as e:
            print(f"✗ Error al obtener parámetros IFO: {e}")
            return None

def verificar_cumplimiento_ifo(id_franja: int, valor_ifo: float, conn, fecha: date, id_eot: str) -> Dict[str, Any]:
    """
    Verifica si el valor de IFO cumple con los parámetros establecidos.
    
    Args:
        id_franja: ID de la franja horaria
        valor_ifo: Valor de IFO calculado (0.0 a 1.0)
        conn: Conexión a la base de datos
        fecha: Fecha de referencia para la verificación
        id_eot: ID de la EOT para contar incumplimientos acumulados
    
    Returns:
        Dict con los resultados de la verificación
    """
    # Obtener parámetros de la franja
    parametros = obtener_parametros_ifo(conn, id_franja, fecha)
    
    if not parametros:
        return {
            'cumple': True,
            'nivel_alerta': 'INFO',
            'mensaje': 'No se encontraron parámetros de cumplimiento para esta franja',
            'tipo_infraccion': 'Sin parámetros',
            'umbral_minimo': 0,
            'normativa': 'No especificada'
        }
    
    # Verificar cumplimiento
    cumple = valor_ifo >= parametros['porc_cumplimiento_minimo']
    
    if cumple:
        return {
            'cumple': True,
            'nivel_alerta': 'CUMPLE',
            'mensaje': f"Cumple con el IFO mínimo de {parametros['porc_cumplimiento_minimo']*100:.0f}% (Valor: {valor_ifo*100:.1f}%)",
            'tipo_infraccion': 'Cumple',
            'umbral_minimo': parametros['porc_cumplimiento_minimo'],
            'normativa': parametros['normativa'],
            'nombre_franja': parametros['nombre_franja']
        }
    
    # Si no cumple, determinar el nivel de infracción según jornales acumulados
    jornales_acumulados = contar_incumplimientos_acumulados(conn, id_eot, id_franja, fecha, dias_atras=30)
    nivel_infraccion = obtener_nivel_infraccion(conn, parametros['id_infraccion'], jornales_acumulados)
    
    return {
        'cumple': False,
        'nivel_alerta': 'ALTA',
        'mensaje': f"No cumple con el IFO mínimo de {parametros['porc_cumplimiento_minimo']*100:.0f}% (Valor: {valor_ifo*100:.1f}%)",
        'tipo_infraccion': nivel_infraccion['descripcion'],
        'umbral_minimo': parametros['porc_cumplimiento_minimo'],
        'normativa': parametros['normativa'],
        'nombre_franja': parametros['nombre_franja'],
        'jornales_acumulados': jornales_acumulados,
        'jornales_limite': nivel_infraccion['jornales']
    }


def calcular_ifo_diario(fecha_proceso=None):
    """
    Función que calcula el IFO para una fecha específica o el día anterior
    """
    global datos_incumplimientos
    
    # Si no se especifica fecha, usar el día anterior
    if fecha_proceso is None:
        fecha_proceso = datetime.now().date() - timedelta(days=1)
    
    print(f"\n{'='*60}")
    print(f"Procesando IFO para la fecha: {fecha_proceso}")
    print(f"{'='*60}")
    
    # Usar una nueva conexión para cada operación
    try:
        # 1. Obtener feriados
        with get_db_connection_with_autocommit() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("SELECT fecha FROM feriados")
                    feriados = set(row[0] for row in cur.fetchall())
                    print(f"Feriados cargados: {len(feriados)}")
                except psycopg2.Error as e:
                    print("⚠ No se encontró la tabla de feriados. Se continuará sin considerar días feriados.")
                    feriados = set()
        
        # 2. Determinar tipo de día y obtener fechas de referencia
        with get_db_connection_with_autocommit() as conn:
            with conn.cursor() as cur:
                # Obtener tipo de día
                id_tipo_dia = get_tipo_dia_id(fecha_proceso, feriados, conn)
                
                # Obtener descripción del tipo de día
                cur.execute("""
                    SELECT descripcion FROM control_metricas.tipo_dia 
                    WHERE id_tipo_dia = %s
                """, (id_tipo_dia,))
                tipo_dia_desc = cur.fetchone()
                tipo_dia_desc = tipo_dia_desc[0] if tipo_dia_desc else "Desconocido"
                print(f"Tipo de día: {tipo_dia_desc} (ID: {id_tipo_dia})")
                
                # 3. Obtener las mismas fechas en las semanas anteriores (4 semanas)
                fechas_mes_anterior = get_fechas_mismas_semanas_anteriores(
                    fecha_proceso, feriados, semanas=4
                )
                print(f"Fechas de referencia (mismas semanas anteriores): {len(fechas_mes_anterior)} días")

                if not fechas_mes_anterior:
                    print("⚠ No hay fechas de referencia en las semanas anteriores")
                    return
                
                # 4. Obtener franjas operativas vigentes
                franjas_vigentes = []
                try:
                    cur.execute("""
                        SELECT f.id_franja, f.denominacion, f.hora_inicio, f.hora_fin
                        FROM control_metricas.franjas_operativas f
                        WHERE f.id_tipo_dia = %s
                            AND f.inicio_vigencia <= %s 
                            AND (f.fin_vigencia IS NULL OR f.fin_vigencia >= %s)
                            AND f.activo = TRUE
                        ORDER BY f.id_franja
                    """, (id_tipo_dia, fecha_proceso, fecha_proceso))
                    
                    franjas_vigentes = cur.fetchall()
                    
                    if not franjas_vigentes:
                        print(f"✗ No hay franjas operativas definidas para el tipo de día {tipo_dia_desc} en la fecha {fecha_proceso}.")
                        print("El proceso se ha cancelado. Por favor, defina las franjas operativas para continuar.")
                        return
                except psycopg2.Error as e:
                    print(f"✗ Error al obtener franjas operativas: {e}")
                    print("El proceso se ha cancelado debido a un error al consultar las franjas operativas.")
                    return
                
                print(f"Franjas operativas a utilizar: {len(franjas_vigentes)}")
        
        # 5. Obtener EOTs permisionarias
        with get_db_connection_with_autocommit() as conn_eots:
            with conn_eots.cursor() as cur:
                cur.execute("""
                    SELECT id_eot_vmt_hex, cod_catalogo, eot_nombre
                    FROM eots
                    WHERE permisionario = TRUE
                """)
                eots = cur.fetchall()
                print(f"EOTs permisionarias: {len(eots)}")

                if not eots:
                    print("⚠ No hay EOTs permisionarias para procesar")
                    return
        
        # 6. Procesar cada EOT
        for id_eot, cod_catalogo, nombre_eot in eots:
            print(f"\nProcesando EOT: {nombre_eot} (Código: {cod_catalogo})")
            
            for id_franja, nombre_franja, hora_inicio, hora_fin in franjas_vigentes:
                with get_db_connection_with_autocommit() as conn_eot:
                    with conn_eot.cursor() as cur_eot:
                        try:
                            eot_num = cod_catalogo
                            
                            # Calcular promedio de idsam únicos por hora para el día actual
                            cur_eot.execute("""
                                WITH horas_franja AS (
                                    SELECT 
                                        generate_series(
                                            (fecha + hora_inicio::interval)::timestamp,
                                            (fecha + hora_fin::interval - interval '1 second')::timestamp,
                                            interval '1 hour'
                                        ) as hora_completa
                                    FROM (SELECT %s::date as fecha, %s::time as hora_inicio, %s::time as hora_fin) t
                                )
                                SELECT COALESCE(AVG(conteo_por_hora), 0)
                                FROM (
                                    SELECT 
                                        date_trunc('hour', (fecha + (hora * INTERVAL '1 hour'))) as hora_completa,
                                        COUNT(DISTINCT idsam) as conteo_por_hora
                                    FROM public.servicios_diarios
                                    WHERE id_eot_catalogo = %s
                                        AND fecha = %s
                                        AND (hora * INTERVAL '1 hour')::time >= %s::time
                                        AND (hora * INTERVAL '1 hour')::time < %s::time
                                    GROUP BY date_trunc('hour', (fecha + (hora * INTERVAL '1 hour')))
                                ) conteos_por_hora
                                RIGHT JOIN horas_franja ON date_trunc('hour', horas_franja.hora_completa) = conteos_por_hora.hora_completa
                            """, (fecha_proceso, hora_inicio, hora_fin, eot_num, fecha_proceso, hora_inicio, hora_fin))
                            
                            idsam_dia_actual = float(cur_eot.fetchone()[0] or 0)
                            
                            # Calcular promedio de buses únicos por GPS para el día actual
                            cur_eot.execute("""
                                WITH horas_franja AS (
                                    SELECT 
                                        generate_series(
                                            (fecha + hora_inicio::interval)::timestamp,
                                            (fecha + hora_fin::interval - interval '1 second')::timestamp,
                                            interval '1 hour'
                                        ) as hora_completa
                                    FROM (SELECT %s::date as fecha, %s::time as hora_inicio, %s::time as hora_fin) t
                                )
                                SELECT COALESCE(AVG(conteo_por_hora), 0)
                                FROM (
                                    SELECT 
                                        date_trunc('hour', (fecha + (hora * INTERVAL '1 hour'))) as hora_completa,
                                        COUNT(DISTINCT mean_id) as conteo_por_hora
                                    FROM control_metricas.cbd_detalle_buses
                                    WHERE id_eot_vmt_hex = %s
                                        AND fecha = %s
                                        AND (hora * INTERVAL '1 hour')::time >= %s::time
                                        AND (hora * INTERVAL '1 hour')::time < %s::time
                                    GROUP BY date_trunc('hour', (fecha + (hora * INTERVAL '1 hour')))
                                ) conteos_por_hora
                                RIGHT JOIN horas_franja ON date_trunc('hour', horas_franja.hora_completa) = conteos_por_hora.hora_completa
                            """, (fecha_proceso, hora_inicio, hora_fin, id_eot, fecha_proceso, hora_inicio, hora_fin))
                            
                            gps_dia_actual = float(cur_eot.fetchone()[0] or 0)
                            
                            # Tomar el mayor entre validaciones y GPS
                            buses_dia_actual_max = max(idsam_dia_actual, gps_dia_actual)
                            origen_numerador = "GPS" if gps_dia_actual > idsam_dia_actual else "Validaciones"
                            
                            # Calcular promedio de idsam únicos por hora para el mes anterior
                            promedios = []
                            for fecha_ref in fechas_mes_anterior:
                                # Consultar validaciones
                                cur_eot.execute("""
                                    WITH horas_franja AS (
                                        SELECT 
                                            generate_series(
                                                (fecha + hora_inicio::interval)::timestamp,
                                                (fecha + hora_fin::interval - interval '1 second')::timestamp,
                                                interval '1 hour'
                                            ) as hora_completa
                                        FROM (SELECT %s::date as fecha, %s::time as hora_inicio, %s::time as hora_fin) t
                                    )
                                    SELECT COALESCE(AVG(conteo_por_hora), 0)
                                    FROM (
                                        SELECT 
                                            date_trunc('hour', (fecha + (hora * INTERVAL '1 hour'))) as hora_completa,
                                            COUNT(DISTINCT idsam) as conteo_por_hora
                                        FROM public.servicios_diarios
                                        WHERE id_eot_catalogo = %s
                                            AND fecha = %s
                                            AND (hora * INTERVAL '1 hour')::time >= %s::time
                                            AND (hora * INTERVAL '1 hour')::time < %s::time
                                        GROUP BY date_trunc('hour', (fecha + (hora * INTERVAL '1 hour')))
                                    ) conteos_por_hora
                                    RIGHT JOIN horas_franja ON date_trunc('hour', horas_franja.hora_completa) = conteos_por_hora.hora_completa
                                """, (fecha_ref, hora_inicio, hora_fin, eot_num, fecha_ref, hora_inicio, hora_fin))
                                
                                count_val = float(cur_eot.fetchone()[0] or 0)
                                
                                # Consultar GPS
                                cur_eot.execute("""
                                    WITH horas_franja AS (
                                        SELECT 
                                            generate_series(
                                                (fecha + hora_inicio::interval)::timestamp,
                                                (fecha + hora_fin::interval - interval '1 second')::timestamp,
                                                interval '1 hour'
                                            ) as hora_completa
                                        FROM (SELECT %s::date as fecha, %s::time as hora_inicio, %s::time as hora_fin) t
                                    )
                                    SELECT COALESCE(AVG(conteo_por_hora), 0)
                                    FROM (
                                        SELECT 
                                            date_trunc('hour', (fecha + (hora * INTERVAL '1 hour'))) as hora_completa,
                                            COUNT(DISTINCT mean_id) as conteo_por_hora
                                        FROM control_metricas.cbd_detalle_buses
                                        WHERE id_eot_vmt_hex = %s
                                            AND fecha = %s
                                            AND (hora * INTERVAL '1 hour')::time >= %s::time
                                            AND (hora * INTERVAL '1 hour')::time < %s::time
                                        GROUP BY date_trunc('hour', (fecha + (hora * INTERVAL '1 hour')))
                                    ) conteos_por_hora
                                    RIGHT JOIN horas_franja ON date_trunc('hour', horas_franja.hora_completa) = conteos_por_hora.hora_completa
                                """, (fecha_ref, hora_inicio, hora_fin, id_eot, fecha_ref, hora_inicio, hora_fin))
                                
                                count_gps = float(cur_eot.fetchone()[0] or 0)
                                
                                # Tomar el máximo para este día de referencia
                                promedios.append(max(count_val, count_gps))
                            
                            promedio_mes_anterior = sum(promedios) / len(promedios) if promedios else 0
                            
                            # Calcular IFO
                            if promedio_mes_anterior > 0:
                                ifo = round(buses_dia_actual_max / promedio_mes_anterior, 4)
                            else:
                                ifo = 0 if buses_dia_actual_max == 0 else 1
                            
                            print(f"  {nombre_franja}: {buses_dia_actual_max:.2f} ({origen_numerador}) / {promedio_mes_anterior:.2f} = {ifo:.4f}")
                            
                            # Verificar cumplimiento con los parámetros
                            cumplimiento = verificar_cumplimiento_ifo(id_franja, ifo, conn_eot, fecha_proceso, id_eot)

                            # Si no cumple, agregar a la lista de incumplimientos
                            if not cumplimiento['cumple']:
                                incumplimiento = {
                                    'eot_nombre': nombre_eot,
                                    'linea_ramal': f"Código: {cod_catalogo}",
                                    'indicador': 'IFO',
                                    'franja_horaria': f"{nombre_franja} ({hora_inicio}-{hora_fin})",
                                    'umbral_requerido': f"{cumplimiento['umbral_minimo']*100:.0f}%",
                                    'valor_observado': f"{float(ifo)*100:.1f}",
                                    'tipo_infraccion': cumplimiento['tipo_infraccion'],
                                    'normativa': cumplimiento.get('normativa', 'No especificada'),
                                    'jornales_acumulados': cumplimiento.get('jornales_acumulados', 0)
                                }
                                datos_incumplimientos.append(incumplimiento)
                            
                            # Eliminar registros existentes
                            cur_eot.execute("""
                                DELETE FROM control_metricas.ifo_historico 
                                WHERE fecha = %s 
                                    AND id_eot_vmt_hex = %s 
                                    AND id_franja = %s
                            """, (fecha_proceso, id_eot, id_franja))
                            
                            # Insertar el nuevo registro
                            cur_eot.execute("""
                                INSERT INTO control_metricas.ifo_historico 
                                (fecha, id_eot_vmt_hex, id_franja, ifo, cumple_parametros, updated_at)
                                VALUES (%s, %s, %s, %s, %s, NOW())
                            """, (fecha_proceso, id_eot, id_franja, ifo, cumplimiento['cumple']))
                        
                        except psycopg2.Error as e:
                            print(f"  ✗ Error al procesar franja {nombre_franja}: {e}")
                            continue
        
        print("\n✓ Procesamiento completado correctamente")
    
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        raise

def procesar_rango_fechas(fecha_inicio, fecha_fin):
    """
    Procesa el cálculo de IFO para un rango de fechas
    """
    global datos_incumplimientos
    datos_incumplimientos = []
    
    print("\n" + "=" * 60)
    print(f"=== Inicio del cálculo de IFO del {fecha_inicio} al {fecha_fin} ===")
    print("=" * 60)
    
    fecha_actual = fecha_inicio
    while fecha_actual <= fecha_fin:
        try:
            calcular_ifo_diario(fecha_actual)
            print(f"\n✓ Procesamiento completado para {fecha_actual}")
        except Exception as e:
            print(f"\n✗ Error al procesar {fecha_actual}: {str(e)}")
            import time
            time.sleep(1)
        
        fecha_actual += timedelta(days=1)
    
    print("\n" + "=" * 60)
    print("=== Proceso finalizado ===")
    print("=" * 60)
    
    return datos_incumplimientos

if __name__ == "__main__":
    import argparse
    from datetime import date, datetime
    
    # Crear el parser de argumentos con ejemplos de uso
    parser = argparse.ArgumentParser(
        description='Calcular el Índice de Frecuencia Operativa (IFO) para una fecha o rango de fechas',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos de uso:
  # Calcular IFO para ayer (comportamiento por defecto)
  python calcular_ifo.py

  # Calcular IFO para una fecha específica
  python calcular_ifo.py --fecha 2025-11-26

  # Calcular IFO para un rango de fechas
  python calcular_ifo.py --desde 2025-11-01 --hasta 2025-11-30

  # Calcular IFO para hoy (fecha actual)
  python calcular_ifo.py --fecha $(Get-Date -Format "yyyy-MM-dd")

Nota: Si no se especifica ninguna fecha, se usará automáticamente el día anterior.
        '''
    )
    
    # Definir los argumentos
    parser.add_argument('--fecha', type=str, help='Fecha específica en formato YYYY-MM-DD')
    parser.add_argument('--desde', type=str, help='Fecha de inicio en formato YYYY-MM-DD (debe usarse con --hasta)')
    parser.add_argument('--hasta', type=str, help='Fecha de fin en formato YYYY-MM-DD (debe usarse con --desde)')
    parser.add_argument('--sin-correo', action='store_true', help='Deshabilita el envío de correos electrónicos')
    
    args = parser.parse_args()
    
    try:
        if args.fecha:
            # Procesar una sola fecha
            fecha = datetime.strptime(args.fecha, '%Y-%m-%d').date()
            datos_incumplimientos = procesar_rango_fechas(fecha, fecha)
        elif args.desde and args.hasta:
            # Procesar rango de fechas
            fecha_desde = datetime.strptime(args.desde, '%Y-%m-%d').date()
            fecha_hasta = datetime.strptime(args.hasta, '%Y-%m-%d').date()
            datos_incumplimientos = procesar_rango_fechas(fecha_desde, fecha_hasta)
        else:
            # Comportamiento por defecto: día anterior
            fecha = date.today() - timedelta(days=1)
            print(f"Usando fecha por defecto: {fecha}")
            datos_incumplimientos = procesar_rango_fechas(fecha, fecha)
        
        # Solo enviar el correo si hay incumplimientos
        if datos_incumplimientos:
            print(f"\n⚠ Se detectaron {len(datos_incumplimientos)} incumplimientos")
            
            if args.sin_correo:
                print("\n[INFO] Envío de correos deshabilitado por el parámetro --sin-correo.")
            else:
                print("\nEnviando informe de incumplimientos por correo electrónico...")
                if enviar_informe_incumplimientos(datos_incumplimientos, fecha):
                    print("✓ Informe de incumplimientos enviado correctamente")
                else:
                    print("✗ No se pudo enviar el informe de incumplimientos")
        else:
            print("\n✓ No hay incumplimientos para reportar.")
    
    except Exception as e:
        print(f"✗ Error al procesar las fechas: {e}")
        traceback.print_exc()
        sys.exit(1)