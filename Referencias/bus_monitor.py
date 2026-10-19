# ====
# INDICACIONES:
# ----
# este script se encarga de analizar los datos de los buses y generar un reporte con los datos de los mismos
# Verifica los buses que estan fuera de sus puntos de inicio y fin de itinerario, y también fuera de los puntos terminales
# No verifica que esté en el itinerario(está preparado para ello, pero está comentado)
# ====
import os
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from dotenv import load_dotenv
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from collections import defaultdict
import pickle
from pathlib import Path
import psycopg2
import sys

# ====
# EJEMPLOS DE USO:
# ----
# 1. Ejecución por defecto (analiza el día de ayer con 6 workers):
#    python bus_monitor.py
#
# 2. Fecha específica (--fecha):
#    python bus_monitor.py --fecha 2025-11-05
#
# 3. Rango de fechas (--fecha-inicio y --fecha-fin):
#    python bus_monitor.py --fecha-inicio 2025-11-01 --fecha-fin 2025-11-15
#
# 4. Filtrar por empresa / EOT (--eot):
#    # Por código de catálogo (numérico o texto):
#    python bus_monitor.py --fecha 2025-11-05 --eot 8
#    python bus_monitor.py --fecha 2025-11-05 --eot "0008"
#    # Por nombre o texto contenido en el nombre:
#    python bus_monitor.py --fecha 2025-11-05 --eot "guarani"
#    # Por identificador hexadecimal VMT:
#    python bus_monitor.py --fecha 2025-11-05 --eot "0a1b2c3d"
#
# 5. Configurar número de workers paralelos (--workers):
#    python bus_monitor.py --fecha 2025-11-05 --workers 4
#    python bus_monitor.py --fecha 2025-11-05 --workers 1   # Modo secuencial (útil para depuración)
#
# 6. Ajustar umbrales mínimos de detección de tránsito:
#    # Duración mínima en minutos de actividad en la hora (por defecto: 15):
#    python bus_monitor.py --fecha 2025-11-05 --min-duracion-min 20
#    # Cantidad mínima de mensajes GPS en la hora (por defecto: 30):
#    python bus_monitor.py --fecha 2025-11-05 --min-mensajes 50
#    # Ambos umbrales modificados:
#    python bus_monitor.py --fecha 2025-11-05 --min-duracion-min 10 --min-mensajes 20
#
# 7. Combinaciones avanzadas / Producción:
#    # Rango de fechas para una empresa específica con workers personalizados:
#    python bus_monitor.py --fecha-inicio 2025-11-01 --fecha-fin 2025-11-15 --eot "guarani" --workers 8
#    # Rango de fechas con filtro de empresa y umbrales personalizados:
#    python bus_monitor.py --fecha-inicio 2025-11-01 --fecha-fin 2025-11-05 --eot 8 --min-duracion-min 10 --min-mensajes 25 --workers 4
# ====

# Cargar las variables de entorno
SCRIPT_DIR = Path(__file__).resolve().parent
for env_candidate in [
    SCRIPT_DIR / ".env",
    SCRIPT_DIR.parent / ".env",
    SCRIPT_DIR.parent / "backend" / ".env",
    SCRIPT_DIR.parent.parent / ".env",
    SCRIPT_DIR.parent.parent.parent / ".env",
]:
    if env_candidate.exists():
        load_dotenv(env_candidate)


def configurar_logging(nivel_consola=logging.INFO, nivel_archivo=logging.DEBUG):
    """Configura logging con niveles separados para consola y archivo."""

    # En Linux intenta /home/ubuntu/logs, en Windows o fallback usa logs/ local
    log_dir = Path('/home/ubuntu/logs')
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_dir = SCRIPT_DIR / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)

    formatter_consola = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    formatter_archivo = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(nivel_consola)
    console_handler.setFormatter(formatter_consola)

    # Forzar UTF-8 si el stream lo soporta
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    try:
        file_handler = logging.FileHandler(log_dir / 'bus_monitor.log', encoding='utf-8')
    except Exception:
        log_dir = SCRIPT_DIR / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / 'bus_monitor.log', encoding='utf-8')

    file_handler.setLevel(nivel_archivo)
    file_handler.setFormatter(formatter_archivo)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers = []
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = configurar_logging()


def get_db_connection():
    """Establece conexión con la base de datos usando variables de entorno."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        return conn
    except Exception as e:
        logger.error(f"  ⚠ Error al conectar a la base de datos: {e}")
        return None


# Variable global para controlar si hubo alertas en la ejecución actual
ALERTA_GENERADA = False


def registrar_ejecucion_correcta(id_script: int = 3, fecha_proceso=None):
    """
    Registra una ejecución correcta en la tabla alertas.registro_ejecuciones.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alertas.registro_ejecuciones 
            (id_script, fecha_proceso, fecha_ejecucion, estado, detalles)
            VALUES (%s, %s, NOW(), %s, %s)
        """, (id_script, fecha_proceso, 'OK', 'Ejecución completada correctamente'))
        
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("  ℹ Ejecución registrada en alertas.registro_ejecuciones")

    except Exception as e:
        logger.error(f"  ⚠ Error al registrar ejecución en BD: {e}")



def registrar_alerta(descripcion: str, id_tipo_alerta: int = 1):
    """
    Registra una alerta en la tabla alertas.control_alertas cuando ocurre un error.
    
    Args:
        descripcion: Descripción del error/incidente
        id_tipo_alerta: ID del tipo de alerta (por defecto 1)
    """
    global ALERTA_GENERADA
    ALERTA_GENERADA = True
    try:
        conn = get_db_connection()
        if not conn:
            logger.warning(f"  ⚠ No se pudo conectar a BD para registrar alerta: {descripcion[:50]}...")
            return False
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alertas.control_alertas 
            (fuente, fechahora_alerta, id_tipo_alerta, verificado, corregido, descripcion_incidente)
            VALUES (%s, NOW(), %s, false, false, %s)
        """, ('bus_monitor.py', id_tipo_alerta, descripcion))
        
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"  ℹ Alerta registrada en control_alertas")
        return True
    except Exception as e:
        logger.error(f"  ⚠ Error al registrar alerta en BD: {e}")
        return False


class LogSymbols:
    """Símbolos para logs con fallback para sistemas sin soporte Unicode."""

    import sys as _sys

    if _sys.stdout and _sys.stdout.encoding and _sys.stdout.encoding.lower().startswith('utf'):
        SUCCESS = '✅'
        WARNING = '⚠️'
        ERROR = '❌'
        INFO = 'ℹ️'
        PROCESS = '🚀'
        BUS = '🚌'
        TIME = '⏰'
        SAVE = '💾'
        SEARCH = '🔍'
        CACHE = '📦'
    else:
        SUCCESS = '[OK]'
        WARNING = '[WARN]'
        ERROR = '[ERR]'
        INFO = '[INFO]'
        PROCESS = '[PROC]'
        BUS = '[BUS]'
        TIME = '[TIME]'
        SAVE = '[SAVE]'
        SEARCH = '[FIND]'
        CACHE = '[CACHE]'


