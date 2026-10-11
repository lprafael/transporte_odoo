# 🚌 Arquitectura Integral del ERP de Transporte (Poliverso Transit & Odoo 18)

Este documento detalla la arquitectura completa del sistema de gestión de transporte público, combinando el **ERP Odoo 18**, el **Microservicio de Telemetría GPS (FastAPI/PostGIS/Redis)**, los flujos de datos de **hardware/AVL** y el modelo de control regulatorio (**Resolución GVMT N° 065/2024 & Decreto N° 710/2023**).

---

## 1. Diagrama de Arquitectura General del Sistema

```mermaid
flowchart TB
    subgraph HARDWARE_EXTERNAL["Dispositivos en Ruta & Fuentes Externas"]
        GPS_BUS["📡 Equipos AVL / GPS en Buses\n(MQTT Protobuf v3 / HTTP REST)"]
        VMT_API["🏛️ Sincronizador Central VMT\n(monitoreo.vmt.gov.py)"]
        WAZE_API["🚦 Waze for Cities API\n(Alertas de Tráfico y Congestión)"]
    end

    subgraph INGESTION_BROKER["Microservicio GPS Broker (FastAPI :8088)"]
        MQTT_CONS["MQTT Consumer\n(Mosquitto :1883)"]
        HTTP_INGEST["HTTP Ingestion API\n(/api/v1/telemetry)"]
        GEO_ENGINE["Motor Geoespacial PostGIS\n(Matching de Shapes, Avance % y Geocercas)"]
        HEADWAY_ENG["Detector de Pegonamiento & Regularidad\n(Headway Engine)"]
        ETA_ENG["Motor de ETA Predictivo por Parada"]
        AUTH_GATEWAY["Módulo de Autenticación Unificada\n(Sesión Odoo flota_db)"]
    end

    subgraph STORAGE["Capa de Persistencia & Caché"]
        REDIS[("⚡ Redis 7\n(Estado de Flota en Vivo, TTL 5s\ny Alertas de Pegonamiento)")]
        POSTGRES[("🐘 PostgreSQL 15 + PostGIS\n(flota_db)\n- Traza de Rutas (LineString)\n- telemetry_ping particionado\n- Modelos ERP Odoo")]
    end

    subgraph ODOO_ERP["Odoo 18 ERP Central (:8069)"]
        direction TB
        M_TRANSIT["🚌 transit_operations\n(Concesionarias, Despachos, Rutas, Paradas, ICF)"]
        M_FLEET["🚐 fleet.vehicle\n(Flota de Buses, Odómetros, Sensores)"]
        M_HR["👨‍✈️ hr.employee\n(Conductores, Horarios, Turnos)"]
        M_CLEARING["💰 transit.clearing\n(Liquidación de Subsidios y Billetaje)"]
        M_SEC["🔐 res.users & res.partner\n(Multi-Tenant Concesionarias / Rol GVMT)"]
    end

    subgraph CLIENT_APPS["Interfaces de Usuario & Dashboards"]
        DASH_HEADWAY["📏 /headway\nTablero Lineal de Frecuencias\n(3 líneas, exclusión cabeceras)"]
        DASH_MAP["🗺️ /map\nRadar Satelital en Vivo\n(Leaflet + WebSockets)"]
        DASH_COMPLIANCE["📊 /compliance\nCumplimiento VMT e ICF Provisorio"]
        DASH_PASSENGER["📱 /parada/{codigo}\nPantalla QR Pasajeros con ETA"]
        ERP_BACKOFFICE["🖥️ Odoo Web Backend (:8069)\nGestión Administrativa y Operativa"]
    end

    %% Conexiones Hardware a Broker
    GPS_BUS -->|MQTT :1883| MQTT_CONS
    GPS_BUS -->|HTTP POST| HTTP_INGEST
    VMT_API -->|Sync Loop| HTTP_INGEST
    WAZE_API -->|Traffic Feed| GEO_ENGINE

    %% Flujo interno Broker
    MQTT_CONS --> GEO_ENGINE
    HTTP_INGEST --> GEO_ENGINE
    GEO_ENGINE <--> REDIS
    GEO_ENGINE <--> POSTGRES
    GEO_ENGINE --> HEADWAY_ENG
    GEO_ENGINE --> ETA_ENG

    %% Enlace Broker - Odoo
    GEO_ENGINE -->|Webhook Eventos / Odómetros| M_TRANSIT
    AUTH_GATEWAY <-->|JSON-RPC /web/session| M_SEC
    M_TRANSIT <--> POSTGRES

    %% Enlace a Dashboards
    HEADWAY_ENG --> DASH_HEADWAY
    REDIS --> DASH_MAP
    M_TRANSIT --> DASH_COMPLIANCE
    ETA_ENG --> DASH_PASSENGER
    M_SEC --> ERP_BACKOFFICE
```

