# Diccionario de Datos — Monitoreo CID
_Generado: 2026-10-23 08:03_

## Bases de datos

| BD | Database | Versión | Tablas/Vistas |
|---|---|---|---|
| CID | `bbdd-monitoreo-cid` | PostgreSQL 16.3 on x86_64-pc-linux-musl | 198 |
| MONITOREO | `bbdd-monitoreo-prod` | PostgreSQL 16.4 on x86_64-pc-linux-musl | 27 |
| AZURE | `opentransit-prod` | PostgreSQL 14.20 (Ubuntu 14.20-1.pgdg24.04+1) on x86_64-pc-linux-gnu | 185 |

## Relaciones cruzadas conocidas (lógica del proyecto)

| Descripción | Origen | Destino | Existe O/D | % coincidencia |
|---|---|---|---|---|
| Bus GPS ↔ bus adjudicado (comparación en UPPER) | `MONITOREO.public.app_monitoreo_mensajeoperativo.mean_id` | `CID.servicios_especiales.bus_adjudicacion.mean_id` | SI/SI | 6.2 |
| Empresa del mensaje GPS ↔ EOT | `MONITOREO.public.app_monitoreo_mensajeoperativo.agency_id` | `CID.public.eots.id_eot_vmt_hex` | SI/SI | 43.8 |
| Ruta informada por el GPS ↔ catálogo de rutas | `MONITOREO.public.app_monitoreo_mensajeoperativo.route_id` | `CID.public.catalogo_rutas.ruta_hex` | SI/SI | 71.0 |
| Validación (SAM del validador) ↔ bus adjudicado | `AZURE.public.c_transacciones.idsam` | `CID.servicios_especiales.bus_adjudicacion.idsam` | SI/SI | 2.0 |
| Ruta informada por el validador ↔ catálogo de rutas (a verificar) | `AZURE.public.c_transacciones.idrutaestacion` | `CID.public.catalogo_rutas.ruta_hex` | SI/SI | 93.6 |
| Entidad de la transacción ↔ EOT (a verificar) | `AZURE.public.c_transacciones.entidad` | `CID.public.eots.id_eot_vmt_hex` | SI/SI | 100.0 |
| Ruta lógica ↔ itinerarios geométricos vigentes | `CID.public.catalogo_rutas.ruta_hex` | `CID.geometria.historico_itinerario.ruta_hex` | SI/SI | 66.7 |
| Geocercas (inicio/fin/hitos/retorno) ↔ itinerario | `CID.geometria.geocercas.id_itinerario` | `CID.geometria.historico_itinerario.id_itinerario` | SI/SI | 100.0 |
| Ruta ↔ EOT operadora | `CID.public.catalogo_rutas.id_eot_catalogo` | `CID.public.eots.cod_catalogo` | SI/SI | 100.0 |

## Relaciones inferidas entre BD / schemas (sin FK declarada)

| Alcance | Columna | Tabla A | Tabla B | Tipos compatibles |
|---|---|---|---|---|
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo` | AZURE.`public.transit_agencies` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_agencies` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo2` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.transit_agencies` | SI |
| ENTRE BD | `agency_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `agency_id` | CID.`public.cant_buses_por_eot` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `agency_id` | CID.`public.cant_buses_por_eot` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `agency_id` | CID.`public.cant_buses_por_eot` | AZURE.`public.transit_agencies` | SI |
| ENTRE BD | `agency_id` | CID.`public.cant_buses_por_eot` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `agency_id` | CID.`public.eot_terminales` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `agency_id` | CID.`public.eot_terminales` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `agency_id` | CID.`public.eot_terminales` | AZURE.`public.transit_agencies` | SI |
| ENTRE BD | `agency_id` | CID.`public.eot_terminales` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `agency_id` | CID.`public.resultado_agencyid_mensajeoperativo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `agency_id` | CID.`public.resultado_agencyid_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `agency_id` | CID.`public.resultado_agencyid_mensajeoperativo` | AZURE.`public.transit_agencies` | SI |
| ENTRE BD | `agency_id` | CID.`public.resultado_agencyid_mensajeoperativo` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `agency_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `agency_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_agencies` | SI |
| ENTRE BD | `agency_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `content_type_id` | CID.`public.auth_permission` | MONITOREO.`public.auth_permission` | SI |
| ENTRE BD | `content_type_id` | CID.`public.auth_permission` | MONITOREO.`public.django_admin_log` | SI |
| ENTRE BD | `content_type_id` | CID.`public.auth_permission` | MONITOREO.`public.reversion_version` | SI |
| ENTRE BD | `content_type_id` | CID.`public.django_admin_log` | MONITOREO.`public.auth_permission` | SI |
| ENTRE BD | `content_type_id` | CID.`public.django_admin_log` | MONITOREO.`public.django_admin_log` | SI |
| ENTRE BD | `content_type_id` | CID.`public.django_admin_log` | MONITOREO.`public.reversion_version` | SI |
| ENTRE BD | `driver_id` | CID.`public.app_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `driver_id` | CID.`public.app_monitoreo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `driver_id` | CID.`public.app_monitoreo_mensajeoperativo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `driver_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `driver_id` | CID.`public.app_monitoreo_mensajeoperativo2` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `driver_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `driver_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativofallido` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo` | MONITOREO.`public.app_monitoreo_usuariobroker` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo` | MONITOREO.`public.app_monitoreo_mensajeoperativofallido` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo` | MONITOREO.`public.app_monitoreo_usuariobroker` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo2` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo2` | MONITOREO.`public.app_monitoreo_mensajeoperativofallido` | SI |
| ENTRE BD | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo2` | MONITOREO.`public.app_monitoreo_usuariobroker` | SI |
| ENTRE BD | `emisor_id` | CID.`servicios_especiales.parametro_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `emisor_id` | CID.`servicios_especiales.parametro_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativofallido` | SI |
| ENTRE BD | `emisor_id` | CID.`servicios_especiales.parametro_monitoreo` | MONITOREO.`public.app_monitoreo_usuariobroker` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.app_archivo` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.compensacion` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.compensacion_aud` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.mv_ctransacciones_horas` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `entidad` | CID.`gestion_cid.auditoria_acciones` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.app_archivo` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.compensacion` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.compensacion_aud` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.mv_ctransacciones_horas` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `entidad` | CID.`public.discapacitados` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_archivo` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.compensacion` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.compensacion_aud` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.mv_ctransacciones_horas` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `entidad` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `funcionario_id` | CID.`asistencias.asistencias` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `funcionario_id` | CID.`asistencias.asistencias` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `funcionario_id` | CID.`asistencias.permisos` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `funcionario_id` | CID.`asistencias.permisos` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `group_id` | CID.`public.auth_group_permissions` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `group_id` | CID.`public.auth_group_permissions` | MONITOREO.`public.auth_group_permissions` | SI |
| ENTRE BD | `group_id` | CID.`public.auth_user_groups` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `group_id` | CID.`public.auth_user_groups` | MONITOREO.`public.auth_group_permissions` | SI |
| ENTRE BD | `id_entidad` | CID.`public.eots` | AZURE.`public.dispositivo_punto_recarga` | NO |
| ENTRE BD | `id_entidad` | CID.`public.eots` | AZURE.`public.dispositivo_sam` | NO |
| ENTRE BD | `id_entidad` | CID.`public.eots` | AZURE.`public.dispositivos_mediostransporte` | NO |
| ENTRE BD | `id_entidad` | CID.`public.eots` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `id_parada` | CID.`geometria.itinerario_parada` | AZURE.`public.parada_tipo_via` | NO |
| ENTRE BD | `id_parada` | CID.`geometria.paradas` | AZURE.`public.parada_tipo_via` | NO |
| ENTRE BD | `id_parametro` | CID.`control_metricas.parametros_ifo` | AZURE.`public.reportes_detalle` | SI |
| ENTRE BD | `id_parametro` | CID.`servicios_especiales.parametro_monitoreo` | AZURE.`public.reportes_detalle` | SI |
| ENTRE BD | `id_sam` | CID.`public.dj_importada` | AZURE.`public.dispositivo_sam` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_informaciónuso` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.app_informaciónuso` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idrutaestacion` | CID.`public.servicios_diarios` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_encabezadoevento` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_informacióngeneral` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_rexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_rinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_sexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.app_sinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.discapacitados` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_encabezadoevento` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_informacióngeneral` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_rexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_rinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_sexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.app_sinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.frecuencia` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_encabezadoevento` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_informacióngeneral` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_rexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_rinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_sexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.app_sinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.nservicios` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_encabezadoevento` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_informacióngeneral` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_rexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_rinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_sexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_sinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_encabezadoevento` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_informacióngeneral` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_rexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_rinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_sexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.app_sinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.salidas` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_encabezadoevento` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_informacióngeneral` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_rexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_rinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_sexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.app_sinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idsam` | CID.`public.servicios_diarios` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_encabezadoevento` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_informacióngeneral` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_rexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_rinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_sexclusionsam` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.app_sinclusiondispositivo` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_dispositivos` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `idsam` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `linea` | CID.`public.frecuencia` | AZURE.`public.itinerarios_generados` | SI |
| ENTRE BD | `linea` | CID.`public.frecuencia` | AZURE.`public.transit_mediostransporte` | SI |
| ENTRE BD | `linea` | CID.`public.frecuencia` | AZURE.`public.transit_mediostransporte_aud` | SI |
| ENTRE BD | `linea` | CID.`public.itinerarios_oficiales` | AZURE.`public.itinerarios_generados` | SI |
| ENTRE BD | `linea` | CID.`public.itinerarios_oficiales` | AZURE.`public.transit_mediostransporte` | SI |
| ENTRE BD | `linea` | CID.`public.itinerarios_oficiales` | AZURE.`public.transit_mediostransporte_aud` | SI |
| ENTRE BD | `linea` | CID.`public.salidas` | AZURE.`public.itinerarios_generados` | SI |
| ENTRE BD | `linea` | CID.`public.salidas` | AZURE.`public.transit_mediostransporte` | SI |
| ENTRE BD | `linea` | CID.`public.salidas` | AZURE.`public.transit_mediostransporte_aud` | SI |
| ENTRE BD | `linea` | CID.`public.servicios_diarios` | AZURE.`public.itinerarios_generados` | SI |
| ENTRE BD | `linea` | CID.`public.servicios_diarios` | AZURE.`public.transit_mediostransporte` | SI |
| ENTRE BD | `linea` | CID.`public.servicios_diarios` | AZURE.`public.transit_mediostransporte_aud` | SI |
| ENTRE BD | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | CID.`public.app_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`public.app_monitoreo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | CID.`public.app_monitoreo_mensajeoperativo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | CID.`public.app_monitoreo_mensajeoperativo2` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | CID.`public.ncant_servicios` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`public.ncant_servicios` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | CID.`public.nservicios` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`public.nservicios` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | CID.`public.nvalidaciones_bus` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`public.nvalidaciones_bus` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | CID.`servicios_especiales.bus_adjudicacion` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `mean_id` | CID.`servicios_especiales.bus_adjudicacion` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `mean_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `object_id` | CID.`public.django_admin_log` | MONITOREO.`public.django_admin_log` | SI |
| ENTRE BD | `object_id` | CID.`public.django_admin_log` | MONITOREO.`public.reversion_version` | SI |
| ENTRE BD | `permission_id` | CID.`public.auth_group_permissions` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `permission_id` | CID.`public.auth_group_permissions` | MONITOREO.`public.auth_group_permissions` | SI |
| ENTRE BD | `permission_id` | CID.`public.auth_user_user_permissions` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `permission_id` | CID.`public.auth_user_user_permissions` | MONITOREO.`public.auth_group_permissions` | SI |
| ENTRE BD | `role_id` | CID.`reclamo.users` | AZURE.`public.roles` | SI |
| ENTRE BD | `route_id` | CID.`control_metricas.cbd_detalle_buses` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `route_id` | CID.`control_metricas.cbd_detalle_buses` | AZURE.`public.gtfs_fare_rules` | SI |
| ENTRE BD | `route_id` | CID.`control_metricas.cbd_detalle_buses` | AZURE.`public.gtfs_trips` | SI |
| ENTRE BD | `route_id` | CID.`control_metricas.cbd_detalle_buses` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `route_id` | CID.`control_metricas.cbd_detalle_buses` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `route_id` | CID.`control_metricas.cbd_detalle_buses` | AZURE.`public.transit_trips` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo` | AZURE.`public.gtfs_fare_rules` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo` | AZURE.`public.gtfs_trips` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo` | AZURE.`public.transit_trips` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.gtfs_fare_rules` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.gtfs_trips` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_trips` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo2` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.gtfs_fare_rules` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.gtfs_trips` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `route_id` | CID.`public.app_monitoreo_mensajeoperativo2` | AZURE.`public.transit_trips` | SI |
| ENTRE BD | `route_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.gtfs_fare_rules` | SI |
| ENTRE BD | `route_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.gtfs_trips` | SI |
| ENTRE BD | `route_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.operation_message` | SI |
| ENTRE BD | `route_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_routes` | SI |
| ENTRE BD | `route_id` | MONITOREO.`public.app_monitoreo_mensajeoperativo` | AZURE.`public.transit_trips` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_econfirmaciónlam` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_econfirmaciónlapa` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_econfirmaciónlapr` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_emisiónef` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eprecargadoemisión` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eprecargadouso` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eproductodevoluciónrecarga` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eproductodevolucióntarifa` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eproductodistribución` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eproductoreactivación` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eproductorecarga` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_eproductouso` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_reventonoefectuado` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_sacciónlam` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_sacciónlapa` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.app_sacciónlapr` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_confirmacion_lam` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_eventosinvalidos` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_mediopago` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_modusuario` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_recarga_uso` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_recargas` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_seriales_deshabilitados` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_seriales_deshabilitados_aud` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_transacciones` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.c_usos` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.compensacion_transacciones` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.mv_ctransacciones_horas` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.transacciones` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.discapacitados` | AZURE.`public.transaccioneshistoricas` | NO |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_econfirmaciónlam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_econfirmaciónlapa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_econfirmaciónlapr` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_emediopagomodusuario` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eprecargadoemisión` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eproductodevoluciónrecarga` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eproductodevolucióntarifa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eproductodistribución` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eproductoreactivación` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eproductorecarga` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_eproductouso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_reventonoefectuado` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_sacciónlam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_sacciónlapa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.app_sacciónlapr` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_recarga_uso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_seriales_deshabilitados` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_seriales_deshabilitados_aud` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.mv_ctransacciones_horas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.nvalidaciones_bus_datos` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_econfirmaciónlam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_econfirmaciónlapa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_econfirmaciónlapr` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_emediopagomodusuario` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eprecargadoemisión` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eproductodevoluciónrecarga` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eproductodevolucióntarifa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eproductodistribución` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eproductoreactivación` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eproductorecarga` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_eproductouso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_reventonoefectuado` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_sacciónlam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_sacciónlapa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.app_sacciónlapr` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_recarga_uso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_seriales_deshabilitados` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_seriales_deshabilitados_aud` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.mv_ctransacciones_horas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.transbordos_v2` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_econfirmaciónlam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_econfirmaciónlapa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_econfirmaciónlapr` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_emediopagomodusuario` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_emisiónef` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eprecargadoemisión` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eprecargadouso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eproductodevoluciónrecarga` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eproductodevolucióntarifa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eproductodistribución` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eproductoreactivación` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eproductorecarga` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_eproductouso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_reventonoefectuado` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_sacciónlam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_sacciónlapa` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.app_sacciónlapr` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_confirmacion_lam` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_eventosinvalidos` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_mediopago` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_modusuario` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_recarga_uso` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_recargas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_seriales_deshabilitados` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_seriales_deshabilitados_aud` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.c_usos` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.compensacion_transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.mv_ctransacciones_horas` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.transacciones` | SI |
| ENTRE BD | `serialmediopago` | CID.`public.vista_transbordos_acumulados` | AZURE.`public.transaccioneshistoricas` | SI |
| ENTRE BD | `user_id` | CID.`public.auth_user_groups` | MONITOREO.`public.django_admin_log` | SI |
| ENTRE BD | `user_id` | CID.`public.auth_user_groups` | MONITOREO.`public.reversion_revision` | SI |
| ENTRE BD | `user_id` | CID.`public.auth_user_user_permissions` | MONITOREO.`public.django_admin_log` | SI |
| ENTRE BD | `user_id` | CID.`public.auth_user_user_permissions` | MONITOREO.`public.reversion_revision` | SI |
| ENTRE BD | `user_id` | CID.`public.django_admin_log` | MONITOREO.`public.django_admin_log` | SI |
| ENTRE BD | `user_id` | CID.`public.django_admin_log` | MONITOREO.`public.reversion_revision` | SI |
| ENTRE BD | `user_id` | CID.`reclamo.caso_movimientos` | MONITOREO.`public.django_admin_log` | SI |
| ENTRE BD | `user_id` | CID.`reclamo.caso_movimientos` | MONITOREO.`public.reversion_revision` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_acceso` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_acceso` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_acceso` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_acceso` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`public.logs_acceso` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`public.logs_acceso` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_auditoria` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_auditoria` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_auditoria` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`public.logs_auditoria` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`public.logs_auditoria` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`public.logs_auditoria` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`public.notificaciones` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`public.notificaciones` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`public.notificaciones` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`public.notificaciones` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`public.notificaciones` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`public.notificaciones` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`public.sesiones_usuarios` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`public.sesiones_usuarios` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`public.sesiones_usuarios` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`public.sesiones_usuarios` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`public.sesiones_usuarios` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`public.sesiones_usuarios` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`public.usuario_rol` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`public.usuario_rol` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`public.usuario_rol` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`public.usuario_rol` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`public.usuario_rol` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`public.usuario_rol` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_acceso` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_acceso` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_acceso` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_acceso` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_acceso` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_acceso` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_acceso` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_auditoria` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_auditoria` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_auditoria` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_auditoria` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_auditoria` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_auditoria` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.logs_auditoria` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.notificaciones` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.notificaciones` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.notificaciones` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.notificaciones` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.notificaciones` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.notificaciones` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.notificaciones` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.sesiones_usuarios` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.sesiones_usuarios` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.sesiones_usuarios` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.sesiones_usuarios` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.sesiones_usuarios` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.sesiones_usuarios` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.sesiones_usuarios` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_rol` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_rol` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_rol` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_rol` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_rol` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_rol` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_rol` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_sistema_rol` | MONITOREO.`public.app_organizaciones_usuario_groups` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_sistema_rol` | MONITOREO.`public.app_organizaciones_usuario_grupos` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_sistema_rol` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_sistema_rol` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_sistema_rol` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_sistema_rol` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | CID.`sistema.usuario_sistema_rol` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_groups` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_groups` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_groups` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_groups` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_grupos` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_grupos` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_grupos` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_grupos` | AZURE.`public.usuarios_aud` | SI |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | AZURE.`public.app_emediopagomodusuario` | NO |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | AZURE.`public.app_emediopagoreconstrucción` | NO |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | AZURE.`public.usuarios` | SI |
| ENTRE BD | `usuario_id` | MONITOREO.`public.app_organizaciones_usuario_user_permissions` | AZURE.`public.usuarios_aud` | SI |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.buses_declarados` | CID.`verificacion_res_65.detalles_incumplimientos` | NO |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.buses_declarados` | CID.`verificacion_res_65.incumplimientos` | SI |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.buses_declarados` | CID.`verificacion_res_65.infraccion` | SI |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.buses_declarados` | CID.`verificacion_res_65.multas` | NO |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.buses_declarados` | CID.`verificacion_res_65.notificaciones` | SI |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.eots` | CID.`verificacion_res_65.detalles_incumplimientos` | NO |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.eots` | CID.`verificacion_res_65.incumplimientos` | SI |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.eots` | CID.`verificacion_res_65.infraccion` | SI |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.eots` | CID.`verificacion_res_65.multas` | NO |
| ENTRE SCHEMAS | `cod_catalogo` | CID.`public.eots` | CID.`verificacion_res_65.notificaciones` | SI |
| ENTRE SCHEMAS | `emisor_id` | CID.`public.app_monitoreo` | CID.`servicios_especiales.parametro_monitoreo` | SI |
| ENTRE SCHEMAS | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo` | CID.`servicios_especiales.parametro_monitoreo` | SI |
| ENTRE SCHEMAS | `emisor_id` | CID.`public.app_monitoreo_mensajeoperativo2` | CID.`servicios_especiales.parametro_monitoreo` | SI |
| ENTRE SCHEMAS | `entidad` | CID.`gestion_cid.auditoria_acciones` | CID.`public.discapacitados` | SI |
| ENTRE SCHEMAS | `entidad` | CID.`gestion_cid.auditoria_acciones` | CID.`public.nvalidaciones_bus_datos` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.incumplimientos_cbd` | CID.`public.concesiones` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.incumplimientos_cbd` | CID.`public.eot_linea` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.incumplimientos_cbd` | CID.`public.eots` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.incumplimientos_ifo` | CID.`public.concesiones` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.incumplimientos_ifo` | CID.`public.eot_linea` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.incumplimientos_ifo` | CID.`public.eots` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.resultados_diarios` | CID.`public.concesiones` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.resultados_diarios` | CID.`public.eot_linea` | SI |
| ENTRE SCHEMAS | `eot_id` | CID.`control_metricas.resultados_diarios` | CID.`public.eots` | SI |
| ENTRE SCHEMAS | `id_alerta` | CID.`alertas.acciones_alerta` | CID.`registro_habilitacion.alertas` | SI |
| ENTRE SCHEMAS | `id_alerta` | CID.`alertas.control_alertas` | CID.`registro_habilitacion.alertas` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.eventos_operacionales` | CID.`registro_habilitacion.alertas` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.eventos_operacionales` | CID.`registro_habilitacion.bus_empresa` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.eventos_operacionales` | CID.`registro_habilitacion.buses` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.eventos_operacionales` | CID.`registro_habilitacion.documentos_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.eventos_operacionales` | CID.`registro_habilitacion.itv_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.eventos_operacionales` | CID.`registro_habilitacion.seguros_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.pasajeros_simulados` | CID.`registro_habilitacion.alertas` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.pasajeros_simulados` | CID.`registro_habilitacion.bus_empresa` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.pasajeros_simulados` | CID.`registro_habilitacion.buses` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.pasajeros_simulados` | CID.`registro_habilitacion.documentos_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.pasajeros_simulados` | CID.`registro_habilitacion.itv_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.pasajeros_simulados` | CID.`registro_habilitacion.seguros_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.posiciones_gps` | CID.`registro_habilitacion.alertas` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.posiciones_gps` | CID.`registro_habilitacion.bus_empresa` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.posiciones_gps` | CID.`registro_habilitacion.buses` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.posiciones_gps` | CID.`registro_habilitacion.documentos_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.posiciones_gps` | CID.`registro_habilitacion.itv_bus` | SI |
| ENTRE SCHEMAS | `id_bus` | CID.`public.posiciones_gps` | CID.`registro_habilitacion.seguros_bus` | SI |
| ENTRE SCHEMAS | `id_consorcio` | CID.`gestion_uf.composicion_consorcio` | CID.`public.consorcios` | SI |
| ENTRE SCHEMAS | `id_consorcio` | CID.`gestion_uf.composicion_consorcio` | CID.`public.empresas` | SI |
| ENTRE SCHEMAS | `id_consorcio` | CID.`gestion_uf.composicion_consorcio` | CID.`public.unidades_funcionales` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.composicion_consorcio` | CID.`public.dj_importada` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.composicion_consorcio` | CID.`public.frecuencia` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.composicion_consorcio` | CID.`public.historico_eot_ruta` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.composicion_consorcio` | CID.`public.salidas` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.composicion_consorcio` | CID.`registro_habilitacion.bus_empresa` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.composicion_consorcio` | CID.`registro_habilitacion.documentos_eot` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.composicion_consorcio` | CID.`servicios_especiales.adjudicacion_servicio` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.contratos` | CID.`public.dj_importada` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.contratos` | CID.`public.frecuencia` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.contratos` | CID.`public.historico_eot_ruta` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.contratos` | CID.`public.salidas` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.contratos` | CID.`registro_habilitacion.bus_empresa` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.contratos` | CID.`registro_habilitacion.documentos_eot` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.contratos` | CID.`servicios_especiales.adjudicacion_servicio` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.dj_importada` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.frecuencia` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.historico_eot_ruta` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.salidas` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`registro_habilitacion.bus_empresa` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`registro_habilitacion.documentos_eot` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`servicios_especiales.adjudicacion_servicio` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_uf` | CID.`public.dj_importada` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_uf` | CID.`public.frecuencia` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_uf` | CID.`public.historico_eot_ruta` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_uf` | CID.`public.salidas` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_uf` | CID.`registro_habilitacion.bus_empresa` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_uf` | CID.`registro_habilitacion.documentos_eot` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`gestion_uf.historico_explotacion_uf` | CID.`servicios_especiales.adjudicacion_servicio` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`public.dj_importada` | CID.`registro_habilitacion.bus_empresa` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`public.dj_importada` | CID.`registro_habilitacion.documentos_eot` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`public.dj_importada` | CID.`servicios_especiales.adjudicacion_servicio` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`public.frecuencia` | CID.`registro_habilitacion.bus_empresa` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`public.frecuencia` | CID.`registro_habilitacion.documentos_eot` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`public.frecuencia` | CID.`servicios_especiales.adjudicacion_servicio` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`public.historico_eot_ruta` | CID.`registro_habilitacion.bus_empresa` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`public.historico_eot_ruta` | CID.`registro_habilitacion.documentos_eot` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`public.historico_eot_ruta` | CID.`servicios_especiales.adjudicacion_servicio` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`public.salidas` | CID.`registro_habilitacion.bus_empresa` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`public.salidas` | CID.`registro_habilitacion.documentos_eot` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`public.salidas` | CID.`servicios_especiales.adjudicacion_servicio` | SI |
| ENTRE SCHEMAS | `id_eot` | CID.`registro_habilitacion.bus_empresa` | CID.`servicios_especiales.adjudicacion_servicio` | NO |
| ENTRE SCHEMAS | `id_eot` | CID.`registro_habilitacion.documentos_eot` | CID.`servicios_especiales.adjudicacion_servicio` | NO |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`geometria.puntos_terminales` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.eots` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`registro_habilitacion.auxiliar` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`verificacion_res_65.detalles_incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`verificacion_res_65.incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`verificacion_res_65.infraccion` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`verificacion_res_65.multas` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.cbd_detalle_buses` | CID.`verificacion_res_65.notificaciones` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.ifo_historico` | CID.`geometria.puntos_terminales` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.ifo_historico` | CID.`registro_habilitacion.auxiliar` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.ifo_historico` | CID.`verificacion_res_65.detalles_incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.ifo_historico` | CID.`verificacion_res_65.incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.ifo_historico` | CID.`verificacion_res_65.infraccion` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.ifo_historico` | CID.`verificacion_res_65.multas` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`control_metricas.ifo_historico` | CID.`verificacion_res_65.notificaciones` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`geometria.puntos_terminales` | CID.`registro_habilitacion.auxiliar` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`geometria.puntos_terminales` | CID.`verificacion_res_65.detalles_incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`geometria.puntos_terminales` | CID.`verificacion_res_65.incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`geometria.puntos_terminales` | CID.`verificacion_res_65.infraccion` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`geometria.puntos_terminales` | CID.`verificacion_res_65.multas` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`geometria.puntos_terminales` | CID.`verificacion_res_65.notificaciones` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`public.eots` | CID.`registro_habilitacion.auxiliar` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`public.eots` | CID.`verificacion_res_65.detalles_incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`public.eots` | CID.`verificacion_res_65.incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`public.eots` | CID.`verificacion_res_65.infraccion` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`public.eots` | CID.`verificacion_res_65.multas` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`public.eots` | CID.`verificacion_res_65.notificaciones` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`registro_habilitacion.auxiliar` | CID.`verificacion_res_65.detalles_incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`registro_habilitacion.auxiliar` | CID.`verificacion_res_65.incumplimientos` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`registro_habilitacion.auxiliar` | CID.`verificacion_res_65.infraccion` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`registro_habilitacion.auxiliar` | CID.`verificacion_res_65.multas` | SI |
| ENTRE SCHEMAS | `id_eot_vmt_hex` | CID.`registro_habilitacion.auxiliar` | CID.`verificacion_res_65.notificaciones` | SI |
| ENTRE SCHEMAS | `id_organismo` | CID.`public.tipo_perfil_especial` | CID.`sistema.usuarios` | SI |
| ENTRE SCHEMAS | `id_parametro` | CID.`control_metricas.parametros_ifo` | CID.`servicios_especiales.parametro_monitoreo` | SI |
| ENTRE SCHEMAS | `id_registro` | CID.`alertas.registro_ejecuciones` | CID.`registro_habilitacion.auditoria` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`geometria.geocercas` | CID.`gestion_uf.tipos_eot` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`geometria.geocercas` | CID.`public.tipos_eot` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`geometria.geocercas` | CID.`registro_habilitacion.tipos_carroceria` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`geometria.tipos_geocerca` | CID.`gestion_uf.tipos_eot` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`geometria.tipos_geocerca` | CID.`public.tipos_eot` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`geometria.tipos_geocerca` | CID.`registro_habilitacion.tipos_carroceria` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`gestion_uf.tipos_eot` | CID.`public.tipos_eot` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`gestion_uf.tipos_eot` | CID.`registro_habilitacion.tipos_carroceria` | SI |
| ENTRE SCHEMAS | `id_tipo` | CID.`public.tipos_eot` | CID.`registro_habilitacion.tipos_carroceria` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.composicion_uf` | CID.`public.composicion_uf` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.composicion_uf` | CID.`public.lineas` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.composicion_uf` | CID.`public.unidades_funcionales` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.contratos` | CID.`public.composicion_uf` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.contratos` | CID.`public.lineas` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.contratos` | CID.`public.unidades_funcionales` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.historico_explotacion_uf` | CID.`public.composicion_uf` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.historico_explotacion_uf` | CID.`public.lineas` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.historico_explotacion_uf` | CID.`public.unidades_funcionales` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.uf_troncales` | CID.`public.composicion_uf` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.uf_troncales` | CID.`public.lineas` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.uf_troncales` | CID.`public.unidades_funcionales` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.unidades_funcionales` | CID.`public.composicion_uf` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.unidades_funcionales` | CID.`public.lineas` | SI |
| ENTRE SCHEMAS | `id_uf` | CID.`gestion_uf.unidades_funcionales` | CID.`public.unidades_funcionales` | SI |
| ENTRE SCHEMAS | `id_usuario` | CID.`perfiles_especiales.perfiles_observaciones` | CID.`public.evidencia_importacion` | SI |
| ENTRE SCHEMAS | `id_usuario` | CID.`perfiles_especiales.perfiles_observaciones` | CID.`sistema.mensajes` | SI |
| ENTRE SCHEMAS | `id_usuario` | CID.`public.evidencia_importacion` | CID.`sistema.mensajes` | SI |
| ENTRE SCHEMAS | `idsam` | CID.`public.discapacitados` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `idsam` | CID.`public.frecuencia` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `idsam` | CID.`public.nservicios` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `idsam` | CID.`public.nvalidaciones_bus_datos` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `idsam` | CID.`public.salidas` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `idsam` | CID.`public.servicios_diarios` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.app_monitoreo` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.app_monitoreo_mensajeoperativo2` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.ncant_servicios` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.nservicios` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.nvalidaciones_bus` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`public.app_monitoreo` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`public.app_monitoreo_mensajeoperativo` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`public.app_monitoreo_mensajeoperativo2` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`public.ncant_servicios` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`public.nservicios` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `mean_id` | CID.`public.nvalidaciones_bus` | CID.`servicios_especiales.bus_adjudicacion` | SI |
| ENTRE SCHEMAS | `permiso_id` | CID.`public.rol_permiso` | CID.`sistema.rol_permiso` | SI |
| ENTRE SCHEMAS | `registro_id` | CID.`public.logs_auditoria` | CID.`sistema.logs_auditoria` | SI |
| ENTRE SCHEMAS | `rol_id` | CID.`public.rol_permiso` | CID.`sistema.rol_permiso` | SI |
| ENTRE SCHEMAS | `rol_id` | CID.`public.rol_permiso` | CID.`sistema.usuario_rol` | SI |
| ENTRE SCHEMAS | `rol_id` | CID.`public.rol_permiso` | CID.`sistema.usuario_sistema_rol` | SI |
| ENTRE SCHEMAS | `rol_id` | CID.`public.usuario_rol` | CID.`sistema.rol_permiso` | SI |
| ENTRE SCHEMAS | `rol_id` | CID.`public.usuario_rol` | CID.`sistema.usuario_rol` | SI |
| ENTRE SCHEMAS | `rol_id` | CID.`public.usuario_rol` | CID.`sistema.usuario_sistema_rol` | SI |
| ENTRE SCHEMAS | `route_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.app_monitoreo` | SI |
| ENTRE SCHEMAS | `route_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.app_monitoreo_mensajeoperativo` | SI |
| ENTRE SCHEMAS | `route_id` | CID.`control_metricas.cbd_detalle_buses` | CID.`public.app_monitoreo_mensajeoperativo2` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`gestion_uf.composicion_uf` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`gestion_uf.historico_explotacion_ruta` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`public.concesiones` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`public.frecuencia` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`public.historico_eot_ruta` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`public.linea_ruta_catalogo` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`public.salidas` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`geometria.historico_itinerario` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.composicion_uf` | CID.`public.concesiones` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.composicion_uf` | CID.`public.frecuencia` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.composicion_uf` | CID.`public.historico_eot_ruta` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.composicion_uf` | CID.`public.linea_ruta_catalogo` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.composicion_uf` | CID.`public.salidas` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.composicion_uf` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.concesiones` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.frecuencia` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.historico_eot_ruta` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.linea_ruta_catalogo` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`public.salidas` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`gestion_uf.historico_explotacion_ruta` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`public.concesiones` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`public.frecuencia` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`public.historico_eot_ruta` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`public.linea_ruta_catalogo` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `ruta_hex` | CID.`public.salidas` | CID.`servicios_especiales.ruta_servicio_especial` | SI |
| ENTRE SCHEMAS | `source_id` | CID.`geometria.paradas_oficiales` | CID.`public.itinerarios_oficiales` | NO |
| ENTRE SCHEMAS | `user_id` | CID.`public.auth_user_groups` | CID.`reclamo.caso_movimientos` | SI |
| ENTRE SCHEMAS | `user_id` | CID.`public.auth_user_user_permissions` | CID.`reclamo.caso_movimientos` | SI |
| ENTRE SCHEMAS | `user_id` | CID.`public.django_admin_log` | CID.`reclamo.caso_movimientos` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_acceso` | CID.`sistema.logs_acceso` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_acceso` | CID.`sistema.logs_auditoria` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_acceso` | CID.`sistema.notificaciones` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_acceso` | CID.`sistema.sesiones_usuarios` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_acceso` | CID.`sistema.usuario_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_acceso` | CID.`sistema.usuario_sistema_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_auditoria` | CID.`sistema.logs_acceso` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_auditoria` | CID.`sistema.logs_auditoria` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_auditoria` | CID.`sistema.notificaciones` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_auditoria` | CID.`sistema.sesiones_usuarios` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_auditoria` | CID.`sistema.usuario_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.logs_auditoria` | CID.`sistema.usuario_sistema_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.notificaciones` | CID.`sistema.logs_acceso` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.notificaciones` | CID.`sistema.logs_auditoria` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.notificaciones` | CID.`sistema.notificaciones` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.notificaciones` | CID.`sistema.sesiones_usuarios` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.notificaciones` | CID.`sistema.usuario_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.notificaciones` | CID.`sistema.usuario_sistema_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.sesiones_usuarios` | CID.`sistema.logs_acceso` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.sesiones_usuarios` | CID.`sistema.logs_auditoria` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.sesiones_usuarios` | CID.`sistema.notificaciones` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.sesiones_usuarios` | CID.`sistema.sesiones_usuarios` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.sesiones_usuarios` | CID.`sistema.usuario_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.sesiones_usuarios` | CID.`sistema.usuario_sistema_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.usuario_rol` | CID.`sistema.logs_acceso` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.usuario_rol` | CID.`sistema.logs_auditoria` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.usuario_rol` | CID.`sistema.notificaciones` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.usuario_rol` | CID.`sistema.sesiones_usuarios` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.usuario_rol` | CID.`sistema.usuario_rol` | SI |
| ENTRE SCHEMAS | `usuario_id` | CID.`public.usuario_rol` | CID.`sistema.usuario_sistema_rol` | SI |

---

# BD CID


## Schema `alertas`


### `alertas.acciones_alerta` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_accion` | integer | NO | SI |  |  |
| `id_alerta` | integer | NO |  | alertas.control_alertas.id_alerta |  |
| `fechahora_accion` | timestamp without time zone | SI |  |  |  |
| `funcionario` | character varying(100) | NO |  |  |  |
| `accion_realizada` | text | NO |  |  |  |
| `soluciono_problema` | boolean | SI |  |  |  |

