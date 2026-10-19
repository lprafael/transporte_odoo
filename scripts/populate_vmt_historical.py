import os
import sys
import time
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor

# Asegurar codificación UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

VMT_HOST = os.getenv("VMT_DB_HOST", "monitoreo.vmt.gov.py")
VMT_PORT = int(os.getenv("VMT_DB_PORT", "5432"))
VMT_NAME = os.getenv("VMT_DB_NAME", "bbdd-monitoreo-prod")
VMT_USER = os.getenv("VMT_DB_USER", "jefe-CID")
VMT_PASS = os.getenv("VMT_DB_PASS", "vmtdmt")

LOCAL_HOST = os.getenv("PG_HOST", "localhost")
LOCAL_PORT = int(os.getenv("PG_PORT", 5437))
LOCAL_DB = os.getenv("PG_DB", "flota_db")
LOCAL_USER = os.getenv("PG_USER", "odoo")
LOCAL_PASS = os.getenv("PG_PASS", "odoo_password")

def populate_sample(target_date="2026-09-19", limit_per_agency=25000):
    print(f"[*] Conectando a VMT DB ({VMT_HOST})...")
    conn_vmt = psycopg2.connect(
        host=VMT_HOST, port=VMT_PORT, dbname=VMT_NAME, user=VMT_USER, password=VMT_PASS,
        sslmode="require", connect_timeout=15
    )
    cur_vmt = conn_vmt.cursor(cursor_factory=RealDictCursor)

    print(f"[*] Conectando a Local DB ({LOCAL_HOST}:{LOCAL_PORT}/{LOCAL_DB})...")
    conn_local = psycopg2.connect(
        host=LOCAL_HOST, port=LOCAL_PORT, dbname=LOCAL_DB, user=LOCAL_USER, password=LOCAL_PASS,
        connect_timeout=10
    )
    cur_local = conn_local.cursor()

    agencies = ['004B', '0008', '002A']
    total_inserted = 0
    t0 = time.time()

    for ag in agencies:
        print(f"\n--- Extrayendo pings de Agencia {ag} para {target_date} (límite {limit_per_agency}) ---")
        t_ag0 = time.time()
        cur_vmt.execute("""
            SELECT 
                agency_id,
                mean_id,
                route_id,
                driver_id,
                type,
                precision,
                latitude,
                longitude,
                altitud,
                rumbo,
                velocidad,
                fecha_hora,
                fecha_hora_procesamiento
            FROM app_monitoreo_mensajeoperativo
            WHERE agency_id = %s
              AND fecha_hora >= %s::timestamp
              AND fecha_hora < (%s::timestamp + INTERVAL '1 day')
            ORDER BY fecha_hora ASC
            LIMIT %s;
        """, (ag, target_date, target_date, limit_per_agency))

        rows = cur_vmt.fetchall()
        print(f"[+] Obtenidos {len(rows)} registros de VMT en {time.time() - t_ag0:.2f}s. Insertando en local...")

        if not rows:
            continue

        insert_query = """
            INSERT INTO telemetry_ping (
                agency_id,
                bus_internal_code,
                route_id,
                driver_id,
                operation_type,
                precision,
                accuracy_m,
                altitude_m,
                heading_deg,
                heading_degrees,
                speed_kmh,
                latitude,
                longitude,
                geom,
                recorded_at
            ) VALUES %s
        """

        records = []
        for r in rows:
            lat = float(r["latitude"]) if r["latitude"] is not None else 0.0
            lon = float(r["longitude"]) if r["longitude"] is not None else 0.0
            rec_time = r["fecha_hora"] or r["fecha_hora_procesamiento"]
            geom_wkt = f"SRID=4326;POINT({lon} {lat})" if (lat and lon) else None
            records.append((
                r["agency_id"],
                r["mean_id"] or "",
                r["route_id"] or "",
                r["driver_id"] or "",
                r["type"] if r["type"] is not None else 2,
                r["precision"],
                r["precision"],
                float(r["altitud"] or 0.0),
                float(r["rumbo"] or 0.0),
                float(r["rumbo"] or 0.0),
                float(r["velocidad"] or 0.0),
                lat,
                lon,
                geom_wkt,
                rec_time
            ))

        # Inserción en bloques de 5000 con template
        template = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromEWKT(%s), %s)"
        execute_values(cur_local, insert_query, records, template=template, page_size=5000)
        conn_local.commit()
        total_inserted += len(records)
        print(f"[✓] Agencia {ag}: {len(records)} pings insertados exitosamente.")

    cur_vmt.close()
    conn_vmt.close()

    # Medir tamaños en local DB
    cur_local.execute("""
        SELECT 
            c.relname AS partition_name,
            COUNT(*) AS row_count,
            pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
            pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
            pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
            pg_total_relation_size(c.oid) AS total_bytes
        FROM pg_class c
        JOIN pg_inherits i ON i.inhrelid = c.oid
        WHERE i.inhparent = 'telemetry_ping'::regclass
        GROUP BY c.relname, c.oid
        ORDER BY c.relname;
    """)
    stats = cur_local.fetchall()

    print("\n=======================================================")
    print(f"ESTADÍSTICAS DE ALMACENAMIENTO (Total insertado en esta sesión: {total_inserted} pings en {time.time() - t0:.2f}s)")
    print("=======================================================")
    total_bytes_all = 0
    total_rows_all = 0
    for s in stats:
        print(f"Partición: {s[0]} | Filas: {s[1]:,} | Tabla: {s[2]} | Índices (PostGIS GIST/Btree): {s[3]} | Total: {s[4]}")
        total_bytes_all += s[5]
        total_rows_all += s[1]

    avg_bytes_per_row = total_bytes_all / total_rows_all if total_rows_all else 0
    print(f"\nTotal general: {total_rows_all:,} filas | {total_bytes_all / (1024*1024):.2f} MB")
    print(f"Promedio por ping (Fila + Índices + PostGIS Point): {avg_bytes_per_row:.1f} bytes ({avg_bytes_per_row/1024:.2f} KB)")

    cur_local.close()
    conn_local.close()

if __name__ == "__main__":
    populate_sample()