---

## 2. Modelo de Datos Relacional del ERP (`transit_operations`)

El siguiente diagrama entidad-relación describe cómo interactúan las tablas operativas con los modelos nativos de Odoo (`fleet`, `hr`, `res_users`):

```mermaid
erDiagram
    res_users ||--o{ transit_concessionaire : "administra / pertenece"
    transit_concessionaire ||--|{ transit_service : "opera"
    transit_concessionaire ||--|{ fleet_vehicle : "es dueña de"
    transit_concessionaire ||--|{ hr_employee : "emplea"

    transit_service ||--|{ transit_route : "comprende ramales"
    transit_route ||--|{ transit_route_shape : "posee versiones de traza"
    transit_route ||--|{ transit_route_checkpoint : "define paradas oficiales"

    transit_route ||--|{ transit_timetable : "itinerarios programados"
    transit_timetable ||--|{ transit_dispatch : "genera"

    fleet_vehicle ||--o{ transit_dispatch : "asignado a vuelta"
    hr_employee ||--o{ transit_dispatch : "conduce vuelta"

    transit_dispatch ||--|{ transit_dispatch_checkpoint : "registra pasos reales vs previstos"
    transit_dispatch ||--o{ transit_clearing_settlement : "liquidado en"

    transit_concessionaire {
        int id PK
        string name "Consorcio Arapotí / Master Bus"
        string code "CONC-L20 / 004B"
        string vat_ruc "RUC legal"
        boolean active
    }

    transit_service {
        int id PK
        int concessionaire_id FK
        string name "Línea 20 (Troncal)"
        string code "L20"
        string service_type "electric / standard"
    }

    transit_route {
        int id PK
        int service_id FK
        string name "E1 - Asunción a J. Augusto Saldivar"
        string direction "outbound / inbound"
        float length_km "42.5"
    }

    transit_route_shape {
        int id PK
        int route_id FK
        geometry geom "LineString PostGIS SRID 4326"
        datetime valid_from
        datetime valid_until
        int version
    }

    transit_route_checkpoint {
        int id PK
        int route_id FK
        string name "Parada Terminal / Centro"
        geometry geom "Point PostGIS"
        float radius_meters "70.0"
        boolean is_terminal "Cabecera"
        int sequence
    }

    transit_dispatch {
        int id PK
        int service_id FK
        int route_id FK
        int vehicle_id FK
        int driver_id FK
        datetime scheduled_departure
        datetime actual_departure
        datetime actual_arrival
        string state "draft/scheduled/in_transit/completed/cancelled"
        string semaphore_color "green/yellow/red/purple/black"
        float provisorio_icf "Índice Cumplimiento Frecuencia"
        string franja_horaria "Punta Mañana / Valle / Punta Tarde"
    }

    fleet_vehicle {
        int id PK
        int concessionaire_id FK
        string name "BUS-104"
        string license_plate "AA 123 BB"
        float odometer "Km acumulados"
        string mean_id "Identificador VMT decimal"
    }

    hr_employee {
        int id PK
        int concessionaire_id FK
        string name "Nombre Conductor"
        string driver_license "Categoría A Profesional"
    }
```

---

## 3. Flujo de Autenticación de Sesión Unificada (Multi-Tenant)

El microservicio GPS en el puerto `:8088` comparte la misma sesión que Odoo en el puerto `:8069` mediante cookies conformes a **RFC 6265**:

```mermaid
sequenceDiagram
    autonumber
    actor Usuario as Operador / Regulador
    participant Browser as Navegador Web
    participant Broker as GPS Broker (:8088)
    participant Odoo as Odoo ERP (:8069)
    participant DB as PostgreSQL (flota_db)

    Usuario->>Browser: Accede a http://187.77.247.23:8088/headway
    Browser->>Broker: GET /headway (sin cookie)
    Broker-->>Browser: HTTP 303 Redirect -> /login?redirect=/headway
    Browser->>Usuario: Muestra pantalla de Login Unificado

    Usuario->>Browser: Ingresa usuario (admin) y contraseña
    Browser->>Broker: POST /login (credentials)
    Broker->>Odoo: JSON-RPC /web/session/authenticate (flota_db, admin, pass)
    Odoo-->>Broker: OK {uid: 2, name: "Administrator", session_id: "token_123"}

    Broker->>DB: Consulta roles y empresa de usuario (res_users -> transit_concessionaire)
    DB-->>Broker: Rol: Administrador Global / Todas las Empresas
    Broker-->>Browser: HTTP 303 Redirect -> /headway<br/>Set-Cookie: session_id=token_123; Path=/; HttpOnly; SameSite=lax

    Browser->>Broker: GET /headway (Cookie: session_id=token_123)
    Broker->>Broker: Valida session_id (Caché rápida 45s / Odoo get_session_info)
    Broker-->>Browser: HTTP 200 OK (Renderiza Tablero Lineal con badge "Administrator")

    opt Navegación a Odoo ERP
        Usuario->>Browser: Clic en botón "⚡ Odoo ERP" (:8069)
        Browser->>Odoo: GET http://187.77.247.23:8069/web (Cookie: session_id=token_123)
        Note over Odoo: Odoo detecta la MISMA cookie enviada por el navegador
        Odoo-->>Browser: Ingreso directo al backend sin pedir login
    end
```

---

## 4. Ciclo de Vida Operativo de un Despacho (`transit.dispatch`)

```mermaid
stateDiagram-v2
    [*] --> Borrador: Generador de Horarios / Matriz
    Borrador --> Programado: Asignación de Bus (fleet.vehicle) y Chofer (hr.employee)

    state "En Tránsito" as EnTransito {
        [*] --> SalidaCabecera: Detección Geocerca Salida (PostGIS)
        SalidaCabecera --> CirculandoRuta: Matching continuo con Shape Oficial
        CirculandoRuta --> VerificacionParadas: Registro de Checkpoints y Horarios
        VerificacionParadas --> CirculandoRuta: Dentro de tolerancia (<400m)
        CirculandoRuta --> AlertaDesvio: Desviación > 400m de traza
        AlertaDesvio --> CirculandoRuta: Retorno a traza oficial
    }

    Programado --> EnTransito: Ping GPS detecta salida de terminal
    EnTransito --> Completado: Detección Geocerca Llegada (Cabecera Destino)
    EnTransito --> Cancelado: Falla mecánica / No cumplimiento

    state "Auditoría Regulatoria VMT" as Auditoria {
        Completado --> ClasificacionSemaforo: Evaluación Res. 065/2024
        note right of ClasificacionSemaforo
            🟢 Cumplido al 100%
            🟡 Con retraso aceptable
            🔴 Déficit de frecuencia
            🟣 Desvío no autorizado
            ⚫ No realizado
        end note
        ClasificacionSemaforo --> CalculoICF: Cálculo ICF Provisorio por Franja
    }

    Auditoria --> LiquidacionSubsidio: transit.clearing
    LiquidacionSubsidio --> [*]
```

---

## 5. Resumen de Capas y Tecnologías

| Capa | Componente | Función Principal |
|---|---|---|
| **ERP Transaccional** | **Odoo 18 (`flota_db`)** | Gestión de flota, RRHH de choferes, planificación horaria, multi-tenant de concesionarias y liquidación financiera. |
| **Ingesta & Telemetría** | **FastAPI + Mosquitto MQTT** | Recepción de pings de buses a alta frecuencia (cada 3-5 seg) sin sobrecargar el ERP. |
| **Motor Geoespacial** | **PostGIS 15** | Shapes LineString, geocercas circulares, cálculo de `% de avance`, desvíos y vinculación bitemporal. |
| **Caché en Tiempo Real** | **Redis 7** | Estado de flota en memoria viva, latencia sub-milisegundo y detección de pegonamiento (*Bunching*). |
| **Regulación VMT** | **Motor de Reglas Res. 065** | Cálculo automatizado de franjas horarias (Puntas/Valle) y semáforo de cumplimiento para subsidios. |
