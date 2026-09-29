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
    route_ids = fields.Many2many(
        'transit.route',
        string='Rutas / Ramales a Programar',
        help='Dejar vacío para incluir todas las rutas activas de la empresa.'
    )
    assignment_mode = fields.Selection([
        ('unassigned', 'Planificar servicios sin unidad (Asignación posterior por Tráfico)'),
        ('auto_assign', 'Auto-asignar unidades rotativamente de la flota activa'),
    ], string='Modo de Asignación de Flota', default='unassigned', required=True)

    def action_generate_schedule(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise ValidationError("La Fecha Fin no puede ser anterior a la Fecha Inicio.")

        # Obtener rutas
        routes = self.route_ids or self.env['transit.route'].search([('active', '=', True)])
        if not routes:
            raise UserError("No se encontraron rutas activas para generar la programación.")

        # Obtener vehículos activos si es auto_assign
        vehicles = []
        if self.assignment_mode == 'auto_assign':
            vehicles = self.env['fleet.vehicle'].search([('active', '=', True)], order='id asc')
            if not vehicles:
                raise UserError("No se encontraron buses activos en la flota para auto-asignar.")

        current_date = self.date_from
        total_created = 0
        vehicle_idx = 0
        dispatch_obj = self.env['transit.dispatch']
        created_dispatches = dispatch_obj.browse()

        while current_date <= self.date_to:
            w = current_date.weekday()
            allowed_days = ['all', str(w)]
            if w in (0, 1, 2, 3, 4):
                allowed_days.append('weekday')
            else:
                allowed_days.append('weekend')

            tt_domain = [
                ('route_id', 'in', routes.ids),
                ('active', '=', True),
                ('day_of_week', 'in', allowed_days)
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
                sched_dep = datetime.combine(current_date, time(hour=hours, minute=minutes))

                vals = {
                    'timetable_id': tt.id,
                    'date': current_date,
                    'scheduled_departure': sched_dep,
                    'state': 'draft',
                }

                if self.assignment_mode == 'auto_assign' and vehicles:
                    veh = vehicles[vehicle_idx % len(vehicles)]
                    vals['vehicle_id'] = veh.id
                    vehicle_idx += 1

                disp = dispatch_obj.create(vals)
                created_dispatches |= disp
                total_created += 1

            current_date += timedelta(days=1)

        if not total_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Programación Operativa',
                    'message': 'No se crearon nuevos despachos (los servicios para estas fechas y rutas ya se encontraban programados).',
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
