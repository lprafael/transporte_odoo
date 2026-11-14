# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

class TransitGpsApiController(http.Controller):

    def _authenticate_request(self):
        """Valida token en header Authorization o permite peticiones locales en dev"""
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header:
            return True
        token = auth_header.replace('Bearer ', '').strip()
        expected_token = request.env['ir.config_parameter'].sudo().get_param('transit.gps_api_token', 'GPS_SECRET_KEY_2026')
        return token == expected_token

    @http.route('/api/v1/transit/events', type='http', auth='none', methods=['POST'], csrf=False)
    def handle_gps_event(self):
        """
        Endpoint REST para recibir eventos consolidados desde Traccar, Geotab o Ingestor GPS.
        Payload esperado:
        {
            "license_plate": "ABC 123",
            "internal_number": "104",
            "event_type": "departure" | "checkpoint" | "arrival" | "speeding_alert" | "deviation_alert" | "telemetry_ping",
            "timestamp": "2026-09-24T10:15:30Z",
            "location": {
                "checkpoint_name": "Terminal Central",
                "latitude": -25.2867,
                "longitude": -57.6470
            },
            "telemetry": {
                "odometer_km": 154210.4,
                "speed_kmh": 74.5,
                "deviation_meters": 320.0
            }
        }
        """
        if not self._authenticate_request():
            return Response(
                json.dumps({'error': 'Unauthorized', 'code': 401}),
                status=401,
                content_type='application/json'
            )

        try:
            payload = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            return Response(
                json.dumps({'error': 'Invalid JSON format', 'code': 400}),
                status=400,
                content_type='application/json'
            )

        license_plate = payload.get('license_plate', '').strip()
        internal_number = payload.get('internal_number', '').strip()
        event_type = payload.get('event_type')
        event_time_str = payload.get('timestamp')
        telemetry = payload.get('telemetry', {})
        odometer = telemetry.get('odometer_km')
        speed_kmh = telemetry.get('speed_kmh', 0.0)
        deviation_meters = telemetry.get('deviation_meters', 0.0)
        location = payload.get('location', {})
        checkpoint_name = location.get('checkpoint_name', 'Punto Control GPS')
        latitude = location.get('latitude')
        longitude = location.get('longitude')

        # Buscar el bus por placa o número de interno
        vehicle_domain = []
        if license_plate:
            vehicle_domain.append(('license_plate', '=ilike', license_plate))
        if internal_number:
            vehicle_domain.append(('bus_internal_number', '=', internal_number))

        if not vehicle_domain:
            return Response(
                json.dumps({'error': 'Se requiere license_plate o internal_number', 'code': 400}),
                status=400,
                content_type='application/json'
            )

        # Entorno con usuario superuser para auth='none'
        import odoo
        env = request.env(user=odoo.SUPERUSER_ID)

        domain = ['|'] * (len(vehicle_domain) - 1) + vehicle_domain if len(vehicle_domain) > 1 else vehicle_domain
        vehicle = env['fleet.vehicle'].search(domain, limit=1)

        if not vehicle:
            return Response(
                json.dumps({'error': f'Vehículo ({license_plate or internal_number}) no encontrado', 'code': 404}),
                status=404,
                content_type='application/json'
            )

        # Buscar el despacho activo para la unidad en curso
        dispatch = env['transit.dispatch'].search([
            ('vehicle_id', '=', vehicle.id),
            ('state', 'in', ['draft', 'inspected', 'dispatched', 'in_transit'])
        ], order='scheduled_departure asc', limit=1)

        # Parsear fecha de evento
        if event_time_str:
            clean_time = event_time_str.replace('Z', '+00:00')
            try:
                event_dt = fields.Datetime.to_datetime(clean_time)
            except Exception:
                event_dt = fields.Datetime.now()
        else:
            event_dt = fields.Datetime.now()

        if not dispatch:
            # Autodetección automática de servicio desde gps_broker / telemetría en vivo
            route = None
            route_code = payload.get('route_code') or payload.get('route_id') or payload.get('service_code')
            if route_code:
                # 1. Buscar directamente por código de ruta o ramal
                route = env['transit.route'].search([('code', '=ilike', str(route_code).strip())], limit=1)
                # 2. Buscar por servicio operativo (ej. E1, E2, E3, B1)
                if not route:
                    service = env['transit.service'].search([('code', '=ilike', str(route_code).strip())], limit=1)
                    if service and service.route_ids:
                        route = service.route_ids[0]

            if not route or not route.exists():
                route_id_val = payload.get('route_id')
                if route_id_val and str(route_id_val).isdigit():
                    route = env['transit.route'].browse(int(route_id_val))

            if not route or not route.exists():
                # Asignar la primera ruta activa asociada a la empresa permisionaria
                route = env['transit.route'].search([('active', '=', True)], limit=1)

            if route:
                event_date = event_dt.date() if hasattr(event_dt, 'date') else fields.Date.context_today(env['transit.dispatch'])
                # Buscar horarios programados para la ruta o servicio
                timetables = env['transit.timetable'].search([
                    '|',
                    ('route_id', '=', route.id),
                    ('service_id', '=', route.service_id.id if route.service_id else False)
                ])

                # Evaluar proximidad con horarios programados (tolerancia ±25 min)
                matched_timetable = False
                matched_scheduled_dt = False
                is_reinforce = True
                if timetables:
                    ev_hour_float = event_dt.hour + (event_dt.minute / 60.0) + (event_dt.second / 3600.0)
                    best_diff = 999.0
                    best_tt = None
                    for tt in timetables:
                        diff_min = abs(tt.departure_time_float - ev_hour_float) * 60.0
                        if diff_min < best_diff:
                            best_diff = diff_min
                            best_tt = tt
                    if best_tt and best_diff <= 25.0:
                        matched_timetable = best_tt
                        sched_h = int(best_tt.departure_time_float)
                        sched_m = int(round((best_tt.departure_time_float - sched_h) * 60.0))
                        import datetime as dt_module
                        matched_scheduled_dt = dt_module.datetime.combine(
                            event_date,
                            dt_module.time(sched_h % 24, sched_m % 60)
                        )
                        is_reinforce = False

                dispatch = env['transit.dispatch'].create({
                    'vehicle_id': vehicle.id,
                    'route_id': route.id,
                    'date': event_date,
                    'timetable_id': matched_timetable.id if matched_timetable else False,
                    'scheduled_departure': matched_scheduled_dt or event_dt,
                    'is_reinforcement': is_reinforce,
                    'state': 'in_transit',
                    'actual_departure': event_dt,
                    'initial_odometer': odometer or 0.0,
                    'last_latitude': latitude or 0.0,
                    'last_longitude': longitude or 0.0,
                    'current_geofence_status': f'Autodetectado en vivo ({checkpoint_name or "Cabecera"})',
                })
                dispatch._compute_performance()
                dispatch._compute_clasificacion_operativa()
                clasif_str = "Según Operativa (Oficial)" if dispatch.segun_operativa else "Fuera de Operativa (Refuerzo / Desfasado)"
                dispatch.message_post(
                    body=f"🤖 <strong>Despacho Autodetectado por Telemetría:</strong> Salida registrada automáticamente por <code>gps_broker</code> para la unidad {vehicle.name} en {checkpoint_name}. Clasificación: <b>{clasif_str}</b>."
                )
                _logger.info("Despacho autodetectado y creado en Odoo: ID %d para vehículo %s (%s)", dispatch.id, vehicle.name, clasif_str)
            else:
                return Response(
                    json.dumps({'error': f'No hay despacho activo hoy ni ruta configurada para la unidad {vehicle.name}', 'code': 422}),
                    status=422,
                    content_type='application/json'
                )

        # Procesar según el evento operativo
        try:
            write_vals = {}
            if latitude is not None and longitude is not None:
                write_vals['last_latitude'] = latitude
                write_vals['last_longitude'] = longitude
            if speed_kmh:
                write_vals['last_speed_kmh'] = speed_kmh
            write_vals['last_gps_time'] = event_dt

            if event_type == 'departure':
                write_vals.update({
                    'actual_departure': event_dt,
                    'initial_odometer': odometer or dispatch.initial_odometer,
                    'state': 'in_transit',
                    'current_geofence_status': 'En Ruta (Salida Registrada)',
                })
                dispatch.write(write_vals)
                dispatch._compute_performance()
                dispatch._compute_clasificacion_operativa()

                # Marcar parada de cabecera como cruzada
                origin_cp = dispatch.checkpoint_ids.filtered(lambda c: c.checkpoint_type == 'origin' or 'cabecera' in c.name.lower())
                if origin_cp:
                    origin_cp.write({'status': 'crossed', 'actual_time': event_dt})

            elif event_type == 'checkpoint':
                write_vals['current_geofence_status'] = f'En Parada: {checkpoint_name}'
                dispatch.write(write_vals)

                # Buscar checkpoint existente o crear uno nuevo
                matched_cp = dispatch.checkpoint_ids.filtered(lambda c: c.name.strip().lower() == checkpoint_name.strip().lower())
                if matched_cp:
                    matched_cp.write({
                        'actual_time': event_dt,
                        'status': 'crossed',
                    })
                else:
                    env['transit.dispatch.checkpoint'].create({
                        'dispatch_id': dispatch.id,
                        'name': checkpoint_name,
                        'actual_time': event_dt,
                        'latitude': latitude or 0.0,
                        'longitude': longitude or 0.0,
                        'status': 'crossed',
                    })

            elif event_type == 'arrival':
                progress_pct = float(payload.get('progress_percent') or 100.0)
                is_incomplete = progress_pct < 80.0  # Regla 80% del VMT

                write_vals.update({
                    'actual_arrival': event_dt,
                    'final_odometer': odometer or dispatch.final_odometer,
                    'is_incomplete': is_incomplete,
                    'state': 'completed',
                    'current_geofence_status': 'En Terminal Destino (Finalizado)' if not is_incomplete else f'Incompleto ({progress_pct:.1f}% traza)',
                })
                dispatch.write(write_vals)
                if dispatch.final_odometer and dispatch.final_odometer > dispatch.initial_odometer:
                    env['fleet.vehicle.odometer'].create({
                        'vehicle_id': dispatch.vehicle_id.id,
                        'value': dispatch.final_odometer,
                        'date': dispatch.date,
                    })
                dispatch._compute_performance()
                dispatch._compute_clasificacion_operativa()

                # Marcar parada destino
                dest_cp = dispatch.checkpoint_ids.filtered(lambda c: c.checkpoint_type == 'destination' or 'destino' in c.name.lower())
                if dest_cp:
                    dest_cp.write({'status': 'crossed', 'actual_time': event_dt})

            elif event_type == 'deviation':
                dev_m = float(payload.get('deviation_meters') or 0.0)
                write_vals['current_geofence_status'] = f'Desviado ({round(dev_m)}m de traza oficial)'
                dispatch.write(write_vals)
                dispatch.message_post(
                    body=f"⚠️ <strong>Alerta de Desvío:</strong> Bus {vehicle.name} desviado de la traza oficial por {round(dev_m)} metros a las {event_dt.strftime('%H:%M:%S')}."
                )

            elif event_type == 'speeding_alert':
                write_vals['speed_alert'] = True
                dispatch.write(write_vals)
                dispatch.message_post(
                    body=f"🚨 <strong>ALERTA DE VELOCIDAD:</strong> Unidad {vehicle.name} reportó <strong>{speed_kmh} km/h</strong> en coordenadas ({latitude}, {longitude}).",
                    message_type='notification'
                )

            elif event_type == 'deviation_alert':
                write_vals['deviation_alert'] = True
                write_vals['last_deviation_meters'] = deviation_meters
                dispatch.write(write_vals)
                dispatch.message_post(
                    body=f"⚠️ <strong>DESVÍO DE ITINERARIO:</strong> Unidad {vehicle.name} desviada a <strong>{round(deviation_meters)} metros</strong> de la traza oficial.",
                    message_type='notification'
                )

            elif event_type == 'telemetry_ping':
                # Actualización de posición en vivo
                write_vals['current_geofence_status'] = payload.get('geofence_status', dispatch.current_geofence_status)
                dispatch.write(write_vals)

            else:
                return Response(
                    json.dumps({'error': f'Tipo de evento desconocido: {event_type}', 'code': 400}),
                    status=400,
                    content_type='application/json'
                )

        except Exception as e:
            _logger.exception("Error procesando evento GPS en Odoo: %s", str(e))
            return Response(
                json.dumps({'error': str(e), 'code': 500}),
                status=500,
                content_type='application/json'
            )

        return Response(
            json.dumps({
                'status': 'success',
                'dispatch_id': dispatch.id,
                'dispatch_name': dispatch.name,
                'vehicle': vehicle.name,
                'state': dispatch.state,
                'compliance_status': dispatch.compliance_status,
                'delay_minutes': dispatch.departure_delay_minutes,
                'current_geofence_status': dispatch.current_geofence_status
            }),
            status=200,
            content_type='application/json'
        )

    @http.route('/api/v1/transit/active_routes_geofences', type='http', auth='none', methods=['GET'], csrf=False)
    def get_active_routes_geofences(self):
        """
        Endpoint para que el broker o ingestor GPS sincronice las rutas y geocercas activas.
        """
        routes = request.env['transit.route'].sudo().search([('active', '=', True)])
        data = []
        for r in routes:
            checkpoints = []
            for cp in r.checkpoint_ids:
                checkpoints.append({
                    'id': cp.id,
                    'sequence': cp.sequence,
                    'name': cp.name,
                    'type': cp.checkpoint_type,
                    'latitude': cp.latitude,
                    'longitude': cp.longitude,
                    'radius_meters': cp.radius_meters,
                    'offset_minutes': cp.offset_minutes
                })
            data.append({
                'id': r.id,
                'name': r.name,
                'code': r.code,
                'direction': r.direction,
                'origin': {
                    'name': r.origin,
                    'latitude': r.origin_latitude,
                    'longitude': r.origin_longitude,
                    'radius_meters': r.origin_radius_meters
                },
                'destination': {
                    'name': r.destination,
                    'latitude': r.destination_latitude,
                    'longitude': r.destination_longitude,
                    'radius_meters': r.destination_radius_meters
                },
                'checkpoints': checkpoints
            })

        return Response(
            json.dumps({'status': 'success', 'count': len(data), 'routes': data}),
            status=200,
            content_type='application/json'
        )

    def _get_broker_base_url(self):
        """Resuelve la URL interna del microservicio GPS Broker.
        Orden de prioridad:
        1. Parámetro de sistema 'transit.gps_broker_internal_url' si está definido.
        2. Hostnames internos conocidos de Docker ('http://gps_broker:8088', 'http://odoo_transporte_gps_broker:8088')
        3. Host local de desarrollo 'http://127.0.0.1:8088' o 'http://host.docker.internal:8088'
        """
        param = request.env['ir.config_parameter'].sudo().get_param('transit.gps_broker_internal_url')
        if param and param.strip():
            return param.strip().rstrip('/')

        # Detección dinámica de conectividad interna con timeout ultra bajo
        candidates = [
            'http://gps_broker:8088',
            'http://odoo_transporte_gps_broker:8088',
            'http://127.0.0.1:8088',
            'http://host.docker.internal:8088',
        ]
        for candidate in candidates:
            try:
                r = requests.get(f"{candidate}/health", timeout=0.5)
                if r.status_code == 200:
                    return candidate
            except Exception:
                continue

        return 'http://gps_broker:8088'

    def _proxy_to_broker(self, path):
        """Reenvía peticiones HTTP internamente al microservicio GPS Broker y retorna la respuesta.
        Permite acceder a los tableros y sus APIs a través del puerto HTTPS estándar (443)
        sin requerir abrir el puerto 8088 en el firewall externo.
        """
        broker_base = self._get_broker_base_url()
        target_url = f"{broker_base}{path}"
        query_string = request.httprequest.query_string.decode('utf-8')
        if query_string:
            target_url += f"?{query_string}"

        forward_headers = {}
        for h in ['User-Agent', 'Accept', 'Accept-Language', 'Content-Type', 'Authorization']:
            val = request.httprequest.headers.get(h)
            if val:
                forward_headers[h] = val

        # Forward session cookies (incluyendo session_id de Odoo para Single Sign-On transparente)
        req_cookies = dict(request.httprequest.cookies)
        if getattr(request, 'session', None) and getattr(request.session, 'sid', None):
            req_cookies['session_id'] = request.session.sid

        data = request.httprequest.get_data() if request.httprequest.method in ['POST', 'PUT', 'PATCH'] else None

        try:
            resp = requests.request(
                method=request.httprequest.method,
                url=target_url,
                headers=forward_headers,
                cookies=req_cookies,
                data=data,
                timeout=15,
                allow_redirects=False,
            )

            # Si el broker intenta redirigir a un login separado, redirigir a /web/login de Odoo
            if resp.status_code in (301, 302, 303, 307, 308) and 'Location' in resp.headers:
                loc = resp.headers['Location']
                if loc.startswith('/login'):
                    return request.redirect(f'/web/login?redirect={path}', local=True)
                return request.redirect(loc, local=True)

            out_headers = {}
            for h in ['Content-Type', 'Cache-Control', 'ETag', 'Last-Modified']:
                if h in resp.headers:
                    out_headers[h] = resp.headers[h]

            return Response(resp.content, status=resp.status_code, headers=out_headers)

        except Exception as e:
            _logger.exception("Error proxying to GPS broker at %s: %s", target_url, e)
            return Response(
                f"<html><head><title>GPS Broker No Disponible</title></head><body style='font-family:sans-serif;padding:40px;background:#0f172a;color:#f8fafc;'>"
                f"<h2>El servicio GPS Broker interno no está respondiendo en {broker_base}.</h2>"
                f"<p style='color:#94a3b8;'>Error de comunicación interna: {str(e)}</p>"
                f"<p><a href='/web' style='color:#38bdf8;'>← Volver a Odoo ERP</a></p>"
                f"</body></html>",
                status=502,
                content_type='text/html; charset=utf-8'
            )

    @http.route([
        '/headway',
        '/map',
        '/compliance',
        '/transit/live/<string:target>',
        '/transit/redirect/<string:target>',
    ], type='http', auth='user', methods=['GET'])
    def proxy_broker_view(self, target=None, **kwargs):
        """Muestra los tableros en vivo (Headway, Radar GPS, Cumplimiento) a través del puerto estándar HTTPS."""
        public_url = (request.env['ir.config_parameter'].sudo().get_param('transit.gps_broker_public_url') or '').strip().rstrip('/')
        if public_url:
            resolved_target = target or request.httprequest.path.strip('/')
            query = request.httprequest.query_string.decode('utf-8')
            url = f"{public_url}/{resolved_target}"
            if query:
                url += f"?{query}"
            return request.redirect(url, local=False)

        path = request.httprequest.path
        if target and path.startswith('/transit/'):
            path = f"/{target}"
        return self._proxy_to_broker(path)

    @http.route([
        '/api/v1/live',
        '/api/v1/headway/<path:subpath>',
        '/api/v1/compliance/<path:subpath>',
        '/api/v1/shapes/<path:subpath>',
        '/api/v1/waze/<path:subpath>',
        '/api/v1/bunching/<path:subpath>',
        '/api/v1/eta/<path:subpath>',
        '/parada/<path:subpath>',
    ], type='http', auth='public', csrf=False, methods=['GET', 'POST', 'OPTIONS'])
    def proxy_broker_api(self, subpath=None, **kwargs):
        """Proxy transparente para las llamadas API del frontend de los tableros en tiempo real."""
        return self._proxy_to_broker(request.httprequest.path)

