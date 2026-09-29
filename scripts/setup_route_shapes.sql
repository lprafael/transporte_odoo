-- ============================================================================
-- SCHEMAS DE SHAPES DE RUTAS Y PARADAS CON VIGENCIA HISTÓRICA
-- Sistema Integral de Control de Flota - Transporte Público Paraguay
-- ============================================================================
-- Requiere: PostGIS (para geometrías geoespaciales)
-- Compatible: PostgreSQL 15
-- ============================================================================

-- Aseguramos que PostGIS esté activo
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- ============================================================================
-- 1. TABLA DE LÍNEAS Y RAMALES (catálogo maestro de rutas)
-- ============================================================================
CREATE TABLE IF NOT EXISTS transit_route (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(20)  NOT NULL,          -- Código oficial VMT (ej: "020f")
    name            TEXT         NOT NULL,           -- Nombre descriptivo completo
    agency_id       VARCHAR(32)  DEFAULT '004B',     -- Empresa operadora (ej: "004B")
    direction       VARCHAR(20)  DEFAULT 'inbound',  -- 'inbound', 'outbound', 'circular'
    origin          VARCHAR(255) DEFAULT 'Terminal',
    destination     VARCHAR(255) DEFAULT 'Cabecera',
    transport_mode  VARCHAR(20)  DEFAULT 'bus',      -- 'bus', 'minibus', 'brt'
    description     TEXT,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- Compatibilidad: si la tabla fue creada por Odoo, asegurar columnas y defaults
ALTER TABLE transit_route 
    ADD COLUMN IF NOT EXISTS agency_id VARCHAR(32) DEFAULT '004B',
    ADD COLUMN IF NOT EXISTS transport_mode VARCHAR(20) DEFAULT 'bus',
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

UPDATE transit_route SET agency_id = '004B' WHERE agency_id IS NULL;
ALTER TABLE transit_route ALTER COLUMN origin DROP NOT NULL;
ALTER TABLE transit_route ALTER COLUMN destination DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_route_code_agency ON transit_route(code, agency_id);

COMMENT ON TABLE transit_route IS 
    'Catálogo maestro de líneas y ramales del sistema de transporte.';

-- ============================================================================
-- 2. TABLA DE SHAPES DE RUTA CON VIGENCIA HISTÓRICA (bi-temporal)
-- ============================================================================
-- Un mismo ramal puede cambiar su trazado a lo largo del tiempo (obras viales,
-- ampliaciones, cambios de frecuencia o itinerario). Esta tabla preserva el
-- historial completo de variaciones geométricas del trayecto.
-- ============================================================================
CREATE TABLE IF NOT EXISTS transit_route_shape (
    id              BIGSERIAL    PRIMARY KEY,
    route_id        INTEGER      NOT NULL REFERENCES transit_route(id) ON DELETE CASCADE,
    version         INTEGER      NOT NULL DEFAULT 1,    -- Versión incremental del shape
    valid_from      DATE         NOT NULL,              -- Inicio de vigencia (inclusive)
    valid_until     DATE,                               -- Fin de vigencia (NULL = vigente hoy)
    
    -- Geometría del trazado completo como linestring (proyección WGS84)
    geom            GEOMETRY(LineString, 4326) NOT NULL,
    
    -- Metadatos del shape
    total_km        NUMERIC(8, 2),                     -- Longitud total del recorrido en km
    shape_source    VARCHAR(50)  DEFAULT 'manual',     -- 'manual', 'gtfs', 'osrm', 'vmt_import'
    notes           TEXT,
    created_by      VARCHAR(100),
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW(),
    
    -- Restricción: sin solapamiento de vigencias para el mismo ramal
    CONSTRAINT uq_route_shape_version UNIQUE (route_id, version),
    CONSTRAINT chk_valid_dates CHECK (valid_until IS NULL OR valid_until > valid_from)
);

COMMENT ON TABLE transit_route_shape IS 
    'Geometrías (LineString) de los trazados de cada ramal con historial de vigencia. '
    'Permite auditar qué recorrido estaba activo en cualquier fecha pasada.';

CREATE INDEX idx_route_shape_geom        ON transit_route_shape USING GIST (geom);
CREATE INDEX idx_route_shape_valid_from  ON transit_route_shape (valid_from);
CREATE INDEX idx_route_shape_route_id    ON transit_route_shape (route_id);

-- ============================================================================
-- 3. TABLA DE PARADAS Y CABECERAS (con vigencia histórica)
-- ============================================================================
CREATE TABLE IF NOT EXISTS transit_stop (
    id              BIGSERIAL    PRIMARY KEY,
    stop_code       VARCHAR(20)  NOT NULL,             -- Código único de parada
    name            TEXT         NOT NULL,              -- Nombre oficial de la parada
    stop_type       VARCHAR(20)  NOT NULL DEFAULT 'stop', -- 'origin', 'stop', 'destination', 'control'
    agency_id       VARCHAR(32),                       -- NULL = parada compartida entre empresas
    
    -- Vigencia de la parada (se desactiva cuando se muda o elimina)
    valid_from      DATE         NOT NULL,
    valid_until     DATE,                              -- NULL = activa hoy
    
    -- Geometría puntual (WGS84)
    geom            GEOMETRY(Point, 4326) NOT NULL,
    
    -- Tolerancia geoespacial para validar llegadas en el sistema de geocercas
    radius_meters   INTEGER      NOT NULL DEFAULT 50,
    
    -- Dirección y datos de accesibilidad
    address         TEXT,
    has_shelter     BOOLEAN      DEFAULT FALSE,
    is_accessible   BOOLEAN      DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    
    CONSTRAINT uq_stop_code UNIQUE (stop_code),
    CONSTRAINT chk_stop_valid_dates CHECK (valid_until IS NULL OR valid_until > valid_from)
);

COMMENT ON TABLE transit_stop IS 
    'Catálogo de paradas, cabeceras y puntos de control con vigencia histórica y geometría puntual.';

CREATE INDEX idx_stop_geom        ON transit_stop USING GIST (geom);
CREATE INDEX idx_stop_valid_from  ON transit_stop (valid_from);
CREATE INDEX idx_stop_type        ON transit_stop (stop_type);

-- ============================================================================
-- 4. TABLA DE SECUENCIA DE PARADAS POR RAMAL Y VERSIÓN (GTFS: stop_times)
-- ============================================================================
-- Vincula cada parada con un shape de ruta y define el orden y tiempos de paso.
CREATE TABLE IF NOT EXISTS transit_route_stop (
    id              BIGSERIAL    PRIMARY KEY,
    route_shape_id  INTEGER      NOT NULL REFERENCES transit_route_shape(id) ON DELETE CASCADE,
    stop_id         BIGINT       NOT NULL REFERENCES transit_stop(id),
    sequence        INTEGER      NOT NULL,             -- Orden de la parada en la ruta
    offset_minutes  INTEGER      NOT NULL DEFAULT 0,   -- Tiempo desde la salida de cabecera (min)
    
    -- Distancia acumulada desde el inicio del recorrido (útil para progreso del viaje)
    distance_from_origin_km NUMERIC(8, 2),
    
    -- La parada puede ser solo de bajada o solo de subida
    pickup_type     INTEGER      DEFAULT 0,            -- 0=todos, 1=ninguno, 3=bajo pedido
    drop_off_type   INTEGER      DEFAULT 0,
    is_timing_point BOOLEAN      DEFAULT FALSE,        -- ¿Es punto de control de puntualidad?
    
    CONSTRAINT uq_route_stop_sequence UNIQUE (route_shape_id, sequence)
);

COMMENT ON TABLE transit_route_stop IS 
    'Secuencia ordenada de paradas para cada versión de trazado de ruta (equivalente a GTFS stop_times).';

CREATE INDEX idx_route_stop_shape  ON transit_route_stop (route_shape_id);
CREATE INDEX idx_route_stop_stop   ON transit_route_stop (stop_id);

-- ============================================================================
-- 5. VISTA: SHAPE VIGENTE HOY POR RAMAL
-- ============================================================================
CREATE OR REPLACE VIEW v_active_route_shapes AS
SELECT
    r.id          AS route_id,
    r.code        AS route_code,
    r.name        AS route_name,
    r.agency_id,
    r.direction,
    s.id          AS shape_id,
    s.version,
    s.valid_from,
    s.valid_until,
    s.total_km,
    s.shape_source,
    s.geom        AS route_geom,
    ST_Length(s.geom::geography) / 1000.0 AS calculated_km
FROM transit_route r
JOIN transit_route_shape s ON s.route_id = r.id
WHERE s.valid_from <= CURRENT_DATE
  AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE);

