-- ==============================================================================
-- Estrategia de Almacenamiento y Particionado de Telemetría GPS
-- Base de Datos: PostgreSQL (flota_db)
-- ==============================================================================

-- 1. Crear tabla principal particionada por RANGO de tiempo (recorded_at)
-- Estándar: Resolución GVMT N° 065/2024
CREATE TABLE IF NOT EXISTS telemetry_ping (
    id BIGSERIAL,
    agency_id VARCHAR(32) DEFAULT '004B',
    bus_internal_code VARCHAR(32) NOT NULL,
    license_plate VARCHAR(32),
    route_id VARCHAR(32),
    driver_id VARCHAR(64),
    operation_type SMALLINT NOT NULL DEFAULT 2,
    accuracy_m INTEGER,
    precision INTEGER,
    geom GEOMETRY(Point, 4326),
    altitude_m NUMERIC(6, 2),
    heading_deg NUMERIC(5, 2),
    heading_degrees NUMERIC(5, 1) DEFAULT 0.0,
    speed_kmh NUMERIC(5, 2) DEFAULT 0.0,
    odometer_km NUMERIC(10, 2) DEFAULT 0.0,
    recorded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- 2. Índices base para consultas rápidas por bus, agencia, geom y rango temporal
CREATE INDEX IF NOT EXISTS idx_telemetry_agency_bus_time 
    ON telemetry_ping (agency_id, bus_internal_code, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_route_time 
    ON telemetry_ping (route_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_shape_time 
    ON telemetry_ping (route_shape_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_ping_geom 
    ON telemetry_ping USING GIST (geom);

-- 3. Función PL/pgSQL para Mantenimiento Automático de Particiones y Retención
CREATE OR REPLACE FUNCTION maintain_telemetry_partitions(retention_months INTEGER DEFAULT 3)
RETURNS VOID AS $$
DECLARE
    v_date DATE;
    v_next_month DATE;
    v_partition_name TEXT;
    v_start_time TIMESTAMPTZ;
    v_end_time TIMESTAMPTZ;
    v_old_partition TEXT;
    v_cutoff_date TIMESTAMPTZ;
BEGIN
    -- 1. Crear particiones: mes actual y siguiente mes (para asegurar escritura sin cortes)
    FOR i IN 0..1 LOOP
        v_date := date_trunc('month', CURRENT_DATE + (i || ' month')::INTERVAL)::DATE;
        v_next_month := (v_date + INTERVAL '1 month')::DATE;
        v_partition_name := 'telemetry_ping_' || to_char(v_date, 'YYYY_MM');
        v_start_time := v_date::TIMESTAMPTZ;
        v_end_time := v_next_month::TIMESTAMPTZ;

        -- Verificar si ya existe antes de crear
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c 
            JOIN pg_namespace n ON n.oid = c.relnamespace 
            WHERE c.relname = v_partition_name
        ) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF telemetry_ping FOR VALUES FROM (%L) TO (%L);',
                v_partition_name, v_start_time, v_end_time
            );
            RAISE NOTICE 'Partición creada: %', v_partition_name;
        END IF;
    END LOOP;

    -- 2. Purgado instantáneo de particiones antiguas que superen los meses de retención (sin bloat)
    v_cutoff_date := date_trunc('month', CURRENT_DATE - (retention_months || ' month')::INTERVAL);
    FOR v_old_partition IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname LIKE 'telemetry_ping_%'
          AND c.relkind = 'r'
          AND to_date(substring(c.relname from 'telemetry_ping_([0-9]{4}_[0-9]{2})'), 'YYYY_MM') < v_cutoff_date::DATE
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I;', v_old_partition);
        RAISE NOTICE 'Partición antigua purgada: %', v_old_partition;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 4. Ejecutar mantenimiento inicial para crear las particiones actuales
SELECT maintain_telemetry_partitions(3);