### `alertas.control_alertas` (TABLA, ~2,532 filas, 1464 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_alerta` | integer | NO | SI |  |  |
| `fuente` | character varying(100) | NO |  |  |  |
| `fechahora_alerta` | timestamp without time zone | SI |  |  |  |
| `id_tipo_alerta` | integer | NO |  | alertas.tipo_alerta.id_tipo_alerta |  |
| `verificado` | boolean | SI |  |  |  |
| `corregido` | boolean | SI |  |  |  |
| `descripcion_incidente` | text | SI |  |  |  |

### `alertas.registro_ejecuciones` (TABLA, ~7,392 filas, 1056 kB)
> Registro de ejecuciones exitosas de workflows n8n para monitoreo diario

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_registro` | integer | NO | SI |  |  |
| `fecha_proceso` | date | NO |  |  | Fecha que procesó el workflow (ej: si ejecuta el 12-01-2025 procesando datos del 11-01-2025, esta columna tendrá 2025-01-11) |
| `fecha_ejecucion` | timestamp without time zone | SI |  |  |  |
| `estado` | character varying(50) | SI |  |  |  |
| `detalles` | text | SI |  |  |  |
| `id_script` | integer | SI |  | alertas.scripts.id_script |  |

### `alertas.scripts` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_script` | integer | NO | SI |  |  |
| `nombre_script` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |

### `alertas.tipo_alerta` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo_alerta` | integer | NO | SI |  |  |
| `descripcion` | character varying(100) | NO |  |  |  |
| `prioridad` | character varying(20) | SI |  |  |  |

## Schema `asistencias`


### `asistencias.asistencias` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `funcionario_id` | bigint | NO |  | asistencias.funcionarios.id |  |
| `fecha` | date | NO |  |  |  |
| `hora_entrada` | time without time zone | SI |  |  |  |
| `hora_salida` | time without time zone | SI |  |  |  |
| `estado` | character varying(20) | NO |  |  |  |
| `created_at` | timestamp without time zone | NO |  |  |  |
| `updated_at` | timestamp without time zone | NO |  |  |  |

### `asistencias.dependencias` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `nombre` | character varying(200) | NO |  |  |  |
| `created_at` | timestamp without time zone | NO |  |  |  |

### `asistencias.funcionarios` (TABLA, ~54 filas, 56 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `nombre` | character varying(150) | NO |  |  |  |
| `cedula` | character varying(20) | NO |  |  |  |
| `cargo` | character varying(120) | NO |  |  |  |
| `dependencia_id` | bigint | NO |  | asistencias.dependencias.id |  |
| `estado` | character varying(20) | NO |  |  |  |
| `created_at` | timestamp without time zone | NO |  |  |  |
| `updated_at` | timestamp without time zone | NO |  |  |  |

### `asistencias.permisos` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `funcionario_id` | bigint | NO |  | asistencias.funcionarios.id |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | NO |  |  |  |
| `motivo` | text | NO |  |  |  |
| `tipo_permiso` | character varying(80) | NO |  |  |  |
| `created_at` | timestamp without time zone | NO |  |  |  |

### `asistencias.users` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `username` | character varying(100) | NO |  |  |  |
| `password_hash` | character varying(255) | NO |  |  |  |
| `full_name` | character varying(150) | NO |  |  |  |
| `role` | character varying(20) | NO |  |  |  |
| `dependencia_id` | bigint | SI |  | asistencias.dependencias.id |  |
| `active` | boolean | NO |  |  |  |
| `created_at` | timestamp without time zone | NO |  |  |  |

## Schema `compensacion`


### `compensacion.compensacion_archivos` (TABLA, ~1,599 filas, 125 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fecha` | date | NO | SI | compensacion.compensacion_interoperabilidad.fecha |  |
| `archivo_tdp` | bytea | SI |  |  |  |
| `archivo_epas` | bytea | SI |  |  |  |
| `archivo_transferencia` | bytea | SI |  |  |  |
| `fecha_carga` | timestamp without time zone | SI |  |  |  |

### `compensacion.compensacion_interoperabilidad` (TABLA, ~1,608 filas, 600 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fecha` | date | NO | SI |  |  |
| `a23_tdp` | numeric(18,2) | SI |  |  |  |
| `a32_tdp` | numeric(18,2) | SI |  |  |  |
| `a23_epas` | numeric(18,2) | SI |  |  |  |
| `a32_epas` | numeric(18,2) | SI |  |  |  |
| `monto_a_transferir` | numeric(18,2) | SI |  |  |  |
| `monto_transferido` | numeric(18,2) | SI |  |  |  |
| `inf_quincenal` | boolean | SI |  |  |  |
| `inf_mensual` | boolean | SI |  |  |  |
| `inf_trimestral` | boolean | SI |  |  |  |

### `compensacion.compensacion_transferencias` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_transferencia` | date | NO |  |  |  |
| `monto` | numeric(18,2) | NO |  |  |  |
| `comprobante` | character varying(100) | SI |  |  |  |
| `comentario` | text | SI |  |  |  |
| `origen` | character varying(50) | SI |  |  |  |
| `destino` | character varying(50) | SI |  |  |  |
| `metodo_pago` | character varying(100) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |
| `fecha_compensada` | date | NO |  | compensacion.compensacion_interoperabilidad.fecha |  |

## Schema `control_metricas`


### `control_metricas.cbd_detalle_buses` (TABLA, ~7,086,132 filas, 2236 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_eot_vmt_hex` | text | NO |  |  |  |
| `fecha` | date | NO |  |  |  |
| `hora` | integer | SI |  |  |  |
| `mean_id` | text | NO |  |  |  |
| `route_id` | text | SI |  |  |  |
| `primera_posicion_timestamp` | timestamp without time zone | SI |  |  |  |
| `ultima_posicion_timestamp` | timestamp without time zone | SI |  |  |  |
| `cantidad_mensajes` | integer | SI |  |  |  |

### `control_metricas.cbd_parametros_minimos` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_tipo_dia` | integer | SI |  |  |  |
| `id_franja` | integer | SI |  |  |  |
| `cbd_minimo_franja` | integer | NO |  |  |  |
| `cbd_minimo_hora` | integer | SI |  |  |  |
| `vigencia_desde` | date | SI |  |  |  |
| `vigencia_hasta` | date | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `id_infraccion_hora` | integer | SI |  |  |  |
| `id_infraccion_franja` | integer | SI |  |  |  |

### `control_metricas.dias_atipicos` (TABLA, ~284 filas, 136 kB)
> Tabla para identificar días que requieren ajuste en exigencia o exclusión de histórico.

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fecha` | date | NO | SI |  | Clave primaria. Fecha del evento. |
| `tipo_atipico` | character varying(50) | NO | SI |  | Categoría del día: FERIADO_LAB, FERIADO_SAB, PRE_POS_FERIADO, LLUVIA, DISRUPTIVO. |
| `factor_exigencia` | numeric(3,2) | NO |  |  | Porcentaje de la flota habitual exigida (ej: 0.30, 0.50, 1.00). |
| `descartar_historico` | boolean | NO |  |  | Indica si el día debe saltarse al buscar las 4 semanas de referencia histórica. |
| `fuente_dato` | character varying(100) | SI |  |  | Origen de la información (DINAC, DMT, etc.). |
| `observacion` | text | SI |  |  | Descripción detallada del evento, especialmente para casos DISRUPTIVOS. |
| `id_tipo_dia_aplicable` | integer | SI |  | control_metricas.tipo_dia.id_tipo_dia |  |

### `control_metricas.franjas_operativas` (TABLA, ~0 filas, 88 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_franja` | integer | NO | SI |  |  |
| `denominacion` | character varying(100) | NO |  |  |  |
| `hora_inicio` | time without time zone | NO |  |  |  |
| `hora_fin` | time without time zone | NO |  |  |  |
| `id_tipo_dia` | integer | NO |  | control_metricas.tipo_dia.id_tipo_dia |  |
| `inicio_vigencia` | date | NO |  |  |  |
| `fin_vigencia` | date | SI |  |  |  |
| `activo` | boolean | NO |  |  |  |

### `control_metricas.ifo_historico` (TABLA, ~53,948 filas, 15 MB)
> Histórico del Índice de Frecuencia Operativa (IFO) por EOT, fecha y franja operativa

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_eot_vmt_hex` | character varying | NO |  | public.eots.id_eot_vmt_hex | ID de la Empresa Operadora de Transporte |
| `fecha` | date | NO |  |  | Fecha del cálculo del IFO |
| `id_franja` | integer | NO |  |  | ID de la franja operativa |
| `ifo` | numeric(6,4) | NO |  |  | Índice de Frecuencia Operativa (valor entre 0 y N) |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |
| `cumple_parametros` | boolean | SI |  |  |  |
| `nivel` | character varying(1) | SI |  |  |  |
| `cbd_indice` | numeric(10,4) | SI |  |  | Índice CBD de la franja (0.0 a 1.0+) |
| `cbd_cantidad` | integer | SI |  |  | Cantidad de buses únicos operando en la franja |

### `control_metricas.incumplimientos_cbd` (TABLA, ~0 filas, 104 kB)
> Registro de incumplimientos de CBD por EOT y franja

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_analisis` | date | NO |  |  |  |
| `eot_id` | integer | NO |  |  |  |
| `id_franja` | integer | NO |  |  |  |
| `denominacion_franja` | character varying(100) | SI |  |  |  |
| `cbd_obs_promedio` | numeric(10,2) | SI |  |  |  |
| `cbd_minimo_franja_exigido` | numeric(10,2) | SI |  |  |  |
| `cbd_cumplimiento_franja_indice` | numeric(5,4) | SI |  |  |  |
| `cbd_estado_cumplimiento` | character varying(20) | SI |  |  |  |
| `tipo_infraccion` | character varying(20) | SI |  |  |  |
| `ajuste_aplicado` | character varying(100) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |

### `control_metricas.incumplimientos_ifo` (TABLA, ~0 filas, 64 kB)
> Registro de incumplimientos de IFO por EOT y franja

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_analisis` | date | NO |  |  |  |
| `eot_id` | integer | NO |  |  |  |
| `id_franja` | integer | NO |  |  |  |
| `denominacion_franja` | character varying(100) | SI |  |  |  |
| `cbd_obs_promedio` | numeric(10,2) | SI |  |  |  |
| `b_dist_ajustado` | numeric(10,2) | SI |  |  |  |
| `ifo_franja_calculado` | numeric(5,2) | SI |  |  |  |
| `ifo_minimo_exigido` | numeric(5,2) | SI |  |  |  |
| `diferencia_porcentual` | numeric(5,2) | SI |  |  |  |
| `ajuste_aplicado` | character varying(100) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |

### `control_metricas.metricas` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_metrica` | integer | NO | SI |  |  |
| `nombre_metrica` | character varying(50) | NO |  |  |  |
| `desc_metrica` | text | SI |  |  |  |

### `control_metricas.niveles_infraccion` (TABLA, ~4 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_infraccion` | integer | NO | SI |  |  |
| `descripcion` | character varying(100) | NO |  |  |  |
| `jornales` | numeric(5,2) | SI |  |  |  |

### `control_metricas.parametros_ifo` (TABLA, ~10 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_parametro` | integer | NO | SI |  |  |
| `descripcion` | character varying(255) | NO |  |  |  |
| `normativa` | character varying(255) | SI |  |  |  |
| `id_franja_operativa` | integer | NO |  |  |  |
| `porc_cumplimiento_minimo` | numeric(5,2) | SI |  |  |  |
| `muestreo_meses` | integer | SI |  |  |  |
| `id_infraccion` | integer | SI |  | control_metricas.niveles_infraccion.id_infraccion |  |
| `inicio_vigencia` | date | NO |  |  |  |
| `fin_vigencia` | date | SI |  |  |  |
| `id_metrica` | integer | NO |  | control_metricas.metricas.id_metrica |  |

### `control_metricas.resultados_diarios` (TABLA, ~218 filas, 112 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fecha_analisis` | date | NO | SI |  |  |
| `eot_id` | integer | NO | SI |  |  |
| `id_franja` | integer | NO | SI |  |  |
| `denominacion_franja` | text | SI |  |  |  |
| `cbd_obs_promedio` | double precision | SI |  |  |  |
| `origen_cbd_final` | text | SI |  |  |  |
| `b_dist_ajustado` | double precision | SI |  |  |  |
| `cbd_minimo_franja_exigido` | double precision | SI |  |  |  |
| `cbd_cumplimiento_franja_indice` | double precision | SI |  |  |  |
| `cbd_estado_cumplimiento` | text | SI |  |  |  |
| `ifo_franja_calculado` | double precision | SI |  |  |  |
| `ifo_estado_cumplimiento` | text | SI |  |  |  |
| `ajuste_aplicado` | text | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |

### `control_metricas.t_casuisticas_lluvia` (TABLA, ~389 filas, 128 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_evento` | date | NO |  |  |  |
| `hora_inicio` | time without time zone | NO |  |  |  |
| `hora_fin` | time without time zone | NO |  |  |  |
| `es_lluvia_intensa` | boolean | SI |  |  |  |
| `registro_comprobado` | boolean | SI |  |  |  |
| `factor_ajuste` | numeric(3,2) | SI |  |  |  |
| `fuente_registro` | character varying(100) | SI |  |  |  |
| `notas` | text | SI |  |  |  |
| `mm_caidos` | numeric(5,2) | SI |  |  |  |

### `control_metricas.tipo_dia` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo_dia` | integer | NO | SI |  |  |
| `codigo` | character varying(20) | NO |  |  |  |
| `descripcion` | character varying(100) | NO |  |  |  |
| `activo` | boolean | NO |  |  |  |

## Schema `geometria`


### `geometria.geocercas` (TABLA, ~34,828 filas, 80 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_geocerca` | integer | NO | SI |  |  |
| `id_itinerario` | integer | SI |  | geometria.historico_itinerario.id_itinerario |  |
| `id_tipo` | integer | NO |  | geometria.tipos_geocerca.id_tipo |  |
| `orden` | integer | NO |  |  |  |
| `geom` | geometry(Polygon,4326) | NO |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_actualizacion` | timestamp without time zone | SI |  |  |  |
| `id_troncal_uf` | integer | SI |  | gestion_uf.uf_troncales.id_troncal |  |

### `geometria.historico_itinerario` (TABLA, ~481 filas, 8208 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_itinerario` | integer | NO | SI |  |  |
| `ruta_hex` | text | NO |  | public.catalogo_rutas.ruta_hex |  |
| `fecha_inicio_vigencia` | date | NO |  |  |  |
| `fecha_fin_vigencia` | date | SI |  |  |  |
| `vigente` | boolean | SI |  |  |  |
| `observacion` | text | SI |  |  |  |
| `geom` | geometry(MultiLineString,4326) | NO |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_actualizacion` | timestamp without time zone | SI |  |  |  |
| `aprobado` | boolean | NO |  |  |  |
| `fecha_aprobacion` | timestamp without time zone | SI |  |  |  |
| `aprobado_por` | character varying(100) | SI |  |  |  |
| `creado_por` | character varying(100) | SI |  |  |  |
| `modificado_por` | character varying(100) | SI |  |  |  |
| `geojson_simple` | text | SI |  |  |  |
| `hash_geometria` | character varying(64) | SI |  |  |  |
| `nro_resolucion` | character varying(100) | SI |  |  |  |
| `observacion_resolucion` | text | SI |  |  |  |
| `hash_fecha` | timestamp without time zone | SI |  |  |  |

### `geometria.itinerario_parada` (TABLA, ~13,549 filas, 1120 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_itinerario` | integer | NO | SI | geometria.historico_itinerario.id_itinerario |  |
| `id_parada` | integer | NO | SI | geometria.paradas_oficiales.id |  |
| `orden` | integer | SI |  |  |  |

### `geometria.paradas` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_parada` | integer | NO | SI |  |  |
| `id_itinerario` | integer | NO |  | geometria.historico_itinerario.id_itinerario |  |
| `nombre` | text | SI |  |  |  |
| `orden` | integer | NO |  |  |  |
| `tipo` | text | SI |  |  |  |
| `geom` | geometry(Point,4326) | SI |  |  |  |

### `geometria.paradas_oficiales` (TABLA, ~797 filas, 1272 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `source_id` | text | SI |  |  |  |
| `source_name` | text | SI |  |  |  |
| `attrs` | jsonb | NO |  |  |  |
| `geom` | geometry(Point,4326) | NO |  |  |  |
| `created_at` | timestamp with time zone | NO |  |  |  |
| `bearing` | double precision | SI |  |  |  |
| `location_type` | integer | SI |  |  |  |
| `parent_station` | character varying | SI |  |  |  |

### `geometria.puntos_terminales` (TABLA, ~103 filas, 256 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_punto` | integer | NO | SI |  |  |
| `id_tipo_geocerca` | integer | NO |  | geometria.tipos_geocerca.id_tipo | Clave foránea a geometria.tipos_geocerca.id_tipo (1=Inicio, 2=Fin, 5=Retorno, 6=Terminal, etc.) |
| `id_eot_vmt_hex` | character varying(50) | NO |  | public.eots.id_eot_vmt_hex |  |
| `numero_terminal` | character varying(100) | NO |  |  |  |
| `latitude` | numeric(10,7) | NO |  |  |  |
| `longitude` | numeric(10,7) | NO |  |  |  |
| `radio_geocerca_m` | integer | NO |  |  |  |
| `geom_punto` | geometry(Point,4326) | NO |  |  |  |
| `geom_geocerca` | geometry(Polygon,4326) | SI |  |  | Buffer geométrico circular generado a partir de latitude, longitude y radio_geocerca_m |
| `fecha_creacion` | timestamp with time zone | SI |  |  |  |
| `fecha_actualizacion` | timestamp with time zone | SI |  |  |  |

### `geometria.tipos_geocerca` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo` | integer | NO | SI |  |  |
| `nombre` | character varying(50) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |

## Schema `gestion_cid`


### `gestion_cid.alertas` (TABLA, ~0 filas, 48 kB)
> Sistema de alertas y notificaciones

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `documento_recibido_id` | integer | SI |  | gestion_cid.documentos_recibidos.id |  |
| `tipo_alerta` | character varying(50) | SI |  |  |  |
| `nivel` | character varying(20) | SI |  |  |  |
| `mensaje` | text | SI |  |  |  |
| `fecha_alerta` | timestamp without time zone | SI |  |  |  |
| `notificado` | boolean | SI |  |  |  |
| `fecha_notificacion` | timestamp without time zone | SI |  |  |  |

### `gestion_cid.auditoria_acciones` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `accion` | character varying(100) | NO |  |  |  |
| `entidad` | character varying(100) | NO |  |  |  |
| `entidad_id` | character varying(100) | NO |  |  |  |
| `usuario` | character varying(150) | SI |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `datos_despues` | jsonb | SI |  |  |  |
| `workflow_id` | character varying(100) | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `gestion_cid.documentos_recibidos` (TABLA, ~0 filas, 64 kB)
> Documentos recibidos por la institución

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `codigo_documento` | character varying(50) | NO |  |  |  |
| `fecha_recepcion` | timestamp without time zone | SI |  |  |  |
| `tipo_documento` | character varying(50) | SI |  |  |  |
| `remitente` | character varying(200) | SI |  |  |  |
| `cargo_remitente` | character varying(200) | SI |  |  |  |
| `asunto` | text | SI |  |  |  |
| `texto_completo` | text | SI |  |  |  |
| `prioridad` | character varying(20) | SI |  |  |  |
| `estado` | character varying(50) | SI |  |  |  |
| `requiere_respuesta` | boolean | SI |  |  |  |
| `fecha_limite` | date | SI |  |  |  |
| `url_archivo_original` | text | SI |  |  |  |
| `analisis_ia` | jsonb | SI |  |  |  |
| `normativas_relacionadas` | jsonb | SI |  |  |  |
| `tags` | text[] | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |
| `drive_file_id` | character varying(255) | SI |  |  |  |
| `drive_file_name` | character varying(500) | SI |  |  |  |
| `url_archivo_drive` | text | SI |  |  |  |
| `ocr_procesado` | boolean | SI |  |  |  |
| `ocr_confianza` | numeric(5,2) | SI |  |  |  |
| `ocr_metodo` | character varying(50) | SI |  |  |  |
| `procesado_por` | character varying(100) | SI |  |  |  |

### `gestion_cid.documentos_salientes` (TABLA, ~0 filas, 48 kB)
> Documentos emitidos como respuesta o comunicación

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `documento_recibido_id` | integer | SI |  | gestion_cid.documentos_recibidos.id |  |
| `codigo_documento` | character varying(50) | NO |  |  |  |
| `fecha_emision` | timestamp without time zone | SI |  |  |  |
| `tipo_documento` | character varying(50) | SI |  |  |  |
| `destinatario` | character varying(200) | SI |  |  |  |
| `asunto` | text | SI |  |  |  |
| `url_archivo` | text | SI |  |  |  |
| `es_borrador` | boolean | SI |  |  |  |
| `aprobado_por` | character varying(100) | SI |  |  |  |
| `fecha_aprobacion` | timestamp without time zone | SI |  |  |  |
| `tiempo_respuesta_dias` | integer | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `gestion_cid.historial_respuestas` (TABLA, ~0 filas, 40 kB)
> Historial para aprendizaje del sistema de IA

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `documento_recibido_id` | integer | SI |  | gestion_cid.documentos_recibidos.id |  |
| `documento_recibido_tipo` | character varying(50) | SI |  |  |  |
| `documento_recibido_tema` | character varying(200) | SI |  |  |  |
| `respuesta_generada` | text | SI |  |  |  |
| `respuesta_final` | text | SI |  |  |  |
| `calificacion` | integer | SI |  |  |  |
| `feedback` | text | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `gestion_cid.normativas` (TABLA, ~0 filas, 48 kB)
> Base de conocimiento de normativas y regulaciones

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(200) | SI |  |  |  |
| `tipo` | character varying(50) | SI |  |  |  |
| `numero` | character varying(50) | SI |  |  |  |
| `fecha_publicacion` | date | SI |  |  |  |
| `vigente` | boolean | SI |  |  |  |
| `url_archivo` | text | SI |  |  |  |
| `contenido_texto` | text | SI |  |  |  |
| `vector_embeddings` | jsonb | SI |  |  |  |
| `tags` | text[] | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