COMMENT ON VIEW v_active_route_shapes IS 
    'Shapes de ruta con vigencia activa al día de hoy (filtro automático por fecha).';

-- ============================================================================
-- 6. VISTA: PARADAS VIGENTES HOY
-- ============================================================================
CREATE OR REPLACE VIEW v_active_stops AS
SELECT
    id,
    stop_code,
    name,
    stop_type,
    agency_id,
    radius_meters,
    address,
    has_shelter,
    is_accessible,
    geom,
    ST_X(geom) AS longitude,
    ST_Y(geom) AS latitude
FROM transit_stop
WHERE valid_from <= CURRENT_DATE
  AND (valid_until IS NULL OR valid_until > CURRENT_DATE);

COMMENT ON VIEW v_active_stops IS 
    'Paradas activas en el día de hoy (excluye paradas históricas o futuras).';

-- ============================================================================
-- 7. FUNCIÓN: OBTENER SHAPE VIGENTE EN UNA FECHA HISTÓRICA ESPECÍFICA
-- ============================================================================
CREATE OR REPLACE FUNCTION get_route_shape_at_date(
    p_route_code VARCHAR,
    p_agency_id  VARCHAR,
    p_date       DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    route_id    INTEGER,
    shape_id    BIGINT,
    route_code  VARCHAR,
    route_name  TEXT,
    valid_from  DATE,
    valid_until DATE,
    total_km    NUMERIC,
    geom        GEOMETRY
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.id,
        s.id,
        r.code::VARCHAR,
        r.name::TEXT,
        s.valid_from,
        s.valid_until,
        s.total_km,
        s.geom
    FROM transit_route r
    JOIN transit_route_shape s ON s.route_id = r.id
    WHERE r.code = p_route_code
      AND r.agency_id = p_agency_id
      AND s.valid_from <= p_date
      AND (s.valid_until IS NULL OR s.valid_until > p_date)
    ORDER BY s.version DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_route_shape_at_date IS 
    'Retorna el trazado (shape) de un ramal vigente en una fecha histórica específica. '
    'Útil para auditar reclamos o reconstruir itinerarios pasados.';

-- ============================================================================
-- 8. FUNCIÓN: CALCULAR PROGRESO DEL BUS EN RUTA (% recorrido)
-- ============================================================================
CREATE OR REPLACE FUNCTION get_bus_route_progress(
    p_bus_lat    DOUBLE PRECISION,
    p_bus_lon    DOUBLE PRECISION,
    p_route_code VARCHAR,
    p_agency_id  VARCHAR
)
RETURNS TABLE (
    route_code         VARCHAR,
    progress_percent   NUMERIC,
    distance_traveled_km NUMERIC,
    total_km           NUMERIC,
    nearest_point_geom GEOMETRY,
    deviation_meters   NUMERIC
) AS $$
DECLARE
    v_shape    GEOMETRY;
    v_total_km NUMERIC;
    v_bus_geom GEOMETRY;
    v_nearest  GEOMETRY;
    v_frac     DOUBLE PRECISION;
BEGIN
    -- Obtener el shape vigente
    SELECT s.geom, s.total_km
    INTO v_shape, v_total_km
    FROM transit_route r
    JOIN transit_route_shape s ON s.route_id = r.id
    WHERE r.code = p_route_code
      AND r.agency_id = p_agency_id
      AND s.valid_from <= CURRENT_DATE
      AND (s.valid_until IS NULL OR s.valid_until > CURRENT_DATE)
    ORDER BY s.version DESC
    LIMIT 1;

    IF v_shape IS NULL THEN
        RETURN;
    END IF;

    -- Crear punto del bus
    v_bus_geom := ST_SetSRID(ST_MakePoint(p_bus_lon, p_bus_lat), 4326);
    
    -- Punto más cercano en la línea
    v_nearest := ST_ClosestPoint(v_shape, v_bus_geom);
    
    -- Fracción del recorrido completado (0.0 a 1.0)
    v_frac := ST_LineLocatePoint(v_shape, v_bus_geom);
    
    -- Total km del shape calculado en km (si no está en la tabla)
    IF v_total_km IS NULL THEN
        v_total_km := ST_Length(v_shape::geography) / 1000.0;
    END IF;

    RETURN QUERY SELECT
        p_route_code,
        ROUND((v_frac * 100.0)::NUMERIC, 1),
        ROUND((v_frac * v_total_km)::NUMERIC, 2),
        ROUND(v_total_km::NUMERIC, 2),
        v_nearest,
        ROUND(ST_Distance(v_bus_geom::geography, v_nearest::geography)::NUMERIC, 0);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_bus_route_progress IS 
    'Calcula el porcentaje de progreso de un bus en su ruta, distancia recorrida y desviación.';

-- ============================================================================
-- 9. DATOS DE EJEMPLO: Rutas reales de la Agencia 004B detectadas en VMT
-- ============================================================================
-- Insertar los ramales reales observados en app_monitoreo_mensajeoperativo

INSERT INTO transit_route (code, name, agency_id, direction, origin, destination, description)
VALUES
    ('020c', 'Ramal 020C - Capiatá a Asunción', '004B', 'inbound',  'Terminal Capiatá', 'Asunción Centro', 'Ramal detectado en telemetría VMT'),
    ('020d', 'Ramal 020D - Capiatá a Asunción', '004B', 'inbound',  'Terminal Capiatá', 'Asunción Centro', 'Ramal detectado en telemetría VMT'),
    ('020e', 'Ramal 020E - Capiatá a Asunción', '004B', 'inbound',  'Terminal Capiatá', 'Asunción Centro', 'Ramal detectado en telemetría VMT'),
    ('020f', 'Ramal 020F - Asunción a Capiatá', '004B', 'outbound', 'Asunción Centro', 'Terminal Capiatá', 'Ramal detectado en telemetría VMT'),
    ('0210', 'Ramal 0210 - Circunvalación',     '004B', 'circular', 'Terminal Capiatá', 'Circunvalación',  'Ramal detectado en telemetría VMT'),
    ('0211', 'Ramal 0211 - Asunción a Capiatá', '004B', 'outbound', 'Asunción Centro', 'Terminal Capiatá', 'Ramal detectado en telemetría VMT'),
    ('0000', 'Sin Ramal / En Depósito',         '004B', 'inbound',  'Patio Maniobras',  'Taller Central',   'Unidad fuera de servicio o en patio')
ON CONFLICT (code, agency_id) DO UPDATE 
    SET name = EXCLUDED.name,
        direction = EXCLUDED.direction,
        description = EXCLUDED.description;

-- ============================================================================
-- 10. MODIFICAR telemetry_ping PARA VINCULAR CON SHAPES
-- ============================================================================
ALTER TABLE telemetry_ping 
    ADD COLUMN IF NOT EXISTS route_shape_id INTEGER REFERENCES transit_route_shape(id),
    ADD COLUMN IF NOT EXISTS geom           GEOMETRY(Point, 4326);

-- Índice espacial en telemetry_ping
CREATE INDEX IF NOT EXISTS idx_telemetry_ping_geom 
    ON telemetry_ping USING GIST (geom);

-- ============================================================================
-- 11. FUNCIÓN: AUTO-VINCULAR PING CON SHAPE VIGENTE
-- ============================================================================
CREATE OR REPLACE FUNCTION link_ping_to_shape()
RETURNS TRIGGER AS $$
BEGIN
    -- Asignar geometría puntual
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;

    -- Vincular con el shape vigente a la hora del ping
    IF NEW.route_id IS NOT NULL AND NEW.agency_id IS NOT NULL THEN
        SELECT s.id INTO NEW.route_shape_id
        FROM transit_route r
        JOIN transit_route_shape s ON s.route_id = r.id
        WHERE r.code = NEW.route_id
          AND r.agency_id = NEW.agency_id
          AND s.valid_from <= NEW.recorded_at::DATE
          AND (s.valid_until IS NULL OR s.valid_until > NEW.recorded_at::DATE)
        ORDER BY s.version DESC
        LIMIT 1;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Solo crear si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'trg_telemetry_link_shape'
    ) THEN
        CREATE TRIGGER trg_telemetry_link_shape
            BEFORE INSERT ON telemetry_ping
            FOR EACH ROW EXECUTE FUNCTION link_ping_to_shape();
    END IF;
END;
$$;

COMMENT ON FUNCTION link_ping_to_shape IS 
    'Trigger: asigna automáticamente la geometría PostGIS y el shape de ruta vigente a cada ping GPS insertado.';

\echo '✅ Schema de Shapes de Rutas con Vigencia Histórica creado exitosamente.'
\echo '   Tablas: transit_route, transit_route_shape, transit_stop, transit_route_stop'
\echo '   Vistas: v_active_route_shapes, v_active_stops'
\echo '   Funciones: get_route_shape_at_date(), get_bus_route_progress()'
\echo '   Trigger: trg_telemetry_link_shape (auto-vincula pings con shapes)'
