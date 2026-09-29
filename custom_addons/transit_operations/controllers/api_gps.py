# -*- coding: utf-8 -*-
import json
import logging
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

        if not dispatch:
            return Response(
                json.dumps({'error': f'No hay despacho activo hoy para la unidad {vehicle.name}', 'code': 422}),
                status=422,
                content_type='application/json'
            )

        # Parsear fecha de evento
        if event_time_str:
            clean_time = event_time_str.replace('Z', '+00:00')
            try:
                event_dt = fields.Datetime.to_datetime(clean_time)
            except Exception:
                event_dt = fields.Datetime.now()
        else:
            event_dt = fields.Datetime.now()

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
                write_vals.update({
                    'actual_arrival': event_dt,
                    'final_odometer': odometer or dispatch.final_odometer,
                    'state': 'completed',
                    'current_geofence_status': 'En Terminal Destino (Finalizado)',
                })
                dispatch.write(write_vals)
                dispatch.action_complete()

                # Marcar parada destino
                dest_cp = dispatch.checkpoint_ids.filtered(lambda c: c.checkpoint_type == 'destination' or 'destino' in c.name.lower())
                if dest_cp:
                    dest_cp.write({'status': 'crossed', 'actual_time': event_dt})

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