## Schema `gestion_uf`


### `gestion_uf.composicion_consorcio` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_comp_cons` | integer | NO | SI |  |  |
| `id_consorcio` | integer | SI |  | public.eots.eot_id |  |
| `id_eot` | integer | SI |  | public.eots.eot_id |  |
| `participacion_pct` | double precision | SI |  |  |  |
| `es_lider` | boolean | SI |  |  |  |
| `fecha_inicio` | date | SI |  |  |  |
| `fecha_fin` | date | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |

### `gestion_uf.composicion_uf` (TABLA, ~543 filas, 112 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_composicion_uf` | integer | NO | SI |  |  |
| `id_uf` | integer | SI |  | gestion_uf.unidades_funcionales.id_uf |  |
| `ruta_hex` | text | SI |  | public.catalogo_rutas.ruta_hex |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | SI |  |  |  |
| `resolucion_legal` | character varying(255) | SI |  |  |  |

### `gestion_uf.contratos` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_contrato` | integer | NO | SI |  |  |
| `numero_contrato` | character varying(100) | SI |  |  |  |
| `id_eot` | integer | SI |  | public.eots.eot_id |  |
| `id_uf` | integer | SI |  | gestion_uf.unidades_funcionales.id_uf |  |
| `fecha_firma` | date | SI |  |  |  |
| `vencimiento` | date | SI |  |  |  |
| `estado_contrato` | character varying(50) | SI |  |  |  |

### `gestion_uf.historico_explotacion_ruta` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_hexp_ruta` | integer | NO | SI |  |  |
| `id_eot` | integer | SI |  | public.eots.eot_id |  |
| `ruta_hex` | text | SI |  | public.catalogo_rutas.ruta_hex |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | SI |  |  |  |

### `gestion_uf.historico_explotacion_uf` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_hexp_uf` | integer | NO | SI |  |  |
| `id_eot` | integer | SI |  | public.eots.eot_id |  |
| `id_uf` | integer | SI |  | gestion_uf.unidades_funcionales.id_uf |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | SI |  |  |  |

### `gestion_uf.tipos_eot` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo` | integer | NO | SI |  |  |
| `nombre` | character varying(50) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |

### `gestion_uf.uf_troncales` (TABLA, ~5 filas, 256 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_troncal` | integer | NO | SI |  |  |
| `id_uf` | integer | NO |  | gestion_uf.unidades_funcionales.id_uf |  |
| `nombre` | character varying(100) | SI |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `geom` | geometry(Geometry,4326) | NO |  |  |  |
| `color_hex` | character varying(7) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_actualizacion` | timestamp without time zone | SI |  |  |  |
| `es_principal` | boolean | SI |  |  |  |

### `gestion_uf.unidades_funcionales` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_uf` | integer | NO | SI |  |  |
| `nombre_uf` | character varying(100) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `tipo_uf` | character varying(50) | SI |  |  |  |
| `norma_legal` | character varying(255) | SI |  |  |  |
| `estado` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |

## Schema `perfiles_especiales`


### `perfiles_especiales.perfiles_observaciones` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_observacion` | integer | NO | SI |  |  |
| `orden` | integer | NO |  |  |  |
| `observacion` | text | NO |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `id_usuario` | integer | NO |  | sistema.usuarios.id |  |
| `atendido` | boolean | SI |  |  |  |
| `resuelto` | boolean | SI |  |  |  |

## Schema `public`


### `public.app_monitoreo` (TABLA, ~1,703 filas, 1632 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario_broker` | character varying(255) | SI |  |  |  |
| `identidad` | bigint | SI |  |  |  |
| `agency_id` | character varying(255) | SI |  |  |  |
| `mean_id` | character varying(255) | SI |  |  |  |
| `route_id` | character varying(255) | SI |  |  |  |
| `driver_id` | character varying(255) | SI |  |  |  |
| `type` | integer | SI |  |  |  |
| `precision` | integer | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `ubicacion` | geometry | SI |  |  |  |
| `altitud` | double precision | SI |  |  |  |
| `rumbo` | double precision | SI |  |  |  |
| `velocidad` | double precision | SI |  |  |  |
| `fecha_hora` | timestamp with time zone | SI |  |  |  |
| `fecha_hora_procesamiento` | timestamp with time zone | SI |  |  |  |
| `emisor_id` | bigint | SI |  |  |  |

### `public.app_monitoreo_mensajeoperativo` (TABLA, ~5,109 filas, 2792 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario_broker` | character varying(255) | SI |  |  |  |
| `identidad` | bigint | SI |  |  |  |
| `agency_id` | character varying(255) | SI |  |  |  |
| `mean_id` | character varying(255) | SI |  |  |  |
| `route_id` | character varying(255) | SI |  |  |  |
| `driver_id` | character varying(255) | SI |  |  |  |
| `type` | integer | SI |  |  |  |
| `precision` | integer | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `ubicacion` | geometry | SI |  |  |  |
| `altitud` | double precision | SI |  |  |  |
| `rumbo` | double precision | SI |  |  |  |
| `velocidad` | double precision | SI |  |  |  |
| `fecha_hora` | timestamp with time zone | SI |  |  |  |
| `fecha_hora_procesamiento` | timestamp with time zone | SI |  |  |  |
| `emisor_id` | bigint | SI |  |  |  |

### `public.app_monitoreo_mensajeoperativo2` (TABLA FORANEA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO |  |  |  |
| `usuario_broker` | character varying(255) | SI |  |  |  |
| `identidad` | bigint | NO |  |  |  |
| `agency_id` | character varying(255) | NO |  |  |  |
| `mean_id` | character varying(255) | NO |  |  |  |
| `route_id` | character varying(255) | NO |  |  |  |
| `driver_id` | character varying(255) | NO |  |  |  |
| `type` | integer | NO |  |  |  |
| `precision` | integer | NO |  |  |  |
| `latitude` | double precision | NO |  |  |  |
| `longitude` | double precision | NO |  |  |  |
| `ubicacion` | geometry | SI |  |  |  |
| `altitud` | double precision | NO |  |  |  |
| `rumbo` | double precision | NO |  |  |  |
| `velocidad` | double precision | NO |  |  |  |
| `fecha_hora` | timestamp with time zone | SI |  |  |  |
| `fecha_hora_procesamiento` | timestamp with time zone | SI |  |  |  |
| `emisor_id` | bigint | SI |  |  |  |

### `public.auth_group` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `name` | character varying(150) | NO |  |  |  |

### `public.auth_group_permissions` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `group_id` | integer | NO |  | public.auth_group.id |  |
| `permission_id` | integer | NO |  | public.auth_permission.id |  |

### `public.auth_permission` (TABLA, ~0 filas, 56 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `name` | character varying(255) | NO |  |  |  |
| `content_type_id` | integer | NO |  | public.django_content_type.id |  |
| `codename` | character varying(100) | NO |  |  |  |

### `public.auth_user` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `password` | character varying(128) | NO |  |  |  |
| `last_login` | timestamp with time zone | SI |  |  |  |
| `is_superuser` | boolean | NO |  |  |  |
| `username` | character varying(150) | NO |  |  |  |
| `first_name` | character varying(150) | NO |  |  |  |
| `last_name` | character varying(150) | NO |  |  |  |
| `email` | character varying(254) | NO |  |  |  |
| `is_staff` | boolean | NO |  |  |  |
| `is_active` | boolean | NO |  |  |  |
| `date_joined` | timestamp with time zone | NO |  |  |  |

### `public.auth_user_groups` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `user_id` | integer | NO |  | public.auth_user.id |  |
| `group_id` | integer | NO |  | public.auth_group.id |  |

### `public.auth_user_user_permissions` (TABLA, ~0 filas, 72 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `user_id` | integer | NO |  | public.auth_user.id |  |
| `permission_id` | integer | NO |  | public.auth_permission.id |  |

### `public.backups_sistema` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `ruta_archivo` | character varying(500) | NO |  |  |  |
| `tamano_bytes` | integer | SI |  |  |  |
| `tipo` | character varying(20) | SI |  |  |  |
| `estado` | character varying(20) | SI |  |  |  |
| `fecha_inicio` | timestamp without time zone | SI |  |  |  |
| `fecha_fin` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | public.usuarios.id |  |
| `detalles` | json | SI |  |  |  |

### `public.buses_declarados` (TABLA, ~199 filas, 72 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_bd` | integer | NO | SI |  |  |
| `cod_catalogo` | integer | SI |  |  |  |
| `empresa` | character varying(120) | SI |  |  |  |
| `cant_ope_declarada` | integer | SI |  |  |  |
| `cant_reserva_declarada` | integer | SI |  |  |  |
| `total_cant_declarada` | integer | SI |  |  |  |
| `diferencial_declarada` | integer | SI |  |  |  |
| `dife_inclusivo_declarada` | integer | SI |  |  |  |
| `convencional_declarado` | integer | SI |  |  |  |
| `conv_inclusivo_declarado` | integer | SI |  |  |  |
| `fecha_hora` | timestamp with time zone | SI |  |  |  |

### `public.cant_buses_por_eot` (TABLA, ~484 filas, 328 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha` | date | NO |  |  |  |
| `agency_id` | character varying(10) | NO |  |  |  |
| `eot_nombre` | character varying(255) | SI |  |  |  |
| `buses_operativos` | integer | NO |  |  |  |
| `buses_detectados` | integer | NO |  |  |  |
| `porcentaje_operativo` | numeric(5,2) | SI |  |  |  |
| `franja_horaria` | character varying(50) | SI |  |  |  |
| `metodo_verificacion` | character varying(50) | SI |  |  |  |
| `distancia_promedio` | numeric(10,2) | SI |  |  |  |
| `buses_con_movimiento` | integer | SI |  |  |  |
| `buses_sin_movimiento` | integer | SI |  |  |  |
| `puntos_gps_totales` | integer | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |

### `public.catalogo_rutas` (TABLA, ~548 filas, 5920 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `ruta_hex` | text | NO | SI |  |  |
| `id_eot_catalogo` | bigint | SI |  |  |  |
| `ruta_gtfs` | double precision | SI |  |  |  |
| `ruta_dec` | bigint | SI |  |  |  |
| `sentido` | text | SI |  |  |  |
| `ramal` | bigint | SI |  |  |  |
| `origen` | text | SI |  |  |  |
| `destino` | text | SI |  |  |  |
| `identificacion` | text | SI |  |  |  |
| `identificador_troncal` | text | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `par_id` | integer | SI |  |  |  |
| `ingresa` | integer | SI |  |  |  |
| `latitud_a` | double precision | SI |  |  |  |
| `longitud_a` | double precision | SI |  |  |  |
| `latitud_b` | double precision | SI |  |  |  |
| `longitud_b` | double precision | SI |  |  |  |
| `estado` | boolean | SI |  |  |  |

### `public.composicion_uf` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_comp_uf` | integer | NO | SI |  |  |
| `id_uf` | integer | SI |  | public.unidades_funcionales.id_uf |  |
| `id_linea` | integer | SI |  | public.lineas.id_linea |  |

### `public.concesiones` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `concesion_id` | integer | NO | SI |  |  |
| `eot_id` | integer | NO |  | public.eots.eot_id |  |
| `ruta_hex` | character varying(255) | NO |  | public.catalogo_rutas.ruta_hex |  |
| `fecha_inicio_vigencia` | date | NO |  |  |  |
| `fecha_fin_vigencia` | date | SI |  |  |  |
| `vigente` | boolean | NO |  |  |  |
| `creado_por` | character varying(50) | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `documento_respaldo` | bytea | SI |  |  |  |
| `nombre_documento` | character varying(255) | SI |  |  |  |

### `public.configuracion_email` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `host` | character varying(100) | NO |  |  |  |
| `puerto` | integer | NO |  |  |  |
| `username` | character varying(100) | NO |  |  |  |
| `password` | character varying(255) | NO |  |  |  |
| `from_email` | character varying(100) | NO |  |  |  |
| `use_tls` | boolean | SI |  |  |  |
| `use_ssl` | boolean | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | public.usuarios.id |  |

### `public.consorcios` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_consorcio` | integer | NO | SI |  |  |
| `nombre` | character varying(200) | NO |  |  |  |
| `id_externo_cid` | character varying(50) | SI |  |  |  |

### `public.control_compensaciones_diarias` (TABLA, ~0 filas, 136 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fecha` | timestamp without time zone | SI |  |  |  |
| `alpha22` | bigint | SI |  |  |  |
| `alpha23` | bigint | SI |  |  |  |
| `alpha32` | bigint | SI |  |  |  |
| `alpha33` | bigint | SI |  |  |  |
| `transferencia_eps` | double precision | SI |  |  |  |
| `transferencia_comprobante` | double precision | SI |  |  |  |
| `nro_comprobante` | double precision | SI |  |  |  |
| `coincidencia` | boolean | SI |  |  |  |
| `seriales procesados` | bigint | SI |  |  |  |
| `seriales con evento tipo 4` | double precision | SI |  |  |  |
| `seriales con diferencias epas` | double precision | SI |  |  |  |
| `seriales con diferencias tdp` | double precision | SI |  |  |  |
| `seriales excluidos` | double precision | SI |  |  |  |
| `porcentaje excluidas sobre procesadas` | double precision | SI |  |  |  |

### `public.discapacitados` (TABLA, ~1,136 filas, 392 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `serialmediopago` | text | SI |  |  |  |
| `fechaevento` | text | SI |  |  |  |
| `idsam` | text | SI |  |  |  |
| `consecutivoaplicación` | text | SI |  |  |  |
| `estadoaplicación` | text | SI |  |  |  |
| `númeroacciónaplicada` | text | SI |  |  |  |
| `datosperfilfuncionario` | text | SI |  |  |  |
| `fechanacimientousuario` | text | SI |  |  |  |
| `credencialusuario` | text | SI |  |  |  |
| `códigoperfil` | text | SI |  |  |  |
| `fechafinperfil` | text | SI |  |  |  |
| `idredusuario` | text | SI |  |  |  |
| `nombreusuario` | text | SI |  |  |  |
| `entidad` | text | SI |  |  |  |
| `recibidodate` | text | SI |  |  |  |
| `usuario` | text | SI |  |  |  |
| `xmlname` | text | SI |  |  |  |
| `consecutivosam` | text | SI |  |  |  |
| `id` | text | SI |  |  |  |

### `public.dj_importada` (TABLA, ~1,265,838 filas, 303 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `codigo_aux` | text | SI |  |  |  |
| `codigo_unico` | text | SI |  |  |  |
| `id_sam` | text | SI |  |  |  |
| `fecha` | date | SI |  |  |  |
| `eps` | text | SI |  |  |  |
| `nro_coche` | text | SI |  |  |  |
| `chasis` | text | SI |  |  |  |
| `chapa` | text | SI |  |  |  |
| `id_eot` | text | SI |  |  |  |
| `tipo_servicio` | text | SI |  |  |  |
| `km_recorrido_para_fecha` | numeric | SI |  |  |  |
| `tipo_sam` | text | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `usos_ccm` | integer | SI |  |  |  |
| `usos_lon_lat` | integer | SI |  |  |  |
| `porcentaje_lat_log` | numeric | SI |  |  |  |
| `id_eot_vmt` | text | SI |  |  |  |
| `empresa` | text | SI |  |  |  |
| `permisionario` | text | SI |  |  |  |
| `documentos` | text | SI |  |  |  |
| `fecha_ivencimiento_itv_anterior` | date | SI |  |  |  |
| `fecha_itv` | date | SI |  |  |  |
| `vencimiento_itv` | date | SI |  |  |  |
| `situacion` | text | SI |  |  |  |
| `validacion` | text | SI |  |  |  |

### `public.django_admin_log` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `action_time` | timestamp with time zone | NO |  |  |  |
| `object_id` | text | SI |  |  |  |
| `object_repr` | character varying(200) | NO |  |  |  |
| `action_flag` | smallint | NO |  |  |  |
| `change_message` | text | NO |  |  |  |
| `content_type_id` | integer | SI |  | public.django_content_type.id |  |
| `user_id` | integer | NO |  | public.auth_user.id |  |

### `public.django_content_type` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `app_label` | character varying(100) | NO |  |  |  |
| `model` | character varying(100) | NO |  |  |  |

### `public.django_migrations` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `app` | character varying(255) | NO |  |  |  |
| `name` | character varying(255) | NO |  |  |  |
| `applied` | timestamp with time zone | NO |  |  |  |

### `public.django_session` (TABLA, ~5 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `session_key` | character varying(40) | NO | SI |  |  |
| `session_data` | text | NO |  |  |  |
| `expire_date` | timestamp with time zone | NO |  |  |  |

### `public.empresas` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_empresa` | integer | NO | SI |  |  |
| `nombre` | character varying(200) | NO |  |  |  |
| `codigo_eot` | character varying(20) | SI |  |  |  |
| `ruc` | character varying(20) | SI |  |  |  |
| `id_consorcio` | integer | SI |  | public.consorcios.id_consorcio |  |
| `estado` | boolean | SI |  |  |  |
| `creado_en` | timestamp without time zone | SI |  |  |  |

### `public.eot_linea` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_eot_linea` | integer | NO | SI |  |  |
| `eot_id` | integer | SI |  | public.eots.eot_id |  |
| `id_linea` | integer | SI |  | public.lineas.id_linea |  |
| `integracion_operativa` | boolean | SI |  |  |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | SI |  |  |  |

### `public.eot_terminales` (TABLA, ~86 filas, 248 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `agency_id` | character varying(50) | NO |  |  |  |
| `terminal_nombre` | character varying(100) | SI |  |  |  |
| `terminal_numero` | integer | SI |  |  |  |
| `centroide_lat` | numeric(10,8) | NO |  |  |  |
| `centroide_lon` | numeric(11,8) | NO |  |  |  |
| `radio_metros` | integer | SI |  |  |  |
| `geocerca` | geometry(Polygon,4326) | NO |  |  |  |
| `cantidad_buses_detectados` | integer | SI |  |  |  |
| `metodo_deteccion` | character varying(50) | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |

### `public.eots` (TABLA, ~73 filas, 128 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `eot_id` | integer | NO | SI |  |  |
| `eot_nombre` | character varying(70) | SI |  |  |  |
| `eot_linea` | character varying(30) | SI |  |  |  |
| `cod_catalogo` | integer | SI |  |  |  |
| `cod_planilla` | character(30) | SI |  |  |  |
| `cod_epas` | character(30) | SI |  |  |  |
| `cod_tdp` | character(30) | SI |  |  |  |
| `situacion` | integer | SI |  |  |  |
| `gre_id` | integer | SI |  |  |  |
| `autorizado` | integer | SI |  |  |  |
| `operativo` | integer | SI |  |  |  |
| `reserva` | integer | SI |  |  |  |
| `permisionario` | boolean | SI |  |  |  |
| `operativo_declarado` | integer | SI |  |  |  |
| `reserva_declarada` | integer | SI |  |  |  |
| `id_eot_vmt_hex` | character varying | SI |  |  |  |
| `e_mail` | character varying(70) | SI |  |  |  |
| `e_mail_ant` | character varying(70) | SI |  |  |  |
| `eot_uf` | boolean | SI |  |  |  |
| `id_tipo_eot` | integer | SI |  | public.tipos_eot.id_tipo |  |
| `eot_UF` | boolean | SI |  |  |  |
| `agency_timezone` | character varying | SI |  |  |  |
| `agency_url` | character varying | SI |  |  |  |
| `agency_lang` | character varying | SI |  |  |  |
| `id_entidad` | integer | SI |  |  |  |

### `public.estados_solicitud_perfiles` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_estado` | integer | NO | SI |  |  |
| `descripcion` | character varying(50) | NO |  |  |  |

### `public.eventos_operacionales` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `tipo_evento` | character varying(50) | SI |  |  |  |
| `id_bus` | integer | SI |  |  |  |
| `id_paradero` | integer | SI |  | public.paraderos.id_paradero |  |
| `timestamp` | timestamp without time zone | SI |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `metadata_evento` | jsonb | SI |  |  |  |
| `id_simulacion` | integer | SI |  | public.simulaciones.id_simulacion |  |

### `public.evidencia_importacion` (TABLA, ~0 filas, 776 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_evidencia` | integer | NO | SI |  |  |
| `nombre_archivo` | character varying(255) | NO |  |  |  |
| `archivo_binario` | bytea | NO |  |  |  |
| `fecha_importacion` | timestamp without time zone | SI |  |  |  |
| `id_usuario` | integer | NO |  | sistema.usuarios.id |  |
| `ip_origen` | character varying(45) | SI |  |  |  |

### `public.feriados` (TABLA, ~103 filas, 80 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fecha` | date | NO | SI |  |  |
| `dia` | character varying | SI |  |  |  |
| `nrodiasemana` | integer | SI |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `observacion` | character varying | SI |  |  |  |

### `public.frecuencia` (TABLA, ~9,364 filas, 1704 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `tipo_reporte` | text | SI |  |  |  |
| `ruta_hex` | text | SI |  |  |  |
| `origen` | text | SI |  |  |  |
| `destino` | text | SI |  |  |  |
| `sentido` | text | SI |  |  |  |
| `troncal` | text | SI |  |  |  |
| `idsam` | text | SI |  |  |  |
| `id_eot` | double precision | SI |  |  |  |
| `eot_nombre` | text | SI |  |  |  |
| `linea` | text | SI |  |  |  |
| `gre_nombre` | text | SI |  |  |  |
| `fecha` | timestamp without time zone | SI |  |  |  |
| `autorizado` | bigint | SI |  |  |  |
| `operativo` | bigint | SI |  |  |  |
| `reserva` | bigint | SI |  |  |  |
| `operativo_declarado` | bigint | SI |  |  |  |
| `reserva_declarada` | bigint | SI |  |  |  |
| `buses_hp_mañana` | double precision | SI |  |  |  |
| `buses_hp_tarde` | double precision | SI |  |  |  |
| `fechamedini` | timestamp without time zone | SI |  |  |  |
| `fechamedfin` | timestamp without time zone | SI |  |  |  |
| `media_hp_mañana` | text | SI |  |  |  |
| `media_hp_tarde` | text | SI |  |  |  |

### `public.geography_columns` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `f_table_catalog` | name | SI |  |  |  |
| `f_table_schema` | name | SI |  |  |  |
| `f_table_name` | name | SI |  |  |  |
| `f_geography_column` | name | SI |  |  |  |
| `coord_dimension` | integer | SI |  |  |  |
| `srid` | integer | SI |  |  |  |
| `type` | text | SI |  |  |  |

### `public.geometry_columns` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `f_table_catalog` | character varying(256) | SI |  |  |  |
| `f_table_schema` | name | SI |  |  |  |
| `f_table_name` | name | SI |  |  |  |
| `f_geometry_column` | name | SI |  |  |  |
| `coord_dimension` | integer | SI |  |  |  |
| `srid` | integer | SI |  |  |  |
| `type` | character varying(30) | SI |  |  |  |

### `public.gremios` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gre_id` | integer | NO | SI |  |  |
| `gre_nombre` | character varying(60) | SI |  |  |  |
| `gre_estado` | integer | SI |  |  |  |

### `public.historico_eot_ruta` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_hist_eot` | integer | NO | SI |  |  |
| `ruta_hex` | character varying | NO |  | public.catalogo_rutas.ruta_hex |  |
| `id_eot` | integer | NO |  | public.eots.eot_id |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | SI |  |  |  |
| `observacion` | text | SI |  |  |  |

### `public.itinerarios_oficiales` (TABLA, ~0 filas, 288 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `source_id` | bigint | SI |  |  |  |
| `linea` | text | SI |  |  |  |
| `empresa` | text | SI |  |  |  |
| `nombre_iti` | text | SI |  |  |  |
| `dependenci` | text | SI |  |  |  |
| `observacio` | text | SI |  |  |  |
| `validado` | text | SI |  |  |  |
| `longitud_m` | double precision | SI |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `source_name` | text | SI |  |  |  |
| `source_description` | text | SI |  |  |  |
| `wkt_original` | text | NO |  |  |  |
| `geom` | geometry(LineStringZ,4326) | NO |  |  |  |
| `created_at` | timestamp with time zone | NO |  |  |  |

### `public.linea_ruta_catalogo` (TABLA, ~546 filas, 144 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_linea_ruta_catalogo` | integer | NO | SI |  |  |
| `id_linea` | integer | SI |  | public.lineas.id_linea |  |
| `ruta_hex` | text | SI |  | public.catalogo_rutas.ruta_hex |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | SI |  |  |  |

### `public.lineas` (TABLA, ~80 filas, 88 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_linea` | integer | NO | SI |  |  |
| `numero_linea` | character varying(50) | NO |  |  |  |
| `nombre_comercial` | text | SI |  |  |  |
| `estado` | boolean | SI |  |  |  |
| `identificador_troncal` | text | SI |  |  |  |
| `id_uf` | integer | SI |  |  |  |
| `color_hex` | character varying(7) | SI |  |  |  |
| `creado_en` | timestamp with time zone | SI |  |  |  |
| `route_type` | integer | SI |  |  |  |
| `route_text_color` | character varying | SI |  |  |  |
| `id_zona` | integer | SI |  | public.zonas.id_zona |  |

### `public.logs_acceso` (TABLA, ~658 filas, 256 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | SI |  | public.usuarios.id |  |
| `username` | character varying(50) | NO |  |  |  |
| `accion` | character varying(50) | NO |  |  |  |
| `ip_address` | character varying(45) | SI |  |  |  |
| `user_agent` | text | SI |  |  |  |
| `fecha` | timestamp without time zone | SI |  |  |  |
| `detalles` | json | SI |  |  |  |
| `exitoso` | boolean | SI |  |  |  |

### `public.logs_auditoria` (TABLA, ~1,932 filas, 1920 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | SI |  | public.usuarios.id |  |
| `username` | character varying(50) | NO |  |  |  |
| `accion` | character varying(50) | NO |  |  |  |
| `tabla` | character varying(50) | NO |  |  |  |
| `registro_id` | integer | SI |  |  |  |
| `datos_anteriores` | json | SI |  |  |  |
| `datos_nuevos` | json | SI |  |  |  |
| `ip_address` | character varying(45) | SI |  |  |  |
| `user_agent` | text | SI |  |  |  |
| `fecha` | timestamp without time zone | SI |  |  |  |
| `detalles` | text | SI |  |  |  |

### `public.ncant_servicios` (TABLA, ~38,797 filas, 3984 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_operativa` | date | SI |  |  |  |
| `sentido` | character varying(20) | SI |  |  |  |
| `mean_id` | character varying(20) | SI |  |  |  |
| `cantidad_servicios` | integer | SI |  |  |  |
| `servicio` | character varying(5) | SI |  |  |  |

### `public.notificaciones` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | NO |  | public.usuarios.id |  |
| `titulo` | character varying(100) | NO |  |  |  |
| `mensaje` | text | NO |  |  |  |
| `tipo` | character varying(20) | SI |  |  |  |
| `leida` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_lectura` | timestamp without time zone | SI |  |  |  |
| `datos_adicionales` | json | SI |  |  |  |

### `public.nservicios` (TABLA, ~107,415 filas, 23 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_operativa` | date | SI |  |  |  |
| `sentido` | character varying(20) | SI |  |  |  |
| `mean_id` | character varying(20) | SI |  |  |  |
| `idsam` | character varying | SI |  |  |  |
| `inicio_cabec` | timestamp without time zone | SI |  |  |  |
| `inicio_serv` | timestamp without time zone | SI |  |  |  |
| `fin_serv` | timestamp without time zone | SI |  |  |  |
| `duración_min` | numeric | SI |  |  |  |
| `total_eventos` | integer | SI |  |  |  |
| `eventos_itinerario` | integer | SI |  |  |  |
| `validaciones` | integer | SI |  |  |  |
| `porcentaje_cumplimiento` | numeric | SI |  |  |  |
| `observación` | character varying(20) | SI |  |  |  |
| `nro_servicio` | integer | SI |  |  |  |
| `dia` | character varying(20) | SI |  |  |  |
| `tipo` | integer | SI |  |  |  |
| `regularidad` | character varying(20) | SI |  |  |  |
| `servicio` | character varying(10) | SI |  |  |  |
| `velocidadpromedio_kmh` | numeric(10,2) | SI |  |  |  |

### `public.nvalidaciones_bus` (TABLA, ~19,658 filas, 2144 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_operativa` | date | SI |  |  |  |
| `mean_id` | character varying(20) | SI |  |  |  |
| `validaciones` | integer | SI |  |  |  |
| `servicio` | character varying(5) | SI |  |  |  |

### `public.nvalidaciones_bus_datos` (TABLA, ~1,699,215 filas, 285 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_operativa` | date | SI |  |  |  |
| `idsam` | character varying | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `entidad` | character varying(20) | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying(20) | SI |  |  |  |
| `tipotransporte` | integer | SI |  |  |  |
| `sentido` | character varying(20) | SI |  |  |  |
| `rango` | character varying(10) | SI |  |  |  |
| `servicio` | character varying(5) | SI |  |  |  |

### `public.nvalidaciones_hora` (TABLA, ~77,909 filas, 7680 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_operativa` | date | SI |  |  |  |
| `sentido` | character varying(20) | SI |  |  |  |
| `rango` | character varying(10) | SI |  |  |  |
| `cantidad_validaciones` | integer | SI |  |  |  |
| `servicio` | character varying(5) | SI |  |  |  |

