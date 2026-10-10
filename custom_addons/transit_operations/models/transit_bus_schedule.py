# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

def float_to_time_tuple(val):
    """Convierte horas decimales (ej. 5.5) a (horas, minutos). Maneja desbordamiento >24h."""
    total_min = int(round((val or 0.0) * 60))
    h = (total_min // 60) % 24
    m = total_min % 60
    return h, m

def float_to_hhmm(val):
    """Convierte 5.5 a '05:30'."""
    h, m = float_to_time_tuple(val)
    return f"{h:02d}:{m:02d}"

LAYOVER_MINIMUMS = {
    'none': 0,
    'regulation': 10,
    'cleaning': 15,
    'driver_rest': 20,
    'charging': 30,
    'maintenance': 30,
}

class TransitBusSchedule(models.Model):
    _name = 'transit.bus.schedule'
    _description = 'Hoja de Ruta y Encadenamiento Diario de Bus'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, vehicle_id asc, id desc'

    name = fields.Char(
        string='Código de Hoja de Ruta',
        required=True,
        copy=False,
        readonly=True,
        default='Nuevo',
        tracking=True
    )
    date = fields.Date(
        string='Fecha Operativa',
        default=fields.Date.context_today,
        required=True,
        index=True,
        tracking=True
    )
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Operadora',
        required=False,
        index=True,
        tracking=True,
        help='Empresa concesionaria que opera este turno.'
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Bus Titular',
        required=True,
        index=True,
        tracking=True,
        help='Vehículo titular asignado a ejecutar esta secuencia de itinerarios.'
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Conductor Principal',
        domain="[('is_driver', '=', True)]",
        tracking=True,
        help='Conductor asignado por defecto para todos los tramos de la jornada.'
    )
    service_id = fields.Many2one(
        'transit.service',
        string='Servicio Principal',
        help='Servicio o concesión predominante de este turno (ej. E1, E2, B1).'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado (Despachos Generados)'),
        ('in_progress', 'En Operación'),
        ('done', 'Finalizado'),
        ('canceled', 'Cancelado'),
    ], string='Estado', default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'transit.bus.schedule.line',
        'schedule_id',
        string='Secuencia de Tramos e Itinerarios',
        copy=True
    )

    # Métricas y Resumen de la Jornada
    total_legs = fields.Integer(
        string='Total de Tramos / Vueltas',
        compute='_compute_metrics',
        store=True
    )
    total_distance_km = fields.Float(
        string='Kilometraje Total (km)',
        compute='_compute_metrics',
        store=True
    )
    total_operating_hours = fields.Float(
        string='Horas de Servicio',
        compute='_compute_metrics',
        store=True,
        help='Tiempo neto estimado de conducción en el día.'
    )
    first_departure_str = fields.Char(
        string='Primera Salida',
        compute='_compute_metrics',
        store=True
    )
    last_arrival_str = fields.Char(
        string='Última Llegada',
        compute='_compute_metrics',
        store=True
    )
    dispatch_count = fields.Integer(
        string='Despachos Creados',
        compute='_compute_dispatch_count'
    )

    # Semáforo de Desempeño Operativo
    green_count = fields.Integer(string='A Tiempo (Verde)', compute='_compute_semaphore_counts', store=True)
    yellow_count = fields.Integer(string='Retrasos (Amarillo)', compute='_compute_semaphore_counts', store=True)
    red_count = fields.Integer(string='Cancelados / Faltantes (Rojo)', compute='_compute_semaphore_counts', store=True)
    blue_count = fields.Integer(string='Cubiertos con Reserva (Azul)', compute='_compute_semaphore_counts', store=True)

    # Alertas Técnicas
    has_layover_alerts = fields.Boolean(
        string='Alertas de Tiempo en Parada',
        compute='_compute_layover_alerts',
        store=True,
        help='Indica si algún tramo no cumple el tiempo mínimo de recarga, limpieza o mantenimiento'
    )
    layover_alerts_summary = fields.Char(
        string='Resumen Alertas Técnicas',
        compute='_compute_layover_alerts',
        store=True
    )

    notes = fields.Text(string='Observaciones de Tráfico')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('transit.bus.schedule') or 'Nuevo'
        return super().create(vals_list)

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            if self.vehicle_id.concessionaire_id:
                self.concessionaire_id = self.vehicle_id.concessionaire_id
            if self.vehicle_id.service_id:
                self.service_id = self.vehicle_id.service_id

    @api.depends('line_ids', 'line_ids.distance_km', 'line_ids.duration_minutes',
                 'line_ids.departure_time_str', 'line_ids.arrival_time_str')
    def _compute_metrics(self):
        for rec in self:
            legs = rec.line_ids.sorted('sequence')
            rec.total_legs = len(legs)
            rec.total_distance_km = sum(l.distance_km for l in legs)
            tot_min = sum(l.duration_minutes for l in legs)
            rec.total_operating_hours = round(tot_min / 60.0, 2)
            rec.first_departure_str = legs[0].departure_time_str if legs else '--:--'
            rec.last_arrival_str = legs[-1].arrival_time_str if legs else '--:--'

    def _compute_dispatch_count(self):
        dispatch_obj = self.env['transit.dispatch']
        for rec in self:
            rec.dispatch_count = dispatch_obj.search_count([('bus_schedule_id', '=', rec.id)])

    @api.depends('line_ids.semaphore_color')
    def _compute_semaphore_counts(self):
        for rec in self:
            rec.green_count = sum(1 for l in rec.line_ids if l.semaphore_color == 'green')
            rec.yellow_count = sum(1 for l in rec.line_ids if l.semaphore_color == 'yellow')
            rec.red_count = sum(1 for l in rec.line_ids if l.semaphore_color == 'red')
            rec.blue_count = sum(1 for l in rec.line_ids if l.semaphore_color == 'blue')

    @api.depends('line_ids.has_layover_alert', 'line_ids.layover_alert_msg')
    def _compute_layover_alerts(self):
        for rec in self:
            alerts = [l.layover_alert_msg for l in rec.line_ids if l.has_layover_alert and l.layover_alert_msg]
            rec.has_layover_alerts = bool(alerts)
            rec.layover_alerts_summary = f"{len(alerts)} tramos con tiempo insuficiente en parada/recarga" if alerts else "Tiempos de parada y recarga conformes"

    def action_confirm(self):
        """Confirma la hoja de ruta y genera o sincroniza todos los despachos."""
        for rec in self:
            if not rec.line_ids:
                raise UserError("Debe agregar al menos un tramo o itinerario antes de confirmar la hoja de ruta.")
            rec.action_generate_dispatches()
            rec.state = 'confirmed'
        return True

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_set_done(self):
        self.write({'state': 'done'})

    def action_generate_dispatches(self):
        """
        Genera o actualiza los despachos oficiales en transit.dispatch para cada tramo.
        Cada despacho queda sincronizado con el radar satelital, detector de pegonamiento
        y tableros de control de puntualidad.
        """
        self.ensure_one()
        dispatch_obj = self.env['transit.dispatch']
        created_count = 0

        for line in self.line_ids.sorted('sequence'):
            h_dep, m_dep = float_to_time_tuple(line.departure_time)
            dt_dep = datetime.combine(self.date, time(hour=h_dep, minute=m_dep))

            h_arr, m_arr = float_to_time_tuple(line.arrival_time)
            date_arr = self.date if line.arrival_time >= line.departure_time else (self.date + timedelta(days=1))
            dt_arr = datetime.combine(date_arr, time(hour=h_arr, minute=m_arr))

            # Determinar vehículo efectivo (titular o de reserva si fue sustituido)
            effective_vehicle = line.substituted_vehicle_id.id if line.is_reserve_substituted and line.substituted_vehicle_id else self.vehicle_id.id

            vals = {
                'route_id': line.route_id.id,
                'vehicle_id': effective_vehicle,
                'driver_id': line.driver_id.id if line.driver_id else (self.driver_id.id if self.driver_id else False),
                'concessionaire_id': self.concessionaire_id.id if self.concessionaire_id else (self.vehicle_id.concessionaire_id.id if self.vehicle_id.concessionaire_id else False),
                'date': self.date,
                'scheduled_departure': dt_dep,
                'scheduled_arrival': dt_arr,
                'bus_schedule_id': self.id,
                'bus_schedule_line_id': line.id,
                'is_reinforcement': line.is_reserve_substituted,
                'battery_soc_departure': line.battery_soc_departure,
                'battery_soc_arrival': line.battery_soc_arrival,
                'layover_type': line.layover_type,
                'layover_duration_minutes': line.rest_minutes,
                'layover_warning': line.layover_alert_msg or False,
                'substituted_vehicle_id': line.substituted_vehicle_id.id if line.is_reserve_substituted else False,
                'is_reserve_substituted': line.is_reserve_substituted,
            }

            if line.dispatch_id:
                line.dispatch_id.write(vals)
            else:
                vals['state'] = 'draft'
                new_disp = dispatch_obj.create(vals)
                line.dispatch_id = new_disp.id
                created_count += 1

            line.state = 'scheduled'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Despachos Generados',
                'message': f"Se sincronizaron con éxito los {len(self.line_ids)} tramos para el Bus {self.vehicle_id.name}.",
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_dispatches(self):
        self.ensure_one()
        return {
            'name': f'Despachos Operativos - {self.vehicle_id.name} ({self.date})',
            'type': 'ir.actions.act_window',
            'res_model': 'transit.dispatch',
            'view_mode': 'list,form,kanban,calendar',
            'domain': [('bus_schedule_id', '=', self.id)],
            'context': {
                'default_bus_schedule_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
                'default_date': self.date,
            }
        }

    def action_add_next_return_leg(self):
        """
        Agrega de forma inteligente el siguiente tramo encadenado:
        Calcula la hora de salida sugerida (llegada anterior + descanso)
        e infiere automáticamente la ruta de retorno (sentido inverso o complementario).
        """
        self.ensure_one()
        line_obj = self.env['transit.bus.schedule.line']
        lines = self.line_ids.sorted('sequence')

        if not lines:
            route = self.env['transit.route'].search([
                ('concessionaire_id', '=', self.concessionaire_id.id) if self.concessionaire_id else ('active', '=', True)
            ], limit=1)
            if not route:
                raise UserError("No hay rutas configuradas para la empresa seleccionada.")
            next_seq = 10
            next_leg = 1
            dep_time = 6.0
            route_id = route.id
            rest_m = 15
        else:
            prev = lines[-1]
            next_seq = prev.sequence + 10
            next_leg = len(lines) + 1
            rest_m = prev.rest_minutes or 15
            dep_time = prev.arrival_time + (rest_m / 60.0)

            # Buscar ruta inversa o complementaria en el mismo servicio / concesión
            prev_route = prev.route_id
            target_direction = 'vuelta' if prev_route.direction == 'ida' else 'ida'
            domain = [
                ('id', '!=', prev_route.id),
                ('active', '=', True),
            ]
            if prev_route.service_id:
                domain.append(('service_id', '=', prev_route.service_id.id))
            elif prev_route.concessionaire_id:
                domain.append(('concessionaire_id', '=', prev_route.concessionaire_id.id))

            candidate = self.env['transit.route'].search(domain + [('direction', '=', target_direction)], limit=1)
            if not candidate:
                candidate = self.env['transit.route'].search(domain, limit=1)
            route_id = candidate.id if candidate else prev_route.id

        new_line = line_obj.create({
            'schedule_id': self.id,
            'sequence': next_seq,
            'leg_number': next_leg,
            'route_id': route_id,
            'departure_time': dep_time,
            'rest_minutes': rest_m,
            'driver_id': self.driver_id.id if self.driver_id else False,
        })
        return True

    def action_open_chain_wizard(self):
        """Abre el asistente interactivo para encadenar ciclos de itinerarios completos en 1 clic."""
        self.ensure_one()
        return {
            'name': 'Asistente de Encadenamiento Rápido de Itinerarios',
            'type': 'ir.actions.act_window',
            'res_model': 'transit.bus.schedule.chain.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_schedule_id': self.id,
                'default_concessionaire_id': self.concessionaire_id.id,
            }
        }


