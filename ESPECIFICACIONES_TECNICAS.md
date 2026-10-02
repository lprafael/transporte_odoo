# Guía de Especificaciones Técnicas
## Sistema Integral de Control de Flota de Buses, Despacho Operativo, Facturación Electrónica SIFEN, Telemetría MQTT/Protobuf (Res. GVMT 065/2024), Motor Geoespacial PostGIS, ETA Predictivo por Parada, Dashboard de Cumplimiento VMT y Detector de Pegonamiento

> **Versión:** 3.0.0 | **Última actualización:** Septiembre 2026 | **Alcance:** Línea 20 Eléctrica (6 ramales: 020c, 020d, 020e, 020f, 0210, 0211 — 692 despachos diarios)

---

### 1. Resumen Ejecutivo y Alcance del Sistema

El sistema implementado en **Odoo 18.0** junto con el **Microservicio Broker de Telemetría GPS** y el broker **Mosquitto MQTT** constituye una plataforma de gestión 360° para empresas de transporte público de pasajeros y flotas comerciales, alineada plenamente a las normativas de la República del Paraguay (DNIT e-Kuatia y Viceministerio de Transporte - GVMT).

El sistema resuelve **once grandes capas** de negocio y tecnología:

1. **Capa Administrativa y de Mantenimiento (ERP / GMAO):**  
   Control de activos vehiculares, especificaciones técnicas de buses, vencimientos legales (ITV, Pólizas de Seguro, Habilitaciones), odometría y mantenimiento preventivo integrado a compras, inventario y talleres.
2. **Capa Operativa de Tráfico y Despacho:**  
   Definición de ramales e itinerarios, cuadros de marcha (frecuencias y horarios teóricos), órdenes de despacho diario, inspección pre-operativa obligatoria de seguridad (checklist mecánico de 5 puntos), control de desvíos y puntualidad con tablero Kanban en tiempo real.
3. **Capa Fiscal - Facturación Electrónica SIFEN (DNIT Paraguay / e-Kuatia):**  
   Liquidación y facturación electrónica periódica mensual consolidada por el monto global recaudado (evitando la inviable emisión individual por cada pasaje masivo). Cálculo estricto del **CDC de 44 dígitos con Módulo 11 ponderado**, generación de URL pública y código QR oficial para consulta en e-Kuatia, y conector listo para Denarius.
4. **Capa de Telemetría GPS, MQTT y Protocol Buffers (Res. GVMT N° 065/2024):**  
   Ingesta dual de alta frecuencia:
   - **MQTT sobre Mosquitto (QoS 1)** con soporte para tramas binarias compactas **Protocol Buffers v3** (`transit.proto`), según la especificación obligatoria para empresas de transporte y proveedores homologados (EPAS, Sitrack, etc.).
   - **REST HTTP** autenticado con `X-Device-Token` para módems y validadores convencionales.
5. **Capa Geoespacial PostGIS y Trazados con Vigencia Histórica Bi-Temporal:**  
   Almacenamiento de geometrías vectoriales (`LineString` y `Point` en WGS84 EPSG:4326), proyección espacial del avance del bus sobre el trazado oficial (`% de itinerario recorrido`), detección métrica de desvíos de ruta (`ST_Distance`) y soporte de **vigencia histórica bi-temporal** (`valid_from` y `valid_until`) para auditar qué trazado regía en cualquier fecha del pasado.
6. **Capa de Supervisión de Regularidad y Detector de Pegonamiento (Headway & Bunching):**  
   Tablero lineal interactivo (`/headway`) con proyección horizontal de cada ramal (0.0 km a total km), cálculo dinámico de la brecha métrica ($\Delta \text{km}$) y tiempo estimado de separación entre coches consecutivos, con alertas semafóricas automáticas ante pegonamiento crítico ($< 800\text{ m}$). API REST dedicada `/api/v1/bunching/alerts` para integración con paneles externos y notificaciones Odoo.
7. **Capa de Contextualización Urbana e Intersección Próxima:**  
   Motor de geocodificación en memoria y Redis (`street_service.py`) que resuelve en $< 1\text{ ms}$ la arteria exacta y la próxima esquina transversal hacia la que se dirige el bus: `Circulando (Calle X aproximándose a Calle Y)`, alimentado por las **340 paradas oficiales del CID/VMT** indexadas por kilometraje PostGIS.
8. **Capa de ETA Predictivo por Parada (Tiempo de Espera en Tiempo Real):**  
   Sistema de cálculo de tiempo de espera para pasajeros, sin aplicación nativa, accesible desde cualquier celular vía QR en la parada física. Calcula cuánto falta para que llegue el próximo eléctrico usando `ST_LineLocatePoint` PostGIS + velocidad media histórica de `telemetry_ping` (last 4h). Cache Redis de 20 segundos. Página móvil-first con auto-refresh cada 15s y código QR embebido.
9. **Capa de Cumplimiento Regulatorio VMT (Res. GVMT 065/2024):**  
   Dashboard interactivo en tiempo real (`/compliance`) que monitorea el cumplimiento de la cuota de **692 despachos diarios** exigida por la Resolución GVMT N° 065/2024. Muestra: % de cumplimiento actual, proyección al cierre del día, detalle por los 6 ramales, historial de 30 días, alertas automáticas de déficit crítico. Integrable vía API REST `/api/v1/compliance/today` y `/api/v1/compliance/alerts`.
10. **Capa de Programación Operativa Soberana (Línea 20 Eléctrica):**  
    Administración y control directo en Odoo (`transit.timetable`) de los **692 despachos diarios oficiales** de los 6 ramales eléctricos (020c, 020d, 020e, 020f, 0210, 0211), con flexibilidad total para adecuar cuadros de marcha, frecuencias e intervalos sin depender de aprobaciones ni enlaces informáticos externos.
11. **Capa de Autonomía Operativa y Soberanía Tecnológica (100% Desconectado / Offline-Ready):**  
    Arquitectura autosuficiente con **cero dependencia operativa** de servidores o bases de datos del Viceministerio de Transporte (VMT). La telemetría ingresa directamente desde las unidades en calle hacia el broker interno vía MQTT (Protobuf v3) o REST; los trazados PostGIS, paradas y cuadros de marcha residen localmente en Odoo y PostgreSQL. La extracción inicial desde el CID se realizó exclusivamente como estrategia de migración/siembra rápida (data bootstrapping) por única vez, garantizando inmunidad ante caídas de servicios gubernamentales.
12. **Capa Multi-Tenant y Gobernanza por Concesionaria (`ir.rule` Security Isolation):**  
    Arquitectura multi-empresa sobre una sola base de datos PostgreSQL/PostGIS. Cada empresa concesionaria (`transit.concessionaire`) cuenta con aislamiento lógico estricto: sus usuarios (despachadores, jefes de tráfico) solo pueden ver, despachar y auditar sus propios buses, rutas, horarios, choferes y boletos. El perfil de Administrador Global / Regulador (VMT) cuenta con visión 360° no restrictiva para fiscalizar la totalidad de la red metropolitana.


---

### 2. Arquitectura de Software y Topología de Red

```
                               +---------------------------------------------+
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
                                           \                          /
                                            \                        /
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
```

#### ¿Por qué una Arquitectura Desacoplada en Tres Niveles? (Justificación Técnica)
* **Protección del ERP:** Si 100 buses transmiten una trama cada 5 segundos, son **1.200 peticiones por minuto (72.000/hora)**. Enviar esta telemetría directamente al ORM de Odoo saturaría el pool de conexiones de PostgreSQL, degradando la facturación, contabilidad y compras.
* **Procesamiento en Redis:** El Broker almacena el estado instantáneo de la flota en Redis con latencia de sub-milisegundo.
* **Event-Driven:** A Odoo solo viaja la información de valor comercial: `"El bus 104 salió de terminal"`, `"Cruzó la parada Multiplaza"`, `"Excedió los 70 km/h"` o `"Finalizó el viaje con Odómetro 154218 km"`.
* **Cómputo Espacial en PostGIS:** El cálculo geométrico de si el bus se desvió del trazado o qué porcentaje del itinerario completó se delega al motor geoespacial nativo (`ST_LineLocatePoint`, `ST_Distance`), liberando a la CPU del servidor de aplicaciones.
* **Autonomía Operativa Total (Offline-Ready):** El sistema opera con soberanía técnica absoluta y no depende de enlaces de red hacia el Viceministerio ni de servidores estatales. Si internet o los servicios del VMT se interrumpen, la empresa sigue despachando, fiscalizando, facturando vía SIFEN y controlando frecuencias en su red local/privada sin ninguna interrupción.