### `public.paraderos` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_paradero` | integer | NO | SI |  |  |
| `nombre` | character varying(200) | SI |  |  |  |
| `tipo` | character varying(20) | SI |  |  |  |
| `geom` | geometry(Point,4326) | SI |  |  |  |
| `orden_ruta` | integer | SI |  |  |  |
| `distancia_desde_inicio_m` | double precision | SI |  |  |  |
| `id_ruta` | integer | SI |  | public.rutas.id_ruta |  |
| `estado` | boolean | SI |  |  |  |

### `public.parametros_sistema` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `codigo` | character varying(50) | NO |  |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `valor` | text | SI |  |  |  |
| `tipo` | character varying(20) | SI |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `categoria` | character varying(50) | SI |  |  |  |
| `editable` | boolean | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_modificacion` | timestamp without time zone | SI |  |  |  |
| `modificado_por` | integer | SI |  | public.usuarios.id |  |

### `public.pasajeros_simulados` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_pasajero` | integer | NO | SI |  |  |
| `id_simulacion` | integer | SI |  | public.simulaciones.id_simulacion |  |
| `id_paradero_origen` | integer | SI |  | public.paraderos.id_paradero |  |
| `id_paradero_destino` | integer | SI |  | public.paraderos.id_paradero |  |
| `hora_llegada` | double precision | SI |  |  |  |
| `hora_abordaje` | double precision | SI |  |  |  |
| `hora_descenso` | double precision | SI |  |  |  |
| `tiempo_espera` | double precision | SI |  |  |  |
| `id_bus` | integer | SI |  |  |  |

### `public.password_resets` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `email` | character varying(100) | NO |  |  |  |
| `token` | character varying(255) | NO |  |  |  |
| `expira_en` | timestamp without time zone | NO |  |  |  |
| `usado` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |

### `public.perfiles_especiales` (TABLA, ~127,137 filas, 46 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `orden` | integer | NO |  |  |  |
| `nombre_apellido` | character varying | SI |  |  |  |
| `fecha_nacimiento` | date | SI |  |  |  |
| `cedula_identidad` | character varying | NO |  |  |  |
| `institucion` | character varying | SI |  |  |  |
| `Lote` | character varying | SI |  |  |  |
| `eps` | character varying | SI |  |  |  |
| `serial_mdp` | character varying | SI |  |  |  |
| `id_tipo_perfil` | integer | NO |  |  |  |
| `id_usuario_carga` | integer | NO |  | sistema.usuarios.id |  |
| `id_usuario_aprob` | integer | SI |  | sistema.usuarios.id |  |
| `id_estado_solicitud` | integer | NO |  | public.estados_solicitud_perfiles.id_estado |  |
| `fecha_solicitud` | timestamp without time zone | SI |  |  |  |
| `fecha_verificacion` | timestamp without time zone | SI |  |  |  |
| `fecha_aprobacion` | timestamp without time zone | SI |  |  |  |
| `fecha_emision` | timestamp without time zone | SI |  |  |  |
| `ip_origen` | character varying(45) | SI |  |  |  |
| `user_agent` | text | SI |  |  |  |
| `device_id` | character varying(255) | SI |  |  |  |
| `id_evidencia` | integer | SI |  | public.evidencia_importacion.id_evidencia |  |
| `id_usuario_verif` | integer | SI |  | sistema.usuarios.id |  |
| `ip_aprobo` | character varying(45) | SI |  |  |  |
| `device_id_aprobo` | character varying(255) | SI |  |  |  |

### `public.permisos` (TABLA, ~0 filas, 56 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(50) | NO |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `modulo` | character varying(50) | SI |  |  |  |
| `accion` | character varying(50) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |

### `public.posiciones_gps` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_bus` | integer | SI |  |  |  |
| `geom` | geometry(Point,4326) | SI |  |  |  |
| `lat` | double precision | SI |  |  |  |
| `lon` | double precision | SI |  |  |  |
| `velocidad` | double precision | SI |  |  |  |
| `rumbo` | integer | SI |  |  |  |
| `timestamp` | timestamp without time zone | SI |  |  |  |
| `fuente` | character varying(20) | SI |  |  |  |
| `id_simulacion` | integer | SI |  | public.simulaciones.id_simulacion |  |

### `public.promedio_diario_operacion` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `idruta` | character varying | SI |  |  |  |
| `fecha_calculo` | date | NO |  |  |  |
| `promedio_anual_lunes_viernes` | integer | SI |  |  |  |
| `promedio_anual_sabados` | integer | SI |  |  |  |
| `promedio_anual_domingos` | integer | SI |  |  |  |
| `promedio_mensual_lunes_viernes` | integer | SI |  |  |  |
| `promedio_mensual_sabados` | integer | SI |  |  |  |
| `promedio_mensual_domingos` | integer | SI |  |  |  |
| `promedio_semanal_lunes_viernes` | integer | SI |  |  |  |
| `promedio_semanal_sabados` | integer | SI |  |  |  |
| `promedio_semanal_domingos` | integer | SI |  |  |  |

### `public.reportes` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `tipo` | character varying(20) | NO |  |  |  |
| `parametros` | json | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_ejecucion` | timestamp without time zone | SI |  |  |  |
| `estado` | character varying(20) | SI |  |  |  |
| `ruta_archivo` | character varying(500) | SI |  |  |  |
| `creado_por` | integer | NO |  | public.usuarios.id |  |
| `detalles` | json | SI |  |  |  |

### `public.resultado_agencyid_mensajeoperativo` (TABLA, ~3,071 filas, 176 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agency_id` | character varying(255) | SI |  |  |  |
| `fecha` | date | SI |  |  |  |

### `public.resultado_frecuencia` (TABLA, ~61 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `GREMIO` | text | SI |  |  |  |
| `EOT` | text | SI |  |  |  |
| `Identificador Troncal` | text | SI |  |  |  |
| `cant_buses_mañana` | bigint | SI |  |  |  |
| `cant_buses_tarde` | bigint | SI |  |  |  |
| `cumplimiento` | text | SI |  |  |  |

### `public.rol_permiso` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `rol_id` | integer | NO | SI | public.roles.id |  |
| `permiso_id` | integer | NO | SI | public.permisos.id |  |

### `public.roles` (TABLA, ~0 filas, 56 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(50) | NO |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | public.usuarios.id |  |

### `public.rutas` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_ruta` | integer | NO | SI |  |  |
| `id_linea` | integer | SI |  | public.lineas.id_linea |  |
| `sentido` | character varying(10) | SI |  |  |  |
| `nombre` | character varying(200) | SI |  |  |  |
| `geom` | geometry(LineString,4326) | SI |  |  |  |
| `id_externo_cid` | integer | SI |  |  |  |
| `distancia_km` | double precision | SI |  |  |  |
| `tiempo_ciclo_min` | double precision | SI |  |  |  |

### `public.rutas_geometria` (TABLA, ~2 filas, 80 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `ruta_id` | character varying(4) | SI |  | public.catalogo_rutas.ruta_hex |  |
| `geom` | geometry(MultiLineString,4326) | SI |  |  |  |

### `public.salidas` (TABLA, ~11,758 filas, 3088 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `tipo_reporte` | text | SI |  |  |  |
| `ruta_hex` | text | SI |  |  |  |
| `origen` | text | SI |  |  |  |
| `destino` | text | SI |  |  |  |
| `sentido` | text | SI |  |  |  |
| `troncal` | text | SI |  |  |  |
| `idsam` | text | SI |  |  |  |
| `id_eot` | double precision | SI |  |  |  |
| `eot_nombre` | text | SI |  |  |  |
| `linea` | text | SI |  |  |  |
| `gremio` | text | SI |  |  |  |
| `fecha` | timestamp without time zone | SI |  |  |  |
| `h00` | double precision | SI |  |  |  |
| `h01` | double precision | SI |  |  |  |
| `h02` | double precision | SI |  |  |  |
| `h03` | double precision | SI |  |  |  |
| `h04` | double precision | SI |  |  |  |
| `h05` | double precision | SI |  |  |  |
| `h06` | double precision | SI |  |  |  |
| `h07` | double precision | SI |  |  |  |
| `h08` | double precision | SI |  |  |  |
| `h09` | double precision | SI |  |  |  |
| `h10` | double precision | SI |  |  |  |
| `h11` | double precision | SI |  |  |  |
| `h12` | double precision | SI |  |  |  |
| `h13` | double precision | SI |  |  |  |
| `h14` | double precision | SI |  |  |  |
| `h15` | double precision | SI |  |  |  |
| `h16` | double precision | SI |  |  |  |
| `h17` | double precision | SI |  |  |  |
| `h18` | double precision | SI |  |  |  |
| `h19` | double precision | SI |  |  |  |
| `h20` | double precision | SI |  |  |  |
| `h21` | double precision | SI |  |  |  |
| `h22` | double precision | SI |  |  |  |
| `h23` | double precision | SI |  |  |  |

### `public.servicios_diarios` (TABLA, ~41,540,680 filas, 7927 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `idsam` | text | SI |  |  |  |
| `idrutaestacion` | text | SI |  |  |  |
| `fecha` | date | SI |  |  |  |
| `hora` | double precision | SI |  |  |  |
| `id_eot_catalogo` | integer | SI |  |  |  |
| `identificador_troncal` | text | SI |  |  |  |
| `linea` | text | SI |  |  |  |
| `identificacion` | text | SI |  |  |  |
| `eot_nombre` | text | SI |  |  |  |
| `gre_nombre` | text | SI |  |  |  |
| `validaciones` | bigint | SI |  |  |  |
| `gre_id` | bigint | SI |  |  |  |

### `public.sesiones_usuarios` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | NO |  | public.usuarios.id |  |
| `token` | character varying(500) | NO |  |  |  |
| `ip_address` | character varying(45) | SI |  |  |  |
| `user_agent` | text | SI |  |  |  |
| `fecha_inicio` | timestamp without time zone | SI |  |  |  |
| `fecha_expiracion` | timestamp without time zone | NO |  |  |  |
| `activa` | boolean | SI |  |  |  |
| `fecha_cierre` | timestamp without time zone | SI |  |  |  |

### `public.simulaciones` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_simulacion` | integer | NO | SI |  |  |
| `nombre` | character varying(200) | SI |  |  |  |
| `estado` | character varying(20) | SI |  |  |  |
| `parametros` | jsonb | SI |  |  |  |
| `resultado_resumen` | jsonb | SI |  |  |  |
| `fecha_inicio_sim` | timestamp without time zone | SI |  |  |  |
| `fecha_fin_sim` | timestamp without time zone | SI |  |  |  |
| `creado_en` | timestamp without time zone | SI |  |  |  |
| `id_linea` | integer | SI |  | public.lineas.id_linea |  |

### `public.spatial_ref_sys` (TABLA, ~8,500 filas, 7144 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `srid` | integer | NO | SI |  |  |
| `auth_name` | character varying(256) | SI |  |  |  |
| `auth_srid` | integer | SI |  |  |  |
| `srtext` | character varying(2048) | SI |  |  |  |
| `proj4text` | character varying(2048) | SI |  |  |  |

### `public.speed_tests` (TABLA, ~235 filas, 176 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `timestamp` | timestamp without time zone | NO |  |  |  |
| `download_speed` | numeric(8,2) | NO |  |  |  |
| `upload_speed` | numeric(8,2) | NO |  |  |  |
| `ping` | numeric(6,2) | NO |  |  |  |
| `server_name` | character varying(255) | SI |  |  |  |
| `server_location` | character varying(255) | SI |  |  |  |
| `server_country` | character varying(100) | SI |  |  |  |
| `isp` | character varying(255) | SI |  |  |  |
| `external_ip` | inet | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `public.tipo_perfil_especial` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo_especial` | bigint | NO | SI |  |  |
| `tipo_especial` | text | NO |  |  |  |
| `id_organismo` | integer | SI |  | sistema.organismos.id |  |

### `public.tipos_eot` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |

### `public.transbordo_combinacion` (TABLA, ~6,237 filas, 736 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_transbordo` | bigint | NO | SI |  |  |
| `id_ruta_origen` | character varying | NO | SI |  |  |
| `id_ruta_destino` | character varying | NO | SI |  |  |

### `public.transbordo_combinacion_temp` (TABLA, ~12,874 filas, 600 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_transbordo` | integer | SI |  |  |  |
| `id_ruta_origen` | character varying | SI |  |  |  |
| `id_ruta_destino` | character varying | SI |  |  |  |

### `public.transbordos_habilitados` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_transbordo` | bigint | NO | SI |  |  |
| `id_eot_1` | bigint | SI |  |  |  |
| `id_eot_2` | bigint | NO |  |  |  |
| `fecha_ini_vig` | date | SI |  |  |  |
| `fecha_fin_vig` | date | SI |  |  |  |
| `normativa` | character varying | SI |  |  |  |

### `public.transbordos_v2` (TABLA, ~4,672,228 filas, 2837 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_transbordo` | bigint | NO | SI |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `fecha_transbordo` | timestamp without time zone | SI |  |  |  |
| `tipotransporte_transbordo` | smallint | SI |  |  |  |
| `consecutivoevento_transbordo` | bigint | SI |  |  |  |
| `idruta_transbordo` | text | SI |  |  |  |
| `empresa_transbordo` | text | SI |  |  |  |
| `entidad_transbordo` | character varying | SI |  |  |  |
| `latitud_transbordo` | double precision | SI |  |  |  |
| `longitud_transbordo` | double precision | SI |  |  |  |
| `idsam_transbordo` | text | SI |  |  |  |
| `montoevento_transbordo` | integer | SI |  |  |  |
| `idsam_madre` | text | SI |  |  |  |
| `fecha_madre` | timestamp without time zone | SI |  |  |  |
| `entidad_madre` | character varying | SI |  |  |  |
| `idruta_madre` | text | SI |  |  |  |
| `empresa_madre` | text | SI |  |  |  |
| `latitud_madre` | double precision | SI |  |  |  |
| `longitud_madre` | double precision | SI |  |  |  |
| `consecutivoevento_madre` | bigint | SI |  |  |  |
| `montoevento_madre` | integer | SI |  |  |  |
| `servicio_transbordo` | text | SI |  |  |  |
| `numerotransbordos` | integer | SI |  |  |  |
| `intervalo` | integer | SI |  |  |  |
| `tipo_transbordo` | smallint | SI |  |  |  |
| `key_transbordo` | text | SI |  |  |  |

### `public.unidades_funcionales` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_uf` | integer | NO | SI |  |  |
| `nombre` | character varying(200) | NO |  |  |  |
| `id_consorcio` | integer | SI |  | public.consorcios.id_consorcio |  |
| `id_externo_cid` | character varying(50) | SI |  |  |  |

### `public.usuario_rol` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `usuario_id` | integer | NO | SI | public.usuarios.id |  |
| `rol_id` | integer | NO | SI | public.roles.id |  |

### `public.usuarios` (TABLA, ~8 filas, 80 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `username` | character varying(50) | NO |  |  |  |
| `email` | character varying(100) | NO |  |  |  |
| `hashed_password` | character varying(255) | NO |  |  |  |
| `nombre_completo` | character varying(100) | NO |  |  |  |
| `rol` | character varying(20) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `ultimo_acceso` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | public.usuarios.id |  |

### `public.vista_transbordos_acumulados` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_transbordo` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `fecha_transbordo` | timestamp without time zone | SI |  |  |  |
| `tipotransporte_transbordo` | smallint | SI |  |  |  |
| `consecutivoevento_transbordo` | bigint | SI |  |  |  |
| `idruta_transbordo` | text | SI |  |  |  |
| `empresa_transbordo` | text | SI |  |  |  |
| `entidad_transbordo` | character varying | SI |  |  |  |
| `latitud_transbordo` | double precision | SI |  |  |  |
| `longitud_transbordo` | double precision | SI |  |  |  |
| `idsam_transbordo` | text | SI |  |  |  |
| `montoevento_transbordo` | integer | SI |  |  |  |
| `idsam_madre` | text | SI |  |  |  |
| `fecha_madre` | timestamp without time zone | SI |  |  |  |
| `entidad_madre` | character varying | SI |  |  |  |
| `idruta_madre` | text | SI |  |  |  |
| `empresa_madre` | text | SI |  |  |  |
| `latitud_madre` | double precision | SI |  |  |  |
| `longitud_madre` | double precision | SI |  |  |  |
| `consecutivoevento_madre` | bigint | SI |  |  |  |
| `montoevento_madre` | integer | SI |  |  |  |
| `servicio_transbordo` | text | SI |  |  |  |
| `numerotransbordos` | integer | SI |  |  |  |
| `intervalo` | integer | SI |  |  |  |
| `tipo_transbordo` | smallint | SI |  |  |  |
| `key_transbordo` | text | SI |  |  |  |

### `public.zonas` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_zona` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |

## Schema `reclamo`