class TransitBusScheduleLine(models.Model):
    _name = 'transit.bus.schedule.line'
    _description = 'Tramo / Leg de Hoja de Ruta'
    _order = 'sequence asc, id asc'

    schedule_id = fields.Many2one(
        'transit.bus.schedule',
        string='Hoja de Ruta Padre',
        required=True,
        ondelete='cascade',
        index=True
    )
    sequence = fields.Integer(string='Secuencia', default=10, index=True)
    leg_number = fields.Integer(string='Nº Tramo', default=1)

    route_id = fields.Many2one(
        'transit.route',
        string='Itinerario / Ruta',
        required=True,
        index=True
    )
    service_id = fields.Many2one(
        'transit.service',
        string='Servicio Especial',
        related='route_id.service_id',
        store=True
    )
    direction = fields.Selection(
        related='route_id.direction',
        string='Sentido',
        store=True
    )
    origin = fields.Char(related='route_id.origin', string='Origen')
    destination = fields.Char(related='route_id.destination', string='Destino')
    distance_km = fields.Float(related='route_id.distance_km', string='Distancia (km)', store=True)

    # Horarios decimales y texto
    departure_time = fields.Float(string='Hora Salida', required=True, default=6.0)
    departure_time_str = fields.Char(
        string='Salida (HH:MM)',
        compute='_compute_times_str',
        store=True
    )

    duration_minutes = fields.Integer(
        string='Duración (min)',
        default=60,
        required=True,
        help='Duración estimada del viaje para este itinerario.'
    )

    arrival_time = fields.Float(
        string='Hora Llegada',
        compute='_compute_arrival',
        store=True
    )
    arrival_time_str = fields.Char(
        string='Llegada (HH:MM)',
        compute='_compute_times_str',
        store=True
    )

    # =========================================================================
    # Tiempos de Parada Técnica, Recarga EV, Limpieza y Mantenimiento
    # =========================================================================
    layover_type = fields.Selection([
        ('none', 'Salida Inmediata (Sin parada técnica)'),
        ('regulation', 'Regulación / Espera en Cabecera (mín. 10m)'),
        ('cleaning', 'Limpieza y Aseo de Unidad (mín. 15m)'),
        ('driver_rest', 'Descanso / Relevo de Chofer (mín. 20m)'),
        ('charging', 'Recarga de Baterías EV (mín. 30m)'),
        ('maintenance', 'Inspección Mecánica / Taller (mín. 30m)'),
    ], string='Actividad en Parada / Cabecera', default='regulation', required=True,
       help='Actividad obligatoria a realizar en la cabecera antes de habilitar la salida del siguiente tramo.')

    rest_minutes = fields.Integer(
        string='Tiempo en Parada (min)',
        default=15,
        required=True,
        help='Minutos de permanencia en cabecera o parada antes de la siguiente salida.'
    )

    min_required_layover_minutes = fields.Integer(
        string='Tiempo Mínimo Requerido (min)',
        compute='_compute_layover_validation',
        store=True
    )

    has_layover_alert = fields.Boolean(
        string='Alerta de Tiempo Insuficiente',
        compute='_compute_layover_validation',
        store=True
    )

    layover_alert_msg = fields.Char(
        string='Detalle Alerta Parada',
        compute='_compute_layover_validation',
        store=True
    )

    suggested_next_departure_str = fields.Char(
        string='Próx. Salida Sugerida',
        compute='_compute_times_str',
        store=True
    )

    # =========================================================================
    # Gestión de Baterías EV (Planilla Oficial de Tránsito)
    # =========================================================================
    battery_soc_departure = fields.Float(
        string='% Batería Salida',
        default=90.0,
        help='Estado de Carga (SoC %) al momento de iniciar este tramo (ej. 91% = 0.91)'
    )
    battery_soc_arrival = fields.Float(
        string='% Batería Llegada',
        default=65.0,
        help='Estado de Carga (SoC %) estimado o real al completar el tramo'
    )
    battery_consumption_pct = fields.Float(
        string='Consumo Batería (%)',
        compute='_compute_battery_consumption',
        store=True,
        help='Diferencia porcentual de batería consumida en este tramo'
    )

    # =========================================================================
    # Buses de Reserva / Sustitución Técnica
    # =========================================================================
    is_reserve_substituted = fields.Boolean(
        string='Cubierto por Bus de Reserva',
        default=False,
        help='Indica si este tramo fue sustituido por una unidad de reserva técnica'
    )
    substituted_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Bus de Reserva Asignado',
        domain="[('is_reserve_unit', '=', True), ('reserve_status', '=', 'available')]",
        help='Unidad de reserva tomada de base para cubrir la salida'
    )

    # =========================================================================
    # Semáforo Operativo por GPS
    # =========================================================================
    semaphore_color = fields.Selection([
        ('green', 'Verde: A Tiempo (En Margen Correcto)'),
        ('yellow', 'Amarillo: Retraso / Adelanto Fuera de Tolerancia'),
        ('red', 'Rojo: Cancelado / Faltante'),
        ('blue', 'Azul: Cubierto con Bus de Reserva'),
        ('gray', 'Gris: Programado (En Espera)'),
    ], string='Semáforo Operativo GPS', compute='_compute_semaphore_status', store=True)

    driver_id = fields.Many2one(
        'res.partner',
        string='Chofer del Tramo',
        domain="[('is_driver', '=', True)]",
        help='Dejar vacío para heredar el chofer principal de la jornada.'
    )
    dispatch_id = fields.Many2one(
        'transit.dispatch',
        string='Despacho Diario Generado',
        readonly=True,
        ondelete='set null'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('scheduled', 'Programado'),
        ('in_progress', 'En Ruta'),
        ('completed', 'Completado'),
        ('canceled', 'Cancelado'),
    ], string='Estado', default='draft')
    notes = fields.Char(string='Nota')

    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id and self.route_id.standard_duration_minutes:
            self.duration_minutes = self.route_id.standard_duration_minutes

    @api.depends('departure_time', 'duration_minutes')
    def _compute_arrival(self):
        for rec in self:
            rec.arrival_time = (rec.departure_time or 0.0) + ((rec.duration_minutes or 0) / 60.0)

    @api.depends('departure_time', 'arrival_time', 'rest_minutes')
    def _compute_times_str(self):
        for rec in self:
            rec.departure_time_str = float_to_hhmm(rec.departure_time)
            rec.arrival_time_str = float_to_hhmm(rec.arrival_time)
            next_float = rec.arrival_time + ((rec.rest_minutes or 0) / 60.0)
            rec.suggested_next_departure_str = float_to_hhmm(next_float)

    @api.depends('layover_type', 'rest_minutes')
    def _compute_layover_validation(self):
        for rec in self:
            min_req = LAYOVER_MINIMUMS.get(rec.layover_type, 0)
            rec.min_required_layover_minutes = min_req
            if rec.layover_type != 'none' and rec.rest_minutes < min_req:
                rec.has_layover_alert = True
                type_label = dict(rec._fields['layover_type'].selection).get(rec.layover_type, rec.layover_type)
                rec.layover_alert_msg = f"⚠️ Tiempo insuficiente: '{type_label}' requiere mín. {min_req} min (programados {rec.rest_minutes} min)."
            else:
                rec.has_layover_alert = False
                rec.layover_alert_msg = False

    @api.depends('battery_soc_departure', 'battery_soc_arrival')
    def _compute_battery_consumption(self):
        for rec in self:
            if rec.battery_soc_departure and rec.battery_soc_arrival:
                rec.battery_consumption_pct = max(0.0, round(rec.battery_soc_departure - rec.battery_soc_arrival, 1))
            else:
                rec.battery_consumption_pct = 0.0

    @api.depends('state', 'dispatch_id.compliance_status', 'dispatch_id.state',
                 'is_reserve_substituted', 'dispatch_id.actual_departure')
    def _compute_semaphore_status(self):
        for rec in self:
            if rec.is_reserve_substituted:
                rec.semaphore_color = 'blue'
            elif rec.state == 'canceled' or (rec.dispatch_id and rec.dispatch_id.state == 'canceled'):
                rec.semaphore_color = 'red'
            elif rec.dispatch_id and rec.dispatch_id.compliance_status == 'on_time':
                rec.semaphore_color = 'green'
            elif rec.dispatch_id and rec.dispatch_id.compliance_status in ('delayed', 'early'):
                rec.semaphore_color = 'yellow'
            elif rec.dispatch_id and rec.dispatch_id.compliance_status == 'unperformed':
                rec.semaphore_color = 'red'
            elif rec.state in ('scheduled', 'draft'):
                rec.semaphore_color = 'gray'
            else:
                rec.semaphore_color = 'green'

    def action_assign_reserve_bus(self):
        """Abre el asistente para asignar un bus de reserva técnica a este tramo."""
        self.ensure_one()
        return {
            'name': f'Asignar Bus de Reserva - Tramo {self.leg_number} ({self.route_id.name})',
            'type': 'ir.actions.act_window',
            'res_model': 'transit.bus.schedule.reserve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_schedule_line_id': self.id,
                'default_concessionaire_id': self.schedule_id.concessionaire_id.id if self.schedule_id.concessionaire_id else False,
            }
        }


