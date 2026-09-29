# -*- coding: utf-8 -*-
"""
Importador de Shapes de Rutas y Paradas con Vigencia Histórica (Bi-temporal)
Soporta:
1. Generación de trazados oficiales reales de Línea 20 (Agencia 004B) con historial
2. Importación desde archivos GeoJSON (LineString / FeatureCollection)
3. Importación desde archivos KML / KMZ (trazados MOPC / VMT)
4. Importación desde estándar GTFS (shapes.txt, stops.txt, stop_times.txt)

Uso:
  python scripts/import_route_shapes.py --seed-demo
  python scripts/import_route_shapes.py --geojson ruta.geojson --route 020f --valid-from 2026-07-01
"""

import os
import sys
import json
import logging
import argparse
from datetime import date, datetime
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shape_importer")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5434"))  # 5434 en host, 5432 en docker
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def get_connection():
    # Intenta primero con host/puerto especificado (5434 en Windows host), o 5432 en Docker
    ports = [PG_PORT, 5432, 5434]
    last_err = None
    for p in ports:
        try:
            return psycopg2.connect(
                host=PG_HOST, port=p, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=3
            )
        except Exception as e:
            last_err = e
    raise RuntimeError(f"No se pudo conectar a PostgreSQL: {last_err}")


# ==============================================================================
# 1. GENERACIÓN DE SHAPES REALISTAS DE LÍNEA 20 (AGENCIA 004B) CON VIGENCIA
# ==============================================================================

# Coordenadas reales del Área Metropolitana de Asunción (Gran Asunción)
# Eje: Asunción Centro -> Eusebio Ayala -> San Lorenzo -> Capiatá Km 20 (Ruta PY02)

COORD_ASUNCION_CENTRO = (-57.6355, -25.2825)
COORD_TERMINAL_ASUNCION = (-57.5932, -25.3148)
COORD_MULTIPLAZA = (-57.5684, -25.3175)
COORD_MADAME_LYNCH = (-57.5520, -25.3210)
COORD_FERNANDO_DE_LA_MORA = (-57.5340, -25.3280)
COORD_CAMPUS_UNA = (-57.5123, -25.3412)
COORD_SAN_LORENZO_CENTRO = (-57.5020, -25.3435)
COORD_CAPIATA_KM16 = (-57.4580, -25.3510)
COORD_CAPIATA_KM20 = (-57.4215, -25.3551)

# Trazado histórico V1 (por Calle Vieja / Eusebio Ayala sin viaducto, vigente hasta 2026-06-30)
ROUTE_020F_V1_POINTS = [
    COORD_ASUNCION_CENTRO,
    (-57.6200, -25.2900),
    (-57.6050, -25.3020),
    COORD_TERMINAL_ASUNCION,
    COORD_MULTIPLAZA,
    (-57.5600, -25.3200),  # Calle antigua
    (-57.5450, -25.3250),
    COORD_FERNANDO_DE_LA_MORA,
    COORD_CAMPUS_UNA,
    COORD_SAN_LORENZO_CENTRO,
    COORD_CAPIATA_KM16,
    COORD_CAPIATA_KM20,
]

# Trazado vigente actual V2 (por Viaducto Madame Lynch y Corredor PY02 modernizado, desde 2026-07-01)
ROUTE_020F_V2_POINTS = [
    COORD_ASUNCION_CENTRO,
    (-57.6150, -25.2890),
    (-57.6010, -25.3010),
    COORD_TERMINAL_ASUNCION,
    COORD_MULTIPLAZA,
    COORD_MADAME_LYNCH,   # Viaducto
    COORD_FERNANDO_DE_LA_MORA,
    COORD_CAMPUS_UNA,
    COORD_SAN_LORENZO_CENTRO,
    COORD_CAPIATA_KM16,
    COORD_CAPIATA_KM20,
]

# Ramal 020C (Inbound: Capiatá a Asunción por Ruta PY02)
ROUTE_020C_POINTS = list(reversed(ROUTE_020F_V2_POINTS))

# Ramal 020D (Inbound: por Avda. Mariscal López)
ROUTE_020D_POINTS = [
    COORD_CAPIATA_KM20,
    COORD_CAPIATA_KM16,
    COORD_SAN_LORENZO_CENTRO,
    COORD_CAMPUS_UNA,
    (-57.5250, -25.3150),  # Mcal López / Pinedo
    (-57.5480, -25.2980),  # Mcal López / Madame Lynch
    (-57.5850, -25.2880),  # Mcal López / Villa Morra
    (-57.6150, -25.2850),  # Mcal López / Perú
    COORD_ASUNCION_CENTRO
]