### `reclamo.alertas_recurrencia` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `linea_id` | bigint | NO |  | reclamo.lineas.id |  |
| `categoria_id` | bigint | SI |  | reclamo.categorias_qrsr.id |  |
| `franja_inicio` | time without time zone | SI |  |  |  |
| `franja_fin` | time without time zone | SI |  |  |  |
| `ventana_dias` | smallint | NO |  |  |  |
| `umbral` | smallint | NO |  |  |  |
| `cantidad` | integer | NO |  |  |  |
| `estado` | character varying(30) | NO |  |  |  |
| `generada_at` | timestamp without time zone | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.cargos` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `code` | character varying(40) | NO |  |  |  |
| `name` | character varying(160) | NO |  |  |  |
| `activo` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.caso_asignaciones` (TABLA, ~0 filas, 112 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `derivacion_id` | bigint | NO |  | reclamo.caso_derivaciones.id |  |
| `asignado_user_id` | bigint | NO |  | reclamo.users.id |  |
| `asignado_por_user_id` | bigint | SI |  | reclamo.users.id |  |
| `instrucciones` | text | SI |  |  |  |
| `fecha_limite` | timestamp without time zone | SI |  |  |  |
| `estado` | character varying(40) | NO |  |  |  |
| `cancelada_motivo` | text | SI |  |  |  |
| `presentada_at` | timestamp without time zone | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |
| `resultado` | text | SI |  |  |  |

### `reclamo.caso_categorias` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `caso_id` | bigint | NO | SI | reclamo.casos.id |  |
| `categoria_id` | bigint | NO | SI | reclamo.categorias_qrsr.id |  |
| `es_principal` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.caso_circuito_adjuntos` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `derivacion_id` | bigint | SI |  | reclamo.caso_derivaciones.id |  |
| `asignacion_id` | bigint | SI |  | reclamo.caso_asignaciones.id |  |
| `informe_version_id` | bigint | SI |  | reclamo.caso_informe_versiones.id |  |
| `comunicacion_id` | bigint | SI |  | reclamo.caso_comunicaciones.id |  |
| `disk` | character varying(40) | NO |  |  |  |
| `path` | character varying(500) | NO |  |  |  |
| `original_name` | character varying(255) | NO |  |  |  |
| `mime` | character varying(120) | NO |  |  |  |
| `size_bytes` | integer | NO |  |  |  |
| `hash_sha256` | character(64) | SI |  |  |  |
| `uploaded_by_user_id` | bigint | SI |  | reclamo.users.id |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.caso_comunicaciones` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `tipo` | character varying(40) | NO |  |  |  |
| `canal` | character varying(20) | NO |  |  |  |
| `destinatario` | character varying(255) | NO |  |  |  |
| `asunto` | character varying(255) | SI |  |  |  |
| `cuerpo` | text | NO |  |  |  |
| `estado_envio` | character varying(30) | NO |  |  |  |
| `intentos` | integer | NO |  |  |  |
| `ultimo_error` | text | SI |  |  |  |
| `enviado_at` | timestamp without time zone | SI |  |  |  |
| `enviado_por_user_id` | bigint | SI |  | reclamo.users.id |  |
| `excepcion_motivo` | text | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.caso_derivaciones` (TABLA, ~8 filas, 176 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `padre_id` | bigint | SI |  | reclamo.caso_derivaciones.id |  |
| `de_dependencia` | character varying(30) | NO |  |  |  |
| `a_dependencia` | character varying(30) | NO |  |  |  |
| `solicitante_user_id` | bigint | SI |  | reclamo.users.id |  |
| `asunto` | character varying(200) | SI |  |  |  |
| `motivo` | text | SI |  |  |  |
| `instrucciones` | text | SI |  |  |  |
| `fecha_limite` | timestamp without time zone | SI |  |  |  |
| `estado` | character varying(40) | NO |  |  |  |
| `cancelada_motivo` | text | SI |  |  |  |
| `respondida_at` | timestamp without time zone | SI |  |  |  |
| `respondida_por_user_id` | bigint | SI |  | reclamo.users.id |  |
| `informe_respuesta_id` | bigint | SI |  | reclamo.caso_informes.id |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |
| `providencia_nro` | character varying(20) | SI |  |  |  |
| `fecha_salida` | date | SI |  |  |  |

### `reclamo.caso_informe_versiones` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `informe_id` | bigint | NO |  | reclamo.caso_informes.id |  |
| `version` | integer | NO |  |  |  |
| `autor_user_id` | bigint | NO |  | reclamo.users.id |  |
| `solicitud_atendida` | text | SI |  |  |  |
| `resumen_verificacion` | text | SI |  |  |  |
| `fuentes_metodologia` | text | SI |  |  |  |
| `hallazgos` | text | SI |  |  |  |
| `conclusion` | text | SI |  |  |  |
| `recomendaciones` | text | SI |  |  |  |
| `estado` | character varying(40) | NO |  |  |  |
| `observacion_revision` | text | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.caso_informes` (TABLA, ~0 filas, 72 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `derivacion_id` | bigint | SI |  | reclamo.caso_derivaciones.id |  |
| `asignacion_id` | bigint | SI |  | reclamo.caso_asignaciones.id |  |
| `autor_user_id` | bigint | NO |  | reclamo.users.id |  |
| `destinatario_dependencia` | character varying(30) | NO |  |  |  |
| `estado` | character varying(40) | NO |  |  |  |
| `version_actual` | integer | NO |  |  |  |
| `remitido_at` | timestamp without time zone | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.caso_movimientos` (TABLA, ~179 filas, 112 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `user_id` | bigint | SI |  | reclamo.users.id |  |
| `actor_tipo` | character varying(20) | NO |  |  |  |
| `accion` | character varying(80) | NO |  |  |  |
| `de_estado` | character varying(40) | SI |  |  |  |
| `a_estado` | character varying(40) | SI |  |  |  |
| `nota` | text | SI |  |  |  |
| `payload_json` | jsonb | SI |  |  |  |
| `ip` | character varying(45) | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.casos` (TABLA, ~8 filas, 192 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `ticket` | character varying(24) | NO |  |  |  |
| `recurrente_id` | bigint | NO |  | reclamo.recurrentes.id |  |
| `tipo` | character varying(30) | NO |  |  |  |
| `categoria_id` | bigint | NO |  | reclamo.categorias_qrsr.id |  |
| `prioridad` | character varying(10) | NO |  |  |  |
| `estado` | character varying(40) | NO |  |  |  |
| `area_asignada` | character varying(30) | SI |  |  |  |
| `asignado_user_id` | bigint | SI |  | reclamo.users.id |  |
| `canal_origen` | character varying(20) | NO |  |  |  |
| `cargado_por_user_id` | bigint | SI |  | reclamo.users.id |  |
| `contra_sistema_general` | smallint | NO |  |  |  |
| `empresa_eot_id` | bigint | SI |  | reclamo.empresas_eot.id |  |
| `linea_id` | bigint | SI |  | reclamo.lineas.id |  |
| `coche_interno` | character varying(40) | SI |  |  |  |
| `desconoce_coche` | smallint | NO |  |  |  |
| `matricula` | character varying(40) | SI |  |  |  |
| `desconoce_matricula` | smallint | NO |  |  |  |
| `falta_bus` | smallint | NO |  |  |  |
| `fecha_hecho` | timestamp without time zone | SI |  |  |  |
| `hecho_recurrente` | smallint | NO |  |  |  |
| `rango_inicio` | date | SI |  |  |  |
| `rango_fin` | date | SI |  |  |  |
| `ventana_espera_inicio` | time without time zone | SI |  |  |  |
| `ventana_espera_fin` | time without time zone | SI |  |  |  |
| `departamento` | character varying(80) | SI |  |  |  |
| `ciudad` | character varying(120) | SI |  |  |  |
| `barrio` | character varying(120) | SI |  |  |  |
| `calle_interseccion` | character varying(200) | SI |  |  |  |
| `punto_referencia` | character varying(200) | SI |  |  |  |
| `latitud` | numeric(10,7) | SI |  |  |  |
| `longitud` | numeric(10,7) | SI |  |  |  |
| `descripcion` | text | NO |  |  |  |
| `declaracion_veracidad` | smallint | NO |  |  |  |
| `autoriza_contacto` | smallint | NO |  |  |  |
| `sugiere_portal_denuncias` | smallint | NO |  |  |  |
| `continuo_como_reclamo` | smallint | NO |  |  |  |
| `confirmation_token` | character varying(64) | SI |  |  |  |
| `confirmation_expires_at` | timestamp without time zone | SI |  |  |  |
| `confirmed_at` | timestamp without time zone | SI |  |  |  |
| `sla_vence_at` | timestamp without time zone | SI |  |  |  |
| `cerrado_at` | timestamp without time zone | SI |  |  |  |
| `cerrado_por_user_id` | bigint | SI |  | reclamo.users.id |  |
| `resumen_cierre` | text | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |
| `destinatario_queja` | character varying(40) | SI |  |  |  |
| `personal_descripcion` | character varying(255) | SI |  |  |  |
| `dependencia_oficina` | character varying(160) | SI |  |  |  |
| `canal_atencion_vmt` | character varying(40) | SI |  |  |  |
| `funcionario_nombre` | character varying(160) | SI |  |  |  |
| `ticket_referencia` | character varying(80) | SI |  |  |  |
| `canal_hecho` | character varying(40) | SI |  |  |  |
| `fecha_hecho_desconocida` | smallint | NO |  |  |  |
| `respuesta_esperada` | text | SI |  |  |  |
| `ambito_sugerencia` | character varying(40) | SI |  |  |  |
| `titulo_propuesta` | character varying(200) | SI |  |  |  |
| `situacion_mejorar` | text | SI |  |  |  |
| `beneficio_esperado` | text | SI |  |  |  |
| `persona_reconocida` | character varying(40) | SI |  |  |  |
| `servicio_destacar` | character varying(255) | SI |  |  |  |
| `lugar_canal_atencion` | character varying(200) | SI |  |  |  |
| `seguimiento_areas` | jsonb | NO |  |  |  |

### `reclamo.categorias_qrsr` (TABLA, ~78 filas, 88 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `code` | character varying(60) | NO |  |  |  |
| `nombre` | character varying(160) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `tipo_default` | character varying(30) | NO |  |  |  |
| `area_default` | character varying(30) | NO |  |  |  |
| `prioridad_base` | character varying(10) | NO |  |  |  |
| `sugiere_denuncia` | smallint | NO |  |  |  |
| `activo` | smallint | NO |  |  |  |
| `orden` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.config_plazos` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `codigo` | character varying(60) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `dias` | integer | NO |  |  |  |
| `activo` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.dependencias` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `code` | character varying(40) | NO |  |  |  |
| `name` | character varying(160) | NO |  |  |  |
| `activo` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.empresas_eot` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `codigo` | character varying(40) | NO |  |  |  |
| `nombre` | character varying(200) | NO |  |  |  |
| `email_contacto` | character varying(190) | SI |  |  |  |
| `telefono` | character varying(40) | SI |  |  |  |
| `activo` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.encuestas_satisfaccion` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `puntuacion` | smallint | NO |  |  |  |
| `comentario` | text | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.evidencias` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `disk` | character varying(40) | NO |  |  |  |
| `path` | character varying(500) | NO |  |  |  |
| `original_name` | character varying(255) | NO |  |  |  |
| `mime` | character varying(120) | NO |  |  |  |
| `size_bytes` | integer | NO |  |  |  |
| `hash_sha256` | character(64) | SI |  |  |  |
| `meta_json` | jsonb | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.informes_tecnicos` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `area` | character varying(10) | NO |  |  |  |
| `autor_user_id` | bigint | NO |  | reclamo.users.id |  |
| `motivo_resumen` | text | SI |  |  |  |
| `fuentes` | text | SI |  |  |  |
| `hallazgos` | text | SI |  |  |  |
| `conclusion` | text | SI |  |  |  |
| `medidas` | text | SI |  |  |  |
| `notificar_empresa` | smallint | NO |  |  |  |
| `derivar_denuncia` | smallint | NO |  |  |  |
| `cierre_propuesto` | character varying(40) | SI |  |  |  |
| `publicado_at` | timestamp without time zone | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.lineas` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `empresa_eot_id` | bigint | NO |  | reclamo.empresas_eot.id |  |
| `codigo` | character varying(40) | NO |  |  |  |
| `nombre` | character varying(160) | NO |  |  |  |
| `activo` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.notificaciones_empresa` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `caso_id` | bigint | NO |  | reclamo.casos.id |  |
| `empresa_eot_id` | bigint | NO |  | reclamo.empresas_eot.id |  |
| `informe_id` | bigint | SI |  | reclamo.informes_tecnicos.id |  |
| `asunto` | character varying(255) | NO |  |  |  |
| `cuerpo` | text | NO |  |  |  |
| `plazo_respuesta` | date | SI |  |  |  |
| `enviada_at` | timestamp without time zone | SI |  |  |  |
| `respondido` | smallint | NO |  |  |  |
| `respondido_at` | timestamp without time zone | SI |  |  |  |
| `respuesta_texto` | text | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.recurrentes` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `tipo_documento` | character varying(20) | NO |  |  |  |
| `numero_documento` | character varying(40) | NO |  |  |  |
| `nacionalidad` | character varying(80) | SI |  |  |  |
| `nombres` | character varying(120) | NO |  |  |  |
| `apellidos` | character varying(120) | NO |  |  |  |
| `fecha_nacimiento` | date | SI |  |  |  |
| `email` | character varying(190) | NO |  |  |  |
| `telefono` | character varying(40) | NO |  |  |  |
| `consent_tyc_at` | timestamp without time zone | SI |  |  |  |
| `consent_privacidad_at` | timestamp without time zone | SI |  |  |  |
| `optin_whatsapp` | smallint | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.roles` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `code` | character varying(40) | NO |  |  |  |
| `name` | character varying(120) | NO |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |

### `reclamo.users` (TABLA, ~3 filas, 80 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `name` | character varying(160) | NO |  |  |  |
| `email` | character varying(190) | NO |  |  |  |
| `email_verified_at` | timestamp without time zone | SI |  |  |  |
| `password` | character varying(255) | NO |  |  |  |
| `role_id` | bigint | SI |  | reclamo.roles.id |  |
| `empresa_eot_id` | bigint | SI |  | reclamo.empresas_eot.id |  |
| `activo` | smallint | NO |  |  |  |
| `remember_token` | character varying(100) | SI |  |  |  |
| `created_at` | timestamp without time zone | SI |  |  |  |
| `updated_at` | timestamp without time zone | SI |  |  |  |
| `username` | character varying(80) | SI |  |  |  |
| `cedula` | character varying(20) | SI |  |  |  |
| `telefono` | character varying(40) | SI |  |  |  |
| `cargo` | character varying(40) | SI |  |  |  |
| `dependencia` | character varying(40) | SI |  |  |  |

## Schema `registro_habilitacion`


### `registro_habilitacion.alertas` (TABLA, ~82,113 filas, 19 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_alerta` | integer | NO | SI |  |  |
| `tipo_alerta` | character varying(50) | SI |  |  |  |
| `id_bus` | integer | SI |  | registro_habilitacion.buses.id_bus |  |
| `titulo` | character varying(200) | SI |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `fecha_alerta` | date | SI |  |  |  |
| `prioridad` | character varying(20) | SI |  |  |  |
| `estado_alerta` | character varying(20) | SI |  |  |  |
| `fecha_atencion` | timestamp without time zone | SI |  |  |  |
| `usuario_atencion` | character varying(100) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |

### `registro_habilitacion.auditoria` (TABLA, ~34,844 filas, 31 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_auditoria` | integer | NO | SI |  |  |
| `tabla_afectada` | character varying(100) | SI |  |  |  |
| `id_registro` | integer | SI |  |  |  |
| `accion` | character varying(20) | SI |  |  |  |
| `datos_anteriores` | jsonb | SI |  |  |  |
| `datos_nuevos` | jsonb | SI |  |  |  |
| `usuario` | character varying(100) | SI |  |  |  |
| `fecha_accion` | timestamp without time zone | SI |  |  |  |
| `ip_usuario` | inet | SI |  |  |  |

### `registro_habilitacion.auxiliar` (TABLA, ~1,909 filas, 432 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `orden` | integer | SI |  |  |  |
| `hexadecimal` | character varying | SI |  |  |  |
| `marca` | character varying | SI |  |  |  |
| `año` | integer | SI |  |  |  |
| `chasis` | character varying | SI |  |  |  |
| `RUA` | character varying | SI |  |  |  |
| `POD / RTD` | character varying | SI |  |  |  |
| `Documentos` | character varying | SI |  |  |  |
| `Habilitacion` | date | SI |  |  |  |
| `Seguro Pasajeros` | date | SI |  |  |  |
| `Seguro Terceros` | date | SI |  |  |  |
| `Tipo de Servicio` | character varying | SI |  |  |  |
| `Tipo de Carroceria` | character varying | SI |  |  |  |
| `Marca de Carroceria` | character varying | SI |  |  |  |
| `Fecha de Vencimiento del ITV Anterior` | date | SI |  |  |  |
| `Fecha de ITV` | date | SI |  |  |  |
| `Vencimiento de ITV` | date | SI |  |  |  |
| `Situacion de ITV Aprobada` | character varying | SI |  |  |  |
| `Codigo` | integer | SI |  |  |  |
| `Empresa_Linea` | character varying | SI |  |  |  |
| `id_eot_vmt_hex` | character varying | SI |  |  |  |
| `id_marca` | integer | SI |  |  |  |
| `id_marca_carroceria` | integer | SI |  |  |  |
| `id_tipo_carroceria` | integer | SI |  |  |  |

### `registro_habilitacion.bus_empresa` (TABLA, ~5,370 filas, 1944 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_asignacion` | integer | NO | SI |  |  |
| `id_bus` | integer | NO |  | registro_habilitacion.buses.id_bus |  |
| `id_eot` | character varying(255) | NO |  | public.eots.id_eot_vmt_hex |  |
| `fecha_asignacion` | date | NO |  |  |  |
| `fecha_fin_asignacion` | date | SI |  |  |  |
| `estado_asignacion` | character varying(20) | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `usuario_registro` | character varying(100) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |
| `motivo` | character varying(30) | SI |  |  |  |
| `normativa` | text | SI |  |  |  |
| `tipo_declaracion` | character varying(3) | SI |  |  |  |

### `registro_habilitacion.buses` (TABLA, ~5,148 filas, 2312 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_bus` | integer | NO | SI |  |  |
| `numero_orden` | integer | SI |  |  |  |
| `id_marca` | integer | SI |  | registro_habilitacion.marcas.id_marca |  |
| `año` | integer | NO |  |  |  |
| `numero_chassis` | character varying(50) | NO |  |  |  |
| `rua` | character varying(20) | NO |  |  |  |
| `id_tipo_carroceria` | integer | SI |  | registro_habilitacion.tipos_carroceria.id_tipo |  |
| `id_marca_carroceria` | integer | SI |  | registro_habilitacion.marcas_carroceria.id_marca_carroceria |  |
| `capacidad_pasajeros` | integer | SI |  |  |  |
| `combustible` | character varying(50) | SI |  |  |  |
| `cilindrada` | character varying(20) | SI |  |  |  |
| `color` | character varying(50) | SI |  |  |  |
| `estado_bus` | character varying(20) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |
| `fecha_modificacion` | timestamp without time zone | SI |  |  |  |
| `id_tipo_servicio` | integer | SI |  | registro_habilitacion.tipos_servicio.id_tipo_servicio |  |
| `tiene_rampa` | boolean | NO |  |  |  |

### `registro_habilitacion.companias_seguros` (TABLA, ~1 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_compania` | integer | NO | SI |  |  |
| `nombre` | character varying(200) | NO |  |  |  |
| `ruc` | character varying(20) | SI |  |  |  |
| `direccion` | text | SI |  |  |  |
| `telefono` | character varying(20) | SI |  |  |  |
| `email` | character varying(100) | SI |  |  |  |
| `fecha_creacion` | timestamp with time zone | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |

### `registro_habilitacion.documentos_bus` (TABLA, ~3,731 filas, 528 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_documento` | integer | NO | SI |  |  |
| `id_bus` | integer | SI |  | registro_habilitacion.buses.id_bus |  |
| `tipo_documento` | character varying(50) | SI |  |  |  |
| `nombre_documento` | character varying(200) | SI |  |  |  |
| `fecha_emision` | date | SI |  |  |  |
| `fecha_vencimiento` | date | SI |  |  |  |
| `estado_documento` | character varying(20) | SI |  |  |  |
| `archivo_url` | character varying(500) | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |

### `registro_habilitacion.documentos_eot` (TABLA, ~0 filas, 96 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_documento_eot` | integer | NO | SI |  |  |
| `id_eot` | character varying(255) | NO |  |  |  |
| `tipo_documento` | character varying(30) | NO |  |  |  |
| `numero_resolucion` | character varying(100) | SI |  |  |  |
| `nombre_documento` | character varying(200) | SI |  |  |  |
| `fecha_emision` | date | SI |  |  |  |
| `fecha_vigencia` | date | SI |  |  |  |
| `cantidad_buses` | integer | SI |  |  |  |
| `archivo_url` | character varying(500) | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `usuario_registro` | character varying(100) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |

### `registro_habilitacion.itv_bus` (TABLA, ~6,850 filas, 1752 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_itv` | integer | NO | SI |  |  |
| `id_bus` | integer | SI |  | registro_habilitacion.buses.id_bus |  |
| `fecha_itv` | date | NO |  |  |  |
| `fecha_vencimiento` | date | NO |  |  |  |
| `resultado_itv` | character varying(20) | SI |  |  |  |
| `centro_itv` | character varying(200) | SI |  |  |  |
| `numero_certificado` | character varying(100) | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `archivo_certificado_url` | character varying(500) | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |
| `es_vigente` | boolean | SI |  |  |  |

### `registro_habilitacion.marcas` (TABLA, ~16 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_marca` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |

### `registro_habilitacion.marcas_carroceria` (TABLA, ~54 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_marca_carroceria` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |

### `registro_habilitacion.seguros_bus` (TABLA, ~23,997 filas, 5224 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_seguro` | integer | NO | SI |  |  |
| `id_bus` | integer | SI |  | registro_habilitacion.buses.id_bus |  |
| `id_compania` | integer | SI |  | registro_habilitacion.companias_seguros.id_compania |  |
| `numero_poliza` | character varying(100) | SI |  |  |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_vencimiento` | date | NO |  |  |  |
| `monto_cobertura` | numeric(12,2) | SI |  |  |  |
| `archivo_poliza_url` | character varying(500) | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |
| `fecha_registro` | timestamp without time zone | SI |  |  |  |
| `id_tipo_seguro` | integer | NO |  | registro_habilitacion.tipos_seguro.id_tipo_seguro |  |
| `seguro_vigente` | boolean | NO |  |  |  |

### `registro_habilitacion.tipos_carroceria` (TABLA, ~82 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo` | integer | NO | SI |  |  |
| `descripcion` | character varying(100) | NO |  |  |  |

### `registro_habilitacion.tipos_seguro` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo_seguro` | integer | NO | SI |  |  |
| `nombre` | character varying(50) | NO |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |

### `registro_habilitacion.tipos_servicio` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipo_servicio` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |

## Schema `servicios_especiales`


### `servicios_especiales.adjudicacion_servicio` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_adjudicacion` | integer | NO | SI |  |  |
| `id_servicio_especial` | integer | NO |  | servicios_especiales.servicio_especial.id_servicio_especial |  |
| `id_eot` | integer | NO |  | public.eots.eot_id |  |
| `fecha_inicio_servicio` | date | NO |  |  |  |
| `fecha_fin_servicio` | date | SI |  |  |  |
| `observacion` | text | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `link_dashboard` | text | SI |  |  |  |

### `servicios_especiales.bus_adjudicacion` (TABLA, ~148 filas, 56 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_bus_adjudicacion` | integer | NO | SI |  |  |
| `id_adjudicacion` | integer | NO |  | servicios_especiales.adjudicacion_servicio.id_adjudicacion |  |
| `numero_orden` | integer | NO |  |  |  |
| `idsam` | character varying(100) | NO |  |  |  |
| `mean_id` | character varying(50) | SI |  |  |  |

### `servicios_especiales.parametro_monitoreo` (TABLA, ~10 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_parametro` | integer | NO | SI |  |  |
| `id_servicio_especial` | integer | NO |  | servicios_especiales.servicio_especial.id_servicio_especial |  |
| `radio_geocerca_m` | integer | NO |  |  |  |
| `radio_itinerario_m` | integer | NO |  |  |  |
| `rango_cumplimiento_pct` | integer | NO |  |  |  |
| `franja_hora_inicio` | character varying(10) | NO |  |  |  |
| `franja_hora_fin` | character varying(10) | NO |  |  |  |
| `tolerancia_antes_min` | integer | NO |  |  |  |
| `tolerancia_despues_min` | integer | NO |  |  |  |
| `emisor_id` | integer | SI |  |  |  |
| `agency_ids` | text | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_actualizacion` | timestamp without time zone | SI |  |  |  |
| `pasa_al_dia_siguiente` | boolean | SI |  |  |  |

### `servicios_especiales.programacion_operativa` (TABLA, ~803 filas, 184 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_programacion` | integer | NO | SI |  |  |
| `id_servicio_especial` | integer | NO |  | servicios_especiales.servicio_especial.id_servicio_especial |  |
| `fecha_inicio_vigencia` | date | NO |  |  |  |
| `fecha_fin_vigencia` | date | SI |  |  |  |
| `numero_servicio` | integer | NO |  |  |  |
| `sentido` | character varying(20) | NO |  |  |  |
| `horario_salida` | time without time zone | NO |  |  |  |
| `horario_llegada` | time without time zone | SI |  |  |  |
| `tipo_dia` | integer | SI |  | control_metricas.tipo_dia.id_tipo_dia |  |

### `servicios_especiales.ruta_servicio_especial` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_ruta_servicio` | integer | NO | SI |  |  |
| `id_servicio_especial` | integer | NO |  | servicios_especiales.servicio_especial.id_servicio_especial |  |
| `ruta_hex` | character varying | NO |  | public.catalogo_rutas.ruta_hex |  |
| `sentido` | character varying(20) | NO |  |  |  |
| `vigente_desde` | date | SI |  |  |  |
| `vigente_hasta` | date | SI |  |  |  |

### `servicios_especiales.servicio_especial` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_servicio_especial` | integer | NO | SI |  |  |
| `codigo` | character varying(50) | NO |  |  |  |
| `nombre` | character varying(200) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_actualizacion` | timestamp without time zone | SI |  |  |  |

## Schema `sistema`


### `sistema.backups_sistema` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `ruta_archivo` | character varying(500) | NO |  |  |  |
| `tamano_bytes` | integer | SI |  |  |  |
| `tipo` | character varying(20) | SI |  |  |  |
| `estado` | character varying(20) | SI |  |  |  |
| `fecha_inicio` | timestamp without time zone | SI |  |  |  |
| `fecha_fin` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | sistema.usuarios.id |  |
| `detalles` | json | SI |  |  |  |

### `sistema.configuracion_email` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `host` | character varying(100) | NO |  |  |  |
| `puerto` | integer | NO |  |  |  |
| `username` | character varying(100) | NO |  |  |  |
| `password` | character varying(255) | NO |  |  |  |
| `from_email` | character varying(100) | NO |  |  |  |
| `use_tls` | boolean | SI |  |  |  |
| `use_ssl` | boolean | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | sistema.usuarios.id |  |

### `sistema.logs_acceso` (TABLA, ~10,193 filas, 2800 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | SI |  | sistema.usuarios.id |  |
| `username` | character varying(50) | NO |  |  |  |
| `accion` | character varying(50) | NO |  |  |  |
| `ip_address` | character varying(45) | SI |  |  |  |
| `user_agent` | text | SI |  |  |  |
| `fecha` | timestamp without time zone | SI |  |  |  |
| `detalles` | json | SI |  |  |  |
| `exitoso` | boolean | SI |  |  |  |
| `sistema_id` | integer | SI |  | sistema.sistemas.id |  |

### `sistema.logs_auditoria` (TABLA, ~1,729 filas, 3400 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | SI |  | sistema.usuarios.id |  |
| `username` | character varying(50) | NO |  |  |  |
| `accion` | character varying(50) | NO |  |  |  |
| `tabla` | character varying(50) | NO |  |  |  |
| `registro_id` | integer | SI |  |  |  |
| `datos_anteriores` | json | SI |  |  |  |
| `datos_nuevos` | json | SI |  |  |  |
| `ip_address` | character varying(45) | SI |  |  |  |
| `user_agent` | text | SI |  |  |  |
| `fecha` | timestamp without time zone | SI |  |  |  |
| `detalles` | text | SI |  |  |  |
| `sistema_id` | integer | SI |  |  |  |

### `sistema.mensajes` (TABLA, ~0 filas, 80 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_usuario` | integer | NO |  | sistema.usuarios.id |  |
| `id_sistema` | integer | NO |  | sistema.sistemas.id |  |
| `tipo` | character varying(30) | NO |  |  |  |
| `mensaje` | text | NO |  |  |  |
| `fecha` | timestamp without time zone | NO |  |  |  |
| `entrante` | boolean | NO |  |  |  |
| `leido` | boolean | NO |  |  |  |
| `solucion` | boolean | NO |  |  |  |
| `id_padre` | integer | SI |  | sistema.mensajes.id |  |

### `sistema.notificaciones` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | NO |  | sistema.usuarios.id |  |
| `titulo` | character varying(100) | NO |  |  |  |
| `mensaje` | text | NO |  |  |  |
| `tipo` | character varying(20) | SI |  |  |  |
| `leida` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_lectura` | timestamp without time zone | SI |  |  |  |
| `datos_adicionales` | json | SI |  |  |  |

### `sistema.organismos` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `sigla` | character varying(20) | NO |  |  |  |
| `nombre_completo` | character varying(200) | NO |  |  |  |
| `activo` | boolean | SI |  |  |  |

### `sistema.parametros_sistema` (TABLA, ~0 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `codigo` | character varying(50) | NO |  |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `valor` | text | SI |  |  |  |
| `tipo` | character varying(20) | SI |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `categoria` | character varying(50) | SI |  |  |  |
| `editable` | boolean | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_modificacion` | timestamp without time zone | SI |  |  |  |
| `modificado_por` | integer | SI |  | sistema.usuarios.id |  |

### `sistema.password_resets` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `email` | character varying(100) | NO |  |  |  |
| `token` | character varying(255) | NO |  |  |  |
| `expira_en` | timestamp without time zone | NO |  |  |  |
| `usado` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |

### `sistema.permisos` (TABLA, ~0 filas, 56 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(50) | NO |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `modulo` | character varying(50) | SI |  |  |  |
| `accion` | character varying(50) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |

### `sistema.reportes` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `tipo` | character varying(20) | NO |  |  |  |
| `parametros` | json | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `fecha_ejecucion` | timestamp without time zone | SI |  |  |  |
| `estado` | character varying(20) | SI |  |  |  |
| `ruta_archivo` | character varying(500) | SI |  |  |  |
| `creado_por` | integer | NO |  | sistema.usuarios.id |  |
| `detalles` | json | SI |  |  |  |

### `sistema.rol_permiso` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `rol_id` | integer | NO | SI | sistema.roles.id |  |
| `permiso_id` | integer | NO | SI | sistema.permisos.id |  |

### `sistema.roles` (TABLA, ~0 filas, 56 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(50) | NO |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | sistema.usuarios.id |  |

### `sistema.sesiones_usuarios` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | NO |  | sistema.usuarios.id |  |
| `token` | character varying(500) | NO |  |  |  |
| `ip_address` | character varying(45) | SI |  |  |  |
| `user_agent` | text | SI |  |  |  |
| `fecha_inicio` | timestamp without time zone | SI |  |  |  |
| `fecha_expiracion` | timestamp without time zone | NO |  |  |  |
| `activa` | boolean | SI |  |  |  |
| `fecha_cierre` | timestamp without time zone | SI |  |  |  |

### `sistema.sistemas` (TABLA, ~0 filas, 40 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying(100) | NO |  |  |  |
| `descripcion` | character varying(200) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |

### `sistema.usuario_rol` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `usuario_id` | integer | NO | SI | sistema.usuarios.id |  |
| `rol_id` | integer | NO | SI | sistema.roles.id |  |

### `sistema.usuario_sistema_rol` (TABLA, ~81 filas, 80 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `usuario_id` | integer | NO |  | sistema.usuarios.id |  |
| `sistema_id` | integer | NO |  | sistema.sistemas.id |  |
| `rol_id` | integer | NO |  | sistema.roles.id |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `tabs_permitidos` | json | SI |  |  |  |

### `sistema.usuarios` (TABLA, ~48 filas, 112 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `username` | character varying(50) | NO |  |  |  |
| `email` | character varying(100) | NO |  |  |  |
| `hashed_password` | character varying(255) | NO |  |  |  |
| `nombre_completo` | character varying(100) | NO |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `fecha_creacion` | timestamp without time zone | SI |  |  |  |
| `ultimo_acceso` | timestamp without time zone | SI |  |  |  |
| `creado_por` | integer | SI |  | sistema.usuarios.id |  |
| `id_organismo` | integer | SI |  | sistema.organismos.id |  |
| `organismo_id` | integer | SI |  | sistema.organismos.id |  |
| `organizacion` | character varying(50) | SI |  |  |  |

## Schema `verificacion_res_65`


### `verificacion_res_65.configuracion_notificaciones` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `clave` | character varying(100) | NO |  |  |  |
| `valor` | text | NO |  |  |  |
| `descripcion` | text | SI |  |  |  |
| `fecha_actualizacion` | timestamp without time zone | NO |  |  |  |

### `verificacion_res_65.detalles_incumplimientos` (TABLA, ~828 filas, 272 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `eot_nombre` | character varying(255) | NO |  |  |  |
| `cod_catalogo` | character varying(50) | NO |  |  |  |
| `id_eot_vmt_hex` | character varying(50) | NO |  |  |  |
| `e_mail` | character varying(255) | SI |  |  |  |
| `fecha_incumplimiento` | date | NO |  |  |  |
| `buses_reportado` | integer | NO |  |  |  |
| `buses_operando_ruta` | integer | NO |  |  |  |
| `porcentaje_cumplimiento` | numeric(5,2) | NO |  |  |  |
| `fecha_hora_registro` | timestamp without time zone | SI |  |  |  |
| `nro_notificacion` | integer | SI |  |  |  |
| `nivel` | integer | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |

### `verificacion_res_65.incumplimientos` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_infra` | integer | NO | SI |  |  |
| `eot_nombre` | character varying(70) | SI |  |  |  |
| `cod_catalogo` | integer | SI |  |  |  |
| `id_eot_vmt_hex` | character varying | SI |  |  |  |
| `e_mail` | character varying(70) | SI |  |  |  |
| `nro_notificacion` | integer | SI |  |  |  |
| `fecha_inicio` | timestamp with time zone | SI |  |  |  |
| `fecha_fin` | timestamp with time zone | SI |  |  |  |
| `fecha_hora` | timestamp with time zone | SI |  |  |  |
| `fecha_incumplimiento` | text | SI |  |  |  |
| `nivel` | integer | SI |  |  |  |

### `verificacion_res_65.infraccion` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `eot_nombre` | character varying(255) | SI |  |  |  |
| `cod_catalogo` | integer | SI |  |  |  |
| `id_eot_vmt_hex` | character varying(50) | SI |  |  |  |
| `fecha_infraccion` | timestamp with time zone | SI |  |  |  |
| `nivel` | integer | SI |  |  |  |

### `verificacion_res_65.multas` (TABLA, ~106 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_multa` | integer | NO | SI |  |  |
| `eot_nombre` | character varying(255) | SI |  |  |  |
| `cod_catalogo` | character varying(50) | SI |  |  |  |
| `id_eot_vmt_hex` | character varying(50) | SI |  |  |  |
| `fecha_multa` | timestamp without time zone | SI |  |  |  |
| `nivel` | integer | SI |  |  |  |

### `verificacion_res_65.notificaciones` (TABLA, ~106 filas, 104 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_noti` | integer | NO | SI |  |  |
| `eot_nombre` | character varying(70) | SI |  |  |  |
| `cod_catalogo` | integer | SI |  |  |  |
| `id_eot_vmt_hex` | character varying | SI |  |  |  |
| `e_mail` | character varying(70) | SI |  |  |  |
| `nro_notificacion` | integer | SI |  |  |  |
| `fecha_inicio` | timestamp with time zone | SI |  |  |  |
| `fecha_fin` | timestamp with time zone | SI |  |  |  |
| `fecha_hora` | timestamp with time zone | SI |  |  |  |
| `fecha_sin_datos` | text | SI |  |  |  |
| `nivel` | integer | SI |  |  |  |

### `verificacion_res_65.notificaciones_smi` (TABLA, ~0 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha_analisis` | date | NO |  |  |  |
| `franja_operativa` | integer | NO |  |  |  |
| `porcentaje_y` | integer | NO |  |  |  |
| `total_eots` | integer | NO |  |  |  |
| `correos_enviados` | integer | NO |  |  |  |
| `email_prueba_enviado` | boolean | NO |  |  |  |
| `fecha_envio` | timestamp without time zone | NO |  |  |  |
| `usuario_envio` | character varying(100) | SI |  |  |  |
| `estado` | character varying(20) | NO |  |  |  |
| `errores` | text | SI |  |  |  |
| `observaciones` | text | SI |  |  |  |

### `verificacion_res_65.notificaciones_smi_detalle` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `notificacion_id` | integer | NO |  | verificacion_res_65.notificaciones_smi.id |  |
| `eot_codigo` | character varying(50) | NO |  |  |  |
| `eot_nombre` | character varying(255) | NO |  |  |  |
| `eot_email` | character varying(255) | SI |  |  |  |
| `cumple_smi` | boolean | NO |  |  |  |
| `cumplimiento_porcentaje` | numeric(5,2) | NO |  |  |  |
| `fecha_envio` | timestamp without time zone | NO |  |  |  |
| `estado_envio` | character varying(20) | NO |  |  |  |
| `error_mensaje` | text | SI |  |  |  |

---

# BD MONITOREO


## Schema `public`


### `public.app_bruteforce_loginattempt` (TABLA, ~0 filas, 104 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `ip_address` | inet | NO |  |  |  |
| `username` | character varying(150) | SI |  |  |  |
| `timestamp` | timestamp with time zone | NO |  |  |  |

### `public.app_entes_reguladores_enteregulador` (TABLA, ~2 filas, 96 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_subsistema` | character varying(2) | NO |  |  |  |
| `nombre` | character varying(255) | NO |  |  |  |
| `nombre_corto` | character varying(255) | NO |  |  |  |
| `url` | character varying(200) | SI |  |  |  |
| `zona_horaria` | character varying(100) | SI |  |  |  |
| `idioma` | character varying(2) | SI |  |  |  |
| `telefono` | character varying(50) | SI |  |  |  |
| `url_tarifas` | character varying(200) | SI |  |  |  |
| `email` | character varying(254) | SI |  |  |  |

### `public.app_eps_emisormensajeoperativo` (TABLA, ~33 filas, 88 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `id_hex` | character varying(2) | NO |  |  |  |
| `nombre_corto` | character varying(100) | NO |  |  |  |
| `nombre_largo` | character varying(100) | NO |  |  |  |
| `email` | character varying(254) | SI |  |  |  |

### `public.app_monitoreo_mensajeoperativo` (TABLA, ~6,425,940,480 filas, 2183 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario_broker` | character varying(255) | SI |  |  |  |
| `identidad` | bigint | NO |  |  |  |
| `agency_id` | character varying(255) | NO |  |  |  |
| `mean_id` | character varying(255) | NO |  |  |  |
| `route_id` | character varying(255) | NO |  |  |  |
| `driver_id` | character varying(255) | NO |  |  |  |
| `type` | integer | NO |  |  |  |
| `precision` | integer | NO |  |  |  |
| `latitude` | double precision | NO |  |  |  |
| `longitude` | double precision | NO |  |  |  |
| `ubicacion` | geometry(Point,4326) | NO |  |  |  |
| `altitud` | double precision | NO |  |  |  |
| `rumbo` | double precision | NO |  |  |  |
| `velocidad` | double precision | NO |  |  |  |
| `fecha_hora` | timestamp with time zone | SI |  |  |  |
| `fecha_hora_procesamiento` | timestamp with time zone | SI |  |  |  |
| `emisor_id` | bigint | SI |  | public.app_eps_emisormensajeoperativo.id |  |

### `public.app_monitoreo_mensajeoperativofallido` (TABLA, ~1 filas, 80 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario_broker` | character varying(255) | NO |  |  |  |
| `contenido_binario` | text | NO |  |  |  |
| `fecha_recepcion` | timestamp with time zone | NO |  |  |  |
| `error` | text | NO |  |  |  |
| `emisor_id` | bigint | SI |  | public.app_eps_emisormensajeoperativo.id |  |

### `public.app_monitoreo_usuariobroker` (TABLA, ~5 filas, 112 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario` | character varying(255) | NO |  |  |  |
| `password` | character varying(255) | NO |  |  |  |
| `confirm_password` | character varying(255) | NO |  |  |  |
| `revocado` | boolean | NO |  |  |  |
| `fecha_creacion` | timestamp with time zone | SI |  |  |  |
| `fecha_revocacion` | timestamp with time zone | SI |  |  |  |
| `creado_por_id` | bigint | SI |  | public.app_organizaciones_usuario.id |  |
| `revocado_por_id` | bigint | SI |  | public.app_organizaciones_usuario.id |  |
| `emisor_id` | bigint | NO |  | public.app_eps_emisormensajeoperativo.id |  |

### `public.app_organizaciones_grupo` (TABLA, ~2 filas, 96 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `nombre` | character varying(255) | NO |  |  |  |
| `descripcion` | text | NO |  |  |  |
| `grupo_django_id` | integer | SI |  |  |  |

### `public.app_organizaciones_organizacion` (TABLA, ~5 filas, 88 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `id_objeto` | integer | NO |  |  |  |
| `tipo_contenido_id` | integer | NO |  | public.django_content_type.id |  |
| `nombre` | character varying(255) | NO |  |  |  |
| `tipo` | character varying(100) | NO |  |  |  |

### `public.app_organizaciones_organizacion_grupos` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `organizacion_id` | bigint | NO |  | public.app_organizaciones_organizacion.id |  |
| `grupo_id` | bigint | NO |  | public.app_organizaciones_grupo.id |  |

### `public.app_organizaciones_permisogrupo` (TABLA, ~11 filas, 96 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `create_permission` | boolean | NO |  |  |  |
| `read_permission` | boolean | NO |  |  |  |
| `update_permission` | boolean | NO |  |  |  |
| `delete_permission` | boolean | NO |  |  |  |
| `campos_incluidos` | jsonb | SI |  |  |  |
| `campos_excluidos` | jsonb | SI |  |  |  |
| `tipo_acceso` | integer | NO |  |  |  |
| `related_content_type_id` | integer | NO |  | public.django_content_type.id |  |
| `grupo_id` | bigint | NO |  | public.app_organizaciones_grupo.id |  |
| `export_permission` | boolean | NO |  |  |  |
| `import_permission` | boolean | NO |  |  |  |

### `public.app_organizaciones_solicitudcambioclave` (TABLA, ~10 filas, 96 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `fecha_solicitud` | timestamp with time zone | NO |  |  |  |
| `ip_solicitud` | inet | SI |  |  |  |
| `descripcion` | text | NO |  |  |  |
| `contrasena_temporal` | character varying(128) | NO |  |  |  |
| `contrasena_anterior` | character varying(128) | NO |  |  |  |
| `contrasena_cambiada` | boolean | NO |  |  |  |
| `fecha_cambio` | timestamp with time zone | SI |  |  |  |
| `ip_cambio` | inet | SI |  |  |  |
| `user_agent` | text | NO |  |  |  |
| `solicitud_por_nuevo_usuario` | boolean | NO |  |  |  |
| `usuario_afectado_id` | bigint | NO |  | public.app_organizaciones_usuario.id |  |
| `usuario_solicitante_id` | bigint | SI |  | public.app_organizaciones_usuario.id |  |

### `public.app_organizaciones_usuario` (TABLA, ~12 filas, 112 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `password` | character varying(128) | NO |  |  |  |
| `last_login` | timestamp with time zone | SI |  |  |  |
| `username` | character varying(150) | NO |  |  |  |
| `first_name` | character varying(150) | NO |  |  |  |
| `last_name` | character varying(150) | NO |  |  |  |
| `email` | character varying(254) | NO |  |  |  |
| `is_staff` | boolean | NO |  |  |  |
| `is_active` | boolean | NO |  |  |  |
| `date_joined` | timestamp with time zone | NO |  |  |  |
| `password_es_temporal` | boolean | NO |  |  |  |
| `is_superuser` | boolean | NO |  |  |  |
| `organizacion_id` | bigint | SI |  | public.app_organizaciones_organizacion.id |  |

### `public.app_organizaciones_usuario_groups` (TABLA, ~9 filas, 104 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario_id` | bigint | NO |  | public.app_organizaciones_usuario.id |  |
| `group_id` | integer | NO |  | public.auth_group.id |  |

### `public.app_organizaciones_usuario_grupos` (TABLA, ~9 filas, 104 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario_id` | bigint | NO |  | public.app_organizaciones_usuario.id |  |
| `grupo_id` | bigint | NO |  | public.app_organizaciones_grupo.id |  |

### `public.app_organizaciones_usuario_user_permissions` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `usuario_id` | bigint | NO |  | public.app_organizaciones_usuario.id |  |
| `permission_id` | integer | NO |  | public.auth_permission.id |  |

### `public.auth_group` (TABLA, ~2 filas, 88 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `name` | character varying(150) | NO |  |  |  |

### `public.auth_group_permissions` (TABLA, ~27 filas, 104 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `group_id` | integer | NO |  | public.auth_group.id |  |
| `permission_id` | integer | NO |  | public.auth_permission.id |  |

### `public.auth_permission` (TABLA, ~76 filas, 88 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `name` | character varying(255) | NO |  |  |  |
| `content_type_id` | integer | NO |  | public.django_content_type.id |  |
| `codename` | character varying(100) | NO |  |  |  |

### `public.django_admin_log` (TABLA, ~96 filas, 104 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `action_time` | timestamp with time zone | NO |  |  |  |
| `object_id` | text | SI |  |  |  |
| `object_repr` | character varying(200) | NO |  |  |  |
| `action_flag` | smallint | NO |  |  |  |
| `change_message` | text | NO |  |  |  |
| `content_type_id` | integer | SI |  | public.django_content_type.id |  |
| `user_id` | bigint | NO |  | public.app_organizaciones_usuario.id |  |

### `public.django_content_type` (TABLA, ~18 filas, 72 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `app_label` | character varying(100) | NO |  |  |  |
| `model` | character varying(100) | NO |  |  |  |

### `public.django_migrations` (TABLA, ~48 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `app` | character varying(255) | NO |  |  |  |
| `name` | character varying(255) | NO |  |  |  |
| `applied` | timestamp with time zone | NO |  |  |  |

### `public.django_session` (TABLA, ~284 filas, 376 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `session_key` | character varying(40) | NO | SI |  |  |
| `session_data` | text | NO |  |  |  |
| `expire_date` | timestamp with time zone | NO |  |  |  |

### `public.geography_columns` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `f_table_catalog` | name | SI |  |  |  |
| `f_table_schema` | name | SI |  |  |  |
| `f_table_name` | name | SI |  |  |  |
| `f_geography_column` | name | SI |  |  |  |
| `coord_dimension` | integer | SI |  |  |  |
| `srid` | integer | SI |  |  |  |
| `type` | text | SI |  |  |  |

### `public.geometry_columns` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `f_table_catalog` | character varying(256) | SI |  |  |  |
| `f_table_schema` | name | SI |  |  |  |
| `f_table_name` | name | SI |  |  |  |
| `f_geometry_column` | name | SI |  |  |  |
| `coord_dimension` | integer | SI |  |  |  |
| `srid` | integer | SI |  |  |  |
| `type` | character varying(30) | SI |  |  |  |

### `public.reversion_revision` (TABLA, ~55 filas, 104 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `date_created` | timestamp with time zone | NO |  |  |  |
| `comment` | text | NO |  |  |  |
| `user_id` | bigint | SI |  | public.app_organizaciones_usuario.id |  |

### `public.reversion_version` (TABLA, ~54 filas, 144 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `object_id` | character varying(191) | NO |  |  |  |
| `format` | character varying(255) | NO |  |  |  |
| `serialized_data` | text | NO |  |  |  |
| `object_repr` | text | NO |  |  |  |
| `content_type_id` | integer | NO |  | public.django_content_type.id |  |
| `revision_id` | integer | NO |  | public.reversion_revision.id |  |
| `db` | character varying(191) | NO |  |  |  |

### `public.spatial_ref_sys` (TABLA, ~8,500 filas, 7144 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `srid` | integer | NO | SI |  |  |
| `auth_name` | character varying(256) | SI |  |  |  |
| `auth_srid` | integer | SI |  |  |  |
| `srtext` | character varying(2048) | SI |  |  |  |
| `proj4text` | character varying(2048) | SI |  |  |  |

---

# BD AZURE


## Schema `pgcopydb`


### `pgcopydb.table_size` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `oid` | oid | SI |  |  |  |
| `bytes` | bigint | SI |  |  |  |

## Schema `public`


### `public.app_archivo` (TABLA, ~440,534,112 filas, 1395 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `s3key` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `encabezadoarchivo_id` | uuid | SI |  | public.app_encabezadoarchivo.id |  |
| `signature_idsignaturetype` | uuid | SI |  | public.app_signaturetype.idsignaturetype |  |
| `binaryfile` | bytea | SI |  |  |  |

### `public.app_archivo_mensajeevento` (TABLA, ~1,305,267,200 filas, 134 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `archivo_id` | uuid | NO |  |  |  |
| `mensajeevento_id` | uuid | NO | SI | public.app_mensajeevento.id |  |

### `public.app_contratoproductoef` (TABLA, ~5,849,844 filas, 1145 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `máximovalor` | integer | NO |  |  |  |
| `mínimovalor` | integer | NO |  |  |  |
| `númeroacciónaplicadaproducto` | integer | NO |  |  |  |
| `númeroreactivaciónproducto` | integer | NO |  |  |  |
| `precioproducto` | integer | NO |  |  |  |
| `serialproducto` | bigint | NO |  |  |  |
| `unidadvalorproducto` | smallint | NO |  |  |  |
| `distribuidorproducto_id` | uuid | SI |  | public.app_distribuidorproducto.id |  |
| `informacióndistribución_id` | uuid | SI |  | public.app_informacióndistribución.id |  |
| `restriccionesproducto_id` | uuid | SI |  | public.app_restriccionesproducto.id |  |
| `validezproducto_id` | uuid | SI |  | public.app_validezproducto.id |  |

### `public.app_devolución` (TABLA, ~2,268,986 filas, 381 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `cmaceventodevuelto` | character varying(255) | SI |  |  |  |
| `disponibilidadaceptación` | smallint | NO |  |  |  |
| `fechavalidezdevolucion` | timestamp without time zone | SI |  |  |  |
| `idproductodevuelto` | character varying(255) | SI |  |  |  |
| `monto` | integer | NO |  |  |  |

### `public.app_digestmethodtype` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `algorithm` | character varying(255) | SI |  |  |  |

### `public.app_distribuidorproducto` (TABLA, ~5,849,763 filas, 562 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `iddistribuidorproducto` | integer | NO |  |  |  |
| `idredproducto` | character varying(255) | SI |  |  |  |

### `public.app_econfirmaciónlam` (TABLA, ~92,104 filas, 11 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |

### `public.app_econfirmaciónlapa` (TABLA, ~28,461 filas, 3560 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `estadoproducto` | smallint | NO |  |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `númeroreactivaciónproducto` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `serialproducto` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |

### `public.app_econfirmaciónlapr` (TABLA, ~63,194,808 filas, 11 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `númeroacciónaplicadaproducto` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `serialproducto` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `eventorecargaremota_id` | uuid | SI |  | public.app_evento.id |  |
| `valorproducto_id` | uuid | SI |  | public.app_valorproductoef.id |  |

### `public.app_emediopagoemisión` (TABLA, ~2,841,677 filas, 426 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `emisión_id` | uuid | SI |  | public.app_emisiónef.id |  |
| `entorno_id` | uuid | SI |  | public.app_entornoef.id |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `eventoemisión_id` | uuid | SI |  | public.app_evento.id |  |

### `public.app_emediopagomodusuario` (TABLA, ~120,664 filas, 16 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `funcionario_id` | uuid | SI |  | public.app_funcionarioef.id |  |
| `usuario_id` | uuid | SI |  | public.app_usuarioef.id |  |

### `public.app_emediopagoreconstrucción` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopagoold` | bigint | NO |  |  |  |
| `emisión_id` | uuid | SI |  | public.app_emisiónef.id |  |
| `entorno_id` | uuid | SI |  | public.app_entornoef.id |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `funcionario_id` | uuid | SI |  | public.app_funcionarioef.id |  |
| `listaproductos_id` | uuid | SI |  | public.app_listaproductosef.id |  |
| `usuario_id` | uuid | SI |  | public.app_usuarioef.id |  |

### `public.app_emediopagoreconstrucción_contratoproductoef` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `emediopagoreconstrucción_id` | uuid | NO | SI | public.app_emediopagoreconstrucción.id |  |
| `contratoproducto_id` | uuid | NO |  | public.app_contratoproductoef.id |  |

### `public.app_emediopagoreconstrucción_devolución` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `emediopagoreconstrucción_id` | uuid | NO | SI | public.app_emediopagoreconstrucción.id |  |
| `devolución_id` | uuid | NO |  | public.app_devolución.id |  |

### `public.app_emediopagoreconstrucción_evento` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `emediopagoreconstrucción_id` | uuid | NO | SI | public.app_emediopagoreconstrucción.id |  |
| `evento_id` | uuid | NO |  | public.app_evento.id |  |

### `public.app_emediopagoreconstrucción_servicioproductoef` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `emediopagoreconstrucción_id` | uuid | NO | SI | public.app_emediopagoreconstrucción.id |  |
| `servicioproducto_id` | uuid | NO |  | public.app_servicioproductoef.id |  |

### `public.app_emediopagoreconstrucción_valorproductoef` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `emediopagoreconstrucción_id` | uuid | NO | SI | public.app_emediopagoreconstrucción.id |  |
| `valorproducto_id` | uuid | NO |  | public.app_valorproductoef.id |  |

### `public.app_emisiónef` (TABLA, ~2,841,746 filas, 500 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fechafinvalideztarjeta` | timestamp without time zone | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `país` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `emisoraplicación_id` | uuid | SI |  | public.app_emisoraplicación.id |  |
| `propietarioaplicación_id` | uuid | SI |  | public.app_propietarioaplicación.id |  |
| `versiónseguridad_id` | uuid | SI |  | public.app_versiónseguridad.id |  |

### `public.app_emisoraplicación` (TABLA, ~2,841,692 filas, 278 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idemisor` | integer | NO |  |  |  |
| `idred` | character varying(255) | SI |  |  |  |

### `public.app_encabezadoarchivo` (TABLA, ~439,589,408 filas, 48 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fechacreacionarchivod` | timestamp without time zone | SI |  |  |  |
| `númeroeventos` | integer | NO |  |  |  |
| `versiónestructura` | integer | NO |  |  |  |

### `public.app_encabezadoevento` (TABLA, ~1,305,751,168 filas, 161 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `númerosecuencial` | bigint | NO |  |  |  |

### `public.app_entornoef` (TABLA, ~2,841,692 filas, 302 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fechafinvalidezaplicacion` | timestamp without time zone | SI |  |  |  |
| `idred` | character varying(255) | SI |  |  |  |
| `versionaplicacion` | character varying(255) | SI |  |  |  |

### `public.app_eprecargadoemisión` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fechaemisiontarjeta` | timestamp without time zone | SI |  |  |  |
| `fechafinvalideztarjeta` | timestamp without time zone | SI |  |  |  |
| `idemisor` | integer | NO |  |  |  |
| `idred` | character varying(255) | SI |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `valorproducto` | integer | NO |  |  |  |
| `versionaplicacion` | character varying(255) | SI |  |  |  |

### `public.app_eprecargadouso` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `consecutivosam` | character varying(255) | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | NO |  |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `idrutaestacion` | character varying(255) | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `montoevento` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `tipoevento` | smallint | NO |  |  |  |
| `tipotransporte` | smallint | NO |  |  |  |
| `valorproducto` | integer | NO |  |  |  |

### `public.app_eproductodevoluciónrecarga` (TABLA, ~7,092 filas, 1000 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `eventodevoluciónrecarga_id` | uuid | SI |  | public.app_evento.id |  |
| `valorproducto_id` | uuid | SI |  | public.app_valorproductoef.id |  |

### `public.app_eproductodevolucióntarifa` (TABLA, ~2,263,719 filas, 487 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `devolución_id` | uuid | SI |  | public.app_devolución.id |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `eventodevolución_id` | uuid | SI |  | public.app_evento.id |  |
| `servicioproducto_id` | uuid | SI |  | public.app_servicioproductoef.id |  |
| `valorproducto_id` | uuid | SI |  | public.app_valorproductoef.id |  |

### `public.app_eproductodistribución` (TABLA, ~5,849,830 filas, 907 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `contratoproductodistribuido_id` | uuid | SI |  | public.app_contratoproductoef.id |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `eventodistribución_id` | uuid | SI |  | public.app_evento.id |  |
| `listaproductos_id` | uuid | SI |  | public.app_listaproductosef.id |  |

### `public.app_eproductoreactivación` (TABLA, ~14,872 filas, 1888 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `estadoproducto` | smallint | NO |  |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `númeroreactivaciónproducto` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `serialproducto` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |

### `public.app_eproductorecarga` (TABLA, ~158,618,816 filas, 22 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `eventorecarga_id` | uuid | SI |  | public.app_evento.id |  |
| `valorproducto_id` | uuid | SI |  | public.app_valorproductoef.id |  |

### `public.app_eproductouso` (TABLA, ~1,019,475,392 filas, 164 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `estadoaplicación_id` | uuid | SI |  | public.app_estadoaplicaciónef.id |  |
| `eventouso_id` | uuid | SI |  | public.app_evento.id |  |
| `servicioproducto_id` | uuid | SI |  | public.app_servicioproductoef.id |  |
| `valorproducto_id` | uuid | SI |  | public.app_valorproductoef.id |  |

### `public.app_estadoaplicaciónef` (TABLA, ~1,260,218,752 filas, 134 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `consecutivoaplicación` | bigint | NO |  |  |  |
| `estadoaplicación` | smallint | NO |  |  |  |
| `númeroacciónaplicada` | smallint | NO |  |  |  |

### `public.app_evento` (TABLA, ~1,258,289,792 filas, 203 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `punteroproducto` | smallint | NO |  |  |  |
| `informacióndevolución_id` | uuid | SI |  | public.app_informacióndevolución.id |  |
| `informacióngeneral_id` | uuid | SI |  | public.app_informacióngeneral.id |  |
| `informaciónubicación_id` | uuid | SI |  | public.app_informaciónubicación.id |  |
| `informaciónuso_id` | uuid | SI |  | public.app_informaciónuso.id |  |

### `public.app_funcionarioef` (TABLA, ~58,306 filas, 9232 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `datosperfilfuncionario` | character varying(255) | SI |  |  |  |

### `public.app_informacióndevolución` (TABLA, ~1,260,712,448 filas, 124 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `motivodevolución` | smallint | NO |  |  |  |

### `public.app_informacióndistribución` (TABLA, ~5,849,904 filas, 663 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fechadistribucionproducto` | timestamp without time zone | SI |  |  |  |
| `iddispositivodistribucion` | character varying(255) | SI |  |  |  |
| `idsamdistribucion` | character varying(255) | SI |  |  |  |

### `public.app_informacióngeneral` (TABLA, ~1,259,931,904 filas, 203 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `consecutivoevento` | bigint | NO |  |  |  |
| `consecutivosam` | character varying(255) | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | NO |  |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `montoevento` | integer | NO |  |  |  |
| `tipoevento` | smallint | NO |  |  |  |

### `public.app_informaciónubicación` (TABLA, ~1,260,476,672 filas, 162 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `configubicación` | smallint | NO |  |  |  |
| `idubicacion` | character varying(255) | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |

### `public.app_informaciónuso` (TABLA, ~1,260,379,648 filas, 142 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idrutaestacion` | character varying(255) | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | NO |  |  |  |
| `númerotransbordos` | smallint | NO |  |  |  |
| `tipotransporte` | smallint | NO |  |  |  |

### `public.app_listaproductosef` (TABLA, ~5,849,808 filas, 1242 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `sector1_id` | uuid | SI |  | public.app_sector.id |  |
| `sector2_id` | uuid | SI |  | public.app_sector.id |  |
| `sector3_id` | uuid | SI |  | public.app_sector.id |  |
| `sector4_id` | uuid | SI |  | public.app_sector.id |  |
| `sector5_id` | uuid | SI |  | public.app_sector.id |  |
| `sector6_id` | uuid | SI |  | public.app_sector.id |  |
| `sector7_id` | uuid | SI |  | public.app_sector.id |  |
| `sector8_id` | uuid | SI |  | public.app_sector.id |  |

### `public.app_mensajeevento` (TABLA, ~1,304,738,688 filas, 171 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `econfirmaciónlam_id` | uuid | SI |  | public.app_econfirmaciónlam.id |  |
| `econfirmaciónlapa_id` | uuid | SI |  | public.app_econfirmaciónlapa.id |  |
| `econfirmaciónlapr_id` | uuid | SI |  | public.app_econfirmaciónlapr.id |  |
| `emediopagoemisión_id` | uuid | SI |  | public.app_emediopagoemisión.id |  |
| `emediopagomodusuario_id` | uuid | SI |  | public.app_emediopagomodusuario.id |  |
| `emediopagoreconstrucción_id` | uuid | SI |  | public.app_emediopagoreconstrucción.id |  |
| `eprecargadoemisión_id` | uuid | SI |  | public.app_eprecargadoemisión.id |  |
| `eprecargadouso_id` | uuid | SI |  | public.app_eprecargadouso.id |  |
| `eproductodevoluciónrecarga_id` | uuid | SI |  | public.app_eproductodevoluciónrecarga.id |  |
| `eproductodevolucióntarifa_id` | uuid | SI |  | public.app_eproductodevolucióntarifa.id |  |
| `eproductodistribución_id` | uuid | SI |  | public.app_eproductodistribución.id |  |
| `eproductoreactivación_id` | uuid | SI |  | public.app_eproductoreactivación.id |  |
| `eproductorecarga_id` | uuid | SI |  | public.app_eproductorecarga.id |  |
| `eproductouso_id` | uuid | SI |  | public.app_eproductouso.id |  |
| `encabezadoevento_id` | uuid | SI |  | public.app_encabezadoevento.id |  |
| `reventonoefectuado_id` | uuid | SI |  | public.app_reventonoefectuado.id |  |
| `rexclusiondispositivo_id` | uuid | SI |  | public.app_rexclusiondispositivo.id |  |
| `rexclusionsam_id` | uuid | SI |  | public.app_rexclusionsam.id |  |
| `rinclusiondispositivo_id` | uuid | SI |  | public.app_rinclusiondispositivo.id |  |
| `sacciónlam_id` | uuid | SI |  | public.app_sacciónlam.id |  |
| `sacciónlapa_id` | uuid | SI |  | public.app_sacciónlapa.id |  |
| `sacciónlapr_id` | uuid | SI |  | public.app_sacciónlapr.id |  |
| `sexclusiondispositivo_id` | uuid | SI |  | public.app_sexclusiondispositivo.id |  |
| `sexclusionsam_id` | uuid | SI |  | public.app_sexclusionsam.id |  |
| `sinclusiondispositivo_id` | uuid | SI |  | public.app_sinclusiondispositivo.id |  |

### `public.app_perfil` (TABLA, ~120,664 filas, 17 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `credencialusuario` | character varying(255) | SI |  |  |  |
| `códigoperfil` | smallint | NO |  |  |  |
| `fechafinperfil` | timestamp without time zone | SI |  |  |  |
| `idredusuario` | character varying(255) | SI |  |  |  |
| `nombreusuario` | character varying(255) | SI |  |  |  |

### `public.app_propietarioaplicación` (TABLA, ~2,841,692 filas, 278 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idpropietario` | integer | NO |  |  |  |
| `idred` | character varying(255) | SI |  |  |  |

### `public.app_restriccionesproducto` (TABLA, ~5,849,820 filas, 812 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `díasrestringidos` | smallint | NO |  |  |  |
| `maxviajesdomingo` | integer | NO |  |  |  |
| `maxviajesespecial` | integer | NO |  |  |  |
| `maxviajesjueves` | integer | NO |  |  |  |
| `maxviajeslunes` | integer | NO |  |  |  |
| `maxviajesmartes` | integer | NO |  |  |  |
| `maxviajesmiercoles` | integer | NO |  |  |  |
| `maxviajessabado` | integer | NO |  |  |  |
| `maxviajesviernes` | integer | NO |  |  |  |
| `passbackspermitidos` | smallint | NO |  |  |  |
| `tiempopassback` | integer | NO |  |  |  |
| `tiempotransbordo` | integer | NO |  |  |  |
| `transbordospermitidos` | smallint | NO |  |  |  |

### `public.app_reventonoefectuado` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `códigorazónfalla` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `tipoeventointentado` | integer | NO |  |  |  |

### `public.app_rexclusiondispositivo` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `rtaexdisp` | integer | NO |  |  |  |
| `tipodispositivo` | integer | NO |  |  |  |

### `public.app_rexclusionsam` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `rtaexsam` | integer | NO |  |  |  |
| `tiposam` | integer | NO |  |  |  |

### `public.app_rinclusiondispositivo` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `rtaindisp` | integer | NO |  |  |  |
| `tipodispositivo` | integer | NO |  |  |  |

### `public.app_sacciónlam` (TABLA, ~146,791 filas, 15 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `códigoacción` | smallint | NO |  |  |  |
| `númeroacciónmediopago` | smallint | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |

### `public.app_sacciónlapa` (TABLA, ~28,278 filas, 2808 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `codigoproducto` | character varying(255) | SI |  |  |  |
| `numerosuspensiónproducto` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |

### `public.app_sacciónlapr` (TABLA, ~49,541,528 filas, 6689 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `codigoproducto` | character varying(255) | SI |  |  |  |
| `montoacción` | integer | NO |  |  |  |
| `numeroacciónproducto` | integer | NO |  |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `fechahorasolicitud` | timestamp without time zone | SI |  |  |  |

### `public.app_sector` (TABLA, ~46,798,552 filas, 4261 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `prioridadproducto` | smallint | NO |  |  |  |
| `punterocontrato` | smallint | NO |  |  |  |
| `punteroservicio` | smallint | NO |  |  |  |
| `punterovalor` | smallint | NO |  |  |  |

### `public.app_servicioproductoef` (TABLA, ~1,019,696,960 filas, 141 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `estadoproducto` | smallint | NO |  |  |  |
| `numeroviajesdomingo` | integer | NO |  |  |  |
| `numeroviajesespecial` | integer | NO |  |  |  |
| `numeroviajesjueves` | integer | NO |  |  |  |
| `numeroviajeslunes` | integer | NO |  |  |  |
| `numeroviajesmartes` | integer | NO |  |  |  |
| `numeroviajesmiercoles` | integer | NO |  |  |  |
| `numeroviajessabado` | integer | NO |  |  |  |
| `numeroviajesviernes` | integer | NO |  |  |  |
| `númeroactualusos` | integer | NO |  |  |  |
| `númerosemanaaño` | smallint | NO |  |  |  |

### `public.app_sexclusiondispositivo` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `tipodispositivo` | integer | NO |  |  |  |

### `public.app_sexclusionsam` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `tiposam` | integer | NO |  |  |  |

### `public.app_signaturemethodtype` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `algorithm` | character varying(255) | SI |  |  |  |

### `public.app_signaturetype` (TABLA, ~439,559,232 filas, 48 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `idsignaturetype` | uuid | NO | SI |  |  |
| `id` | character varying(255) | SI |  |  |  |
| `signaturevalue_idsignaturevaluetype` | uuid | SI |  | public.app_signaturevaluetype.idsignaturevaluetype |  |

### `public.app_signaturevaluetype` (TABLA, ~440,018,656 filas, 912 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `idsignaturevaluetype` | uuid | NO | SI |  |  |
| `id` | character varying(255) | SI |  |  |  |
| `value` | bytea | SI |  |  |  |
| `valuehex` | text | SI |  |  |  |

### `public.app_sinclusiondispositivo` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `tipodispositivo` | integer | NO |  |  |  |

### `public.app_usuarioef` (TABLA, ~120,664 filas, 13 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fechanacimientousuario` | timestamp without time zone | SI |  |  |  |
| `perfil_id` | uuid | SI |  | public.app_perfil.id |  |

### `public.app_validezproducto` (TABLA, ~5,849,725 filas, 663 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `finvalidezdía` | integer | NO |  |  |  |
| `finvalidezproducto` | timestamp without time zone | SI |  |  |  |
| `iniciovalidezdía` | integer | NO |  |  |  |
| `iniciovalidezproducto` | timestamp without time zone | SI |  |  |  |

### `public.app_valorproductoef` (TABLA, ~1,250,762,112 filas, 124 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `valorproducto` | integer | NO |  |  |  |

### `public.app_versiónseguridad` (TABLA, ~2,841,692 filas, 253 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `idalgseguridad` | smallint | NO |  |  |  |
| `idversiónllaves` | smallint | NO |  |  |  |

### `public.c_confirmacion_lam` (TABLA, ~90,456 filas, 20 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | text | SI |  |  |  |
| `punteroproducto` | text | SI |  |  |  |
| `motivodevolución` | text | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `consecutivosam` | text | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | text | SI |  |  |  |
| `iddispositivo` | text | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `montoevento` | integer | SI |  |  |  |
| `tipoevento` | integer | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | SI |  |  |  |
| `númerotransbordos` | smallint | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `valorproducto` | integer | SI |  |  |  |
| `númeroAcciónAplicada` | smallint | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `surrogate_id` | integer | NO | SI |  |  |

### `public.c_dispositivos` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | NO | SI |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `tipodispositivo` | integer | SI |  |  |  |
| `activo` | integer | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |

### `public.c_eventosinvalidos` (TABLA, ~759 filas, 152 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `idsam` | text | SI |  |  |  |
| `consecutivosam` | text | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `eliminado` | boolean | SI |  |  |  |
| `xmlname` | text | SI |  |  |  |
| `disabled` | integer | SI |  |  |  |

### `public.c_mediopago` (TABLA, ~2,762,175 filas, 899 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `punteroproducto` | smallint | SI |  |  |  |
| `motivodevolución` | smallint | SI |  |  |  |
| `idemisor` | integer | SI |  |  |  |
| `idpropietario` | integer | SI |  |  |  |
| `idred` | character varying(255) | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `montoevento` | smallint | SI |  |  |  |
| `tipoevento` | smallint | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying(255) | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying(255) | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `idalgseguridad` | smallint | SI |  |  |  |
| `idversiónllaves` | smallint | SI |  |  |  |
| `fechafinvalidezaplicacion` | timestamp without time zone | SI |  |  |  |
| `versionaplicacion` | character varying(255) | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `consecutivosam` | text | SI |  |  |  |
| `consecutivoaplicacioninicial` | bigint | SI |  |  |  |
| `id` | uuid | NO | SI |  |  |

### `public.c_modusuario` (TABLA, ~232,486 filas, 64 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `serialmediopago` | bigint | SI |  |  |  |
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `númeroacciónaplicada` | smallint | SI |  |  |  |
| `datosperfilfuncionario` | character varying(255) | SI |  |  |  |
| `fechanacimientousuario` | timestamp without time zone | SI |  |  |  |
| `credencialusuario` | character varying(255) | SI |  |  |  |
| `códigoperfil` | smallint | SI |  |  |  |
| `fechafinperfil` | timestamp without time zone | SI |  |  |  |
| `idredusuario` | character varying(255) | SI |  |  |  |
| `nombreusuario` | character varying(255) | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `consecutivosam` | text | SI |  |  |  |
| `id` | uuid | NO | SI |  |  |

### `public.c_pagado` (TABLA, ~3,152 filas, 368 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `identidaduso` | integer | SI |  |  |  |
| `identidadrecarga` | integer | SI |  |  |  |
| `fecha_compensacion` | date | NO |  |  |  |
| `saldopagado` | bigint | SI |  |  |  |
| `nombre_entidad_recarga` | text | SI |  |  |  |
| `nombre_entidad_uso` | text | SI |  |  |  |

### `public.c_recarga_devolucion` (TABLA, ~508 filas, 176 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `c_recarga_devolucion_id` | uuid | NO | SI |  |  |
| `c_recarga_id` | uuid | NO |  |  |  |
| `c_recarga_devuelta_id` | uuid | NO |  |  |  |
| `saldodevuelto` | integer | NO |  |  |  |
| `fecha_calculo_compensacion` | timestamp(6) without time zone | NO |  |  |  |
| `fecha_compensacion` | date | SI |  |  | Esta es la fecha de compensación donde se inserto el registro |

### `public.c_recarga_uso` (TABLA, ~149,448,384 filas, 29 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `c_recarga_uso_id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `c_recarga_id` | uuid | NO |  | public.c_recargas.c_recargas_id |  |
| `c_uso_id` | uuid | NO |  | public.c_usos.c_usos_id |  |
| `identidadrecarga` | integer | NO |  |  |  |
| `identidaduso` | integer | NO |  |  |  |
| `saldopagado` | integer | NO |  |  |  |
| `fecha_compensacion` | date | NO |  |  |  |
| `fecha_calculo_compensacion` | timestamp with time zone | NO |  |  |  |
| `fechahoraevento_recarga` | timestamp without time zone | SI |  |  |  |
| `fechahoraevento_uso` | timestamp without time zone | SI |  |  |  |

### `public.c_recargas` (TABLA, ~228,736,912 filas, 104 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `c_recargas_id` | uuid | NO | SI |  |  |
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `punteroproducto` | smallint | SI |  |  |  |
| `motivodevolución` | smallint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `montoevento` | integer | SI |  |  |  |
| `tipoevento` | smallint | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying(255) | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying(255) | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | SI |  |  |  |
| `númerotransbordos` | smallint | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `valorproducto` | integer | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `devolucion` | boolean | SI |  |  |  |
| `consecutivosam` | character varying | SI |  |  |  |
| `identidadsolicitud` | integer | SI |  |  |  |
| `numeroaccion` | integer | SI |  |  |  |
| `disponible` | boolean | NO |  |  | Indica si la recarga aún está disponible con saldo |

### `public.c_seriales_deshabilitados` (TABLA, ~337,727 filas, 42 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `serialmediopago` | bigint | NO |  |  |  |
| `fecha_inicio` | date | NO |  |  |  |
| `fecha_fin` | date | NO |  |  |  |
| `created_at` | timestamp without time zone | NO |  |  |  |
| `updated_at` | timestamp without time zone | NO |  |  |  |

### `public.c_seriales_deshabilitados_aud` (TABLA, ~536,908 filas, 56 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `rev` | integer | NO | SI | public.revinfo.rev |  |
| `revtype` | smallint | SI |  |  |  |
| `fecha_fin` | date | SI |  |  |  |
| `fecha_inicio` | date | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |

### `public.c_transacciones` (TABLA, ~1,293,654,656 filas, 600 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | character varying | SI |  |  |  |
| `punteroproducto` | smallint | SI |  |  |  |
| `motivodevolución` | smallint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `consecutivosam` | character varying | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `iddispositivo` | character varying | SI |  |  |  |
| `idsam` | character varying | SI |  |  |  |
| `montoevento` | integer | SI |  |  |  |
| `tipoevento` | integer | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | SI |  |  |  |
| `númerotransbordos` | smallint | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `valorproducto` | integer | SI |  |  |  |
| `estadoproducto` | integer | SI |  |  |  |
| `númerosemanaaño` | integer | SI |  |  |  |
| `numeroviajeslunes` | integer | SI |  |  |  |
| `numeroviajesmartes` | integer | SI |  |  |  |
| `numeroviajesmiercoles` | integer | SI |  |  |  |
| `numeroviajesjueves` | integer | SI |  |  |  |
| `numeroviajesviernes` | integer | SI |  |  |  |
| `numeroviajessabado` | integer | SI |  |  |  |
| `numeroviajesdomingo` | integer | SI |  |  |  |
| `numeroviajesespecial` | integer | SI |  |  |  |
| `númeroactualusos` | integer | SI |  |  |  |
| `codigoaccion` | integer | SI |  |  |  |
| `numeroaccion` | integer | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `id` | uuid | NO | SI |  |  |

### `public.c_transacciones_update` (TABLA, ~1,534 filas, 176 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `activo` | boolean | SI |  |  |  |

### `public.c_usos` (TABLA, ~1,012,629,632 filas, 590 GB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `c_usos_id` | uuid | NO | SI |  |  |
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | character varying(255) | SI |  |  |  |
| `punteroproducto` | smallint | SI |  |  |  |
| `motivodevolución` | smallint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `iddispositivo` | character varying(255) | SI |  |  |  |
| `idsam` | character varying(255) | SI |  |  |  |
| `montoevento` | integer | SI |  |  |  |
| `tipoevento` | smallint | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying(255) | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying(255) | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | SI |  |  |  |
| `númerotransbordos` | smallint | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `valorproducto` | integer | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `montofinal` | double precision | SI |  |  |  |
| `consecutivosam` | text | SI |  |  |  |
| `compensado` | boolean | SI |  |  |  |
| `disponible` | boolean | NO |  |  | Indica si un uso está disponible |

### `public.compensacion` (TABLA, ~787 filas, 224 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `fecha` | timestamp(6) without time zone | SI |  |  |  |
| `entidad` | text | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `usuario` | text | SI |  |  |  |
| `estado` | smallint | SI |  |  |  |
| `report_bucket_key` | text | SI |  |  |  |
| `fechahorainicio` | timestamp without time zone | SI |  |  |  |
| `fechahorafin` | timestamp without time zone | SI |  |  |  |
| `primerdia` | boolean | SI |  |  |  |
| `fechahoramaximarecibido` | timestamp without time zone | SI |  |  |  |
| `ejecutar` | boolean | SI |  |  |  |
| `cons_interop` | text | SI |  |  | Esta es la cons interop para la compensación |
| `modificated_by` | character varying | SI |  |  | Este es el identificador de modificación |

### `public.compensacion_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |
| `fecha` | timestamp without time zone | SI |  |  |  |
| `entidad` | text | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `estado` | smallint | SI |  |  |  |
| `report_bucket_key` | text | SI |  |  |  |
| `fechahorainicio` | timestamp without time zone | SI |  |  |  |
| `fechahorafin` | timestamp without time zone | SI |  |  |  |
| `primerdia` | boolean | SI |  |  |  |
| `fechahoramaximarecibido` | timestamp without time zone | SI |  |  |  |
| `ejecutar` | boolean | SI |  |  |  |
| `cons_interop` | text | SI |  |  |  |

### `public.compensacion_estado` (TABLA, ~4 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `compensacion_estado_id` | smallint | NO | SI |  |  |
| `compensacion_estado_nombre` | character varying(10) | NO |  |  |  |

### `public.compensacion_transacciones` (TABLA, ~16,491,082 filas, 6455 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | character varying | SI |  |  |  |
| `punteroproducto` | smallint | SI |  |  |  |
| `motivodevolución` | smallint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `consecutivosam` | character varying | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `iddispositivo` | character varying | SI |  |  |  |
| `idsam` | character varying | SI |  |  |  |
| `montoevento` | integer | SI |  |  |  |
| `tipoevento` | integer | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | SI |  |  |  |
| `númerotransbordos` | smallint | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `valorproducto` | integer | SI |  |  |  |
| `estadoproducto` | integer | SI |  |  |  |
| `númerosemanaaño` | integer | SI |  |  |  |
| `numeroviajeslunes` | integer | SI |  |  |  |
| `numeroviajesmartes` | integer | SI |  |  |  |
| `numeroviajesmiercoles` | integer | SI |  |  |  |
| `numeroviajesjueves` | integer | SI |  |  |  |
| `numeroviajesviernes` | integer | SI |  |  |  |
| `numeroviajessabado` | integer | SI |  |  |  |
| `numeroviajesdomingo` | integer | SI |  |  |  |
| `numeroviajesespecial` | integer | SI |  |  |  |
| `númeroactualusos` | integer | SI |  |  |  |
| `codigoaccion` | integer | SI |  |  |  |
| `numeroaccion` | integer | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |
| `activo` | boolean | SI |  |  |  |
| `id` | uuid | NO | SI |  |  |

### `public.configuracion` (TABLA, ~1 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `configuracion_id` | bigint | NO | SI |  |  |
| `configuracion_limite_maximo` | bigint | NO |  |  |  |
| `configuracion_aumento_limite` | bigint | NO |  |  |  |
| `configuracion_created_at` | timestamp with time zone | NO |  |  |  |
| `configuracion_activa` | bigint | NO |  |  |  |
| `constante_interoperabilidad` | numeric | SI |  |  |  |
| `tiempo_devolucion` | integer | SI |  |  |  |
| `configuracion_end_at` | timestamp with time zone | SI |  |  |  |

### `public.datosregistrador` (TABLA, ~4 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `datosregistrador_id` | bigint | NO | SI |  |  |
| `datosregistrador_idproducto` | character varying(4) | NO |  |  |  |
| `datosregistrador_prioridadproducto` | character varying(2) | NO |  |  |  |
| `datosregistrador_minimovalor` | bigint | NO |  |  |  |
| `datosregistrador_maximovalor` | bigint | NO |  |  |  |
| `datosregistrador_diasrestringidos` | character varying(2) | NO |  |  |  |
| `datosregistrador_maxviajesdiasemana` | character varying(8) | NO |  |  |  |
| `datosregistrador_tiempopassback` | integer | NO |  |  |  |
| `datosregistrador_tiempotransbordo` | integer | NO |  |  |  |
| `datosregistrador_transbordospermitidos` | integer | NO |  |  |  |
| `datosregistrador_passbackspermitidos` | integer | NO |  |  |  |

### `public.dispositivo_estado` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |

### `public.dispositivo_punto_recarga` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_dispositivo` | text | NO |  | public.dispositivos.dispositivo_id |  |
| `id_entidad` | text | NO |  | public.dispositivos.dispositivo_entidad |  |
| `recharging_point_id` | text | NO |  | public.recharging_points.id |  |
| `id_dispositivo_punto_recarga` | uuid | NO | SI |  |  |

### `public.dispositivo_sam` (TABLA, ~1,483 filas, 200 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_dispositivo_sam` | bigint | NO | SI |  |  |
| `id_sam` | text | NO |  | public.sams.sam_serial |  |
| `id_dispositivo` | text | NO |  | public.dispositivos.dispositivo_id |  |
| `id_entidad` | text | SI |  | public.dispositivos.dispositivo_entidad |  |

### `public.dispositivo_tipo` (TABLA, ~5 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `dispositivo_tipo_id` | bigint | NO | SI |  |  |
| `dispositivo_tipo_nombre` | text | NO |  |  |  |

### `public.dispositivos` (TABLA, ~1,320 filas, 208 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `dispositivo_id` | character varying(4) | NO | SI |  |  |
| `dispositivo_entidad` | character varying(4) | NO | SI |  |  |
| `dispositivo_sam_serial` | character varying(14) | SI |  |  |  |
| `dispositivo_tipo` | bigint | NO |  | public.dispositivo_tipo.dispositivo_tipo_id |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `dispositivo_activo` | smallint | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |

### `public.dispositivos_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `dispositivo_id` | character varying(4) | NO |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `dispositivo_entidad` | character varying(4) | NO |  |  |  |
| `dispositivo_tipo` | bigint | NO |  | public.dispositivo_tipo.dispositivo_tipo_id |  |
| `dispositivo_activo` | smallint | SI |  |  |  |

### `public.dispositivos_mediostransporte` (TABLA, ~1,319 filas, 208 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_dispositivos_mediotransporte` | uuid | NO | SI |  |  |
| `id_dispositivo` | text | NO |  | public.dispositivos.dispositivo_id |  |
| `id_mediostransporte` | uuid | NO |  | public.transit_mediostransporte.id_mediostransporte |  |
| `id_entidad` | text | SI |  | public.dispositivos.dispositivo_entidad |  |

### `public.entidad` (TABLA, ~3 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `entidad_codigo` | character varying(4) | NO | SI |  |  |
| `entidad_nombre` | text | NO |  |  |  |
| `entidad_certificado` | text | SI |  |  |  |
| `entidad_activa` | integer | NO |  |  |  |
| `created_at` | timestamp with time zone | NO |  |  |  |
| `updated_at` | timestamp with time zone | NO |  |  |  |
| `entidad_pais` | text | SI |  |  |  |
| `entidad_ciudad` | text | SI |  |  |  |
| `entidad_estado` | text | SI |  |  |  |
| `entidad_direccion` | text | SI |  |  |  |
| `entidad_email` | text | SI |  |  |  |
| `entidad_telefono` | text | SI |  |  |  |
| `entidad_paissiglas` | text | SI |  |  |  |
| `entidad_main` | boolean | NO |  |  |  |
| `entidad_certificado_data` | text | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  | Este es el identificador de modificación para la entidad |

### `public.entidad_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `entidad_codigo` | character varying(4) | NO |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `entidad_nombre` | text | NO |  |  |  |
| `entidad_certificado` | text | SI |  |  |  |
| `entidad_activa` | integer | NO |  |  |  |
| `entidad_pais` | text | SI |  |  |  |
| `entidad_ciudad` | text | SI |  |  |  |
| `entidad_estado` | text | SI |  |  |  |
| `entidad_direccion` | text | SI |  |  |  |
| `entidad_email` | text | SI |  |  |  |
| `entidad_telefono` | text | SI |  |  |  |
| `entidad_paissiglas` | text | SI |  |  |  |
| `entidad_main` | boolean | NO |  |  |  |
| `entidad_certificado_data` | text | SI |  |  |  |

### `public.festivos` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `fecha` | date | NO |  |  |  |

### `public.franja_horaria` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `tipo_evento` | text | SI |  |  |  |
| `hora_inicio` | time without time zone | NO |  |  |  |
| `hora_fin` | time without time zone | NO |  |  |  |
| `rango` | timerange | SI |  |  |  |

### `public.frecuencia_operacion` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `intervalo_max` | integer | SI |  |  |  |
| `intervalo_min` | integer | SI |  |  |  |

### `public.gtfs_agencies` (TABLA, ~60 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | character varying(50) | NO | SI |  |  |
| `fareurl` | character varying(255) | SI |  |  |  |
| `lang` | character varying(255) | SI |  |  |  |
| `name` | character varying(255) | SI |  |  |  |
| `phone` | character varying(255) | SI |  |  |  |
| `timezone` | character varying(255) | SI |  |  |  |
| `url` | character varying(255) | SI |  |  |  |

### `public.gtfs_calendar_dates` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `date` | character varying(8) | SI |  |  |  |
| `exceptiontype` | integer | SI |  |  |  |
| `serviceid_agencyid` | character varying(50) | SI |  |  |  |
| `serviceid_id` | character varying(255) | SI |  |  |  |

### `public.gtfs_calendars` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `monday` | integer | SI |  |  |  |
| `tuesday` | integer | SI |  |  |  |
| `wednesday` | integer | SI |  |  |  |
| `thursday` | integer | SI |  |  |  |
| `friday` | integer | SI |  |  |  |
| `saturday` | integer | SI |  |  |  |
| `sunday` | integer | SI |  |  |  |
| `startdate` | character varying(8) | SI |  |  |  |
| `enddate` | character varying(8) | SI |  |  |  |
| `serviceid_agencyid` | character varying(50) | SI |  |  |  |
| `serviceid_id` | character varying(255) | SI |  |  |  |

### `public.gtfs_fare_attributes` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agencyid` | character varying(50) | NO | SI |  |  |
| `id` | character varying(255) | NO | SI |  |  |
| `price` | real | SI |  |  |  |
| `currencytype` | character varying(255) | SI |  |  |  |
| `paymentmethod` | text | SI |  |  |  |
| `transfers` | integer | SI |  |  |  |
| `transferduration` | text | SI |  |  |  |
| `journeyduration` | integer | SI |  |  |  |

### `public.gtfs_fare_rules` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `fare_agencyid` | character varying(50) | SI |  | public.gtfs_fare_attributes.agencyid |  |
| `fare_id` | character varying(255) | SI |  | public.gtfs_fare_attributes.id |  |
| `route_agencyid` | character varying(50) | SI |  | public.gtfs_routes.agencyid |  |
| `route_id` | character varying(255) | SI |  | public.gtfs_routes.id |  |
| `originid` | character varying(255) | SI |  |  |  |
| `destinationid` | character varying(255) | SI |  |  |  |
| `containsid` | character varying(255) | SI |  |  |  |

### `public.gtfs_feed_info` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `publishername` | character varying(255) | SI |  |  |  |
| `publisherurl` | character varying(255) | SI |  |  |  |
| `lang` | character varying(255) | SI |  |  |  |
| `startdate` | character varying(8) | SI |  |  |  |
| `enddate` | character varying(8) | SI |  |  |  |
| `version` | character varying(255) | SI |  |  |  |

### `public.gtfs_file` (TABLA, ~0 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gtfs_file_id` | bigint | NO | SI |  |  |
| `gtfs_file_nombre` | character varying(255) | SI |  |  |  |
| `gtfs_file_nombre_servidor` | character varying(255) | SI |  |  |  |
| `gtfs_file_ubicacion` | character varying(255) | SI |  |  |  |
| `gtfs_file_hash` | character varying(255) | SI |  |  |  |
| `gtfs_file_usuario` | character varying(255) | SI |  |  |  |
| `gtfs_file_tipo_almacenamiento_id` | character varying(255) | SI |  |  |  |
| `gtfs_file_estado_id` | character varying(255) | SI |  |  |  |

### `public.gtfs_file_estado` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | character varying(255) | NO | SI |  |  |
| `nombre` | character varying(255) | NO |  |  |  |

### `public.gtfs_file_tipo_almacenamiento` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | character varying(255) | NO | SI |  |  |
| `nombre` | character varying(255) | NO |  |  |  |

### `public.gtfs_frequencies` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `trip_agencyid` | character varying(50) | SI |  | public.gtfs_trips.agencyid |  |
| `trip_id` | character varying(255) | SI |  | public.gtfs_trips.id |  |
| `starttime` | time without time zone | SI |  |  |  |
| `endtime` | time without time zone | SI |  |  |  |
| `exacttimes` | integer | SI |  |  |  |
| `headwaysecs` | integer | SI |  |  |  |
| `labelonly` | integer | SI |  |  |  |

### `public.gtfs_levels` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agencyid` | character varying(50) | NO |  |  |  |
| `id` | character varying(255) | NO | SI |  |  |
| `index` | double precision | SI |  |  |  |
| `name` | character varying(255) | SI |  |  |  |

### `public.gtfs_pathways` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agencyid` | character varying(50) | NO | SI |  |  |
| `id` | character varying(255) | NO | SI |  |  |
| `fromstop_agencyid` | character varying(50) | SI |  |  |  |
| `fromstop_id` | character varying(255) | SI |  |  |  |
| `tostop_agencyid` | character varying(50) | SI |  |  |  |
| `tostop_id` | character varying(255) | SI |  |  |  |
| `pathwaytype` | integer | SI |  |  |  |
| `traversaltime` | integer | SI |  |  |  |
| `wheelchairtraversaltime` | integer | SI |  |  |  |

### `public.gtfs_riderships` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `agencyid` | character varying(50) | SI |  |  |  |
| `routeid` | character varying(50) | SI |  |  |  |
| `tripid` | character varying(50) | SI |  |  |  |
| `stopid` | character varying(50) | SI |  |  |  |
| `totalboardings` | integer | SI |  |  |  |
| `totalalightings` | integer | SI |  |  |  |
| `startdate` | character varying(8) | SI |  |  |  |
| `enddate` | character varying(8) | SI |  |  |  |
| `averageload` | double precision | SI |  |  |  |

### `public.gtfs_routes` (TABLA, ~162 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agencyid` | character varying(50) | NO | SI |  |  |
| `id` | character varying(255) | NO | SI |  |  |
| `description` | text | SI |  |  |  |
| `shortname` | character varying(255) | SI |  |  |  |
| `longname` | character varying(255) | SI |  |  |  |
| `type` | integer | SI |  |  |  |
| `url` | character varying(255) | SI |  |  |  |
| `color` | character varying(255) | SI |  |  |  |
| `textcolor` | character varying(255) | SI |  |  |  |
| `agency` | character varying(50) | NO |  | public.gtfs_agencies.id |  |

### `public.gtfs_shape_points` (TABLA, ~55,080 filas, 5760 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `sequence` | integer | SI |  |  |  |
| `disttraveled` | double precision | SI |  |  |  |
| `lat` | double precision | SI |  |  |  |
| `lon` | double precision | SI |  |  |  |
| `shapeid_agencyid` | character varying(50) | SI |  |  |  |
| `shapeid_id` | character varying(255) | SI |  |  |  |

### `public.gtfs_sistemasdetransporte` (TABLA, ~7 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_sistemasdetransporte` | bigint | NO | SI |  |  |
| `nombre_sistemasdetransporte` | text | NO |  |  |  |
| `descripcion_sistemasdetransporte` | text | SI |  |  |  |

### `public.gtfs_stop_times` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `stop_agencyid` | character varying(50) | SI |  |  |  |
| `stop_id` | character varying(255) | SI |  |  |  |
| `trip_agencyid` | character varying(50) | SI |  | public.gtfs_trips.agencyid |  |
| `trip_id` | character varying(255) | SI |  | public.gtfs_trips.id |  |
| `stopsequence` | integer | SI |  |  |  |
| `arrivaltime` | time without time zone | SI |  |  |  |
| `departuretime` | time without time zone | SI |  |  |  |
| `timepoint` | integer | SI |  |  |  |
| `stopheadsign` | character varying(255) | SI |  |  |  |
| `routeshortname` | character varying(255) | SI |  |  |  |
| `pickuptype` | text | SI |  |  |  |
| `dropofftype` | text | SI |  |  |  |
| `shapedisttraveled` | text | SI |  |  |  |

### `public.gtfs_stops` (TABLA, ~2,238 filas, 384 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agencyid` | character varying(50) | SI |  |  |  |
| `id` | character varying(255) | NO | SI |  |  |
| `code` | character varying(255) | SI |  |  |  |
| `name` | character varying(255) | SI |  |  |  |
| `description` | character varying(255) | SI |  |  |  |
| `direction` | character varying(255) | SI |  |  |  |
| `lat` | double precision | SI |  |  |  |
| `lon` | double precision | SI |  |  |  |
| `zoneid` | character varying(255) | SI |  |  |  |
| `url` | character varying(255) | SI |  |  |  |
| `locationtype` | integer | SI |  |  |  |
| `parentstation` | character varying(255) | SI |  |  |  |
| `timezone` | character varying(255) | SI |  |  |  |
| `vehicletype` | integer | SI |  |  |  |
| `wheelchairboarding` | integer | SI |  |  |  |
| `platformcode` | character varying(255) | SI |  |  |  |
| `stop_archived_date` | timestamp with time zone | SI |  |  |  |
| `stop_active` | smallint | SI |  |  |  |

### `public.gtfs_transfers` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `gid` | integer | NO | SI |  |  |
| `fromstop_agencyid` | character varying(50) | SI |  |  |  |
| `fromstop_id` | character varying(255) | SI |  |  |  |
| `fromroute_agencyid` | character varying(50) | SI |  | public.gtfs_routes.agencyid |  |
| `fromroute_id` | character varying(255) | SI |  | public.gtfs_routes.id |  |
| `fromtrip_agencyid` | character varying(50) | SI |  | public.gtfs_trips.agencyid |  |
| `fromtrip_id` | character varying(255) | SI |  | public.gtfs_trips.id |  |
| `tostop_agencyid` | character varying(50) | SI |  |  |  |
| `tostop_id` | character varying(255) | SI |  |  |  |
| `toroute_agencyid` | character varying(50) | SI |  | public.gtfs_routes.agencyid |  |
| `toroute_id` | character varying(255) | SI |  | public.gtfs_routes.id |  |
| `totrip_agencyid` | character varying(50) | SI |  | public.gtfs_trips.agencyid |  |
| `totrip_id` | character varying(255) | SI |  | public.gtfs_trips.id |  |
| `transfertype` | integer | SI |  |  |  |
| `mintransfertime` | integer | SI |  |  |  |

### `public.gtfs_trips` (TABLA, ~10,854 filas, 1368 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agencyid` | character varying(50) | NO | SI |  |  |
| `id` | character varying(255) | NO | SI |  |  |
| `route_agencyid` | character varying(50) | SI |  | public.gtfs_routes.agencyid |  |
| `route_id` | character varying(255) | SI |  | public.gtfs_routes.id |  |
| `serviceid_agencyid` | character varying(50) | SI |  |  |  |
| `serviceid_id` | character varying(255) | SI |  |  |  |
| `shapeid_agencyid` | character varying(50) | SI |  |  |  |
| `shapeid_id` | character varying(255) | SI |  |  |  |
| `tripshortname` | character varying(255) | SI |  |  |  |
| `tripheadsign` | character varying(255) | SI |  |  |  |
| `routeshortname` | character varying(255) | SI |  |  |  |
| `directionid` | character varying(255) | SI |  |  |  |
| `blockid` | character varying(255) | SI |  |  |  |
| `wheelchairaccessible` | integer | SI |  |  |  |

### `public.itinerarios` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `trip_id` | text | NO | SI |  |  |
| `franja_horaria_id` | integer | NO | SI | public.franja_horaria.id |  |
| `frecuencia_id` | integer | NO | SI | public.frecuencia_operacion.id |  |
| `tipo_dia_id` | integer | NO | SI | public.reportes_parametros.id |  |
| `id` | uuid | SI |  |  |  |

### `public.itinerarios_generados` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `diff_tiempo` | interval | SI |  |  |  |
| `id` | integer | NO | SI |  |  |
| `fecha` | date | SI |  |  |  |
| `tiempo` | time without time zone | SI |  |  |  |
| `hora` | double precision | SI |  |  |  |
| `semana` | integer | SI |  |  |  |
| `quincena` | integer | SI |  |  |  |
| `mes` | integer | SI |  |  |  |
| `empresa` | character varying(255) | SI |  |  |  |
| `itinerario` | character varying(255) | SI |  |  |  |
| `linea` | character varying(255) | SI |  |  |  |
| `parada` | character varying(255) | SI |  |  |  |
| `tipo_via` | text | SI |  |  |  |
| `tipo_dia` | text | SI |  |  |  |
| `tipo_evento` | text | SI |  |  |  |
| `intervalo_min` | time without time zone | SI |  |  |  |
| `intervalo_max` | time without time zone | SI |  |  |  |
| `ejecucion` | timestamp with time zone | SI |  |  |  |

### `public.key_types` (TABLA, ~3 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `key_type_id` | bigint | NO | SI |  |  |
| `key_type_nombre` | text | NO |  |  |  |

### `public.keys` (TABLA, ~3 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `key_id` | bigint | NO | SI |  |  |
| `key_data` | text | NO |  |  |  |
| `key_created_at` | timestamp with time zone | NO |  |  |  |
| `key_updated_at` | timestamp with time zone | NO |  |  |  |
| `key_activa` | smallint | NO |  |  |  |
| `key_mid` | text | NO |  |  |  |
| `key_mspec` | text | NO |  |  |  |
| `key_mregion` | text | NO |  |  |  |
| `key_acceskeyid` | text | NO |  |  |  |
| `key_secretkeyid` | text | NO |  |  |  |
| `key_key_type` | bigint | SI |  | public.key_types.key_type_id |  |

### `public.module` (TABLA, ~10 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `module_id` | bigint | NO | SI |  |  |
| `module_nombre` | text | NO |  |  |  |
| `module_descripcion` | text | NO |  |  |  |
| `module_created_at` | timestamp with time zone | NO |  |  |  |
| `module_updated_at` | timestamp with time zone | NO |  |  |  |

### `public.mv_archivos_semana` (VISTA MATERIALIZADA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `dia` | date | SI |  |  |  |
| `tdp` | integer | SI |  |  |  |
| `epas` | integer | SI |  |  |  |

### `public.mv_ctransacciones_horas` (VISTA MATERIALIZADA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `evento` | text | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `idproducto` | character varying | SI |  |  |  |
| `tipoevento` | integer | SI |  |  |  |
| `hora` | integer | SI |  |  |  |

### `public.operation_message` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_entidad` | bigint | NO |  |  |  |
| `agency_id` | text | SI |  |  |  |
| `mean_id` | text | NO |  | public.transit_mediostransporte.id_chasis |  |
| `route_id` | text | SI |  |  |  |
| `itinerary_id` | text | SI |  |  |  |
| `driver_id` | text | SI |  |  |  |
| `stop_id` | text | SI |  |  |  |
| `operation_type` | integer | NO |  | public.operation_type.id |  |
| `accuracy` | double precision | NO |  |  |  |
| `latitude` | double precision | NO |  |  |  |
| `longitude` | double precision | NO |  |  |  |
| `altitude` | double precision | NO |  |  |  |
| `bearing` | double precision | NO |  |  |  |
| `speed` | double precision | NO |  |  |  |
| `datetime` | timestamp without time zone | NO |  |  |  |

### `public.operation_type` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | bigint | NO | SI |  |  |
| `name` | character varying | NO |  |  |  |

### `public.parada_tipo_via` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_parada_tipo_via` | uuid | NO | SI |  |  |
| `id_tipo_via` | text | NO |  | public.troncales_ramales.id |  |
| `id_parada` | character varying | NO |  |  |  |
| `punto_control` | boolean | SI |  |  |  |

### `public.parameter_types` (TABLA, ~5 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `parameter_type_id` | bigint | NO | SI |  |  |
| `parameter_type_name` | text | NO |  |  |  |
| `parameter_type_description` | text | NO |  |  |  |
| `parameter_created_at` | timestamp with time zone | NO |  |  |  |
| `parameter_updated_at` | timestamp with time zone | NO |  |  |  |

### `public.parameters` (TABLA, ~20 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `parameter_id` | bigint | NO | SI |  |  |
| `parameter_name` | text | NO |  |  |  |
| `parameter_description` | text | NO |  |  |  |
| `parameter_module_id` | bigint | NO |  | public.module.module_id |  |
| `parameter_created_at` | timestamp with time zone | NO |  |  |  |
| `parameter_updated_at` | timestamp with time zone | NO |  |  |  |
| `parameter_value` | text | SI |  |  |  |
| `parameter_parameter_type_id` | bigint | SI |  | public.parameter_types.parameter_type_id |  |
| `order` | bigint | NO |  |  |  |
| `editable` | boolean | NO |  |  |  |

### `public.permissions` (TABLA, ~17 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `permissions_id` | bigint | NO | SI |  |  |
| `permissions_nombre` | text | NO |  |  |  |
| `permissions_descripcion` | text | NO |  |  |  |
| `permissions_created_at` | timestamp with time zone | NO |  |  |  |
| `permissions_updated_at` | timestamp with time zone | NO |  |  |  |
| `permission_module_id` | bigint | NO |  | public.module.module_id |  |

### `public.pg_buffercache` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `bufferid` | integer | SI |  |  |  |
| `relfilenode` | oid | SI |  |  |  |
| `reltablespace` | oid | SI |  |  |  |
| `reldatabase` | oid | SI |  |  |  |
| `relforknumber` | smallint | SI |  |  |  |
| `relblocknumber` | bigint | SI |  |  |  |
| `isdirty` | boolean | SI |  |  |  |
| `usagecount` | smallint | SI |  |  |  |
| `pinning_backends` | integer | SI |  |  |  |

### `public.pg_stat_statements` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `userid` | oid | SI |  |  |  |
| `dbid` | oid | SI |  |  |  |
| `toplevel` | boolean | SI |  |  |  |
| `queryid` | bigint | SI |  |  |  |
| `query` | text | SI |  |  |  |
| `plans` | bigint | SI |  |  |  |
| `total_plan_time` | double precision | SI |  |  |  |
| `min_plan_time` | double precision | SI |  |  |  |
| `max_plan_time` | double precision | SI |  |  |  |
| `mean_plan_time` | double precision | SI |  |  |  |
| `stddev_plan_time` | double precision | SI |  |  |  |
| `calls` | bigint | SI |  |  |  |
| `total_exec_time` | double precision | SI |  |  |  |
| `min_exec_time` | double precision | SI |  |  |  |
| `max_exec_time` | double precision | SI |  |  |  |
| `mean_exec_time` | double precision | SI |  |  |  |
| `stddev_exec_time` | double precision | SI |  |  |  |
| `rows` | bigint | SI |  |  |  |
| `shared_blks_hit` | bigint | SI |  |  |  |
| `shared_blks_read` | bigint | SI |  |  |  |
| `shared_blks_dirtied` | bigint | SI |  |  |  |
| `shared_blks_written` | bigint | SI |  |  |  |
| `local_blks_hit` | bigint | SI |  |  |  |
| `local_blks_read` | bigint | SI |  |  |  |
| `local_blks_dirtied` | bigint | SI |  |  |  |
| `local_blks_written` | bigint | SI |  |  |  |
| `temp_blks_read` | bigint | SI |  |  |  |
| `temp_blks_written` | bigint | SI |  |  |  |
| `blk_read_time` | double precision | SI |  |  |  |
| `blk_write_time` | double precision | SI |  |  |  |
| `wal_records` | bigint | SI |  |  |  |
| `wal_fpi` | bigint | SI |  |  |  |
| `wal_bytes` | numeric | SI |  |  |  |

### `public.pg_stat_statements_info` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `dealloc` | bigint | SI |  |  |  |
| `stats_reset` | timestamp with time zone | SI |  |  |  |

### `public.recharging_networks` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |

### `public.recharging_points` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | character varying | NO | SI |  |  |
| `name` | text | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `status` | smallint | SI |  |  |  |
| `network_id` | bigint | SI |  |  |  |
| `entity_id` | character varying | SI |  |  |  |
| `city` | character varying | SI |  |  |  |
| `department` | character varying | SI |  |  |  |
| `country` | character varying | SI |  |  |  |
| `direction` | character varying | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |

### `public.recharging_points_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `recharging_point_id` | character varying | NO | SI |  |  |
| `rev` | integer | NO | SI | public.revinfo.rev |  |
| `revtype` | smallint | SI |  |  |  |
| `recharging_point_name` | text | SI |  |  |  |
| `recharging_point_latitude` | double precision | SI |  |  |  |
| `recharging_point_longitude` | double precision | SI |  |  |  |
| `recharging_point_created_at` | timestamp with time zone | SI |  |  |  |
| `recharging_point_updated_at` | timestamp with time zone | SI |  |  |  |
| `recharging_point_status` | smallint | SI |  |  |  |
| `recharging_point_network_id` | bigint | SI |  |  |  |
| `recharging_point_entity_id` | character varying | SI |  |  |  |
| `recharging_point_city` | character varying | SI |  |  |  |
| `recharging_point_department` | character varying | SI |  |  |  |
| `recharging_point_country` | character varying | SI |  |  |  |
| `recharging_point_direction` | character varying | SI |  |  |  |

### `public.reporte_itinerario_detalle` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `ref_reporte` | uuid | NO |  | public.reportes_listado.id |  |
| `v_actual` | time without time zone | NO |  |  |  |
| `v_esperado` | timerange | NO |  |  |  |
| `fechainicial` | date | NO |  |  |  |
| `fechafinal` | date | NO |  |  |  |
| `hora` | integer | NO |  |  |  |
| `tipo_dia` | text | NO |  |  |  |
| `operativa` | text | NO |  |  |  |
| `geografica` | text | NO |  |  |  |
| `cumplimiento` | boolean | NO |  |  |  |

### `public.reportes_detalle` (TABLA, ~3,270 filas, 312 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_reporte` | uuid | SI |  | public.reportes_listado.id |  |
| `id_parametro` | integer | SI |  | public.reportes_parametros.id |  |
| `valor` | text | SI |  |  |  |

### `public.reportes_listado` (TABLA, ~219 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `id_tipo_reporte` | integer | SI |  | public.reportes_tipos.id |  |
| `ubicacion` | text | SI |  |  |  |
| `estado` | text | SI |  |  |  |
| `fecha_solicitud` | timestamp without time zone | SI |  |  |  |

### `public.reportes_parametros` (TABLA, ~45 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `id_tipo_reporte` | integer | SI |  | public.reportes_tipos.id |  |
| `tipo` | integer | NO |  |  |  |
| `nombre` | text | NO |  |  |  |

### `public.reportes_tipos` (TABLA, ~3 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | text | NO |  |  |  |

### `public.revinfo` (TABLA, ~537,224 filas, 34 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `rev` | integer | NO | SI |  |  |
| `revtstmp` | bigint | SI |  |  |  |

### `public.roles` (TABLA, ~6 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `role_id` | bigint | NO | SI |  |  |
| `role_name` | text | NO |  |  |  |
| `role_description` | text | NO |  |  |  |
| `role_created_at` | timestamp with time zone | NO |  |  |  |
| `role_updated_at` | timestamp with time zone | NO |  |  |  |
| `role_main` | boolean | NO |  |  |  |

### `public.roles_permissions` (TABLA, ~32 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `roles_permissions_id` | bigint | NO | SI |  |  |
| `roles_permissions_role_id` | bigint | NO |  | public.roles.role_id |  |
| `roles_permissions_permission_id` | bigint | NO |  | public.permissions.permissions_id |  |
| `roles_permissions_created_at` | timestamp with time zone | NO |  |  |  |
| `roles_permissions_updated_at` | timestamp with time zone | NO |  |  |  |

### `public.sam_tipos` (TABLA, ~8 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `sam_tipo_id` | smallint | NO | SI |  |  |
| `sam_tipo` | text | NO |  |  |  |
| `sam_descripcion` | text | SI |  |  |  |

### `public.sams` (TABLA, ~10,993 filas, 1560 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `sam_serial` | character varying(14) | NO | SI |  |  |
| `created_at` | timestamp with time zone | NO |  |  |  |
| `updated_at` | timestamp with time zone | NO |  |  |  |
| `sam_activa` | smallint | NO |  |  |  |
| `sam_tipo` | smallint | NO |  | public.sam_tipos.sam_tipo_id |  |
| `sam_entidad` | bigint | SI |  |  |  |
| `sam_fecha_bloqueado` | timestamp without time zone | SI |  |  |  |
| `sam_bloqueado_razon` | text | SI |  |  |  |
| `sam_comentarios` | text | SI |  |  |  |
| `sam_entidad_codigo` | character varying(4) | NO |  | public.entidad.entidad_codigo |  |
| `modificated_by` | character varying | SI |  |  |  |

### `public.sams_archivos` (TABLA, ~4 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `sams_archivos_id` | uuid | NO | SI |  |  |
| `sams_archivos_nombre` | text | SI |  |  |  |
| `sams_archivos_numero_sams` | bigint | SI |  |  |  |
| `sams_archivos_created_at` | timestamp without time zone | SI |  |  |  |
| `sams_archivos_username` | text | SI |  |  |  |

### `public.sams_aud` (TABLA, ~1 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `sam_serial` | character varying(14) | NO |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `sam_activa` | smallint | NO |  |  |  |
| `sam_tipo` | smallint | NO |  | public.sam_tipos.sam_tipo_id |  |
| `sam_fecha_bloqueado` | timestamp without time zone | SI |  |  |  |
| `sam_bloqueado_razon` | text | SI |  |  |  |
| `sam_comentarios` | text | SI |  |  |  |
| `sam_entidad_codigo` | text | NO |  | public.entidad.entidad_codigo |  |
| `sam_entidad` | bigint | NO |  |  |  |

### `public.seguridad_ip` (TABLA, ~0 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `ip` | text | NO |  |  |  |
| `intento` | integer | SI |  |  |  |
| `fecha_bloqueo` | timestamp without time zone | SI |  |  |  |

### `public.semaforo` (TABLA, ~1 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `locked_ts` | timestamp with time zone | SI |  |  |  |
| `unlocked_ts` | timestamp with time zone | SI |  |  |  |
| `activo` | boolean | NO |  |  |  |

### `public.tipo_transporte` (TABLA, ~4 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |

### `public.token` (TABLA, ~6,481 filas, 1760 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `token_id` | bigint | NO | SI |  |  |
| `token_data` | text | SI |  |  |  |
| `token_username` | text | SI |  |  |  |
| `token_created_at` | timestamp with time zone | SI |  |  |  |
| `token_expires_at` | timestamp with time zone | SI |  |  |  |

### `public.transacciones` (VISTA, ~0 filas, 0 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | character varying | SI |  |  |  |
| `punteroproducto` | smallint | SI |  |  |  |
| `motivodevolución` | smallint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `consecutivosam` | character varying | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `iddispositivo` | character varying | SI |  |  |  |
| `idsam` | character varying | SI |  |  |  |
| `montoevento` | integer | SI |  |  |  |
| `tipoevento` | integer | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | SI |  |  |  |
| `númerotransbordos` | smallint | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `valorproducto` | integer | SI |  |  |  |
| `estadoproducto` | integer | SI |  |  |  |
| `númerosemanaaño` | integer | SI |  |  |  |
| `numeroviajeslunes` | integer | SI |  |  |  |
| `numeroviajesmartes` | integer | SI |  |  |  |
| `numeroviajesmiercoles` | integer | SI |  |  |  |
| `numeroviajesjueves` | integer | SI |  |  |  |
| `numeroviajesviernes` | integer | SI |  |  |  |
| `numeroviajessabado` | integer | SI |  |  |  |
| `numeroviajesdomingo` | integer | SI |  |  |  |
| `numeroviajesespecial` | integer | SI |  |  |  |
| `númeroactualusos` | integer | SI |  |  |  |
| `codigoaccion` | integer | SI |  |  |  |
| `numeroaccion` | integer | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |

### `public.transacciones_detalle` (TABLA, ~2,206,563 filas, 2999 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | uuid | NO | SI |  |  |
| `ubicacion` | text | NO |  |  |  |
| `estado` | text | NO |  |  |  |
| `detalle` | text | SI |  |  |  |
| `firma_hex` | text | SI |  |  |  |
| `xml_name` | text | SI |  |  |  |
| `created_at` | timestamp without time zone | NO |  |  |  |
| `updated_at` | timestamp without time zone | NO |  |  |  |

### `public.transaccioneshistoricas` (VISTA MATERIALIZADA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `fechaevento` | timestamp without time zone | SI |  |  |  |
| `númerosecuencial` | bigint | SI |  |  |  |
| `serialmediopago` | bigint | SI |  |  |  |
| `consecutivoaplicación` | bigint | SI |  |  |  |
| `estadoaplicación` | smallint | SI |  |  |  |
| `idproducto` | character varying | SI |  |  |  |
| `punteroproducto` | smallint | SI |  |  |  |
| `motivodevolución` | smallint | SI |  |  |  |
| `consecutivoevento` | bigint | SI |  |  |  |
| `consecutivosam` | character varying | SI |  |  |  |
| `fechahoraevento` | timestamp without time zone | SI |  |  |  |
| `identidad` | integer | SI |  |  |  |
| `iddispositivo` | character varying | SI |  |  |  |
| `idsam` | character varying | SI |  |  |  |
| `montoevento` | integer | SI |  |  |  |
| `tipoevento` | integer | SI |  |  |  |
| `configubicación` | smallint | SI |  |  |  |
| `idubicacion` | character varying | SI |  |  |  |
| `latitude` | double precision | SI |  |  |  |
| `longitude` | double precision | SI |  |  |  |
| `idrutaestacion` | character varying | SI |  |  |  |
| `limitetransbordo` | timestamp without time zone | SI |  |  |  |
| `númeropassbacks` | smallint | SI |  |  |  |
| `númerotransbordos` | smallint | SI |  |  |  |
| `tipotransporte` | smallint | SI |  |  |  |
| `valorproducto` | integer | SI |  |  |  |
| `estadoproducto` | integer | SI |  |  |  |
| `númerosemanaaño` | integer | SI |  |  |  |
| `numeroviajeslunes` | integer | SI |  |  |  |
| `numeroviajesmartes` | integer | SI |  |  |  |
| `numeroviajesmiercoles` | integer | SI |  |  |  |
| `numeroviajesjueves` | integer | SI |  |  |  |
| `numeroviajesviernes` | integer | SI |  |  |  |
| `numeroviajessabado` | integer | SI |  |  |  |
| `numeroviajesdomingo` | integer | SI |  |  |  |
| `numeroviajesespecial` | integer | SI |  |  |  |
| `númeroactualusos` | integer | SI |  |  |  |
| `codigoaccion` | integer | SI |  |  |  |
| `numeroaccion` | integer | SI |  |  |  |
| `entidad` | character varying(255) | SI |  |  |  |
| `usuario` | character varying(255) | SI |  |  |  |
| `recibidodate` | timestamp without time zone | SI |  |  |  |
| `xmlname` | character varying(255) | SI |  |  |  |

### `public.transit_agencies` (TABLA, ~1 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `agency_id` | text | NO | SI |  |  |
| `agency_name` | text | NO |  |  |  |
| `agency_url` | text | NO |  |  |  |
| `agency_timezone` | text | NO |  |  |  |
| `agency_phone` | text | NO |  |  |  |
| `agency_lang` | text | NO |  |  |  |

### `public.transit_mediostransporte` (TABLA, ~2,127 filas, 640 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_mediostransporte` | uuid | NO | SI |  |  |
| `id_operador` | integer | NO |  | public.transit_operator.transit_operator_id |  |
| `id_tipovehiculo` | integer | SI |  | public.transit_tipovehiculo.id_tipovehiculo |  |
| `id_sistematransporte` | integer | NO |  | public.gtfs_sistemasdetransporte.id_sistemasdetransporte |  |
| `active_mediostransporte` | integer | NO |  |  |  |
| `marca` | text | SI |  |  |  |
| `año` | integer | SI |  |  |  |
| `id_chasis` | text | NO |  |  |  |
| `rua` | text | SI |  |  |  |
| `pod_rtd` | text | SI |  |  |  |
| `documentos` | text | SI |  |  |  |
| `habilitacion_municipal` | date | SI |  |  |  |
| `seguro_pasajeros` | date | SI |  |  |  |
| `seguro_terceros` | date | SI |  |  |  |
| `tipo_carroceria` | text | SI |  |  |  |
| `tipo_bono` | integer | SI |  |  |  |
| `marca_carroceria` | integer | SI |  |  |  |
| `fecha_itv` | date | SI |  |  |  |
| `vencimiento_itv` | date | SI |  |  |  |
| `acceso_rampa` | boolean | SI |  |  |  |
| `zonal` | integer | SI |  |  |  |
| `codigo` | bigint | SI |  |  |  |
| `linea` | text | SI |  |  |  |
| `id_empresa_seguro_pasajeros` | integer | SI |  |  |  |
| `id_empresa_seguro_terceros` | integer | SI |  |  |  |
| `id_potencia_motor` | integer | SI |  |  |  |
| `id_taller_itv` | integer | SI |  |  |  |
| `fecha_inclusion` | date | SI |  |  |  |
| `numero_orden` | integer | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |

### `public.transit_mediostransporte_archivosadjuntos` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_archivoadjunto` | bigint | NO | SI |  |  |
| `id_mediotransporte` | text | NO |  |  |  |
| `filename` | text | NO |  |  |  |
| `filename_s3` | text | SI |  |  |  |

### `public.transit_mediostransporte_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `id_mediostransporte` | uuid | NO |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `id_operador` | integer | NO |  | public.transit_operator.transit_operator_id |  |
| `id_tipovehiculo` | integer | SI |  | public.transit_tipovehiculo.id_tipovehiculo |  |
| `id_sistematransporte` | integer | NO |  | public.gtfs_sistemasdetransporte.id_sistemasdetransporte |  |
| `active_mediostransporte` | integer | NO |  |  |  |
| `marca` | text | SI |  |  |  |
| `año` | integer | SI |  |  |  |
| `id_chasis` | text | NO |  |  |  |
| `RUA` | text | SI |  |  |  |
| `POD_RTD` | text | SI |  |  |  |
| `documentos` | text | SI |  |  |  |
| `habilitacion_municipal` | date | SI |  |  |  |
| `seguro_pasajeros` | date | SI |  |  |  |
| `seguro_terceros` | date | SI |  |  |  |
| `tipo_carroceria` | text | SI |  |  |  |
| `tipo_bono` | integer | SI |  |  |  |
| `marca_carroceria` | integer | SI |  |  |  |
| `fecha_itv` | date | SI |  |  |  |
| `vencimiento_itv` | date | SI |  |  |  |
| `acceso_rampa` | boolean | SI |  |  |  |
| `zonal` | integer | SI |  |  |  |
| `codigo` | bigint | SI |  |  |  |
| `linea` | text | SI |  |  |  |
| `id_empresa_seguro_pasajeros` | integer | SI |  |  |  |
| `id_empresa_seguro_terceros` | integer | SI |  |  |  |
| `id_potencia_motor` | integer | SI |  |  |  |
| `id_taller_itv` | integer | SI |  |  |  |
| `fecha_inclusion` | date | SI |  |  |  |
| `numero_orden` | integer | NO |  |  |  |

### `public.transit_mediostransporte_bodywork` (TABLA, ~52 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |

### `public.transit_mediostransporte_bodywork_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `id` | integer | SI |  |  |  |

### `public.transit_mediostransporte_brand` (TABLA, ~15 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |

### `public.transit_mediostransporte_brand_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `id` | integer | SI |  |  |  |

### `public.transit_mediostransporte_estado` (TABLA, ~2 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |

### `public.transit_mediostransporte_insurance` (TABLA, ~10 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |

### `public.transit_mediostransporte_insurance_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `id` | integer | NO |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |

### `public.transit_mediostransporte_power` (TABLA, ~101 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |

### `public.transit_mediostransporte_power_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `id` | integer | SI |  |  |  |

### `public.transit_mediostransporte_workshop_itv` (TABLA, ~7 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id` | integer | NO | SI |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |

### `public.transit_mediostransporte_workshop_itv_aud` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `id` | integer | NO |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |
| `nombre` | character varying | NO |  |  |  |
| `descripcion` | character varying | SI |  |  |  |

### `public.transit_operator` (TABLA, ~50 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `transit_operator_id` | bigint | NO | SI |  |  |
| `transit_operator_name` | character varying(255) | SI |  |  |  |
| `transit_operator_url` | character varying(255) | SI |  |  |  |
| `transit_operator_phone` | character varying(255) | SI |  |  |  |
| `transit_operator_email` | character varying(255) | SI |  |  |  |
| `created_at` | timestamp with time zone | NO |  |  |  |
| `updated_at` | timestamp with time zone | NO |  |  |  |
| `transit_operator_status` | boolean | NO |  |  |  |
| `transit_operator_agency_id` | character varying(255) | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |

### `public.transit_operator_aud` (TABLA, ~1 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `transit_operator_id` | integer | NO |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `modificated_by` | character varying | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | timestamp with time zone | SI |  |  |  |
| `transit_operator_name` | character varying(255) | SI |  |  |  |
| `transit_operator_url` | character varying(255) | SI |  |  |  |
| `transit_operator_phone` | character varying(255) | SI |  |  |  |
| `transit_operator_email` | character varying(255) | SI |  |  |  |
| `transit_operator_status` | boolean | NO |  |  |  |
| `transit_operator_agency_id` | character varying(255) | SI |  |  |  |

### `public.transit_routes` (TABLA, ~251 filas, 48 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `route_id` | text | NO | SI |  |  |
| `agency_id` | text | NO |  | public.transit_agencies.agency_id |  |
| `route_short_name` | text | NO |  |  |  |
| `route_long_name` | text | NO |  |  |  |
| `route_desc` | text | SI |  |  |  |
| `route_type` | bigint | NO |  |  |  |
| `route_url` | text | SI |  |  |  |
| `route_color` | text | SI |  |  |  |
| `route_text_color` | text | SI |  |  |  |

### `public.transit_shapes` (TABLA, ~1,591,345 filas, 150 MB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `shape_id` | text | NO |  |  |  |
| `shape_pt_lat` | double precision | NO |  |  |  |
| `shape_pt_lon` | double precision | NO |  |  |  |
| `shape_pt_sequence` | bigint | NO |  |  |  |
| `shape_dist_traveled` | double precision | NO |  |  |  |
| `surrogate_id` | integer | NO | SI |  |  |

### `public.transit_stops` (TABLA, ~16,510 filas, 1960 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `stop_id` | text | NO | SI |  |  |
| `stop_code` | text | NO |  |  |  |
| `stop_name` | text | NO |  |  |  |
| `stop_desc` | text | SI |  |  |  |
| `stop_lat` | double precision | NO |  |  |  |
| `stop_lon` | double precision | NO |  |  |  |
| `zone_id` | integer | SI |  |  |  |
| `stop_url` | text | SI |  |  |  |

### `public.transit_tipovehiculo` (TABLA, ~2 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_tipovehiculo` | bigint | NO | SI |  |  |
| `nombre_tipovehiculo` | text | NO |  |  |  |
| `descripcion_tipovehiculo` | text | SI |  |  |  |
| `id_gtfs_sistemadetransporte` | integer | NO |  | public.gtfs_sistemasdetransporte.id_sistemasdetransporte |  |

### `public.transit_trips` (TABLA, ~46,456 filas, 5672 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `route_id` | text | NO |  | public.transit_routes.route_id |  |
| `service_id` | text | NO |  |  |  |
| `trip_id` | text | NO | SI |  |  |
| `trip_headsign` | text | SI |  |  |  |
| `direction_id` | bigint | SI |  |  |  |
| `block_id` | text | SI |  |  |  |
| `shape_id` | text | SI |  |  |  |

### `public.troncales_ramales` (TABLA, ~0 filas, 16 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `name` | text | NO |  |  |  |
| `description` | text | NO |  |  |  |
| `type` | text | NO |  |  |  |
| `id` | text | NO | SI |  |  |

### `public.usuarios` (TABLA, ~29 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `usuario_id` | bigint | NO | SI |  |  |
| `usuario_nombre` | text | SI |  |  |  |
| `usuario_username` | text | NO |  |  |  |
| `usuario_password` | text | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | time with time zone | SI |  |  |  |
| `usuario_activo` | smallint | NO |  |  |  |
| `usuario_entidad` | character varying(4) | SI |  | public.entidad.entidad_codigo |  |
| `usuario_salt` | text | SI |  |  |  |
| `usuario_email` | text | SI |  |  |  |
| `usuario_telefono` | text | SI |  |  |  |
| `usuario_fecha_nacimiento` | date | SI |  |  |  |
| `usuario_link_activacion` | text | SI |  |  |  |
| `usuario_fecha_expiracion_link` | timestamp without time zone | SI |  |  |  |
| `usuario_main` | boolean | NO |  |  |  |
| `usuario_apellido` | text | NO |  |  |  |
| `modificated_by` | text | SI |  |  | Este es el identificador de modificación para usuarios |
| `contador_bloqueo` | integer | SI |  |  | Este es el contador de bloque para el usuarios |
| `bloqueado` | boolean | SI |  |  | Este es el estado bloqueado para el usuarios |

### `public.usuarios_aud` (TABLA, ~133 filas, 64 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `id_aud` | uuid | NO | SI |  |  |
| `usuario_id` | bigint | SI |  |  |  |
| `rev` | integer | NO |  |  |  |
| `revtype` | smallint | SI |  |  |  |
| `created_at` | timestamp with time zone | SI |  |  |  |
| `updated_at` | time with time zone | SI |  |  |  |
| `modificated_by` | text | SI |  |  |  |
| `usuario_nombre` | text | SI |  |  |  |
| `usuario_username` | text | NO |  |  |  |
| `usuario_password` | text | SI |  |  |  |
| `usuario_activo` | smallint | NO |  |  |  |
| `usuario_entidad` | character varying(4) | SI |  |  |  |
| `usuario_salt` | text | SI |  |  |  |
| `usuario_email` | text | SI |  |  |  |
| `usuario_telefono` | text | SI |  |  |  |
| `usuario_fecha_nacimiento` | date | SI |  |  |  |
| `usuario_link_activacion` | text | SI |  |  |  |
| `usuario_fecha_expiracion_link` | timestamp without time zone | SI |  |  |  |
| `usuario_main` | boolean | NO |  |  |  |
| `usuario_apellido` | text | NO |  |  |  |

### `public.usuarios_permissions` (TABLA, ~0 filas, 8192 bytes)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `usuarios_permissions_id` | bigint | NO | SI |  |  |
| `usuarios_permissions_usuario_id` | bigint | NO |  | public.usuarios.usuario_id |  |
| `usuarios_permissions_permission_id_id` | bigint | NO |  | public.permissions.permissions_id |  |
| `usuarios_permissions_created_at` | timestamp with time zone | NO |  |  |  |
| `usuarios_permissions_updated_at` | timestamp with time zone | NO |  |  |  |

### `public.usuarios_roles` (TABLA, ~41 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `usuarios_roles` | bigint | NO | SI |  |  |
| `usuarios_roles_usuario_id` | bigint | NO |  | public.usuarios.usuario_id |  |
| `usuarios_roles_rol_id` | bigint | NO |  | public.roles.role_id |  |
| `usuarios_roles_created_at` | timestamp with time zone | NO |  |  |  |
| `usuarios_roles_updated_at` | timestamp with time zone | NO |  |  |  |

### `public.z_codigofalla` (TABLA, ~5 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `codigofalla_id` | bigint | NO | SI |  |  |
| `codigofalla_nombre` | text | SI |  |  |  |

### `public.z_estadoaplicacion` (TABLA, ~3 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `estadoaplicacion_id` | integer | NO | SI |  |  |
| `estadoaplicacion_name` | text | SI |  |  |  |

### `public.z_perfil` (TABLA, ~4 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `perfil_id` | bigint | NO | SI |  |  |
| `perfil_nombre` | text | SI |  |  |  |

### `public.z_tipoevento` (TABLA, ~26 filas, 32 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `tipoevento_id` | integer | NO | SI |  |  |
| `tipoevento_descripcion` | text | SI |  |  |  |

### `public.z_tipoproducto` (TABLA, ~3 filas, 24 kB)

| Columna | Tipo | Nulo | PK | FK → | Comentario |
|---|---|---|---|---|---|
| `tipoproducto_id` | bigint | NO | SI |  |  |
| `tipoproducto_idproducto` | character varying(4) | SI |  |  |  |
| `tipoproducto_nombre` | character varying(2) | SI |  |  |  |