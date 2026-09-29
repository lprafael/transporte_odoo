"""
Actualiza ESPECIFICACIONES_TECNICAS.md y regenera ESPECIFICACIONES_TECNICAS.html
para reflejar que el sistema trabaja 100% desconectado del VMT, con autonomia operativa,
corrigiendo ademas el encoding y la numeracion de secciones.
"""
import re
import pathlib

def clean_mojibake(text):
    # Diccionario de correcion de secuencias con problemas de encoding
    replacements = {
        '\ufeff': '',
        'Ã\xad': 'í',
        'Ã³': 'ó',
        'Ã¡': 'á',
        'Ã©': 'é',
        'Ãº': 'ú',
        'Ã±': 'ñ',
        'Ã\x81': 'Á',
        'Ã\x89': 'É',
        'Ã\x8d': 'Í',
        'Ã\x93': 'Ó',
        'Ã\x9a': 'Ú',
        'Ã\x91': 'Ñ',
        'Ãš': 'Ú',
        'Ã‰': 'É',
        'Ã“': 'Ó',
        'Ã ': 'À',
        'â€”': '—',
        'â€“': '–',
        'Â°': '°',
        'â†’': '→',
        'â€¢': '•',
        'âœ“': '✓',
        'â— ': '●',
        'âˆ†': 'Δ',
        'â‰¥': '≥',
        'â‰¤': '≤',
        'Â¿': '¿',
        'Â¡': '¡',
        'Ã¼': 'ü',
        'Ã': 'í',  # residual
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def main():
    md_file = pathlib.Path('ESPECIFICACIONES_TECNICAS.md')
    content = md_file.read_text(encoding='utf-8', errors='ignore')
    content = clean_mojibake(content)

    # 1. Actualizar Capa 10 y 11 en el Resumen Ejecutivo
    old_capas = """10. **Capa de Programación Operativa CID (Servicios Especiales Eléctricos):**  
    Sincronización bidireccional del esquema `servicios_especiales.programacion_operativa` del CID/VMT hacia `transit.timetable` en Odoo, para los **908 cuadros de marcha oficiales** de los 6 ramales eléctricos exclusivamente (ids: 3, 8, 10).
11. **Capa de Conexión y Streaming Continuo con el VMT / CID:**  
    Servicio desacoplado en segundo plano (`odoo_transporte_vmt_sync`) que consulta continuamente cada 10 segundos la base de datos de producción del Viceministerio (`monitoreo.vmt.gov.py`) y sincroniza los shapes y paradas oficiales desde el CID (`bbdd-monitoreo-cid`)."""

    new_capas = """10. **Capa de Programación Operativa Soberana (Línea 20 Eléctrica):**  
    Administración y control directo en Odoo (`transit.timetable`) de los **692 despachos diarios oficiales** de los 6 ramales eléctricos (020c, 020d, 020e, 020f, 0210, 0211), con flexibilidad total para adecuar cuadros de marcha, frecuencias e intervalos sin depender de aprobaciones ni enlaces informáticos externos.
11. **Capa de Autonomía Operativa y Soberanía Tecnológica (100% Desconectado / Offline-Ready):**  
    Arquitectura autosuficiente con **cero dependencia operativa** de servidores o bases de datos del Viceministerio de Transporte (VMT). La telemetría ingresa directamente desde las unidades en calle hacia el broker interno vía MQTT (Protobuf v3) o REST; los trazados PostGIS, paradas y cuadros de marcha residen localmente en Odoo y PostgreSQL. La extracción inicial desde el CID se realizó exclusivamente como estrategia de migración/siembra rápida (data bootstrapping) por única vez, garantizando inmunidad ante caídas de servicios gubernamentales."""

    if old_capas in content:
        content = content.replace(old_capas, new_capas)
    else:
        # Regex replacement if minor char differences
        pattern = r"10\.\s+\*\*Capa de Programación Operativa CID.*?\n11\.\s+\*\*Capa de Conexión y Streaming Continuo.*?\n"
        content = re.sub(pattern, new_capas + "\n", content, flags=re.DOTALL)

    # 2. Actualizar Diagrama ASCII de Arquitectura
    old_diagram_pattern = r"\+---------------------------------------\+\s+\+---------------------------------------------\+\n\s+\|\s+BASE CENTRAL VMT \(PROD / CID\).*?\+---------------------------------------------------------\+\s+\+------------------------------------+\n"
    new_diagram = """                               +---------------------------------------------+
                               |          UNIDADES / BUSES EN CALLE          |
                               |   (Modem 4G / Validador / AVL Teltonika)    |
                               +---------------------------------------------+
                                           |                           |
                                           | Tramas Protobuf v3        | Pings HTTP POST
                                           | Topic MQTT GVMT           | (X-Device-Token)
                                           v                           v
                               +-------------------------+     +-------------------------+
                               |  MOSQUITTO MQTT BROKER  |     |     REST API INGESTA    |
                               | (Puerto 1883 / WS 9001) |     |  FastAPI (Puerto 8088)  |
                               +-------------------------+     +-------------------------+
                                           \\                          /
                                            \\                        /
                                             v                      v
                          +-------------------------------------------------+
                          |           MICROSERVICIO BROKER / INGESTOR       |
                          |            FastAPI / Python (Puerto 8088)       |
                          +-------------------------------------------------+
                          | - Ingesta masiva sin colapsar DB (<1ms)         |
                          | - Persistencia en Redis 7 (Estado RAM 0ms)      |
                          | - Linear Referencing PostGIS: ST_LineLocatePoint|
                          | - Detector de Pegonamiento (Headway & Bunching) |
                          | - Contextualizador de Calles (street_service.py)|
                          | - Transmisión en tiempo real vía WebSockets     |
                          | - Radar Leaflet (/map) & Tablero Lineal (/headway)
                          +-------------------------------------------------+
                                  |                                  |
                                  | Webhook consolidado (REST)       | Inserción asíncrona
                                  | SOLO en hitos operativos         | de pings y paradas
                                  v                                  v
+---------------------------------------------------------+   +------------------------------------+
|                   ODOO 18.0 ERP CORE                    |   |      POSTGRESQL 15 + POSTGIS 3.4   |
|            (Docker Container: Puerto 8069)              |   | (Docker: 5432, Host: 5434)         |
+---------------------------------------------------------+   +------------------------------------+
|  [custom_addons/transit_operations]                     |   | * telemetry_ping (Particionada)    |
|  * transit.route             * transit.dispatch         |   | * transit_route_shape (LineString) |
|    - 6 Ramales Línea 20        - Estados de viaje       |   |   - valid_from / valid_until       |
|    - Geocercas y Paradas       - Checklist seguridad    |   | * transit_stop (Point - 340 Paradas|
|    - Tarifas & Distancias      - Control puntualidad    |   | * transit_route_stop (Secuencia km)|
|  * transit.timetable         * account.move (SIFEN)     |   | * Vistas y Funciones espaciales:   |
|    - 692 Despachos Diarios     - CDC 44 dígitos Mod 11  |   |   - get_route_shape_at_date()      |
|    - Frecuencias por día       - Código QR e-Kuatia     |   |   - get_bus_route_progress()       |
|  * transit.ticket            * fleet.vehicle            |   |   - ST_LineLocatePoint / ST_Dist   |
|    - Emisión pasajes           - Activos, ITV, Seguro   |   |   - Trigger auto-vínculo de shape  |
+---------------------------------------------------------+   +------------------------------------+
"""
    content = re.sub(old_diagram_pattern, new_diagram, content, flags=re.DOTALL)

    # 3. Actualizar justificacion punto 5
    old_just_5 = "* **Aislamiento del Conector VMT:** El contenedor `vmt_sync` corre como un proceso independiente en bucle continuo; si la red pública de internet o la base de datos externa del Viceministerio experimenta latencia o microcortes, no afecta en absoluto la estabilidad de Odoo ni del broker interno."
    new_just_5 = "* **Autonomía Operativa Total (Offline-Ready):** El sistema opera con soberanía técnica absoluta y no depende de enlaces de red hacia el Viceministerio ni de servidores estatales. Si internet o los servicios del VMT se interrumpen, la empresa sigue despachando, fiscalizando, facturando vía SIFEN y controlando frecuencias en su red local/privada sin ninguna interrupción."
    content = content.replace(old_just_5, new_just_5)

    # 4. Reemplazar Seccion 9 completa
    old_sec_9_pattern = r"### 9\. Conector y Streaming Continuo con el Viceministerio \(VMT / CID\).*?(?=### 10\. Endpoints)"
    new_sec_9 = """### 9. Arquitectura de Autonomía Operativa y Soberanía de Datos (Offline-Ready)

El sistema está diseñado bajo el principio fundamental de **autonomía operativa plena y soberanía de datos**, eliminando cualquier dependencia de infraestructura externa en el día a día:

#### 9.1. Principio de No Dependencia de Servidores Externos
* **Operación Soberana:** Todos los procesos operacionales (despacho en terminales, inspección pre-operativa, control de headway en calle, facturación mensual consolidada SIFEN y cálculo de ETA) se ejecutan de manera 100% autosuficiente en los servidores propios de la empresa.
* **Cero Puntos Únicos de Fallo Gubernamentales:** Si la base central del VMT o los enlaces del Estado experimentan caídas, bloqueos de firewall, mantenimientos o lentitud, las operaciones de la Línea 20 no se ven afectadas en lo más mínimo.
* **Estrategia de Carga Inicial (Data Bootstrapping):** La interacción previa con las bases del CID (`bbdd-monitoreo-cid`) fue concebida exclusivamente como un **mecanismo de migración e importación por única vez (onboarding acelerado)**. Esto permitió cargar los 692 despachos oficiales y las 340 paradas homologadas con precisión métrica sin requerir semanas de digitación manual.
* **Gobierno Local de la Operación:** Toda la información cargada reside en PostgreSQL (`flota_db`) y en los modelos de Odoo (`transit.timetable`, `transit.route`, `transit_route_shape`), siendo propiedad directa de la empresa, que puede reconfigurar horarios, ramales o paradas según sus necesidades de tráfico.
* **Exportación Batch Opcional:** En caso de que normativas futuras exijan remitir auditorías o informes periódicos al Viceministerio, la arquitectura permite habilitar conectores de exportación asíncrona en segundo plano, sin interferir jamás en la ingesta de telemetría ni en la operación de tráfico.

---

"""
    content = re.sub(old_sec_9_pattern, new_sec_9, content, flags=re.DOTALL)

    # 5. Renumerar las secciones
    # Cambiar el segundo "### 11. Programación Operativa" por "### 12. Programación Operativa..."
    content = content.replace("### 11. Programación Operativa y Trazados de Servicios Eléctricos (Línea 20 VMT)", "### 12. Programación Operativa y Trazados de Servicios Eléctricos (Línea 20)")
    content = content.replace("#### 11.1. Arquitectura de Datos del Schema", "#### 12.1. Arquitectura de Datos del Schema")
    content = content.replace("#### 11.2. Mapeo Hacia el Modelo de Odoo", "#### 12.2. Mapeo Hacia el Modelo de Odoo")
    content = content.replace("#### 11.3. Distribución Consolidada de Salidas", "#### 12.3. Distribución Consolidada de Salidas")
    content = content.replace("#### 11.4. Shapes Vectoriales y Paradas", "#### 12.4. Shapes Vectoriales y Paradas")

    # Actualizar texto de introduccion de Seccion 12
    old_intro_12 = "El sistema integra y sincroniza de forma nativa la programación operativa oficial y los trazados vectoriales históricos de los **Servicios Eléctricos de Línea 20 (E1, E2 y E3)** desde la base de datos oficial del Centro de Información y Datos del VMT (`bbdd-monitoreo-cid`)."
    new_intro_12 = "El sistema almacena y gestiona en su base local `flota_db` de forma **100% autónoma y soberana** la programación operativa y los trazados vectoriales de los **Servicios Eléctricos de Línea 20 (E1, E2 y E3)**, habiendo utilizado la base del CID únicamente como estrategia de migración/siembra rápida (data bootstrapping) por única vez."
    content = content.replace(old_intro_12, new_intro_12)

    # Renumerar seccion 12 a 13
    content = content.replace("### 12. Guía de Ejecución y Pruebas Locales", "### 13. Guía de Ejecución y Pruebas Locales")
    content = content.replace("#### 12.1. Levantar los Servicios en Docker", "#### 13.1. Levantar los 5 Servicios Nucleares en Docker")
    content = content.replace("#### 12.2. Sincronización Oficial de Shapes y Paradas desde CID", "#### 13.2. Carga Inicial de Shapes y Paradas (Bootstrap / Migración por única vez)")
    content = content.replace("#### 12.3. Sincronización de la Programación Operativa (CID -> Odoo)", "#### 13.3. Carga Inicial de la Programación Operativa (Bootstrap / Migración por única vez)")
    content = content.replace("#### 12.4. Acceso a los Tableros de Control", "#### 13.4. Acceso a los Tableros de Control")
    content = content.replace("#### 12.5.a. API de ETA y Cumplimiento VMT", "#### 13.5.a. API de ETA y Cumplimiento Regulatorio")
    content = content.replace("#### 12.5. Pruebas de Homologación e Ingesta Masiva MQTT Protobuf v3", "#### 13.5.b. Pruebas de Homologación e Ingesta Masiva MQTT Protobuf v3")

    # Renumerar seccion 13 a 14 y 14 a 15
    content = content.replace("### 13. Resumen de Modelos y Archivos Clave del Repositorio", "### 14. Resumen de Modelos y Archivos Clave del Repositorio")
    content = content.replace("### 14. Nuevas Funcionalidades Avanzadas (Version 3.0.0)", "### 15. Nuevas Funcionalidades Avanzadas (Version 3.0.0)")
    content = content.replace("#### 14.1. ETA Predictivo por Parada (`eta_service.py`)", "#### 15.1. ETA Predictivo por Parada (`eta_service.py`)")
    content = content.replace("#### 14.2. Dashboard de Cumplimiento VMT (`compliance_service.py`)", "#### 15.2. Dashboard de Cumplimiento Regulatorio (`compliance_service.py`)")
    content = content.replace("#### 14.3. API de Bunching Mejorada (`/api/v1/bunching/alerts`)", "#### 15.3. API de Bunching Mejorada (`/api/v1/bunching/alerts`)")

    # Actualizar la lista de contenedores Docker (5 nucleares, sin vmt_sync requerido)
    old_docker_list = """Verifica que los 6 contenedores estén corriendo:
1. `odoo_transporte_app` → `http://localhost:8069` (ERP Odoo 18)
2. `odoo_transporte_db` → `localhost:5434` (PostgreSQL 15 + PostGIS 3.4)
3. `odoo_transporte_redis` → `localhost:6379` (Redis 7 con geocaché de calles y estado de flota)
4. `odoo_transporte_mosquitto` → `localhost:1883` y `9001` (Mosquitto MQTT con autenticación)
5. `odoo_transporte_gps_broker` → `http://localhost:8088` (Broker FastAPI con WebSockets, Headway y PostGIS)
6. `odoo_transporte_vmt_sync` → Daemon continuo de sincronización con la BD de VMT (cada 10s)."""

    new_docker_list = """Verifica que los 5 contenedores nucleares autónomos estén corriendo:
1. `odoo_transporte_app` → `http://localhost:8069` (ERP Odoo 18)
2. `odoo_transporte_db` → `localhost:5434` (PostgreSQL 15 + PostGIS 3.4)
3. `odoo_transporte_redis` → `localhost:6379` (Redis 7 con geocaché de calles y estado de flota en RAM)
4. `odoo_transporte_mosquitto` → `localhost:1883` y `9001` (Mosquitto MQTT para ingesta Protobuf v3 directa de buses)
5. `odoo_transporte_gps_broker` → `http://localhost:8088` (Broker FastAPI con WebSockets, Headway, PostGIS y ETA)

*(Nota: El sistema no requiere daemon de sincronización externa en bucle continuo, operando de manera 100% autónoma y desconectada).*"""

    content = content.replace(old_docker_list, new_docker_list)

    # Actualizar tabla de modelos/archivos para clarificar roles de scripts CID/VMT
    old_script_row = "| `sync_vmt_telemetry.py` | `scripts/sync_vmt_telemetry.py` | Conector continuo de telemetría desde BD VMT (Agencia 004B) hacia el broker interno."
    new_script_row = "| `sync_vmt_telemetry.py` | `scripts/sync_vmt_telemetry.py` | *Utilitario Opcional / Pruebas:* Herramienta de inyección de telemetría o testing offline (no requerida en producción autónoma)."
    content = content.replace(old_script_row, new_script_row)

    old_shape_row = "| `sync_cid_shapes_to_flota.py` | `scripts/sync_cid_shapes_to_flota.py` | Sincronizador de shapes vectoriales (LineString) desde CID a `transit_route_shape`."
    new_shape_row = "| `sync_cid_shapes_to_flota.py` | `scripts/sync_cid_shapes_to_flota.py` | *Script de Migración Inicial:* Carga inicial por única vez de los 46 shapes vectoriales históricos en PostGIS."
    content = content.replace(old_shape_row, new_shape_row)

    old_prog_row = "| `sync_cid_programacion_to_flota.py` | `scripts/sync_cid_programacion_to_flota.py` | Sincronizador de 692 despachos diarios de servicios especiales hacia `transit_timetable`."
    new_prog_row = "| `sync_cid_programacion_to_flota.py` | `scripts/sync_cid_programacion_to_flota.py` | *Script de Migración Inicial:* Carga inicial por única vez de los 692 despachos diarios hacia `transit_timetable` en Odoo."
    content = content.replace(old_prog_row, new_prog_row)

    md_file.write_text(content, encoding='utf-8')
    print("ESPECIFICACIONES_TECNICAS.md actualizado con éxito.")

if __name__ == '__main__':
    main()