---

### 3. Especificaciones Funcionales por Módulo

#### 3.1. Gestión de Flota y Activos (`fleet.vehicle`)
Extiende el módulo oficial `fleet` de Odoo 18:
* **Identificación del Bus:** Campo `bus_internal_number` (Número de Coche/Interno, ej: `01` al `30`).
* **Fabricante y Origen:** **Master Transportation Bus Manufacturing Ltd. (Master Bus)**, origen taiwanés. Complejo fabril y ensamblaje local instalado en Minga Guazú (Alto Paraná), dentro del Parque Tecnológico Inteligente de Taiwán, orientado al mercado nacional y exportación al Mercosur.
* **Modelos Homologados en el Sistema:**
  1. `Master Bus MB120NSE - 12m Piso Bajo Urbano (LTO Carga Rápida)`: 45 asientos, 25 parados (70 pasajeros totales), rampa de accesibilidad para movilidad reducida, batería LTO de 350 kWh y autonomía estimada de 280 km.
  2. `Master Bus MB90NSE - 9m Piso Bajo Urbano (LTO Carga Rápida)`: 32 asientos, 18 parados (50 pasajeros totales), rampa para sillas de ruedas, batería LTO de 260 kWh y autonomía estimada de 240 km.
  3. `Master Bus MB120Inter - 12m Interurbano (LTO Carga Rápida)`: 49 asientos reclinables, 10 parados (59 pasajeros totales), batería LTO de 380 kWh y autonomía de 320 km.
* **Electrificación y Tecnología de Baterías:** Tecnología de **Baterías LTO (Lithium Titanate Oxide / Titanato de Litio)** de carga ultra-rápida (15-20 minutos en cabecera/patio), conector estándar **GB/T** (Res. GVMT 065/2024), telemetría de estado de carga (`current_soc`), estado de salud (`current_soh` ~99.5%) y validación de pre-acondicionamiento térmico de cabina.
* **Flota Activa Vinculada (Sincronización CID / VMT):** 30 unidades 100% eléctricas (Coches 1 al 30) adjudicadas al Consorcio Arapoti (Agencia `004B` / Línea 20 Eléctrica), con chapas oficiales RUA (`IOT093` a `IOT129`), números de chasis (`RHVALCLE...`), IDSAM de validador de billetaje electrónico y certificados de Inspección Técnica Vehicular (ITV Ivesur) y seguros vigentes.
* **Equipamiento Operativo:** Aire Acondicionado de alta capacidad (`has_air_conditioning`), Rampa para sillas de ruedas / Movilidad Reducida (`has_wheelchair_ramp`), e Identificador del Validador de Billetaje (`validator_terminal_id`).
* **Control Legal y Vencimientos:** Fechas de expiración de **Inspección Técnica Vehicular (ITV)** y **Póliza de Seguros**, con semáforo dinámico de alerta:
  * `vigente` (Verde)
  * `por_vencer` (Amarillo: menos de 30 días)
  * `vencido` (Rojo: bloquea asignación en despachos)
* **Actualización Automática de Odómetro:** Cada viaje completado en `transit.dispatch` inyecta automáticamente la lectura en la tabla oficial `fleet.vehicle.odometer`.

#### 3.2. Gestión de Conductores (`res.partner`)
Extiende el modelo de contactos de Odoo para choferes y clientes:
* **Habilitación de Chofer:** Indicador `is_driver`.
* **Licencia de Conducir:** Categoría (`Profesional A`, `Profesional B`, etc.), número de registro, fecha de expedición y vencimiento.
* **Semáforo de Licencia:** Computado automáticamente (`valid`, `expiring_soon`, `expired`). Un chofer con licencia expirada no puede pasar la inspección de salida.
* **Datos Fiscales SIFEN:** Tipo de Documento (RUC, Cédula Paraguaya, Pasaporte), RUC con Dígito Verificador (DV) calculado.

#### 3.3. Rutas, Itinerarios y Trazados con Vigencia Histórica (`transit_route` & PostGIS)
* **Datos del Ramal:** Código de Línea (ej: `020f`, `020c`, `020d`), Sentido (`inbound` Ida, `outbound` Vuelta, `circular`), Distancia total en km y Tarifa estándar de pasaje.
* **Shapes de Rutas Bi-Temporales (`transit_route_shape`):**
  * Geometría completa del itinerario en formato `GEOMETRY(LineString, 4326)`.
  * Historial de vigencia temporal: `valid_from` (DATE) y `valid_until` (DATE, `NULL` si continúa vigente hoy).
  * Versión incremental (`version`). Un ramal puede tener trazados diferentes a lo largo del tiempo por desvíos viales u obras sin perder el historial.
* **Paradas Oficiales y Geocercas (`transit_stop`):**
  * Coordenadas puntuales en `GEOMETRY(Point, 4326)`.
  * Radio de geocerca en metros (`radius_meters`: 50m a 100m).
  * Vigencia temporal propia (`valid_from` / `valid_until`).
* **Secuencia de Paradas (`transit_route_stop`):**
  * Orden y tiempos teóricos acumulados desde la cabecera (`offset_minutes`), equivalente al estándar GTFS `stop_times`.

#### 3.4. Cuadro de Marchas y Programación Operativa hacia Adelante
* **Malla Maestra de Horarios (`transit.timetable`):**
  * Horarios programados clasificados por vigencia semanal: `all` (Todos los días), `weekday` (Lunes a Viernes), `weekend` (Sábados y Domingos), o días individuales (`0`=Lunes a `6`=Domingo).
  * Hora de salida en formato flotante (ej: `05.5` = 05:30 hs, `14.75` = 14:45 hs) para ordenamiento cronológico instantáneo.
  * Duración estándar de vuelta y código de servicio (ej: `S01`, `V04`).
* **Asistente de Generación Masiva de Programación Operativa (`transit.schedule.generator`):**
  * Diseñado para planificar la operación hacia adelante (mañana, próxima semana o el mes completo) en 1 solo clic.
  * **Criterios del Asistente:**
    * Rango de fechas: `Fecha Inicio` y `Fecha Fin`.
    * Selección de rutas/ramales a programar (o todas las rutas activas).
    * Modo de asignación de flota:
      * *Planificar servicios sin unidad:* Genera todas las órdenes de viaje en estado borrador (`draft`), permitiendo a la Jefatura de Tráfico asignar buses y choferes flexiblemente según la disponibilidad técnica del taller.
      * *Auto-asignar unidades rotativamente:* Distribuye equitativamente las unidades activas de la flota entre los servicios generados.
  * **Prevención de Duplicados:** Valida que no existan despachos previos no cancelados para el mismo horario y fecha.
  * **Clonado Automático de Geocercas Teóricas:** Al crearse cada despacho, el sistema hereda automáticamente todas las paradas del ramal (`transit.dispatch.checkpoint`), calculando la hora teórica exacta de paso (`scheduled_time = scheduled_departure + offset_minutes`).

#### 3.5. Despacho Diario, Telemetría y Control de Puntualidad / Headway (`transit.dispatch`)
Vincula: Unidad (`fleet.vehicle`) + Chofer (`res.partner`) + Horario Programado (`transit.timetable`):
* **Máquina de Estados Operativa:** `draft` &rarr; `inspected` &rarr; `dispatched` &rarr; `in_transit` &rarr; `completed` &rarr; `canceled`.
* **Checklist Pre-Operativo Obligatorio (Seguridad Vial):**
  * Neumáticos y Presión OK
  * Frenos de Servicio y Emergencia OK
  * Luces Reglamentarias e Indicadores OK
  * Fluidos Mecánicos (Aceite, Agua, Combustible) OK
  * Validador de Billetaje Operativo
  * *Regla de Validación:* Si un solo ítem está desmarcado o la licencia del chofer está vencida, el sistema bloquea la aprobación de la inspección.