def retry_on_failure(
    max_retries: int = 4,
    wait_time: int = 3,
    exceptions: tuple = (Exception,),
    log_level_retry: int = logging.DEBUG,
    log_level_final: int = logging.ERROR,
):
    """Decorador para reintentar funciones en caso de error."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt < max_retries:
                        sleep_time = wait_time * attempt
                        logger.log(
                            log_level_retry,
                            f"{LogSymbols.WARNING} Intento {attempt}/{max_retries} fallido en {func.__name__}: {e}. "
                            f"Reintentando en {sleep_time}s...",
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.log(
                            log_level_final,
                            f"{LogSymbols.ERROR} {func.__name__} falló tras {max_retries} intentos: {e}",
                            exc_info=True,
                        )
                        raise
            return None

        return wrapper

    return decorator


class DatabaseConfig:
    """Configuración centralizada de la base de datos."""

    @staticmethod
    def get_main_engine() -> Engine:
        return create_engine(
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )

    @staticmethod
    def get_vmt_engine() -> Engine:
        return create_engine(
            f"postgresql://{os.getenv('VMT_DB_USER', os.getenv('DB_USER'))}:"
            f"{os.getenv('VMT_DB_PASSWORD', os.getenv('DB_PASSWORD'))}@"
            f"{os.getenv('VMT_DB_HOST', os.getenv('DB_HOST'))}:"
            f"{os.getenv('VMT_DB_PORT', os.getenv('DB_PORT'))}/"
            f"{os.getenv('VMT_DB_NAME', os.getenv('DB_NAME'))}",
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )


class BusMonitor:
    """Sistema de monitoreo de autobuses optimizado."""

    _script_dir = Path(__file__).resolve().parent
    CACHE_DIR = (
        _script_dir / 'cache_bus_monitor'
        if (_script_dir / 'cache_bus_monitor').exists()
        else (
            _script_dir.parent.parent / 'cache_bus_monitor'
            if (_script_dir.parent.parent / 'cache_bus_monitor').exists()
            else _script_dir / 'cache_bus_monitor'
        )
    )
    MAX_MESSAGES_PER_QUERY = 50000

    def __init__(
        self,
        target_date: Optional[datetime] = None,
        max_workers: int = 6,
        eot_filter: Optional[str] = None,
        min_duracion_min: int = 15,
        min_mensajes: int = 30,
    ) -> None:
        self.target_date = target_date or (datetime.now() - timedelta(days=1)).date()
        self.max_workers = max_workers
        self.eot_filter = eot_filter
        self.min_duracion_min = min_duracion_min
        self.min_mensajes = min_mensajes

        self.main_engine = DatabaseConfig.get_main_engine()
        self.vmt_engine = DatabaseConfig.get_vmt_engine()

        self._db_write_lock = Lock()

        self._geocercas_cache: Dict[str, pd.DataFrame] = {}
        self._geocercas_prep_cache: Dict[str, Dict[str, List[str]]] = {}
        self._time_slots_by_type: Dict[str, pd.DataFrame] = {}
        self._allowed_hours_cache: Optional[List[int]] = None

        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.verificar_indices_db()

        logger.info(
            f"{LogSymbols.SUCCESS} Initialized BusMonitor for date: {self.target_date} "
            f"(workers={max_workers}, eot_filter={eot_filter}, min_duracion={min_duracion_min}min, min_msgs={min_mensajes})"
        )

    def verificar_indices_db(self) -> None:
        """Verifica y crea índices necesarios en la base de datos."""
        indices_requeridos = [
            # app_monitoreo_mensajeoperativo
            '''
            CREATE INDEX IF NOT EXISTS idx_mensajeop_agency_fecha_coords
            ON app_monitoreo_mensajeoperativo (agency_id, fecha_hora, latitude, longitude)
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            ''',
            '''
            CREATE INDEX IF NOT EXISTS idx_mensajeop_spatial
            ON app_monitoreo_mensajeoperativo USING GIST(
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            )
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            ''',
            # control_metricas.cbd_detalle_buses
            '''
            CREATE INDEX IF NOT EXISTS idx_cbd_detalle_eot_fecha_hora
            ON control_metricas.cbd_detalle_buses (id_eot_vmt_hex, fecha, hora, mean_id)
            ''',
            # geometria.geocercas
            '''
            CREATE INDEX IF NOT EXISTS idx_geocercas_spatial
            ON geometria.geocercas USING GIST (geom)
            WHERE id_tipo IN (1, 2, 3)
            ''',
            '''
            CREATE INDEX IF NOT EXISTS idx_geocercas_itinerario_tipo
            ON geometria.geocercas(id_itinerario, id_tipo, orden)
            ''',
        ]

        try:
            with self.main_engine.begin() as conn:
                for idx_query in indices_requeridos:
                    conn.execute(text(idx_query))
            logger.info(f"{LogSymbols.SUCCESS} Índices verificados/creados exitosamente")
        except Exception as e:
            logger.warning(f"{LogSymbols.WARNING} Error verificando índices: {e}")

    @contextmanager
    def get_main_connection(self):
        """Context manager para conexión a la base de datos principal."""
        conn = self.main_engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_vmt_connection(self):
        """Context manager para conexión a la base de datos VMT."""
        conn = self.vmt_engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_connection_with_timeout(self, engine: Engine, timeout_seconds: int = 300):
        """Context manager para conexión con timeout configurado."""
        conn = engine.connect()
        try:
            conn.execute(text(f"SET statement_timeout = {timeout_seconds * 1000}"))
            yield conn
        except Exception as e:
            logger.error(f"{LogSymbols.ERROR} Error en conexión con timeout: {e}")
            raise
        finally:
            conn.close()

    def close(self) -> None:
        """Cierra todas las conexiones de la base de datos."""
        if hasattr(self, 'main_engine'):
            self.main_engine.dispose()
        if hasattr(self, 'vmt_engine'):
            self.vmt_engine.dispose()
        logger.info(f"{LogSymbols.INFO} Todas las conexiones de la base de datos cerradas")

    @staticmethod
    def _to_time(value) -> datetime.time:
        """Convierte varios tipos de fecha/hora a datetime.time."""
        if value is None:
            return datetime.min.time()
        if isinstance(value, datetime):
            return value.time()
        if hasattr(value, 'to_pydatetime'):
            return value.to_pydatetime().time()
        if hasattr(value, 'time'):
            return value.time()
        return value

    @staticmethod
    def _expand_hours_from_slot(hora_inicio, hora_fin) -> Set[int]:
        """Expande un rango de horas a un conjunto de horas individuales."""
        inicio = BusMonitor._to_time(hora_inicio)
        fin = BusMonitor._to_time(hora_fin)

        inicio_seg = inicio.hour * 3600 + inicio.minute * 60 + inicio.second
        fin_seg = fin.hour * 3600 + fin.minute * 60 + fin.second

        fin_inclusive = fin.hour
        if fin.minute == 0 and fin.second == 0 and inicio_seg != fin_seg:
            fin_inclusive = max(fin_inclusive - 1, 0)

        hours: Set[int] = set()

        if fin_seg < inicio_seg:
            hours.update(range(inicio.hour, 24))
            hours.update(range(0, fin_inclusive + 1))
        else:
            hours.update(range(inicio.hour, fin_inclusive + 1))

        return {h for h in hours if 0 <= h <= 23}

    def _preparar_time_slots_con_horas(self, time_slots: pd.DataFrame) -> pd.DataFrame:
        """Prepara franjas horarias expandiendo las horas."""
        if 'horas_expandidas' not in time_slots.columns:
            time_slots = time_slots.copy()
            time_slots['horas_expandidas'] = time_slots.apply(
                lambda row: self._expand_hours_from_slot(row['hora_inicio'], row['hora_fin']),
                axis=1,
            )
        return time_slots

    def _get_allowed_hours(self, time_slots: pd.DataFrame) -> List[int]:
        """Obtiene lista de horas permitidas desde las franjas horarias."""
        if self._allowed_hours_cache is not None:
            return self._allowed_hours_cache

        time_slots = self._preparar_time_slots_con_horas(time_slots)
        hours: Set[int] = set()
        for horas_set in time_slots['horas_expandidas']:
            hours.update(horas_set)

        self._allowed_hours_cache = sorted(hours)
        return self._allowed_hours_cache

    def validar_dataframes(self, **dataframes) -> bool:
        """Valida que los DataFrames no estén vacíos o sean None."""
        for nombre, df in dataframes.items():
            if isinstance(df, pd.DataFrame) and df.empty:
                logger.warning(f"{LogSymbols.WARNING} {nombre} está vacío")
                return False
            elif df is None:
                logger.warning(f"{LogSymbols.WARNING} {nombre} es None")
                return False
        return True

    @retry_on_failure(max_retries=3, wait_time=2)
    def obtener_eots(self) -> pd.DataFrame:
        """Obtiene la lista de EOTs activos."""
        query = '''
            SELECT 
                eot_nombre, 
                cod_catalogo, 
                id_eot_vmt_hex 
            FROM public.eots
            WHERE permisionario = TRUE
        '''
        params = {}
        if self.eot_filter:
            query += " AND (cod_catalogo::text = :eot_filter OR id_eot_vmt_hex = :eot_filter OR eot_nombre ILIKE :eot_filter_like)"
            params['eot_filter'] = str(self.eot_filter)
            params['eot_filter_like'] = f"%{self.eot_filter}%"
        query += " ORDER BY eot_nombre"
        try:
            with self.main_engine.connect() as conn:
                return pd.read_sql(text(query), conn, params=params)
        except Exception as e:
            error_msg = f"Error obteniendo EOTs de la base de datos: {e}"
            logger.error(f"{LogSymbols.ERROR} {error_msg}")
            registrar_alerta(error_msg)
            return pd.DataFrame()

    @retry_on_failure(max_retries=3, wait_time=2)
    def obtener_mensajes_operativos(self, id_eot_vmt_hex: str) -> pd.DataFrame:
        """Obtiene mensajes operativos para un EOT específico."""
        franjas = self.obtenerFranjasOperativas()

        if isinstance(franjas, pd.DataFrame) and not franjas.empty:
            min_inicio = self._to_time(franjas['hora_inicio'].min())
            max_fin = self._to_time(franjas['hora_fin'].max())

            fecha_inicio = datetime.combine(self.target_date, min_inicio)
            fecha_fin = datetime.combine(self.target_date, max_fin) + timedelta(seconds=1)
        else:
            fecha_inicio = datetime.combine(self.target_date, datetime.min.time())
            fecha_fin = datetime.combine(self.target_date, datetime.max.time())

        query = '''
            SELECT 
                mean_id,
                longitude,
                latitude,
                fecha_hora,
                EXTRACT(HOUR FROM fecha_hora)::int as hora
            FROM app_monitoreo_mensajeoperativo
            WHERE 
                agency_id = :agency_id
                AND fecha_hora >= :fecha_inicio
                AND fecha_hora < :fecha_fin
                AND latitude IS NOT NULL 
                AND longitude IS NOT NULL
                AND latitude BETWEEN -26 AND -25
                AND longitude BETWEEN -57.8 AND -57.2
            ORDER BY mean_id, fecha_hora
        '''

        params = {
            'agency_id': id_eot_vmt_hex,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
        }

        with self.vmt_engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
            
        if not df.empty:
            try:
                # Convertir a zona horaria local (America/Asuncion)
                df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], utc=True)
                df["fecha_hora"] = df["fecha_hora"].dt.tz_convert('America/Asuncion')
                # Actualizar la columna hora con la hora local
                df["hora"] = df["fecha_hora"].dt.hour
            except Exception as e:
                logger.warning(f"{LogSymbols.WARNING} Error convert timezone: {e}")

        logger.debug(f"{LogSymbols.SEARCH} Recuperados {len(df)} mensajes para EOT {id_eot_vmt_hex}")
        return df

    def get_cache_path(self, cod_catalogo: str) -> Path:
        """Genera la ruta del archivo de caché para un catálogo."""
        fecha_str = self.target_date.strftime('%Y%m%d')
        return self.CACHE_DIR / f"geocercas_v6_{cod_catalogo}_{fecha_str}.pkl"

    @retry_on_failure(max_retries=3, wait_time=2)
    def obtener_geocercas(self, cod_catalogo: str, id_eot_vmt_hex: str, force_refresh: bool = False) -> pd.DataFrame:
        """Obtiene geocercas para un catálogo específico con caché."""
        cache_file = self.get_cache_path(cod_catalogo)
        if not force_refresh:
            if cod_catalogo in self._geocercas_cache:
                logger.debug(f"{LogSymbols.CACHE} Geocercas de memoria para {cod_catalogo}")
                return self._geocercas_cache[cod_catalogo].copy()

            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        df = pickle.load(f)
                    self._geocercas_cache[cod_catalogo] = df
                    logger.debug(f"{LogSymbols.CACHE} Geocercas de disco para {cod_catalogo}")
                    return df.copy()
                except Exception as e:
                    logger.warning(f"{LogSymbols.WARNING} Error leyendo caché: {e}")

        query = '''
            SELECT 
                hi.id_itinerario,
                cr.ruta_hex,
                gc.id_tipo,
                gc.orden,
                ST_AsText(gc.geom) as geom_wkt
            FROM public.catalogo_rutas cr
            JOIN geometria.historico_itinerario hi 
                ON cr.ruta_hex = hi.ruta_hex
            JOIN geometria.geocercas gc 
                ON hi.id_itinerario = gc.id_itinerario
            WHERE 
                cr.id_eot_catalogo = :cod_catalogo
                AND cr.estado = TRUE
                AND hi.vigente = TRUE
                AND gc.id_tipo IN (1, 2, 3, 6)
                AND (hi.fecha_fin_vigencia IS NULL 
                    OR hi.fecha_fin_vigencia > :target_date)
            
            UNION ALL
            
            SELECT 
                NULL as id_itinerario,
                NULL as ruta_hex,
                6 as id_tipo,
                0 as orden,
                ST_AsText(pt.geom_geocerca) as geom_wkt
            FROM geometria.puntos_terminales pt
            WHERE pt.id_eot_vmt_hex = :id_eot_vmt_hex
            
            ORDER BY id_itinerario, id_tipo, orden
        '''

        with self.get_main_connection() as conn:
            df = pd.read_sql(
                text(query), 
                conn, 
                params={
                    'cod_catalogo': cod_catalogo,
                    'id_eot_vmt_hex': id_eot_vmt_hex,
                    'target_date': self.target_date
                }
            )

        self._geocercas_cache[cod_catalogo] = df
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(df, f)
        except Exception as e:
            logger.warning(f"{LogSymbols.WARNING} Error guardando caché: {e}")

        logger.info(f"{LogSymbols.SEARCH} {len(df)} geocercas para {cod_catalogo} (cacheadas)")
        return df.copy()

    def _preparar_geocercas_para_consulta(self, geocercas: pd.DataFrame) -> Dict[str, List[str]]:
        """Prepara geocercas para consulta espacial con caché."""
        cache_key = f"geocercas_{id(geocercas)}"

        if cache_key in self._geocercas_prep_cache:
            return self._geocercas_prep_cache[cache_key]

        geocerca_inicio = geocercas[geocercas['id_tipo'] == 1]
        geocerca_fin = geocercas[geocercas['id_tipo'] == 2]
        geocerca_itinerario = geocercas[geocercas['id_tipo'] == 3]
        geocerca_terminal = geocercas[geocercas['id_tipo'] == 6]

        resultado = {
            'inicio_wkts': [str(g) for g in geocerca_inicio['geom_wkt'] if pd.notna(g)] or ['POLYGON EMPTY'],
            'fin_wkts': [str(g) for g in geocerca_fin['geom_wkt'] if pd.notna(g)] or ['POLYGON EMPTY'],
            'itinerario_wkts': [str(g) for g in geocerca_itinerario['geom_wkt'] if pd.notna(g)] or ['POLYGON EMPTY'],
            'terminal_wkts': [str(g) for g in geocerca_terminal['geom_wkt'] if pd.notna(g)] or ['POLYGON EMPTY'],
        }

        self._geocercas_prep_cache[cache_key] = resultado
        return resultado

    def _preparar_mensajes_para_consulta(self, messages: pd.DataFrame) -> Optional[Dict]:
        """Prepara mensajes para consulta espacial."""
        mask_valid = messages['latitude'].notna() & messages['longitude'].notna()
        valid_messages = messages[mask_valid]

        if valid_messages.empty:
            return None

        return {
            'mean_ids': valid_messages['mean_id'].astype(str).tolist(),
            'fechas_hora': valid_messages['fecha_hora'].tolist(),
            'horas': valid_messages['hora'].tolist(),
            'lons': valid_messages['longitude'].astype(float).tolist(),
            'lats': valid_messages['latitude'].astype(float).tolist(),
        }

    @retry_on_failure(max_retries=2, wait_time=1)
    def obtenerFranjasOperativas(self) -> pd.DataFrame:
        """Obtiene franjas operativas según el tipo de día."""
        dia_semana = self.target_date.weekday()

        if dia_semana == 5:
            id_tipo_dia = 6
        elif dia_semana == 6:
            id_tipo_dia = 7
        else:
            id_tipo_dia = 5

        cache_key = f"time_slots_{id_tipo_dia}"

        if cache_key in self._time_slots_by_type:
            logger.debug(f"{LogSymbols.CACHE} Franjas para tipo día {id_tipo_dia} desde caché")
            return self._time_slots_by_type[cache_key]

        query = '''
            SELECT 
                id_franja,
                denominacion as nombre_franja,
                hora_inicio,
                hora_fin
            FROM control_metricas.franjas_operativas
            WHERE id_tipo_dia = :id_tipo_dia
                AND :fecha_actual BETWEEN COALESCE(inicio_vigencia, :fecha_limite_inferior) 
                    AND COALESCE(fin_vigencia, :fecha_limite_superior)
            ORDER BY hora_inicio
        '''

        with self.get_main_connection() as conn:
            df = pd.read_sql(
                text(query),
                conn,
                params={
                    'id_tipo_dia': id_tipo_dia,
                    'fecha_actual': self.target_date,
                    'fecha_limite_inferior': self.target_date - pd.DateOffset(years=5),
                    'fecha_limite_superior': self.target_date + pd.DateOffset(years=1),
                },
            )

        self._time_slots_by_type[cache_key] = df

        if df.empty:
            logger.warning(
                f"{LogSymbols.WARNING} No se encontraron franjas horarias activas para tipo de día {id_tipo_dia}"
            )
        else:
            logger.info(
                f"{LogSymbols.TIME} Franjas activas: {len(df)} encontradas (tipo día {id_tipo_dia})"
            )

        return df

    def get_buses_in_transit_batch(
        self,
        mensajes_prep: Dict,
        geocercas_prep: Dict,
    ) -> Dict[int, Tuple[int, List[Dict]]]:
        """
        Procesa un lote de mensajes por rangos horarios y devuelve 1 registro por mean_id por hora.
        
        Retorna:
            Dict[hora, (cantidad_buses, lista_de_buses)]
            donde cada bus tiene: mean_id, primera_posicion_timestamp, ultima_posicion_timestamp, cantidad_mensajes
        """
        resultados_por_hora = {}
        
        # Obtener el rango de horas en los datos
        if not mensajes_prep.get('horas'):
            return {}
            
        horas_unicas = sorted(set(mensajes_prep['horas']))
        
        for hora in horas_unicas:
            try:
                # Filtrar mensajes para esta hora
                indices_hora = [i for i, h in enumerate(mensajes_prep['horas']) if h == hora]
                
                if not indices_hora:
                    continue
                    
                # Crear diccionario con solo los datos de esta hora
                mensajes_hora = {
                    'mean_ids': [mensajes_prep['mean_ids'][i] for i in indices_hora],
                    'fechas_hora': [mensajes_prep['fechas_hora'][i] for i in indices_hora],
                    'horas': [mensajes_prep['horas'][i] for i in indices_hora],
                    'lons': [mensajes_prep['lons'][i] for i in indices_hora],
                    'lats': [mensajes_prep['lats'][i] for i in indices_hora]
                }

                query = '''
                    WITH mensajes_geo AS (
                        SELECT 
                            unnest(CAST(:mean_ids AS text[]))::text as mean_id,
                            unnest(CAST(:fechas_hora AS timestamp[])) as fecha_hora,
                            unnest(CAST(:horas AS int[])) as hora,
                            unnest(CAST(:lons AS double precision[])) as lon,
                            unnest(CAST(:lats AS double precision[])) as lat,
                            ST_SetSRID(ST_MakePoint(
                                unnest(CAST(:lons AS double precision[])),
                                unnest(CAST(:lats AS double precision[]))
                            ), 4326) as geom
                    ),
                    geocercas_consolidadas AS (
                        SELECT
                            (SELECT ST_Union(ST_GeomFromText(geom_wkt, 4326))
                             FROM unnest(CAST(:inicio_wkts AS text[])) as geom_wkt
                             WHERE geom_wkt IS NOT NULL AND geom_wkt != '') as inicio,

                            (SELECT ST_Union(ST_GeomFromText(geom_wkt, 4326))
                             FROM unnest(CAST(:fin_wkts AS text[])) as geom_wkt
                             WHERE geom_wkt IS NOT NULL AND geom_wkt != '') as fin,

                            (SELECT ST_Union(ST_GeomFromText(geom_wkt, 4326))
                             FROM unnest(CAST(:itinerario_wkts AS text[])) as geom_wkt
                             WHERE geom_wkt IS NOT NULL AND geom_wkt != '') as itinerario,

                            (SELECT ST_Union(ST_GeomFromText(geom_wkt, 4326))
                             FROM unnest(CAST(:terminal_wkts AS text[])) as geom_wkt
                             WHERE geom_wkt IS NOT NULL AND geom_wkt != '') as terminal
                    )
                    SELECT
                        mg.hora,
                        mg.mean_id,
                        MIN(mg.fecha_hora) as primera_posicion_timestamp,
                        MAX(mg.fecha_hora) as ultima_posicion_timestamp,
                        COUNT(*) as cantidad_mensajes
                    FROM mensajes_geo mg
                    CROSS JOIN geocercas_consolidadas gc
                    WHERE
                        (gc.inicio IS NULL OR NOT ST_Within(mg.geom, gc.inicio)) AND
                        (gc.fin IS NULL OR NOT ST_Within(mg.geom, gc.fin)) AND
                        (gc.terminal IS NULL OR NOT ST_Within(mg.geom, gc.terminal)) AND
                        (gc.itinerario IS NULL OR ST_Within(mg.geom, gc.itinerario))

                    GROUP BY mg.hora, mg.mean_id
                    ORDER BY mg.mean_id, mg.hora
                '''

                params = {
                    'mean_ids': mensajes_hora['mean_ids'],
                    'fechas_hora': mensajes_hora['fechas_hora'],
                    'horas': mensajes_hora['horas'],
                    'lons': mensajes_hora['lons'],
                    'lats': mensajes_hora['lats'],
                    'inicio_wkts': geocercas_prep.get('inicio_wkts', []),
                    'fin_wkts': geocercas_prep.get('fin_wkts', []),
                    'itinerario_wkts': geocercas_prep.get('itinerario_wkts', []),
                    'terminal_wkts': geocercas_prep.get('terminal_wkts', [])
                }

                with self.vmt_engine.connect() as conn:
                    df = pd.read_sql(text(query), conn, params=params)
                
                if not df.empty:
                    buses = []
                    for _, row in df.iterrows():
                        buses.append({
                            'mean_id': str(row['mean_id']),
                            'primera_posicion_timestamp': row['primera_posicion_timestamp'],
                            'ultima_posicion_timestamp': row['ultima_posicion_timestamp'],
                            'cantidad_mensajes': int(row['cantidad_mensajes'])
                        })
                    resultados_por_hora[hora] = (len(buses), buses)
                    
            except Exception as e:
                logger.error(f"Error procesando hora {hora}: {str(e)}")
                continue
                
        return resultados_por_hora

    def get_buses_in_transit_all_hours(
        self,
        messages: pd.DataFrame,
        geocercas: pd.DataFrame,
        allowed_hours: List[int],
    ) -> Dict[int, Tuple[int, List[Dict]]]:
        """
        Procesa todos los mensajes (dividiendo en lotes si es necesario) y retorna buses por hora.
        """
        if not self.validar_dataframes(messages=messages, geocercas=geocercas):
            return {}

        hour_messages = messages[messages['hora'].isin(allowed_hours)].copy()

        if hour_messages.empty:
            return {}

        geocercas_prep = self._preparar_geocercas_para_consulta(geocercas)

        total_messages = len(hour_messages)

        all_results: Dict[int, Tuple[int, List[Dict]]] = {}

        if total_messages > self.MAX_MESSAGES_PER_QUERY:
            logger.warning(
                f"{LogSymbols.WARNING} {total_messages} mensajes exceden el límite de {self.MAX_MESSAGES_PER_QUERY}. "
                f"Dividiendo en lotes..."
            )
            num_batches = (total_messages // self.MAX_MESSAGES_PER_QUERY) + 1

            for i in range(num_batches):
                start_idx = i * self.MAX_MESSAGES_PER_QUERY
                end_idx = min((i + 1) * self.MAX_MESSAGES_PER_QUERY, total_messages)

                batch = hour_messages.iloc[start_idx:end_idx]
                logger.info(
                    f"{LogSymbols.PROCESS} Procesando lote {i + 1}/{num_batches}: "
                    f"{len(batch)} mensajes ({start_idx}-{end_idx})"
                )

                mensajes_prep = self._preparar_mensajes_para_consulta(batch)
                if not mensajes_prep:
                    continue

                batch_results = self.get_buses_in_transit_batch(mensajes_prep, geocercas_prep)

                for hora, (count, buses) in batch_results.items():
                    if hora not in all_results:
                        all_results[hora] = (0, [])
                    existing_count, existing_buses = all_results[hora]
                    all_results[hora] = (existing_count + count, existing_buses + buses)
        else:
            mensajes_prep = self._preparar_mensajes_para_consulta(hour_messages)
            if not mensajes_prep:
                return {}
            all_results = self.get_buses_in_transit_batch(mensajes_prep, geocercas_prep)

        return all_results

    def _consolidar_detalles_buses(self, bus_details: List[Dict]) -> Dict:
        """
        Consolida detalles de buses por (id_eot_vmt_hex, fecha, hora, mean_id).
        Esto previene duplicados si vienen de múltiples lotes.
        """
        if not bus_details:
            return {}

        df = pd.DataFrame(bus_details)

        consolidated = (
            df.groupby(['id_eot_vmt_hex', 'fecha', 'hora', 'mean_id'])
            .agg(
                {
                    'primera_posicion_timestamp': 'min',
                    'ultima_posicion_timestamp': 'max',
                    'cantidad_mensajes': 'sum',
                }
            )
            .reset_index()
        )

        # Regla de continuidad operativa inteligente
        if self.min_duracion_min > 0 or self.min_mensajes > 0:
            consolidated['duracion_min'] = (
                pd.to_datetime(consolidated['ultima_posicion_timestamp']) - 
                pd.to_datetime(consolidated['primera_posicion_timestamp'])
            ).dt.total_seconds() / 60.0

            buses_horas = set(zip(consolidated['mean_id'], consolidated['hora']))

            def es_bus_operativo(row):
                b = row['mean_id']
                h = row['hora']
                dur = row['duracion_min']
                msgs = row['cantidad_mensajes']
                
                # Si cumple duración y mensajes mínimos, es plenamente operativo
                if dur >= self.min_duracion_min and msgs >= self.min_mensajes:
                    return True
                    
                # Si dura menos, verificar si continúa en la hora siguiente (H+1)
                continua_sig = (b, h + 1) in buses_horas
                viene_ant = (b, h - 1) in buses_horas
                
                # Presente en H-1 y en H+1: servicio continuo a través de la hora H
                if viene_ant and continua_sig:
                    return True

                # Inicio de servicio al final de la hora H que continúa en H+1
                if continua_sig and not viene_ant and msgs >= 15:
                    return True
                    
                # Si venía de H-1 y en H solo estuvo unos minutos antes de guardar coche: repliegue
                if viene_ant and not continua_sig:
                    return False
                    
                # Aislado con muy poca actividad en la hora: descartar
                if not viene_ant and not continua_sig:
                    return False
                    
                return False

            total_antes = len(consolidated)
            consolidated = consolidated[consolidated.apply(es_bus_operativo, axis=1)]
            descartados = total_antes - len(consolidated)
            if descartados > 0:
                logger.info(
                    f"  {LogSymbols.INFO} Filtro operativo inteligente: {descartados} registros descartados por repliegue/actividad insuficiente (<{self.min_duracion_min}min)"
                )

        return {
            (row['id_eot_vmt_hex'], row['fecha'], row['hora'], row['mean_id']): row.to_dict()
            for _, row in consolidated.iterrows()
        }

    @retry_on_failure(max_retries=3, wait_time=3)
    def guardar_detalle_buses(self, bus_details: List[Dict], eot_nombre: str) -> None:
        """
        Guarda detalles de buses en la tabla cbd_detalle_buses.
        Usa ON CONFLICT para actualizar si ya existe el registro.
        """
        try:
            with self.main_engine.begin() as conn:
                if bus_details:
                    consolidated = self._consolidar_detalles_buses(bus_details)
                    if not consolidated:
                        return

                    insert_detalle_hora = '''
                        INSERT INTO control_metricas.cbd_detalle_buses 
                        (id_eot_vmt_hex, fecha, hora, mean_id,
                         primera_posicion_timestamp, ultima_posicion_timestamp, cantidad_mensajes)
                        VALUES (:id_eot_vmt_hex, :fecha, :hora, :mean_id,
                                :primera_posicion_timestamp, :ultima_posicion_timestamp, :cantidad_mensajes)
                        ON CONFLICT (id_eot_vmt_hex, fecha, hora, mean_id) 
                        DO UPDATE SET 
                            primera_posicion_timestamp = LEAST(
                                control_metricas.cbd_detalle_buses.primera_posicion_timestamp,
                                EXCLUDED.primera_posicion_timestamp
                            ),
                            ultima_posicion_timestamp = GREATEST(
                                control_metricas.cbd_detalle_buses.ultima_posicion_timestamp,
                                EXCLUDED.ultima_posicion_timestamp
                            ),
                            cantidad_mensajes = control_metricas.cbd_detalle_buses.cantidad_mensajes + EXCLUDED.cantidad_mensajes
                    '''

                    conn.execute(text(insert_detalle_hora), list(consolidated.values()))

                    logger.info(
                        f"  {LogSymbols.SAVE} {len(consolidated)} detalles de buses guardados para {eot_nombre}"
                    )

                logger.debug(f"  {LogSymbols.SUCCESS} Guardado exitoso para {eot_nombre}")
        except Exception as e:
            logger.error(
                f"  {LogSymbols.ERROR} Error guardando detalles de buses para {eot_nombre}: {e}"
            )
            raise

    def procesar_eot_completo(
        self,
        eot_data: Dict,
        time_slots: pd.DataFrame,
        allowed_hours: List[int],
    ) -> Dict:
        """
        Procesa un EOT completo: obtiene mensajes, geocercas, calcula buses en tránsito y guarda.
        """
        eot_nombre = eot_data['eot_nombre']
        id_eot_vmt_hex = eot_data['id_eot_vmt_hex']
        cod_catalogo = eot_data['cod_catalogo']

        try:
            logger.info(f"\n{LogSymbols.PROCESS} Procesando: {eot_nombre} ({id_eot_vmt_hex})")

            messages = self.obtener_mensajes_operativos(id_eot_vmt_hex)
            geocercas = self.obtener_geocercas(cod_catalogo, id_eot_vmt_hex)

            if geocercas.empty:
                logger.info(f"{LogSymbols.WARNING} Geocercas vacías para {eot_nombre} (Catalog: {cod_catalogo}). Forzando recarga desde BD...")
                geocercas = self.obtener_geocercas(cod_catalogo, id_eot_vmt_hex, force_refresh=True)

            if messages.empty:
                logger.warning(f"{LogSymbols.WARNING} Sin mensajes para {eot_nombre}")
                return {'success': False, 'eot_nombre': eot_nombre, 'error': 'Sin mensajes'}

            if geocercas.empty:
                logger.warning(f"{LogSymbols.WARNING} Sin geocercas para {eot_nombre} (Catalog: {cod_catalogo})")
                return {'success': False, 'eot_nombre': eot_nombre, 'error': 'Sin geocercas'}

            # Verificar si faltan terminales
            if geocercas[geocercas['id_tipo'] == 6].empty:
                logger.warning(f"{LogSymbols.WARNING} {eot_nombre} NO tiene geocercas de terminal (tipo 6). Los buses en terminal podrían ser contados incorrectamente.")

            tipo_counts = geocercas.groupby('id_tipo').size()
            logger.info(
                f"  {LogSymbols.SEARCH} Geocercas: Inicio={tipo_counts.get(1, 0)}, "
                f"Fin={tipo_counts.get(2, 0)}, Itinerario={tipo_counts.get(3, 0)}, "
                f"Terminal={tipo_counts.get(6, 0)}"
            )
            logger.info(
                f"  {LogSymbols.SEARCH} Mensajes: {len(messages)}, "
                f"Buses únicos: {messages['mean_id'].nunique()}"
            )

            results_by_hour = self.get_buses_in_transit_all_hours(messages, geocercas, allowed_hours)

            bus_details_all: List[Dict] = []

            buses_por_hora_summary = {
                'total_horas': len(allowed_hours),
                'horas_con_buses': sum(
                    1 for h in allowed_hours if results_by_hour.get(h, (0, []))[0] > 0
                ),
                'total_buses_observados': sum(
                    results_by_hour.get(h, (0, []))[0] for h in allowed_hours
                ),
                'max_buses': max(
                    (results_by_hour.get(h, (0, []))[0] for h in allowed_hours), default=0
                ),
            }

            logger.info(
                f"  {LogSymbols.BUS} Resumen: {buses_por_hora_summary['horas_con_buses']}"
                f"/{buses_por_hora_summary['total_horas']} horas con buses, "
                f"total={buses_por_hora_summary['total_buses_observados']}, "
                f"máximo={buses_por_hora_summary['max_buses']}"
            )

            if logger.isEnabledFor(logging.DEBUG):
                for hora in allowed_hours:
                    bus_count, _ = results_by_hour.get(hora, (0, []))
                    logger.debug(f"    Hora {hora:02d}:00: {bus_count} buses")

            for hora in allowed_hours:
                bus_count, bus_details = results_by_hour.get(hora, (0, []))

                for bus in bus_details:
                    bus_details_all.append(
                        {
                            'id_eot_vmt_hex': id_eot_vmt_hex,
                            'fecha': self.target_date,
                            'hora': hora,
                            'mean_id': bus['mean_id'],
                            'primera_posicion_timestamp': bus['primera_posicion_timestamp'],
                            'ultima_posicion_timestamp': bus['ultima_posicion_timestamp'],
                            'cantidad_mensajes': bus['cantidad_mensajes'],
                        }
                    )

            if bus_details_all:
                with self._db_write_lock:
                    self.guardar_detalle_buses(bus_details_all, eot_nombre)

            logger.info(f"{LogSymbols.SUCCESS} {eot_nombre} completado exitosamente")

            return {
                'success': True,
                'eot_nombre': eot_nombre,
                'error': None,
            }
        except Exception as e:
            error_msg = f"Error en {eot_nombre}: {e}"
            logger.error(f"{LogSymbols.ERROR} {error_msg}", exc_info=True)
            # Notificamos la alerta solo si el error no es "Sin mensajes" o "Sin geocercas"
            # para no saturar la tabla con problemas de datos que son comunes
            if "Sin mensajes" not in str(e) and "Sin geocercas" not in str(e):
                registrar_alerta(error_msg)
            return {
                'success': False,
                'eot_nombre': eot_nombre,
                'error': str(e),
            }

    def limpiar_datos_existentes(self) -> None:
        """Borra los datos existentes en la base de datos para la fecha objetivo."""
        try:
            with self.main_engine.begin() as conn:
                if self.eot_filter:
                    eots = self.obtener_eots()
                    if not eots.empty:
                        vmt_hexes = eots['id_eot_vmt_hex'].dropna().tolist()
                        query = text("DELETE FROM control_metricas.cbd_detalle_buses WHERE fecha = :fecha AND id_eot_vmt_hex = ANY(:vmt_hexes)")
                        result = conn.execute(query, {'fecha': self.target_date, 'vmt_hexes': vmt_hexes})
                    else:
                        return
                else:
                    query = text("DELETE FROM control_metricas.cbd_detalle_buses WHERE fecha = :fecha")
                    result = conn.execute(query, {'fecha': self.target_date})
                logger.info(
                    f"{LogSymbols.SAVE} Limpieza: {result.rowcount} registros previos borrados para el {self.target_date}"
                )
        except Exception as e:
            logger.error(f"{LogSymbols.ERROR} Error durante la limpieza de datos: {e}")
            raise

    def calcularBusesEnTransito(self) -> None:
        """
        Función principal que coordina el cálculo de buses en tránsito para todos los EOTs.
        """
        try:
            eots = self.obtener_eots()
            time_slots = self.obtenerFranjasOperativas()

            if eots.empty:
                logger.warning(f"{LogSymbols.WARNING} No se encontraron EOTs")
                return

            if time_slots.empty:
                logger.warning(f"{LogSymbols.WARNING} No se encontraron franjas horarias")
                return

            allowed_hours = self._get_allowed_hours(time_slots)
            if not allowed_hours:
                allowed_hours = list(range(24))

            self.imprimirEncabezado()
            
            # Limpiar datos existentes antes de procesar
            self.limpiar_datos_existentes()

            eots_list = eots.to_dict('records')
            logger.info(
                f"\n{LogSymbols.PROCESS} Procesando {len(eots_list)} EOTs en paralelo "
                f"(max_workers={self.max_workers})"
            )

            failed_eots = []

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_eot = {
                    executor.submit(
                        self.procesar_eot_completo,
                        eot,
                        time_slots,
                        allowed_hours,
                    ): eot
                    for eot in eots_list
                }

                completed = 0
                failed = 0

                for future in as_completed(future_to_eot):
                    eot = future_to_eot[future]
                    eot_nombre = eot['eot_nombre']
                    try:
                        result = future.result()
                        if result['success']:
                            completed += 1
                        else:
                            failed += 1
                            failed_eots.append(eot)

                        logger.info(
                            f"{LogSymbols.INFO} Progreso: {completed}/{len(eots_list)} completados, "
                            f"{failed} fallidos"
                        )
                    except Exception as e:
                        failed += 1
                        failed_eots.append(eot)
                        logger.error(
                            f"{LogSymbols.ERROR} Excepción procesando {eot_nombre}: {e}"
                        )

            # Reintentos de EOTs fallidos
            if failed_eots:
                print(f"\n{LogSymbols.WARNING} Reintentando {len(failed_eots)} EOTs fallidos...\n")
                
                # Opcional: Reintentar secuencialmente para evitar sobrecarga si el fallo fue por eso
                reitentos_exitosos = 0
                for eot in failed_eots:
                    eot_nombre = eot['eot_nombre']
                    logger.info(f"{LogSymbols.PROCESS} Reintentando: {eot_nombre}")
                    try:
                        # Llamada síncrona para el reintento
                        result = self.procesar_eot_completo(eot, time_slots, allowed_hours)
                        if result['success']:
                            reitentos_exitosos += 1
                            logger.info(f"{LogSymbols.SUCCESS} Reintento exitoso para {eot_nombre}")
                        else:
                            logger.warning(f"{LogSymbols.WARNING} Reintento fallido para {eot_nombre}: {result.get('error')}")
                    except Exception as e:
                        logger.error(f"{LogSymbols.ERROR} Error en reintento de {eot_nombre}: {e}")

                print(f"\n{LogSymbols.INFO} Reintentos finalizados: {reitentos_exitosos} recuperados de {len(failed_eots)} fallidos.")

            logger.info(
                f"\n{'=' * 100}\n"
                f"{LogSymbols.SUCCESS} Proceso completado\n"
                f"  - EOTs procesados exitosamente (1ra vuelta): {completed}\n"
                f"  - EOTs fallidos (1ra vuelta): {failed}\n"
                f"{'=' * 100}\n"
            )
        except Exception as e:
            error_msg = f"Error en calcularBusesEnTransito: {e}"
            logger.error(f"{LogSymbols.ERROR} {error_msg}", exc_info=True)
            registrar_alerta(error_msg)

    def imprimirEncabezado(self) -> None:
        """Imprime encabezado del reporte."""
        print("\n" + "=" * 100)
        print(f"{'REPORTE DE BUSES EN TRÁNSITO':^100}")
        print(f"{'Fecha: ' + str(self.target_date):^100}")
        print(f"{'Workers: ' + str(self.max_workers):^100}")
        print("=" * 100 + "\n")


def main() -> None:
    """Función principal del script - Compatible con Prefect."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Monitoreo de autobuses en tránsito (OPTIMIZADO)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos de uso:
  # 1. Por defecto (ayer, 6 workers)
  python bus_monitor.py

  # 2. Fecha específica
  python bus_monitor.py --fecha 2025-11-06

  # 3. Rango de fechas
  python bus_monitor.py --fecha-inicio 2025-11-01 --fecha-fin 2025-12-11

  # 4. Filtrar por empresa / EOT (código de catálogo, nombre o ID hex)
  python bus_monitor.py --fecha 2025-11-06 --eot "guarani"
  python bus_monitor.py --fecha 2025-11-06 --eot 8

  # 5. Con workers personalizados (paralelismo)
  python bus_monitor.py --fecha 2025-11-06 --workers 8
  python bus_monitor.py --fecha 2025-11-06 --workers 1

  # 6. Ajustar umbrales mínimos (duración en minutos y cantidad de mensajes GPS)
  python bus_monitor.py --fecha 2025-11-06 --min-duracion-min 20 --min-mensajes 50

  # 7. Combinación completa (rango de fechas, empresa, workers y umbrales)
  python bus_monitor.py --fecha-inicio 2025-11-01 --fecha-fin 2025-11-10 --eot 8 --workers 6 --min-duracion-min 10 --min-mensajes 25