class TransitBusScheduleReserveWizard(models.TransientModel):
    _name = 'transit.bus.schedule.reserve.wizard'
    _description = 'Asistente de Asignación de Bus de Reserva'

    schedule_line_id = fields.Many2one(
        'transit.bus.schedule.line',
        string='Tramo de Hoja de Ruta',
        required=True
    )
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Operadora'
    )
    titular_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Bus Titular Afectado',
        related='schedule_line_id.schedule_id.vehicle_id',
        readonly=True
    )
    reason = fields.Selection([
        ('breakdown', 'Avería Mecánica / Eléctrica'),
        ('delay', 'Retraso Crítico en Tramo Anterior'),
        ('battery_low', 'Batería Insuficiente (SoC Bajo)'),
        ('cleaning', 'Unidad en Limpieza Profunda'),
        ('accident', 'Incidente Vial / Choque'),
    ], string='Motivo de la Sustitución', default='delay', required=True)

    reserve_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Bus de Reserva Disponible',
        required=True,
        domain="[('is_reserve_unit', '=', True), ('reserve_status', '=', 'available')]",
        help='Seleccione el colectivo de reserva listo en base para salir'
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Conductor de la Reserva',
        domain="[('is_driver', '=', True)]"
    )
    notes = fields.Char(string='Observación de Tráfico')

    def action_confirm_substitution(self):
        self.ensure_one()
        line = self.schedule_line_id
        line.write({
            'is_reserve_substituted': True,
            'substituted_vehicle_id': self.reserve_vehicle_id.id,
            'driver_id': self.driver_id.id if self.driver_id else line.driver_id.id,
            'notes': f"Sustituido por Bus de Reserva {self.reserve_vehicle_id.name}. Motivo: {self.reason}. {self.notes or ''}".strip(),
        })

        # Actualizar estado de la unidad de reserva
        self.reserve_vehicle_id.write({'reserve_status': 'active_substitute'})

        # Si el tramo ya tiene despacho oficial generado, sincronizarlo
        if line.dispatch_id:
            line.dispatch_id.write({
                'vehicle_id': self.reserve_vehicle_id.id,
                'is_reinforcement': True,
                'is_reserve_substituted': True,
                'substituted_vehicle_id': self.reserve_vehicle_id.id,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bus de Reserva Asignado',
                'message': f"El tramo {line.leg_number} ahora será cubierto por la unidad de reserva {self.reserve_vehicle_id.name}.",
                'type': 'info',
                'sticky': False,
            }
        }