* **Control Posterior de Despacho Puntual (Cabecera y Salida):**
  * **Captura de Salida:** Se registra manualmente mediante el botón del inspector o **100% automatizado por GPS Broker** en cuanto el bus abandona el polígono de la terminal origen.
  * **Métrica Exacta de Desvío:**  
    $$\text{Desvío (minutos)} = \frac{\text{Salida Real} - \text{Salida Programada}}{60}$$
  * **Semáforo Reglamentario de Cumplimiento (`compliance_status`):**
    * ðŸŸ¢ **Puntual (Â±3 min):** Salida dentro de la ventana de tolerancia reglamentaria (-1.0 a +3.0 minutos).
    * ðŸ”´ **Con Retraso (>3 min):** Salida demorada (mayor a 3 minutos).
    * ðŸŸ¡ **Adelantado (<-1 min):** Salida prematura (más de 1 minuto antes de hora, penalizado por romper la regularidad del intervalo/headway).
* **Control de Regularidad en Ruta (Checkpoints Intermedios):**
  * Cada parada intermedia geocercada compara en tiempo real `actual_time` vs `scheduled_time`, computando `delay_minutes` por hito hasta la llegada a terminal de destino (`actual_arrival`).
* **Vistas de Monitoreo, Control y Auditoría:**
  * **Tablero Kanban en Vivo:** Vista visual organizada por columnas de estado operativo con badges de puntualidad coloreados y alertas activas.
  * **Vista Calendario Mensual/Semanal (`calendar`):** Grilla temporal para visualizar la programación futura de servicios por unidad y chofer.
  * **Vista Pivot Multidimensional (`pivot`):** Cubo OLAP gerencial para auditoría de cumplimiento (% de puntualidad, promedio de retraso en minutos, km recorridos, pasajeros transportados y recaudación) agrupado por Ruta, Unidad, Chofer o Fecha.
  * **Vista Gráfica (`graph`):** Gráficos de barras para comparar rápidamente la puntualidad entre diferentes ramales o turnos.
* **Telemetría GPS en Vivo en el Despacho:**
  * Última latitud, longitud y velocidad instantánea.
  * Porcentaje de avance en el itinerario (`% completado`) y kilómetros recorridos.
  * Geocerca actual y metros de desvío de la traza oficial.
  * Alertas de Exceso de Velocidad (>70 km/h) y Desvío de Itinerario (>400m).

#### 3.6. Billetaje Operativo y Facturación Mensual Consolidada (`transit.ticket`)
* **Emisión Operativa de Boletos:** Emisión ágil de pasajes asociada a cada despacho (`transit.ticket`). Cada boleto registra fecha, hora, interno del bus, ramal y tarifa abonada (Efectivo, Tarjeta Billetaje / Validador, QR). Su función principal es el control de tráfico, conteo de pasajeros y arqueo diario de recaudación por chofer.
* **Facturación Electrónica Mensual Consolidada (SIFEN):**  
  Debido a la naturaleza del transporte público masivo (miles de transacciones diarias a tarifas fijas de 3.400 Gs o 4.000 Gs), emitir un comprobante fiscal SIFEN por cada pasajero individual es operativamente inviable y saturaría los servicios fiscales. En su lugar, el sistema implementa la **Facturación Periódica Consolidada**:
  1. El área contable selecciona los boletos confirmados del mes o período mediante el filtro predefinido *"Pendientes de Facturar"*.
  2. Ejecuta la acción masiva **"Generar Factura Electrónica Mensual Consolidada SIFEN"**.
  3. Odoo consolida el monto total acumulado, desglosa las líneas contables por ramal/itinerario, genera una única factura en `account.move` por el monto global a nombre de *Consumidor Final / Recaudación Mensual* (o a nombre de la empresa liquidadora de billetaje / VMT), calcula el **CDC de 44 dígitos** y genera el **código QR oficial**.
  4. Todos los boletos incluidos quedan enlazados a la factura mensual (`invoice_id`) y cambian automáticamente su estado a `invoiced`.

---

### 4. Especificaciones del Módulo SIFEN (DNIT Paraguay)

Cumple con la normativa técnica de Facturación Electrónica de la República del Paraguay:

#### 4.1. Código de Control (CDC) de 44 Dígitos
Estructura algorítmica del CDC implementada en `sifen_util.py` para facturas mensuales consolidadas y facturas a clientes corporativos:
$$\text{CDC} = \text{TipoDoc (2)} + \text{RUC (8)} + \text{DV (1)} + \text{Establecimiento (3)} + \text{PuntoExp (3)} + \text{Secuencia (7)} + \text{TipoContrib (1)} + \text{Fecha (8)} + \text{TipoEmision (1)} + \text{CodSeguridad (9)} + \text{DV\_CDC (1)}$$

* **Código de Seguridad:** 9 dígitos aleatorios criptográficamente seguros.
* **Dígito Verificador (Módulo 11 Ponderado):** Pesos cíclicos del **2 al 11** aplicados de derecha a izquierda sobre los primeros 43 dígitos. Si el residuo es 0, el DV es 0; si es 1, el DV es 1; en los demás casos, es $11 - \text{residuo}$.

#### 4.2. Código QR y Consulta Pública en e-Kuatia
* URL de consulta oficial: `https://ekuatia.set.gov.py/consultas/qr?nVersion=150&Id={CDC}&...`
* Generación de imagen QR en base64 para impresión en el boleto / factura electrónica (KUDE).

#### 4.3. Modelo de Facturación Consolidada de Pasajes (Monto Global Periódico)
* **Receptor Fiscal:** Emitida a nombre de *Consumidor Final (Recaudación Mensual Consolidada)* con RUC innominado (`44444401-7`), o a nombre de la entidad liquidadora del sistema de billetaje electrónico (ej: Pronet / TDP / Jaha / Más) o subsidio estatal VMT.
* **Cuentas Contables Integradas:** Imputación automática a la cuenta de ingresos *4.1.01.01 Ingresos por Venta de Pasajes* contra *1.1.02.01 Clientes por Pasajes a Cobrar*.
* **Trazabilidad Total:** Cada boleto individual emitido por los buses o terminales mantiene la referencia exacta a la factura electrónica mensual en la que fue consolidado.

---

### 5. Especificación del Protocolo MQTT, Protobuf y Microservicio Receptor (Res. GVMT N° 065/2024)

El sistema incorpora la arquitectura de mensajería y el estándar regulatorio exigido por el Viceministerio de Transporte (Paraguay) mediante la **Resolución GVMT N° 065/2024**:

#### 5.1. Broker Mosquitto MQTT y Transporte de Red
* **Contenedor:** `odoo_transporte_mosquitto` (Eclipse Mosquitto 2.1.2).
* **Protocolos:** MQTT versión 3.1.1 o 5.0.
* **Puertos:** `1883` (TCP plano / red interna) y `9001` (WebSocket para clientes web).
* **Calidad de Servicio (QoS):** QoS 1 (*At least once* / Al menos una vez) con persistencia en disco activada (`mosquitto.db`).
* **Estructura Jerárquica del Topic:**
  $$\text{transporte/flota/}\{\text{agency\_id}\}/\text{operacion}$$
  *Ejemplo:* `transporte/flota/004B/operacion` (para la Empresa La Limpeña / Línea 20).
* **Autenticación y Seguridad:** Autenticación por contraseña hasheada (PBKDF2/SHA-512) y listas de control de acceso (ACLs) para aislar tópicos por operadora.

#### 5.2. Esquema Oficial Protocol Buffers v3 (`transit.proto`)
El payload recibido corresponde al binario serializado del contrato de interfaz oficial:

```protobuf
syntax = "proto3";
package transit.telemetry;

import "google/protobuf/timestamp.proto";

message Operation {
  enum OperationType {
    INICIADO   = 0;    // Bus inicia recorrido (salida de cabecera)
    FINALIZADO = 1;    // Bus concluye servicio (llegada a terminal)
    OPERANDO   = 2;    // Coordenada periódica en ruta (cada 10s)
    SUSPENDIDO = 3;    // Servicio cancelado / auxilio mecánico
  }

  // Identificadores y Requeridos
  int32  identidad = 1;                     // ID de la entidad emisora
  string agency_id = 2;                    // Identificador de la Empresa Operadora (ej: "004B")
  string mean_id = 3;                      // Identificador del bus (interno o matrícula, ej: "00016")
  string route_id = 4;                     // Identificador de la ruta o ramal asignado (ej: "020f")
  string driver_id = 5;                    // Identificador del chofer (cédula o legajo)
  OperationType type = 6;                  // Estado operativo del servicio
  int32  accuracy = 7;                     // Precisión GPS en metros
  double latitude = 8;                     // Latitud en grados decimales (WGS 84)
  double longitude = 9;                    // Longitud en grados decimales (WGS 84)
  google.protobuf.Timestamp datetime = 13; // Fecha y hora UTC del envío del satélite

  // Campos Opcionales / Cinemática
  double altitude = 10;                    // Altitud sobre el nivel del mar en metros
  double bearing = 11;                     // Rumbo angular del vehículo (0° a 360°)
  double speed = 12;                       // Velocidad instantánea en km/h
}
```

