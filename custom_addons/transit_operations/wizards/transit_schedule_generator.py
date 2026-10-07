# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class TransitScheduleGenerator(models.TransientModel):
    _name = 'transit.schedule.generator'
    _description = 'Asistente de Generación de Programación Operativa'

    date_from = fields.Date(
        string='Fecha Inicio',
        required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=1)
    )
    date_to = fields.Date(
        string='Fecha Fin',
        required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=7)
    )
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Operadora (Filtro)',
        help='Opcional: Dejar vacío para incluir todas las operadoras.'
    )
    service_ids = fields.Many2many(
        'transit.service',
        string='Servicios a Programar',
        help='Dejar vacío para incluir todos los servicios activos.'
    )
    route_ids = fields.Many2many(
        'transit.route',
        string='Ramales Específicos',
        help='Dejar vacío para incluir todos los ramales de los servicios seleccionados.'
    )
    assignment_mode = fields.Selection([
        ('unassigned', 'Planificar servicios sin unidad (Asignación posterior por Tráfico)'),
        ('auto_assign', 'Auto-asignar unidades rotativamente de la flota activa asignada'),
    ], string='Modo de Asignación de Flota', default='unassigned', required=True)

    def action_generate_schedule(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise ValidationError("La Fecha Fin no puede ser anterior a la Fecha Inicio.")

        # Obtener rutas objetivo
        domain_routes = [('active', '=', True)]
        if self.concessionaire_id:
            domain_routes.append(('concessionaire_id', '=', self.concessionaire_id.id))
        if self.service_ids:
            domain_routes.append(('service_id', 'in', self.service_ids.ids))
        if self.route_ids:
            domain_routes.append(('id', 'in', self.route_ids.ids))

        routes = self.env['transit.route'].search(domain_routes)
        if not routes:
            raise UserError("No se encontraron rutas activas con los filtros seleccionados.")

        # Obtener vehículos activos si es auto_assign
        vehicles = []
        if self.assignment_mode == 'auto_assign':
            v_domain = [('active', '=', True)]
            if self.concessionaire_id:
                v_domain.append(('concessionaire_id', '=', self.concessionaire_id.id))
            if self.service_ids:
                v_domain.append(('service_id', 'in', self.service_ids.ids))
            vehicles = self.env['fleet.vehicle'].search(v_domain, order='bus_internal_number asc, id asc')
            if not vehicles:
                # Fallback general
                vehicles = self.env['fleet.vehicle'].search([('active', '=', True)], order='id asc')

        current_date = self.date_from
        total_created = 0
        vehicle_idx = 0
        dispatch_obj = self.env['transit.dispatch']
        holiday_obj = self.env['transit.holiday']

        while current_date <= self.date_to:
            day_info = holiday_obj.get_day_type_info(current_date)
            tipo_d = day_info['tipo_dia']  # '5', '6', '7'

            w = current_date.weekday()
            allowed_days = ['all', str(w)]
            if w in (0, 1, 2, 3, 4):
                allowed_days.append('weekday')
            else:
                allowed_days.append('weekend')

            # Buscar cuadros de marcha que coincidan por tipo_dia oficial O por day_of_week
            tt_domain = [
                ('route_id', 'in', routes.ids),
                ('active', '=', True),
                '|',
                ('tipo_dia', '=', tipo_d),
                '&', ('tipo_dia', '=', False), ('day_of_week', 'in', allowed_days)
            ]
            timetables = self.env['transit.timetable'].search(tt_domain, order='departure_time_float asc')

            for tt in timetables:
                # Evitar duplicados si ya existe un despacho programado para este horario y día
                existing = dispatch_obj.search_count([
                    ('timetable_id', '=', tt.id),
                    ('date', '=', current_date),
                    ('state', '!=', 'canceled')
                ])
                if existing:
                    continue

                hours = int(tt.departure_time_float)
                minutes = int(round((tt.departure_time_float - hours) * 60))
                if minutes >= 60:
                    hours += 1
                    minutes = 0
                sched_dep = datetime.combine(current_date, time(hour=min(hours, 23), minute=minutes))

                vals = {
                    'timetable_id': tt.id,
                    'route_id': tt.route_id.id,
                    'date': current_date,
                    'scheduled_departure': sched_dep,
                    'state': 'draft',
                    'is_reinforcement': False,
                }

                if self.assignment_mode == 'auto_assign' and vehicles:
                    veh = vehicles[vehicle_idx % len(vehicles)]
                    vals['vehicle_id'] = veh.id
                    vehicle_idx += 1

                disp = dispatch_obj.create(vals)
                total_created += 1

            current_date += timedelta(days=1)

        if not total_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Programación Operativa',
                    'message': 'No se crearon nuevos despachos (los servicios para estas fechas y rutas ya se encontraban generados).',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Retornar vista filtrada con los despachos del rango
        action = self.env['ir.actions.act_window']._for_xml_id('transit_operations.action_transit_dispatch')
        action['domain'] = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        action['context'] = {'search_default_group_date': 1}
        action['name'] = f"Programación Generada ({self.date_from.strftime('%d/%m/%Y')} al {self.date_to.strftime('%d/%m/%Y')}) - {total_created} Servicios"
        return action