''',
    )
    parser.add_argument(
        '--fecha',
        type=str,
        help='Fecha en formato YYYY-MM-DD (por defecto: ayer)',
        metavar='YYYY-MM-DD',
    )
    parser.add_argument(
        '--fecha-inicio',
        type=str,
        help='Fecha de inicio del rango en formato YYYY-MM-DD',
        metavar='YYYY-MM-DD',
    )
    parser.add_argument(
        '--fecha-fin',
        type=str,
        help='Fecha de fin del rango en formato YYYY-MM-DD (inclusive)',
        metavar='YYYY-MM-DD',
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=6,
        help='Número de workers para procesamiento paralelo (por defecto: 6)',
        metavar='N',
    )
    parser.add_argument(
        '--eot',
        type=str,
        help='Filtrar por código de catálogo, id_eot_vmt_hex o nombre de EOT (ej: 8 o "0008" o "guarani")',
        metavar='EOT',
    )
    parser.add_argument(
        '--min-duracion-min',
        type=int,
        default=15,
        help='Duración mínima en minutos de actividad en tránsito en la hora (por defecto: 15)',
        metavar='MIN',
    )
    parser.add_argument(
        '--min-mensajes',
        type=int,
        default=30,
        help='Cantidad mínima de mensajes GPS en la hora (por defecto: 30)',
        metavar='N',
    )
    args = parser.parse_args()

    # Determinar las fechas a procesar
    fechas_a_procesar = []

    if args.fecha_inicio and args.fecha_fin:
        # Modo rango de fechas
        try:
            fecha_inicio = datetime.strptime(args.fecha_inicio, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(args.fecha_fin, '%Y-%m-%d').date()
            
            if fecha_inicio > fecha_fin:
                logger.error(f"{LogSymbols.ERROR} La fecha de inicio debe ser anterior o igual a la fecha de fin")
                return
            
            # Generar todas las fechas en el rango
            fecha_actual = fecha_inicio
            while fecha_actual <= fecha_fin:
                fechas_a_procesar.append(fecha_actual)
                fecha_actual += timedelta(days=1)
            
            logger.info(f"{LogSymbols.INFO} Procesando rango de fechas: {fecha_inicio} a {fecha_fin} ({len(fechas_a_procesar)} días)")
            
        except ValueError as e:
            logger.error(f"{LogSymbols.ERROR} Formato de fecha inválido. Use YYYY-MM-DD: {e}")
            return
    elif args.fecha:
        # Modo fecha única
        try:
            target_date = datetime.strptime(args.fecha, '%Y-%m-%d').date()
            fechas_a_procesar.append(target_date)
        except ValueError:
            logger.error(f"{LogSymbols.ERROR} Formato de fecha inválido. Use YYYY-MM-DD")
            return
    else:
        # Por defecto: ayer
        fechas_a_procesar.append(datetime.now().date() - timedelta(days=1))

    total_start_time = datetime.now()
    total_fechas = len(fechas_a_procesar)
    fechas_exitosas = 0
    fechas_fallidas = []

    for i, target_date in enumerate(fechas_a_procesar, 1):
        print("\n" + "=" * 80)
        logger.info(f"{LogSymbols.PROCESS} [{i}/{total_fechas}] Procesando fecha: {target_date}")
        print("=" * 80)
        
        start_time = datetime.now()
        monitor = None
        
        try:
            # Resetear flag de alerta para esta fecha
            global ALERTA_GENERADA
            ALERTA_GENERADA = False
            
            monitor = BusMonitor(
                target_date=target_date,
                max_workers=args.workers,
                eot_filter=args.eot,
                min_duracion_min=args.min_duracion_min,
                min_mensajes=args.min_mensajes,
            )
            monitor.calcularBusesEnTransito()
            
            if not ALERTA_GENERADA:
                registrar_ejecucion_correcta(fecha_proceso=target_date)
                fechas_exitosas += 1
            else:
                logger.warning(f"{LogSymbols.WARNING} Ejecución completada pero con alertas. No se registra como ejecución correcta.")
                # Consideramos falla si hubo alertas para efectos de resumen? 
                # El usuario no especificó, pero mantendré logicamente que si no es "correcta" tal vez no cuenta como exitosa plena.
                # Pero la variable 'fechas_exitosas' parece contar ejecuciones que "terminaron".
                # Dejemos 'fechas_exitosas' solo si se registró.

            
        except Exception as e:
            logger.error(f"{LogSymbols.ERROR} Error procesando {target_date}: {e}", exc_info=True)
            fechas_fallidas.append(target_date)
            
        finally:
            elapsed_time = datetime.now() - start_time
            logger.info(f"{LogSymbols.TIME} Tiempo para {target_date}: {elapsed_time}")
            if monitor:
                monitor.close()

    # Resumen final
    total_elapsed = datetime.now() - total_start_time
    print("\n" + "=" * 80)
    print(f"{'RESUMEN DE PROCESAMIENTO':^80}")
    print("=" * 80)
    print(f"  Total de fechas procesadas: {total_fechas}")
    print(f"  Fechas exitosas: {fechas_exitosas}")
    print(f"  Fechas fallidas: {len(fechas_fallidas)}")
    if fechas_fallidas:
        print(f"  Fechas con error: {', '.join(str(f) for f in fechas_fallidas)}")
    print(f"  Tiempo total: {total_elapsed}")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()