* **Ventajas de Eficiencia:** La trama binaria empaquetada ocupa únicamente **~70 a 97 bytes** frente a los ~350 bytes de un JSON equivalente, logrando un ahorro del **80% en tráfico de datos 4G**.
* **Compilación Nativa:** Compilado con `protoc` / `grpcio-tools` generando [`gps_broker/proto/transit_pb2.py`](file:///c:/Users/lpraf/OneDrive/Documentos/Poliverso/transporte_odoo/gps_broker/proto/transit_pb2.py), garantizando deserialización en C++/Python de máxima velocidad con fallback de emergencia integrado en [`decoder.py`](file:///c:/Users/lpraf/OneDrive/Documentos/Poliverso/transporte_odoo/gps_broker/proto/decoder.py).

#### 5.3. Frecuencia y Temporización Oficial
* **Frecuencia de Transmisión:** Un (1) mensaje cada diez (10) segundos por móvil en estado operativo (`OPERANDO`).
* **Ventana de Timeout y Detección de Desconexión:** Tolerancia máxima de sesenta (60) segundos sin reporte. Tras 60 segundos de inactividad, Redis marca el móvil como *Desconectado / Sin Señal*.

#### 5.4. Validaciones Físicas y Filtros del Ingestor
* **Validación de Coordenadas Geográficas:** Se rechazan y loguean tramas con latitud fuera del rango $[-90, 90]$ o longitud fuera del rango $[-180, 180]$. Se descartan de forma estricta tramas con coordenadas $(0.0, 0.0)$ o sin fijación satelital.
* **Filtro de Precisión GPS (`accuracy`):** Si `accuracy > 50` metros, el registro se persiste para auditoría pero se marca con bandera de baja precisión, suspendiendo el disparo de geocercas para prevenir falsos positivos de llegada o salida.

#### 5.5. Capa de Eventos hacia Odoo 18 (Webhooks Resilientes)
El ingestor únicamente emite peticiones HTTP hacia Odoo (`POST /api/v1/transit/events`) cuando ocurre una transición de negocio relevante:
1. **Transición a `INICIADO` (0):** Marca la salida de cabecera e inicia el cómputo del despacho.
2. **Cruce Validado de Geocerca (Checkpoint):** Al ingresar al radio de una parada oficial (tolerancia 50m a 100m).
3. **Transición a `FINALIZADO` (1):** Cierre de despacho, cálculo de duración total y lectura del odómetro final del bus.
4. **Detección de Desvío Sostenido:** Desviación ortogonal de la ruta oficial superior a la tolerancia configurada sostenida en el tiempo.
* **Resiliencia de Red:** Las llamadas a Odoo se gestionan en segundo plano con reintentos automáticos y **Exponential Backoff** ($2^n$ segundos de espera) ante eventuales reinicios o microcortes del ERP.

#### 5.6. Requerimientos No Funcionales y Homologación
* **Capacidad de Concurrencia:** Ingesta de al menos **500 mensajes/segundo** sostenidos sin encolamiento en RAM ni pérdida de paquetes.
* **Latencia de Procesamiento:** Tiempo entre la recepción del paquete MQTT y su actualización en Redis **< 50 ms**.
* **Disponibilidad:** 99.8% con reinicio automático de contenedores (`restart: unless-stopped`).

---

### 6. Motor Geoespacial PostGIS y Trazados con Vigencia Histórica

#### 6.1. Esquema de Base de Datos Espacial (`scripts/setup_route_shapes.sql` y `scripts/setup_telemetry_db.sql`)
La persistencia histórica se apoya en PostgreSQL 15 con PostGIS 3.4 y particionado mensual para evitar el *table bloat*:

```sql
-- 1. Tabla de telemetría GPS particionada por mes (Resolución GVMT 065/2024 Sección 4.1)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE telemetry_ping (
    id BIGSERIAL,
    agency_id VARCHAR(32) DEFAULT '004B',
    bus_internal_code VARCHAR(32) NOT NULL,
    license_plate VARCHAR(32),
    route_id VARCHAR(32),
    driver_id VARCHAR(64),
    operation_type SMALLINT NOT NULL DEFAULT 2,     -- 0: INICIADO, 1: FINALIZADO, 2: OPERANDO, 3: SUSPENDIDO
    accuracy_m INTEGER,                              -- Precisión GPS (metros)
    geom GEOMETRY(Point, 4326),                      -- Geometría WGS84 puntual
    altitude_m NUMERIC(6, 2),                        -- Altitud s.n.m.
    heading_deg NUMERIC(5, 2),                       -- Rumbo (0° - 360°)
    speed_kmh NUMERIC(5, 2) DEFAULT 0.0,             -- Velocidad instantánea
    odometer_km NUMERIC(10, 2) DEFAULT 0.0,
    recorded_at TIMESTAMPTZ NOT NULL,                -- Timestamp UTC del satélite
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- Índices optimizados para auditoría espacial y temporal
CREATE INDEX idx_telemetry_agency_bus_time 
    ON telemetry_ping (agency_id, bus_internal_code, recorded_at DESC);
CREATE INDEX idx_telemetry_ping_geom 
    ON telemetry_ping USING GIST (geom);
```

```sql
-- 1. Trazados de ruta con vigencia bi-temporal
CREATE TABLE transit_route_shape (
    id              BIGSERIAL PRIMARY KEY,
    route_id        INTEGER NOT NULL REFERENCES transit_route(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL DEFAULT 1,
    valid_from      DATE NOT NULL,
    valid_until     DATE,                          -- NULL = vigente actualmente
    geom            GEOMETRY(LineString, 4326) NOT NULL,
    total_km        NUMERIC(8, 2),
    shape_source    VARCHAR(50) DEFAULT 'vmt_import',
    notes           TEXT,
    CONSTRAINT uq_route_shape_version UNIQUE (route_id, version),
    CONSTRAINT chk_valid_dates CHECK (valid_until IS NULL OR valid_until > valid_from)
);

-- 2. Paradas y geocercas
CREATE TABLE transit_stop (
    id              BIGSERIAL PRIMARY KEY,
    stop_code       VARCHAR(20) NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    stop_type       VARCHAR(20) NOT NULL DEFAULT 'stop',
    agency_id       VARCHAR(32),
    valid_from      DATE NOT NULL,
    valid_until     DATE,
    geom            GEOMETRY(Point, 4326) NOT NULL,
    radius_meters   INTEGER NOT NULL DEFAULT 70,
    address         TEXT
);
```

#### 6.2. Funciones Espaciales Clave

1. **`get_bus_route_progress(lat, lon, route_code, agency_id)`**:
   Proyecta el punto del bus sobre la línea del shape vigente utilizando `ST_LineLocatePoint`.
   Retorna:
   - `progress_percent`: Porcentaje completado del recorrido (0.0% a 100.0%).
   - `distance_traveled_km`: Kilómetros avanzados en el itinerario.
   - `total_km`: Longitud total del trazado.
   - `deviation_meters`: Distancia ortogonal en metros entre el bus y el eje de la ruta oficial (`ST_Distance`).
2. **`get_route_shape_at_date(route_code, agency_id, date)`**:
   Retorna el trazado exacto que estaba legalmente vigente en una fecha histórica específica, resolviendo:
   $$\text{valid\_from} \le \text{fecha} \quad \text{y} \quad (\text{valid\_until} \text{ IS NULL} \lor \text{valid\_until} > \text{fecha})$$
3. **Trigger `trg_telemetry_link_shape`**:
   Ejecutado automáticamente en cada `INSERT` sobre la tabla `telemetry_ping`:
   - Construye el punto PostGIS: `geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)`.
   - Busca y vincula la clave foránea `route_shape_id` correspondiente a la versión vigente en el momento en que se emitió el ping.

#### 6.3. Trazados y Paradas Oficiales Homologadas (Base CID / VMT)

Mediante el script [`scripts/sync_cid_shapes_to_flota.py`](file:///c:/Users/lpraf/OneDrive/Documentos/Poliverso/transporte_odoo/scripts/sync_cid_shapes_to_flota.py) y [`scripts/sync_cid_stops_to_flota.py`](file:///c:/Users/lpraf/OneDrive/Documentos/Poliverso/transporte_odoo/scripts/sync_cid_stops_to_flota.py) se sincronizaron directamente desde la base central CID (`bbdd-monitoreo-cid`) los 6 ramales operativos oficiales de la Empresa La Limpeña SRL (Línea 20 - Agencia 004B) con sus respectivas geometrías, fechas de vigencia y **340 paradas oficiales**:

| Ramal | Sentido | Origen Oficial | Destino Oficial | Longitud | Paradas CID |
| :---: | :---: | :--- | :--- | :---: | :---: |
| **020c** | `inbound` (Ida) | San Lorenzo (Azara) | Asunción Centro (Puerto) | 18.28 km | 37 paradas |
| **020d** | `outbound` (Vuelta) | Asunción Centro (Puerto) | San Lorenzo (Azara) | 18.02 km | 45 paradas |
| **020e** | `inbound` (Ida) | San Lorenzo (Azara) | Asunción Centro (Puerto) | 18.92 km | 56 paradas |
| **020f** | `outbound` (Vuelta) | Asunción Centro (Puerto) | San Lorenzo (Azara) | 18.91 km | 77 paradas |
| **0210** | `inbound` (Ida) | Luque (Rotonda Aeropuerto) | Asunción Centro (Puerto) | 18.33 km | 56 paradas |
| **0211** | `outbound` (Vuelta) | Asunción Centro (Puerto) | Luque (Rotonda Aeropuerto) | 18.84 km | 69 paradas |

#### 6.4. Paradas Oficiales y Referenciación Lineal PostGIS (`transit_stop` & `transit_route_stop`)
Cada una de las **340 paradas oficiales** se encuentra georreferenciada y proyectada ortogonalmente sobre el shape correspondiente mediante la función PostGIS:
$$\text{distance\_from\_origin\_km} = \text{ST\_LineLocatePoint}(\text{shape\_geom}, \text{stop\_geom}) \times \text{total\_km}$$
Esto permite determinar con precisión métrica la distancia en kilómetros desde el punto de partida hasta cada parada, sirviendo como hito de control temporal e intersección física para los tableros de control.

---

### 7. Tablero Lineal de Frecuencias y Detector de Pegonamiento (Headway & Bunching)

El módulo [`gps_broker/headway_service.py`](file:///c:/Users/lpraf/OneDrive/Documentos/Poliverso/transporte_odoo/gps_broker/headway_service.py) expone una interfaz visual interactiva de última generación orientada a los controladores de tráfico y despachadores:

#### 7.1. Modelo Matemático de Regularidad e Intervalos (Headway)
Para cada ramal activo, los buses en circulación (`IN_TRANSIT`) se ordenan de menor a mayor avance métrico a lo largo de la traza ($0.0\text{ km} \le d_i \le L$).
Para cada par de coches consecutivos (donde $b_{\text{leader}}$ precede a $b_{\text{trailer}}$):
$$\Delta d = d_{\text{leader}} - d_{\text{trailer}} \quad (\text{en km})$$
$$\Delta t_{\text{est}} = \Delta d \times 2.4 \quad (\text{minutos estimados a } 25\text{ km/h en régimen urbano})$$

#### 7.2. Clasificación Semafórica de Intervalos y Alerta de Pegonamiento
El algoritmo clasifica instantáneamente la brecha entre unidades según las normas operativas de transporte masivo:
* ðŸš¨ **CRITICAL (Pegonamiento / Bus Bunching):**  
  $\Delta d < 0.8\text{ km}$ ($< 800\text{ m}$ o $< 2.0\text{ min}$).  
  Indica que dos o más colectivos circulan prácticamente juntos. El coche puntero viaja saturado de pasajeros mientras que el de atrás viaja vacío, destruyendo la regularidad de la frecuencia. Se activa una animación pulsante roja sobre la línea y sobre los buses involucrados.
* âš ï¸ **WARNING (Intervalo Corto):**  
  $0.8\text{ km} \le \Delta d \le 1.5\text{ km}$ ($2.0\text{ a } 3.6\text{ min}$).  
  Riesgo inminente de pegonamiento si el primer bus se detiene en paradas densas.
* ðŸŸ¢ **OPTIMAL (Intervalo Regular):**  
  $1.5\text{ km} < \Delta d \le 5.5\text{ km}$ ($3.6\text{ a } 13.2\text{ min}$).  
  Frecuencia óptima y servicio equilibrado.
* â³ **GAP (Hueco Excesivo / Vacío de Servicio):**  
  $\Delta d > 5.5\text{ km}$ ($> 13.2\text{ min}$).  
  Hueco que genera esperas prolongadas en las paradas.

#### 7.3. Componentes Visuales del Tablero Lineal (`/headway`)
1. **Línea Recta Horizontal por Ramal:** Cada ramal se representa como un riel horizontal continuo de $0\%$ a $100\%$ con etiquetas de cabecera origen ($0.0\text{ km}$) y destino final.
2. **Hitos Kilométricos Dinámicos:** Marcas de escala cada $25\%$ ($0\text{ km}$, $25\%$, $50\%$, $75\%$, $100\%$).
3. **Marcadores de Buses en Tiempo Real:** Iconos de coches ubicados exactamente en su porcentaje de recorrido, mostrando interno y velocidad instantánea.
4. **Segmentos Conectores de Intervalo:** Cintas coloreadas entre coches consecutivos que muestran la distancia métrica y minutos estimados ($\Delta \text{km}$ y $\Delta \text{min}$).
5. **Tabla de Auditoría en Vivo:** Detalle por unidad de: Coche, Estado Contextual, Velocidad, Kilómetro en Shape, Desvío del Eje (m), Hora del último ping y Diagnóstico de Intervalo.
6. **Refresco Reactivo:** Polling optimizado cada 3 segundos (`setInterval(fetchHeadwayData, 3000)`) consumiendo `/api/v1/headway/data`.

---

### 8. Motor de Contextualización Urbana e Intersección Próxima (`street_service.py`)

Para que la supervisión operativa y la experiencia del usuario no dependan de frías coordenadas geográficas ni de porcentajes abstractos, el módulo [`gps_broker/street_service.py`](file:///c:/Users/lpraf/OneDrive/Documentos/Poliverso/transporte_odoo/gps_broker/street_service.py) resuelve el estado contextual de cada colectivo en tiempo real:

$$\text{Estado:} \quad \mathbf{\text{Circulando (Calle X aproximándose a Calle Y)}}$$
*Ejemplos resueltos en vivo:*
* `Circulando (Av. Mcal. López aproximándose a Cnel. Escurra)`
* `Circulando (Av. Aviadores del Chaco aproximándose a Prócer Juan Manuel Iturbe)`
* `Circulando (Calle Azara aproximándose a Brasil)`

#### 8.1. Arquitectura de Caché Multi-Nivel (< 1 ms de latencia)
1. **Nivel 1 (Memoria RAM del Proceso):** Diccionario LRU indexado por cuadrícula geoespacial de $\approx 100\text{ metros}$ (`round(lat, 3)`, `round(lon, 3)`).
2. **Nivel 2 (Redis Geocache):** Claves `street_grid:{lat3}:{lon3}` con TTL de 30 días, compartidas entre todos los workers y contenedores.
3. **Nivel 3 (Motor Geocodificador con Resiliencia):** Reverse-geocoding solo ejecutado en la primera pasada por una celda desconocida, evitando bloqueos o rate-limits.

#### 8.2. Normalización de Nomenclatura del Gran Asunción
El servicio incluye expresiones regulares optimizadas para abreviar y formalizar arterias metropolitanas:
* `Avenida Mariscal Francisco Solano López` &rarr; `Av. Mcal. López`
* `Avenida Aviadores del Chaco` &rarr; `Av. Aviadores del Chaco`
* `Ruta Nacional Mariscal Estigarribia` &rarr; `Ruta PY02 (Mcal. Estigarribia)`
* `Félix de Azara` &rarr; `Calle Azara`
* `General / Coronel / Mariscal` &rarr; `Gral. / Cnel. / Mcal.`

#### 8.3. Detección de Intersección por Paradas Homologadas
El cruce transversal próximo no requiere consultar cartografía pesada: el motor compara el kilometraje lineal actual del bus ($d_{\text{bus}}$) contra el vector en memoria de las 340 paradas oficiales del ramal, seleccionando la primera parada ubicada adelante ($d_{\text{stop}} \ge d_{\text{bus}} - 0.02\text{ km}$) y extrayendo el nombre de la calle que cruza (*source_name* oficial del CID).

---

### 9. Arquitectura de Autonomía Operativa y Soberanía de Datos (Offline-Ready)

El sistema está diseñado bajo el principio fundamental de **autonomía operativa plena y soberanía de datos**, eliminando cualquier dependencia de infraestructura externa en el día a día:

#### 9.1. Principio de No Dependencia de Servidores Externos
* **Operación Soberana:** Todos los procesos operacionales (despacho en terminales, inspección pre-operativa, control de headway en calle, facturación mensual consolidada SIFEN y cálculo de ETA) se ejecutan de manera 100% autosuficiente en los servidores propios de la empresa.
* **Cero Puntos Únicos de Fallo Gubernamentales:** Si la base central del VMT o los enlaces del Estado experimentan caídas, bloqueos de firewall, mantenimientos o lentitud, las operaciones de la Línea 20 no se ven afectadas en lo más mínimo.
* **Estrategia de Carga Inicial (Data Bootstrapping):** La interacción previa con las bases del CID (`bbdd-monitoreo-cid`) fue concebida exclusivamente como un **mecanismo de migración e importación por única vez (onboarding acelerado)**. Esto permitió cargar los 692 despachos oficiales y las 340 paradas homologadas con precisión métrica sin requerir semanas de digitación manual.
* **Gobierno Local de la Operación:** Toda la información cargada reside en PostgreSQL (`flota_db`) y en los modelos de Odoo (`transit.timetable`, `transit.route`, `transit_route_shape`), siendo propiedad directa de la empresa, que puede reconfigurar horarios, ramales o paradas según sus necesidades de tráfico.
* **Exportación Batch Opcional:** En caso de que normativas futuras exijan remitir auditorías o informes periódicos al Viceministerio, la arquitectura permite habilitar conectores de exportación asíncrona en segundo plano, sin interferir jamás en la ingesta de telemetría ni en la operación de tráfico.

---

### 10. Endpoints de la API del Microservicio Broker (:8088)

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/v1/telemetry` | Ingesta masiva HTTP de pings GPS con token. Evalúa geocercas, resuelve calle/intersección, calcula avance en PostGIS y emite por WebSocket. |
| `POST` | `/telemetry/gps` | Alias unificado para ingesta de telemetría desde módem, scripts de streaming o reenvíos MQTT. |
| `WS` | `/ws/live` | **Canal WebSocket en Vivo:** Transmisión reactiva de 0 ms con coordenadas, progreso, velocidad, estado contextual y alertas de flota. |
| `GET` | `/api/v1/live` | Retorna el estado en tiempo real de todos los buses (`status_display`, `street_name`, `approaching`), alertas y capas GeoJSON. |
| `GET` | `/headway` | **Tablero Lineal de Intervalos & Pegonamiento:** Vista HTML interactiva con proyección de buses sobre líneas rectas horizontales y semáforo de regularidad. |
| `GET` | `/api/v1/headway/data` | JSON optimizado para el tablero lineal: brechas en km ($\Delta \text{km}$), tiempos estimados, banderas de pegonamiento y auditoría por bus. |
| `GET` | `/map` | **Radar Web Satelital en Vivo:** Dashboard Leaflet con dibujo de rutas vectoriales, paradas, selector de vigencia histórica y cartografía CARTO Dark Matter. |
| `GET` | `/api/v1/shapes/active` | Retorna las geometrías `LineString` de todas las rutas vigentes hoy en formato GeoJSON FeatureCollection. |
| `GET` | `/api/v1/shapes/history` | Consulta el trazado que regía en una fecha pasada (`?route_code=020f&agency_id=004B&date=YYYY-MM-DD`). |
| `GET` | `/api/v1/stops/active` | Retorna las 340 paradas y radios de geocerca activos en formato GeoJSON FeatureCollection. |
| `GET` | `/api/v1/routes` | Catálogo maestro de los 6 ramales oficiales y sus versiones activas de trazado. |
| `POST` | `/api/v1/test_mqtt_ping` | Publica una trama binaria Protobuf v3 de prueba en Mosquitto MQTT para validar el flujo completo. |
| `GET` | `/health` | Healthcheck con diagnóstico de Redis, Mosquitto MQTT, sincronizador y clientes WebSockets conectados. |

---

### 11. Estrategia de Almacenamiento, Base de Datos y Retención

#### 11.1. Dimensionamiento para Flota Comercial
* **Pings generados (30 buses a 10s):** ~194.400 pings/mes por bus &rarr; **~5,83 millones de registros mensuales**.
* **Consumo de base de datos:** ~1,28 GB / mes (~15 a 18 GB / año).
* **Particionado declarativo por rango mensual en PostgreSQL:**
  * Tabla base: `telemetry_ping` con `PARTITION BY RANGE (recorded_at)`.
  * Particiones hijas: `telemetry_ping_YYYY_MM`.
  * Índices espaciales GIST sobre `geom` para consultas geoespaciales veloces.
  * Purgado instantáneo sin *table bloat* mediante `DROP TABLE` sobre particiones que superen la política de retención (ej: 90 días).

#### 11.2. Respaldos Automatizados (`scripts/backup_flota.sh`)
* Extracción binaria comprimida de PostgreSQL (`pg_dump -F c`).
* Respaldo del Filestore de Odoo (volumen `odoo-web-data`).
* Empaquetado en `.tar.gz` con rotación local de 7 días y sincronización remota hacia S3 / Google Drive.

---

### 12. Programación Operativa y Trazados de Servicios Eléctricos (Línea 20)

El sistema almacena y gestiona en su base local `flota_db` de forma **100% autónoma y soberana** la programación operativa y los trazados vectoriales de los **Servicios Eléctricos de Línea 20 (E1, E2 y E3)**, habiendo utilizado la base del CID únicamente como estrategia de migración/siembra rápida (data bootstrapping) por única vez.

#### 12.1. Arquitectura de Datos del Schema `servicios_especiales` en `flota_db`

En la base de datos local `flota_db` de PostgreSQL 15 / PostGIS se clonó el esquema con los datos oficiales de los 3 servicios eléctricos y sus 6 ramales:

| Tabla Local en `flota_db` | Registros | Descripción y Propósito |
|---|:---:|---|
| `servicios_especiales.servicio_especial` | **3** | Catálogo de servicios eléctricos de Línea 20: `E1` (Eléctrico 1), `E2` (Eléctrico 2) y `E3` (Eléctrico 3). |
| `servicios_especiales.ruta_servicio_especial` | **6** | Mapeo bivalente entre el servicio, sentido (`ida`/`vuelta`) y clave hexadecimal oficial (`020c`, `020d`, `020e`, `020f`, `0210`, `0211`). |
| `servicios_especiales.adjudicacion_servicio` | **3** | Actos administrativos y contratos de adjudicación por EOT de los servicios eléctricos con enlaces a Looker Studio. |
| `servicios_especiales.bus_adjudicacion` | **90** | Parque móvil de buses eléctricos asignados contractualmente con identificación SAM (`idsam`) y `mean_id`. |
| `servicios_especiales.parametro_monitoreo` | **3** | Reglas de auditoría automática: radio de geocerca (100–500 m), tolerancia de itinerario (50 m), % cumplimiento (70–80%) y tolerancias horarias (-5/+10 min). |
| `servicios_especiales.programacion_operativa` | **692** | Tabla maestra de despachos diarios: número de servicio, sentido, horario de salida, horario de llegada, tipo de día y vigencia activa. |
| `control_metricas.tipo_dia` | **3** | Catálogo oficial de calendario: `5 = LABORAL` (Lunes a Viernes), `6 = SABADO` (Sábado), `7 = NO LABORAL` (Domingos y Feriados). |

#### 12.2. Mapeo Hacia el Modelo de Odoo (`transit_timetable` / `transit.timetable`)

Cada uno de los **692 despachos planificados** se proyecta de forma biunívoca hacia la tabla `transit_timetable` de Odoo 18:

* **Ruta (`route_id`):** Vinculada al ramal correspondiente en `transit_route` (`020c`, `020d`, `020e`, `020f`, `0210`, `0211`).
* **Código de Servicio (`service_code`):** Normalizado como `f"S{numero_servicio:02d}"` (ej. `S01`, `S02`, `S15`).
* **Horario de Salida Decimal (`departure_time_float`):** Precisión en coma flotante ($H + M/60 + S/3600$) para visualización nativa con widget `float_time` de Odoo (`HH:MM`).
* **Horario de Llegada Decimal (`arrival_time_float`):** Proyección horaria de arribo a la cabecera opuesta.
* **Duración Programada (`scheduled_duration_minutes`):** Cálculo diferencial automático entre horario de salida y llegada.
* **Día de Operación (`day_of_week`):**
  * `tipo_dia = 5` &rarr; `'weekday'` (Lunes a Viernes)
  * `tipo_dia = 6` &rarr; `'5'` (Sábado)
  * `tipo_dia = 7` &rarr; `'6'` (Domingo / Feriado)
* **Atributos de Vigencia y Trazabilidad:** Almacenamiento de `direction` (`ida`/`vuelta`), `valid_from`, `valid_until` y clave foránea `cid_programacion_id` con índice B-Tree dedicado.

#### 12.3. Distribución Consolidada de Salidas Diarias de Línea 20 (Eléctricos)

```
========================================================================================
RESUMEN OPERATIVO DE HORARIOS PROGRAMADOS (692 SALIDAS OFICIALES LÍNEA 20)
========================================================================================
- RAMAL 020C - ELÉCTRICO 1 IDA (San Lorenzo -> Asunción):
  * Días Laborales:  46 salidas (00:20 a 23:45)
  * Sábados:         46 salidas (00:20 a 23:45)
  * Domingos/Fer.:   18 salidas (04:00 a 19:40)
  Total: 110 salidas programadas

- RAMAL 020D - ELÉCTRICO 1 VUELTA (Asunción -> San Lorenzo):
  * Días Laborales:  46 salidas (00:10 a 23:34)
  * Sábados:         46 salidas (00:10 a 23:34)
  * Domingos/Fer.:   18 salidas (05:00 a 20:40)
  Total: 110 salidas programadas

- RAMAL 020E - ELÉCTRICO 2 IDA (San Lorenzo -> Asunción Variante):
  * Días Laborales:  63 salidas (00:02 a 23:32)
  * Sábados:         63 salidas (00:02 a 23:32)
  * Domingos/Fer.:   24 salidas (04:00 a 20:00)
  Total: 150 salidas programadas

- RAMAL 020F - ELÉCTRICO 2 VUELTA (Asunción -> San Lorenzo Variante):
  * Días Laborales:  63 salidas (00:02 a 23:32)
  * Sábados:         63 salidas (00:02 a 23:32)
  * Domingos/Fer.:   24 salidas (05:00 a 21:00)
  Total: 150 salidas programadas

- RAMAL 0210 - ELÉCTRICO 3 IDA (Luque Aeropuerto -> Asunción):
  * Días Laborales:  34 salidas (00:00 a 23:10)
  * Sábados:         34 salidas (00:00 a 23:10)
  * Domingos/Fer.:   18 salidas (04:00 a 19:40)
  Total: 86 salidas programadas

- RAMAL 0211 - ELÉCTRICO 3 VUELTA (Asunción -> Luque Aeropuerto):
  * Días Laborales:  34 salidas (00:10 a 23:19)
  * Sábados:         34 salidas (00:10 a 23:19)
  * Domingos/Fer.:   18 salidas (05:00 a 20:40)
  Total: 86 salidas programadas
========================================================================================
TOTAL GENERAL: 692 SALIDAS DIARIAS PROGRAMADAS (100% SERVICIOS ELÉCTRICOS LÍNEA 20)
========================================================================================
```

#### 12.4. Shapes Vectoriales y Paradas Exclusivas de los Eléctricos

Los 46 trazados históricos en PostGIS (`transit_route_shape`) corresponden exclusivamente a los 6 ramales eléctricos:
* **`020c`**: 8 shapes históricos (vigencia normal y desvíos por eventos en Costanera).
* **`020d`**: 8 shapes históricos.
* **`020e`**: 7 shapes históricos.
* **`020f`**: 8 shapes históricos.
* **`0210`**: 7 shapes históricos.
* **`0211`**: 8 shapes históricos.
* **Paradas Oficiales:** 340 paradas homologadas con kilometraje lineal PostGIS (`ST_LineLocatePoint`) calculadas a lo largo de estos 6 ramales.

---

### 13. Guía de Ejecución y Pruebas Locales

#### 13.1. Levantar los 5 Servicios Nucleares en Docker
```bash
docker compose up -d
```
Verifica que los 5 contenedores nucleares autónomos estén corriendo:
1. `odoo_transporte_app` &rarr; `http://localhost:8069` (ERP Odoo 18)
2. `odoo_transporte_db` &rarr; `localhost:5434` (PostgreSQL 15 + PostGIS 3.4)
3. `odoo_transporte_redis` &rarr; `localhost:6379` (Redis 7 con geocaché de calles y estado de flota)
4. `odoo_transporte_mosquitto` &rarr; `localhost:1883` y `9001` (Mosquitto MQTT con autenticación e ingesta Protobuf v3 directa)
5. `odoo_transporte_gps_broker` &rarr; `http://localhost:8088` (Broker FastAPI con WebSockets, Headway, PostGIS y ETA)

*(Nota: El sistema no requiere daemon de sincronización continua con bases externas, operando de manera 100% autónoma y soberana).*

#### 13.2. Carga Inicial de Shapes y Paradas (Bootstrap / Migración por única vez)
```powershell
# Extraer los 6 ramales oficiales y sus 340 paradas desde la base CID:
python scripts/sync_cid_shapes_to_flota.py
```

#### 13.3. Carga Inicial de la Programación Operativa (Bootstrap / Migración por única vez)
```powershell
# Extraer y cargar los 908 horarios de servicios_especiales.programacion_operativa:
python scripts/sync_cid_programacion_to_flota.py
```

#### 13.4. Acceso a los Tableros de Control
* **Tablero Lineal de Intervalos & Pegonamiento:** [http://localhost:8088/headway](http://localhost:8088/headway)
* **Radar Satelital en Vivo con Leaflet:** [http://localhost:8088/map](http://localhost:8088/map)
* **Dashboard Cumplimiento VMT (Res. 065/2024):** [http://localhost:8088/compliance](http://localhost:8088/compliance)
* **Pagina de Parada para Pasajeros (con QR):** [http://localhost:8088/parada/{stop_code}](http://localhost:8088/parada/P001)
* **ERP Odoo 18 (Operaciones de Transporte):** [http://localhost:8069](http://localhost:8069)
* **Cuadros de Marcha / Horarios Oficiales en Odoo:** Menu `Operaciones de Transporte > Planificacion de Trafico > Cuadros de Marcha / Frecuencias`.

#### 13.5.a. API de ETA y Cumplimiento Regulatorio
```bash
# ETA de una parada especifica (ej: parada P001):
curl http://localhost:8088/api/v1/eta/P001

# ETA de todas las paradas activas:
curl http://localhost:8088/api/v1/eta/all

# Cumplimiento del dia actual:
curl http://localhost:8088/api/v1/compliance/today

# Alertas activas de bunching:
curl http://localhost:8088/api/v1/bunching/alerts

# Historial de 30 dias:
curl http://localhost:8088/api/v1/compliance/history
```

#### 13.5.b. Pruebas de Homologación e Ingesta Masiva MQTT Protobuf v3
```powershell
# Simulación de viaje completo con tramas compactas Protobuf v3:
docker exec -e MQTT_BROKER_HOST=mosquitto odoo_transporte_gps_broker python /scripts/simulate_mqtt_protobuf.py --delay 1.0
```

---

### 14. Resumen de Modelos y Archivos Clave del Repositorio

| Componente / Archivo | Ubicación | Descripción |
|---|---|---|
| `fleet.vehicle` | `custom_addons/transit_operations/models/fleet_vehicle.py` | Unidad / Bus, ITV, Poliza, Validador, Asientos. |
| `res.partner` | `custom_addons/transit_operations/models/res_partner.py` | Licencias de Chofer y RUC/DV para SIFEN. |
| `transit.route` | `custom_addons/transit_operations/models/transit_route.py` | 6 Ramales oficiales Linea 20, Tarifas, Cabeceras. |
| `transit.route.checkpoint` | `custom_addons/transit_operations/models/transit_route_checkpoint.py` | Paradas intermedias con lat/lon y radio en Odoo. |
| `transit.timetable` | `custom_addons/transit_operations/models/transit_timetable.py` | Horarios teoricos, frecuencias y programacion CID. |
| `transit.dispatch` | `custom_addons/transit_operations/models/transit_dispatch.py` | Despacho diario, checklist, odometria, telemetria. |
| `transit.ticket` | `custom_addons/transit_operations/models/transit_ticket.py` | Emision de boletos con facturacion 1 clic. |
| `account.move` | `custom_addons/transit_operations/models/account_move_sifen.py` | Facturacion Electronica SIFEN, CDC 44 y QR. |
| `main.py` | `gps_broker/main.py` | Broker FastAPI v3.0.0, Redis, WebSockets, motor PostGIS, 15+ endpoints REST. |
| `headway_service.py` | `gps_broker/headway_service.py` | Tablero Lineal de Frecuencias, regularidad y detector de pegonamiento. |
| `eta_service.py` | `gps_broker/eta_service.py` | **NUEVO:** ETA predictivo por parada. ST_LineLocatePoint + velocidad historica + pagina movil con QR. |
| `compliance_service.py` | `gps_broker/compliance_service.py` | **NUEVO:** Dashboard cumplimiento Res. GVMT 065/2024: 692 despachos/dia, alertas, historial 30d. |
| `street_service.py` | `gps_broker/street_service.py` | Motor de contextualizacion de calles y proximas intersecciones con Redis geocache. |
| `sync_vmt_telemetry.py` | `scripts/sync_vmt_telemetry.py` | Conector continuo con base productiva VMT (`app_monitoreo_mensajeoperativo`). |
| `sync_cid_shapes_to_flota.py` | `scripts/sync_cid_shapes_to_flota.py` | Sincronizador de shapes vectoriales historicos de los 6 ramales desde CID. |
| `sync_cid_stops_to_flota.py` | `scripts/sync_cid_stops_to_flota.py` | Sincronizador de 340 paradas oficiales del CID con kilometraje lineal PostGIS. |
| `sync_cid_programacion_to_flota.py` | `scripts/sync_cid_programacion_to_flota.py` | Sincronizador de 908 cuadros de marcha oficiales Electricos hacia Odoo `transit.timetable`. |
| `mosquitto.conf` / `passwd` | `config/mosquitto/` | Configuracion de Mosquitto MQTT, listeners 1883/9001 y credenciales cifradas. |
| `transit.proto` | `gps_broker/proto/transit.proto` | Especificacion Protobuf v3 oficial de la Resolucion GVMT N 065/2024. |
| `transit_pb2.py` | `gps_broker/proto/transit_pb2.py` | Clases Python compiladas nativamente con `protoc` para deserializacion de ultra-alta velocidad. |
| `decoder.py` | `gps_broker/proto/decoder.py` | Decodificador Protobuf v3 con soporte dual (nativo y parser de emergencia). |
| `mqtt_consumer.py` | `gps_broker/mqtt_consumer.py` | Consumidor MQTT background suscrito a `transporte/flota/+/operacion`. |
| `backup_flota.sh` | `scripts/backup_flota.sh` | Script de respaldo y rotacion para VPS de produccion. |

---

### 15. Nuevas Funcionalidades Avanzadas (Version 3.0.0)

#### 15.1. ETA Predictivo por Parada (`eta_service.py`)

El sistema calcula en tiempo real cuanto falta para que llegue el proximo bus electrico a cada parada fisica.

**Algoritmo:**
```
fraccion_parada = ST_LineLocatePoint(shape, geom_parada)  -- valor 0.0 a 1.0
fraccion_bus    = distancia_recorrida_km / total_km
km_restantes    = (fraccion_parada - fraccion_bus) * total_km
velocidad_media = AVG(speed_kmh) FROM telemetry_ping WHERE route = X AND recorded_at > NOW()-4h
eta_minutos     = (km_restantes / velocidad_media) * 60
```

**Caracteristicas:**
- Cache Redis con TTL 20s para respuesta instantanea
- Fallback a velocidad media de ciudad (22 km/h) si no hay historico
- Pagina movil `/parada/{stop_code}`: auto-refresh 15s, QR embebido, sin app requerida
- API REST: `GET /api/v1/eta/{stop_code}` y `GET /api/v1/eta/all`
- Muestra hasta 3 buses proximos ordenados por ETA

#### 15.2. Dashboard de Cumplimiento Regulatorio (`compliance_service.py`)

Monitoreo en tiempo real del cumplimiento de la cuota diaria de **692 despachos** exigida por la Resolucion GVMT 065/2024.

**Metricas calculadas:**
| Metrica | Fuente | Descripcion |
|---|---|---|
| Despachos ejecutados | `telemetry_ping (type=0)` | Pings de inicio de operacion (salida de cabecera) |
| Despachos programados | `transit_timetable` | Cuadros de marcha vigentes del CID |
| % Cumplimiento | Calculado | `(ejecutados / 692) * 100` |
| Proyeccion al cierre | Calculado | Tasa horaria * horas restantes |
| Historial 30 dias | `telemetry_ping` | Tendencia de cumplimiento reciente |

**Alertas automaticas:**
- **CRITICAL:** Cumplimiento < 85% con menos de 4 horas para cierre
- **WARNING:** Proyeccion < 85% del cupo al cierre del dia
- Por ramal: alerta si cumplimiento < 85% con < 6 horas restantes

**Endpoints:**
- `GET /compliance` - Dashboard HTML interactivo
- `GET /api/v1/compliance/today` - JSON completo del dia
- `GET /api/v1/compliance/alerts` - Solo alertas activas
- `GET /api/v1/compliance/history` - Historial de 30 dias

#### 15.3. API de Bunching Mejorada (`/api/v1/bunching/alerts`)

Endpoint dedicado que expone solo las alertas activas de pegonamiento en formato consumible por paneles externos, sistemas de notificacion y webhooks Odoo.

**Respuesta JSON:**
```json
{
  "timestamp": "2026-09-28T23:00:00Z",
  "total_bunching_alerts": 2,
  "alerts": [
    {
      "route_code": "020f",
      "severity": "CRITICAL",
      "trailer_id": "00016",
      "leader_id": "00023",
      "gap_km": 0.45,
      "gap_meters": 450,
      "est_minutes": 1.1,
      "alert_label": "Pegonamiento critico: buses 00016 y 00023 a 450m de separacion en 020F"
    }
  ]
}
```