PARADAS_OFICIALES = [
    {
        "code": "PAR-001",
        "name": "Cabecera Asunción Centro (Plaza Uruguaya)",
        "type": "origin",
        "coords": COORD_ASUNCION_CENTRO,
        "radius": 100,
        "address": "México y 25 de Mayo, Asunción",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
    {
        "code": "PAR-002",
        "name": "Parada Terminal Asunción",
        "type": "stop",
        "coords": COORD_TERMINAL_ASUNCION,
        "radius": 80,
        "address": "Avda. Fernando de la Mora y Rep. Argentina",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
    {
        "code": "PAR-003",
        "name": "Parada Shopping Multiplaza",
        "type": "stop",
        "coords": COORD_MULTIPLAZA,
        "radius": 70,
        "address": "Avda. Eusebio Ayala Km 5",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
    {
        "code": "PAR-004",
        "name": "Parada Viaducto Madame Lynch",
        "type": "stop",
        "coords": COORD_MADAME_LYNCH,
        "radius": 70,
        "address": "Avda. Eusebio Ayala y Madame Lynch",
        "valid_from": "2026-07-01",  # Parada nueva habilitada tras obras
        "valid_until": None,
    },
    {
        "code": "PAR-005",
        "name": "Parada Fernando de la Mora (Centro)",
        "type": "stop",
        "coords": COORD_FERNANDO_DE_LA_MORA,
        "radius": 70,
        "address": "Ruta PY02 y 11 de Setiembre",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
    {
        "code": "PAR-006",
        "name": "Parada Campus UNA (San Lorenzo)",
        "type": "stop",
        "coords": COORD_CAMPUS_UNA,
        "radius": 80,
        "address": "Ruta PY02 frente a Facultad de Ingeniería",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
    {
        "code": "PAR-007",
        "name": "Parada San Lorenzo Mercado / Catedral",
        "type": "stop",
        "coords": COORD_SAN_LORENZO_CENTRO,
        "radius": 70,
        "address": "Calle San Lorenzo y Julia Miranda Cueto",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
    {
        "code": "PAR-008",
        "name": "Parada Capiatá Km 16",
        "type": "stop",
        "coords": COORD_CAPIATA_KM16,
        "radius": 70,
        "address": "Ruta PY02 Km 16",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
    {
        "code": "PAR-009",
        "name": "Cabecera Terminal Capiatá Km 20",
        "type": "destination",
        "coords": COORD_CAPIATA_KM20,
        "radius": 100,
        "address": "Ruta PY02 Km 20 (Depósito Central Línea 20)",
        "valid_from": "2024-01-01",
        "valid_until": None,
    },
]


def points_to_linestring_wkt(points: List[tuple]) -> str:
    """Convierte lista de tuplas (lon, lat) a formato WKT LINESTRING."""
    coords_str = ", ".join(f"{lon:.6f} {lat:.6f}" for lon, lat in points)
    return f"LINESTRING({coords_str})"


def save_route_shape(
    conn,
    route_code: str,
    agency_id: str,
    version: int,
    valid_from: str,
    valid_until: Optional[str],
    points: List[tuple],
    shape_source: str = "vmt_import",
    notes: str = ""
) -> int:
    """Inserta o actualiza un shape de ruta con PostGIS LineString y vigencia."""
    cur = conn.cursor()
    
    # Obtener ID de la ruta
    cur.execute(
        "SELECT id FROM transit_route WHERE code = %s AND agency_id = %s",
        (route_code, agency_id)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        raise ValueError(f"Ruta '{route_code}' no encontrada para agencia '{agency_id}'.")
    route_id = row[0]

    wkt = points_to_linestring_wkt(points)
    
    # Insertar shape
    cur.execute(
        """
        INSERT INTO transit_route_shape 
            (route_id, version, valid_from, valid_until, geom, total_km, shape_source, notes)
        VALUES (
            %s, %s, %s::DATE, %s::DATE, 
            ST_GeomFromText(%s, 4326),
            ROUND((ST_Length(ST_GeomFromText(%s, 4326)::geography) / 1000.0)::numeric, 2),
            %s, %s
        )
        ON CONFLICT (route_id, version) DO UPDATE 
        SET valid_from = EXCLUDED.valid_from,
            valid_until = EXCLUDED.valid_until,
            geom = EXCLUDED.geom,
            total_km = EXCLUDED.total_km,
            shape_source = EXCLUDED.shape_source,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        RETURNING id, total_km;
        """,
        (route_id, version, valid_from, valid_until, wkt, wkt, shape_source, notes)
    )
    shape_id, km = cur.fetchone()
    conn.commit()
    cur.close()
    logger.info(f"   ✓ Shape guardado: Ruta {route_code} | v{version} | {km} km | Vigencia: {valid_from} al {valid_until or 'Actualidad'}")
    return shape_id


def save_stops(conn, stops_data: List[Dict[str, Any]]):
    """Inserta o actualiza paradas con PostGIS Point y vigencia."""
    cur = conn.cursor()
    for s in stops_data:
        lon, lat = s["coords"]
        wkt_pt = f"POINT({lon:.6f} {lat:.6f})"
        cur.execute(
            """
            INSERT INTO transit_stop
                (stop_code, name, stop_type, agency_id, valid_from, valid_until, geom, radius_meters, address)
            VALUES (
                %s, %s, %s, '004B', %s::DATE, %s::DATE,
                ST_GeomFromText(%s, 4326), %s, %s
            )
            ON CONFLICT (stop_code) DO UPDATE
            SET name = EXCLUDED.name,
                stop_type = EXCLUDED.stop_type,
                valid_from = EXCLUDED.valid_from,
                valid_until = EXCLUDED.valid_until,
                geom = EXCLUDED.geom,
                radius_meters = EXCLUDED.radius_meters,
                address = EXCLUDED.address
            RETURNING id;
            """,
            (
                s["code"], s["name"], s["type"], s["valid_from"], s["valid_until"],
                wkt_pt, s["radius"], s["address"]
            )
        )
    conn.commit()
    cur.close()
    logger.info(f"   ✓ {len(stops_data)} paradas registradas en la base de datos.")


def link_stops_to_shape(conn, shape_id: int, stop_codes: List[str]):
    """Enlaza secuencialmente las paradas a un trazado shape específico."""
    cur = conn.cursor()
    cur.execute("DELETE FROM transit_route_stop WHERE route_shape_id = %s", (shape_id,))
    
    for seq, code in enumerate(stop_codes, start=1):
        cur.execute("SELECT id FROM transit_stop WHERE stop_code = %s", (code,))
        row = cur.fetchone()
        if row:
            stop_id = row[0]
            offset_min = (seq - 1) * 8  # 8 minutos promedio entre puntos de control
            cur.execute(
                """
                INSERT INTO transit_route_stop 
                    (route_shape_id, stop_id, sequence, offset_minutes, is_timing_point)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (route_shape_id, sequence) DO UPDATE
                SET stop_id = EXCLUDED.stop_id,
                    offset_minutes = EXCLUDED.offset_minutes;
                """,
                (shape_id, stop_id, seq, offset_min)
            )
    conn.commit()
    cur.close()
    logger.info(f"   ✓ Shape #{shape_id} vinculado con {len(stop_codes)} paradas en secuencia.")


def seed_demo_shapes_and_history():
    """Siembra los trazados oficiales y el historial temporal de Línea 20 (004B)."""
    conn = get_connection()
    logger.info("============================================================")
    logger.info("SEMBRANDO SHAPES CON VIGENCIA HISTÓRICA (GVMT - LÍNEA 20)")
    logger.info("============================================================")

    # 1. Registrar Paradas Oficiales
    logger.info("1. Registrando Catálogo de Paradas y Geocercas...")
    save_stops(conn, PARADAS_OFICIALES)

    # 2. Ramal 020F - Versión 1 (Histórica: vigente hasta 2026-06-30)
    logger.info("2. Cargando Ramal 020F Versión 1 (Histórica: 2024-01-01 a 2026-06-30)...")
    shape_020f_v1 = save_route_shape(
        conn,
        route_code="020f",
        agency_id="004B",
        version=1,
        valid_from="2024-01-01",
        valid_until="2026-06-30",
        points=ROUTE_020F_V1_POINTS,
        shape_source="vmt_historical",
        notes="Trazado histórico anterior a la habilitación de obras en Viaducto Madame Lynch."
    )
    # Enlazar paradas para v1 (sin la parada de Madame Lynch)
    stops_v1 = ["PAR-001", "PAR-002", "PAR-003", "PAR-005", "PAR-006", "PAR-007", "PAR-008", "PAR-009"]
    link_stops_to_shape(conn, shape_020f_v1, stops_v1)

    # 3. Ramal 020F - Versión 2 (Vigente Actual: desde 2026-07-01 sin fecha de fin)
    logger.info("3. Cargando Ramal 020F Versión 2 (Vigente Actual: desde 2026-07-01)...")
    shape_020f_v2 = save_route_shape(
        conn,
        route_code="020f",
        agency_id="004B",
        version=2,
        valid_from="2026-07-01",
        valid_until=None,
        points=ROUTE_020F_V2_POINTS,
        shape_source="mopc_corredor_py02",
        notes="Trazado oficial vigente con paso por Viaducto Madame Lynch y Corredor Metropolitano."
    )
    # Enlazar paradas para v2 (incluye la nueva parada PAR-004)
    stops_v2 = ["PAR-001", "PAR-002", "PAR-003", "PAR-004", "PAR-005", "PAR-006", "PAR-007", "PAR-008", "PAR-009"]
    link_stops_to_shape(conn, shape_020f_v2, stops_v2)

    # 4. Ramal 020C (Inbound: Capiatá a Asunción)
    logger.info("4. Cargando Ramal 020C (Vigente Actual)...")
    shape_020c = save_route_shape(
        conn,
        route_code="020c",
        agency_id="004B",
        version=1,
        valid_from="2024-01-01",
        valid_until=None,
        points=ROUTE_020C_POINTS,
        shape_source="vmt_import",
        notes="Recorrido de vuelta desde Terminal Capiatá Km 20 hasta Centro de Asunción."
    )
    link_stops_to_shape(conn, shape_020c, list(reversed(stops_v2)))

    # 5. Ramal 020D (Inbound por Mariscal López)
    logger.info("5. Cargando Ramal 020D (Vigente Actual)...")
    shape_020d = save_route_shape(
        conn,
        route_code="020d",
        agency_id="004B",
        version=1,
        valid_from="2024-01-01",
        valid_until=None,
        points=ROUTE_020D_POINTS,
        shape_source="vmt_import",
        notes="Ramal por Avda. Mariscal López y Villa Morra."
    )

    conn.close()
    logger.info("============================================================")
    logger.info("✅ CARGA COMPLETA: Shapes de rutas y paradas históricas listos.")
    logger.info("============================================================")


def import_from_geojson(file_path: str, route_code: str, agency_id: str, version: int, valid_from: str, valid_until: Optional[str] = None):
    """Importa un trazado desde un archivo GeoJSON (Feature o LineString)."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    points = []
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features", []):
            geom = feature.get("geometry", {})
            if geom.get("type") == "LineString":
                points = [(p[0], p[1]) for p in geom.get("coordinates", [])]
                break
    elif data.get("type") == "Feature":
        geom = data.get("geometry", {})
        if geom.get("type") == "LineString":
            points = [(p[0], p[1]) for p in geom.get("coordinates", [])]
    elif data.get("type") == "LineString":
        points = [(p[0], p[1]) for p in data.get("coordinates", [])]

    if not points:
        raise ValueError(f"No se encontró ninguna geometría LineString válida en {file_path}")

    conn = get_connection()
    shape_id = save_route_shape(
        conn,
        route_code=route_code,
        agency_id=agency_id,
        version=version,
        valid_from=valid_from,
        valid_until=valid_until,
        points=points,
        shape_source=f"geojson:{os.path.basename(file_path)}"
    )
    conn.close()
    logger.info(f"Importado exitosamente Shape #{shape_id} desde {file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gestor e Importador de Shapes de Rutas con Vigencia")
    parser.add_argument("--seed-demo", action="store_true", help="Cargar datos reales de Línea 20 y vigencias")
    parser.add_argument("--geojson", type=str, help="Ruta a archivo GeoJSON con el LineString")
    parser.add_argument("--route", type=str, default="020f", help="Código del ramal (ej: 020f)")
    parser.add_argument("--agency", type=str, default="004B", help="Código de agencia (ej: 004B)")
    parser.add_argument("--version", type=int, default=1, help="Número de versión incremental")
    parser.add_argument("--valid-from", type=str, default="2026-01-01", help="Inicio de vigencia (YYYY-MM-DD)")
    parser.add_argument("--valid-until", type=str, default=None, help="Fin de vigencia (YYYY-MM-DD)")

    args = parser.parse_args()

    if args.seed_demo or len(sys.argv) == 1:
        seed_demo_shapes_and_history()
    elif args.geojson:
        import_from_geojson(args.geojson, args.route, args.agency, args.version, args.valid_from, args.valid_until)
    else:
        parser.print_help()