class TransitBusScheduleChainWizard(models.TransientModel):
    _name = 'transit.bus.schedule.chain.wizard'
    _description = 'Asistente de Encadenamiento Rápido de Itinerarios'

    schedule_id = fields.Many2one(
        'transit.bus.schedule',
        string='Hoja de Ruta',
        required=True,
        ondelete='cascade'
    )
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Operadora',
        related='schedule_id.concessionaire_id'
    )
    route_1_id = fields.Many2one(
        'transit.route',
        string='Ruta 1 (Itinerario Inicial / Ida)',
        required=True,
        help='Primer itinerario del ciclo (ej. E1 Ida: San Lorenzo -> Asunción)'
    )
    route_2_id = fields.Many2one(
        'transit.route',
        string='Ruta 2 (Itinerario Retorno / Vuelta)',
        required=True,
        help='Itinerario de retorno o siguiente ramal (ej. E2 Vuelta: Asunción -> Capiatá)'
    )
    route_3_id = fields.Many2one(
        'transit.route',
        string='Ruta 3 (Opcional - Tercer Ramal / Triangular)',
        help='Opcional: Si el bus cubre un tercer ramal antes de reiniciar el ciclo (ej. E3)'
    )
    first_departure_time = fields.Float(
        string='Hora de Primera Salida',
        default=5.5,
        required=True,
        help='Hora inicial del primer viaje de la jornada (ej. 5.5 = 05:30)'
    )

    # Parada Técnica y Actividad en Cabecera
    default_layover_type = fields.Selection([
        ('regulation', 'Regulación / Espera en Cabecera (10-15m)'),
        ('charging', 'Recarga de Baterías EV (30-60m)'),
        ('cleaning', 'Limpieza y Aseo de la Unidad (15-20m)'),
        ('driver_rest', 'Descanso / Relevo de Conductor (20-30m)'),
    ], string='Actividad en Parada Técnica', default='regulation', required=True)

    rest_minutes = fields.Integer(
        string='Tiempo en Parada / Cabecera (min)',
        default=15,
        required=True,
        help='Tiempo de permanencia entre la llegada de un tramo y la salida del siguiente para descanso, recarga o limpieza.'
    )

    initial_battery_soc = fields.Float(
        string='% Batería Inicial (SoC Salida)',
        default=95.0,
        help='Estado de carga de la batería del bus al inicio del día (ej. 95% = 0.95)'
    )

    cycles_count = fields.Integer(
        string='Cantidad de Vueltas / Ciclos',
        default=4,
        required=True,
        help='Número de veces que se repetirá el ciclo completo de rutas a lo largo del día.'
    )
    clear_existing = fields.Boolean(
        string='Reemplazar tramos existentes',
        default=True,
        help='Si está marcado, borra los tramos actuales en borrador antes de generar el nuevo encadenamiento.'
    )

    @api.onchange('default_layover_type')
    def _onchange_layover_type(self):
        if self.default_layover_type:
            self.rest_minutes = LAYOVER_MINIMUMS.get(self.default_layover_type, 15)

    @api.onchange('concessionaire_id')
    def _onchange_concessionaire(self):
        if self.concessionaire_id:
            routes = self.env['transit.route'].search([('concessionaire_id', '=', self.concessionaire_id.id)])
            if len(routes) >= 2:
                self.route_1_id = routes[0].id
                self.route_2_id = routes[1].id

    def action_generate_chain(self):
        self.ensure_one()
        schedule = self.schedule_id

        if self.cycles_count <= 0:
            raise ValidationError("La cantidad de ciclos debe ser mayor a 0.")

        if self.clear_existing:
            schedule.line_ids.unlink()

        routes_sequence = [self.route_1_id, self.route_2_id]
        if self.route_3_id:
            routes_sequence.append(self.route_3_id)

        curr_time = self.first_departure_time
        curr_soc = self.initial_battery_soc
        line_obj = self.env['transit.bus.schedule.line']
        seq = 10
        leg_num = 1

        for cycle in range(self.cycles_count):
            for r in routes_sequence:
                dur = r.standard_duration_minutes or 60
                # Estimación de consumo por tramo (aprox 12-15% por vuelta si es EV)
                soc_dep = curr_soc
                dist = r.distance_km or 18.0
                consumed_soc = round((dist * 1.15 / 350.0) * 100, 1)  # consumo basado en kWh
                soc_arr = max(10.0, round(soc_dep - consumed_soc, 1))

                # Si es parada de recarga, recarga batería antes del próximo tramo
                if self.default_layover_type == 'charging':
                    next_soc = min(100.0, round(soc_arr + (self.rest_minutes * 0.8), 1))
                else:
                    next_soc = soc_arr

                line_obj.create({
                    'schedule_id': schedule.id,
                    'sequence': seq,
                    'leg_number': leg_num,
                    'route_id': r.id,
                    'departure_time': curr_time,
                    'duration_minutes': dur,
                    'layover_type': self.default_layover_type,
                    'rest_minutes': self.rest_minutes,
                    'battery_soc_departure': soc_dep,
                    'battery_soc_arrival': soc_arr,
                    'driver_id': schedule.driver_id.id if schedule.driver_id else False,
                    'state': 'draft',
                })
                # El siguiente tramo sale tras la llegada + tiempo de parada técnica
                curr_time += (dur / 60.0) + (self.rest_minutes / 60.0)
                curr_soc = next_soc
                seq += 10
                leg_num += 1

        schedule._compute_metrics()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Encadenamiento Generado',
                'message': f"Se generaron con éxito {len(schedule.line_ids)} tramos para el Bus {schedule.vehicle_id.name} respetando los tiempos de parada.",
                'type': 'success',
                'sticky': False,
            }
        }
