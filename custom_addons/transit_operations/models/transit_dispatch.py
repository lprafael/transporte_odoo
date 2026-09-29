# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TransitDispatch(models.Model):
    _name = 'transit.dispatch'
    _description = 'Despacho Diario de Bus'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_departure desc, id desc'

    name = fields.Char(
        string='Número de Despacho',
        required=True,
        copy=False,
        readonly=True,
        default='Nuevo'
    )
    date = fields.Date(
        string='Fecha Operativa',
        default=fields.Date.context_today,
        required=True,
        index=True,
        tracking=True
    )

    timetable_id = fields.Many2one(
        'transit.timetable',
        string='Servicio / Horario Programado',
        required=True,
        tracking=True
    )
    route_id = fields.Many2one(
        'transit.route',
        string='Ruta / Ramal',
        related='timetable_id.route_id',
        store=True,
        readonly=True
    )

    # Asignaciones
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Concesionaria',
        compute='_compute_concessionaire_id',
        store=True,
        index=True
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Unidad / Bus',
        required=False,
        tracking=True
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Chofer Asignado',
        domain="[('is_driver', '=', True)]",
        tracking=True
    )

    # Tiempos de Despacho
    scheduled_departure = fields.Datetime(
        string='Salida Programada',
        required=True,
        tracking=True
    )
    actual_departure = fields.Datetime(
        string='Salida Real',
        tracking=True
    )
    scheduled_arrival = fields.Datetime(
        string='Llegada Estimada',
        compute='_compute_scheduled_arrival',
        store=True
    )
    actual_arrival = fields.Datetime(
        string='Llegada Real',
        tracking=True
    )

    # Cumplimiento y Puntualidad
    departure_delay_minutes = fields.Float(
        string='Desvío Salida (min)',
        compute='_compute_performance',
        store=True,
        help='Positivo indica retraso; negativo indica salida adelantada'
    )
    compliance_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('on_time', 'Puntual (±3 min)'),
        ('delayed', 'Con Retraso (>3 min)'),
        ('early', 'Adelantado (<-1 min)'),
    ], string='Estado Puntualidad', compute='_compute_performance', store=True, tracking=True)

    # Checklist Pre-operativo (Inspección Rápida de Seguridad)
    check_tires = fields.Boolean(string='Neumáticos y Presión en Buen Estado', default=False)
    check_brakes = fields.Boolean(string='Frenos de Servicio y Emergencia OK', default=False)
    check_lights = fields.Boolean(string='Luces Reglamentarias e Indicadores OK', default=False)
    check_fluids = fields.Boolean(string='Niveles de Aceite, Agua y Combustible OK', default=False)
    check_validator = fields.Boolean(string='Validador / Billetaje Operativo', default=False)
    inspection_passed = fields.Boolean(
        string='Inspección Previa Aprobada',
        compute='_compute_inspection_passed',
        store=True
    )
    inspection_notes = fields.Text(string='Observaciones de Inspección')

    # Odómetros
    initial_odometer = fields.Float(string='Odómetro Inicial (km)', digits=(10, 1))
    final_odometer = fields.Float(string='Odómetro Final (km)', digits=(10, 1))
    km_traveled = fields.Float(
        string='Km Recorridos',
        compute='_compute_km',
        store=True,
        digits=(10, 1)
    )

    # Telemetría GPS y Geocercas en Tiempo Real
    last_latitude = fields.Float(string='Última Latitud GPS', digits=(10, 6), readonly=True)
    last_longitude = fields.Float(string='Última Longitud GPS', digits=(10, 6), readonly=True)
    last_speed_kmh = fields.Float(string='Velocidad Actual (km/h)', default=0.0, readonly=True)
    last_gps_time = fields.Datetime(string='Último Reporte GPS', readonly=True)
    current_geofence_status = fields.Char(string='Estado Geocerca', default='En Terminal Origen', readonly=True)
    speed_alert = fields.Boolean(string='Alerta Exceso Velocidad', default=False, tracking=True)
    deviation_alert = fields.Boolean(string='Alerta Desvío Itinerario', default=False, tracking=True)
    last_deviation_meters = fields.Float(string='Desvío de Ruta (m)', default=0.0, readonly=True)

    # Estado de la Operación
    state = fields.Selection([
        ('draft', 'Borrador / Asignado'),
        ('inspected', 'Inspección Aprobada'),
        ('dispatched', 'Despachado en Cabecera'),
        ('in_transit', 'En Ruta'),
        ('completed', 'Viaje Completado'),
        ('canceled', 'Cancelado'),
    ], string='Estado de Operación', default='draft', tracking=True)

    checkpoint_ids = fields.One2many(
        'transit.dispatch.checkpoint',
        'dispatch_id',
        string='Puntos de Control / Paradas'
    )

    ticket_ids = fields.One2many(
        'transit.ticket',
        'dispatch_id',
        string='Boletos / Pasajes'
    )
    total_passengers = fields.Integer(string='Pasajeros Transportados', compute='_compute_passengers_revenue')
    total_revenue = fields.Float(string='Recaudación Total (Gs.)', compute='_compute_passengers_revenue')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('transit.dispatch') or 'DESP-AUTO'
            if not vals.get('scheduled_departure') and vals.get('timetable_id') and vals.get('date'):
                timetable = self.env['transit.timetable'].browse(vals['timetable_id'])
                if timetable:
                    hours = int(timetable.departure_time_float)
                    minutes = int(round((timetable.departure_time_float - hours) * 60))
                    departure_time = time(hour=hours, minute=minutes)
                    date_val = fields.Date.to_date(vals['date'])
                    vals['scheduled_departure'] = datetime.combine(date_val, departure_time)
        records = super(TransitDispatch, self).create(vals_list)
        for rec in records:
            if not rec.checkpoint_ids and rec.route_id and rec.route_id.checkpoint_ids:
                rec.populate_checkpoints_from_route()
        return records

    def populate_checkpoints_from_route(self):
        """Copia las geocercas/paradas definidas en la ruta al despacho actual con tiempos calculados"""
        self.ensure_one()
        if not self.route_id or not self.route_id.checkpoint_ids:
            return
        base_time = self.scheduled_departure or fields.Datetime.now()
        checkpoint_vals = []
        for cp in self.route_id.checkpoint_ids:
            sched_time = base_time + timedelta(minutes=cp.offset_minutes) if cp.offset_minutes else base_time
            checkpoint_vals.append((0, 0, {
                'sequence': cp.sequence,
                'name': cp.name,
                'checkpoint_type': cp.checkpoint_type,
                'latitude': cp.latitude,
                'longitude': cp.longitude,
                'radius_meters': cp.radius_meters,
                'scheduled_time': sched_time,
                'status': 'pending',
            }))
        self.write({'checkpoint_ids': checkpoint_vals})

    @api.onchange('timetable_id', 'date')
    def _onchange_timetable_date(self):
        if self.timetable_id and self.date:
            hours = int(self.timetable_id.departure_time_float)
            minutes = int(round((self.timetable_id.departure_time_float - hours) * 60))
            departure_time = time(hour=hours, minute=minutes)
            self.scheduled_departure = datetime.combine(self.date, departure_time)

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            latest_odometer = self.env['fleet.vehicle.odometer'].search(
                [('vehicle_id', '=', self.vehicle_id.id)],
                order='value desc',
                limit=1
            )
            if latest_odometer and not self.initial_odometer:
                self.initial_odometer = latest_odometer.value

    @api.depends('check_tires', 'check_brakes', 'check_lights', 'check_fluids', 'check_validator')
    def _compute_inspection_passed(self):
        for rec in self:
            rec.inspection_passed = (
                rec.check_tires and
                rec.check_brakes and
                rec.check_lights and
                rec.check_fluids and
                rec.check_validator
            )

    @api.depends('scheduled_departure', 'timetable_id.scheduled_duration_minutes')
    def _compute_scheduled_arrival(self):
        for rec in self:
            if rec.scheduled_departure and rec.timetable_id:
                rec.scheduled_arrival = rec.scheduled_departure + timedelta(
                    minutes=rec.timetable_id.scheduled_duration_minutes or 60
                )
            else:
                rec.scheduled_arrival = False

    @api.depends('scheduled_departure', 'actual_departure')
    def _compute_performance(self):
        for rec in self:
            if rec.scheduled_departure and rec.actual_departure:
                diff_seconds = (rec.actual_departure - rec.scheduled_departure).total_seconds()
                diff_minutes = diff_seconds / 60.0
                rec.departure_delay_minutes = round(diff_minutes, 1)
                if -1.0 <= rec.departure_delay_minutes <= 3.0:
                    rec.compliance_status = 'on_time'
                elif rec.departure_delay_minutes > 3.0:
                    rec.compliance_status = 'delayed'
                else:
                    rec.compliance_status = 'early'
            else:
                rec.departure_delay_minutes = 0.0
                rec.compliance_status = 'pending'

    @api.depends('initial_odometer', 'final_odometer')
    def _compute_km(self):
        for rec in self:
            if rec.final_odometer and rec.initial_odometer and rec.final_odometer >= rec.initial_odometer:
                rec.km_traveled = rec.final_odometer - rec.initial_odometer
            else:
                rec.km_traveled = 0.0

    # Sensórica APC (Cámaras 3D en Puertas) y Auditoría de Evasión
    apc_boardings = fields.Integer(string='Ascensos (Cámara 3D APC)', default=0)
    apc_alightings = fields.Integer(string='Descensos (Cámara 3D APC)', default=0)
    apc_total_passengers = fields.Integer(
        string='Pasajeros Reales (APC)',
        compute='_compute_apc_metrics',
        store=True,
        help='Total acumulado de ascensos auditados ópticamente por cámaras 3D.'
    )
    electronic_validations = fields.Integer(
        string='Validaciones Electrónicas',
        compute='_compute_apc_metrics',
        store=True,
        help='Pasajes efectivamente cobrados o validados electrónicamente.'
    )
    evasion_gap_passengers = fields.Integer(
        string='Discrepancia / Evasión (Pasajeros)',
        compute='_compute_apc_metrics',
        store=True
    )
    evasion_rate = fields.Float(
        string='% Tasa de Evasión',
        compute='_compute_apc_metrics',
        store=True,
        digits=(5, 1)
    )
    evasion_alert = fields.Boolean(
        string='Alerta Alta Evasión (>10%)',
        compute='_compute_apc_metrics',
        store=True,
        tracking=True
    )
    calculated_ipk = fields.Float(
        string='Índice Pasajero / Km (IPK)',
        compute='_compute_apc_metrics',
        store=True,
        digits=(6, 3),
        help='IPK = Total Pasajeros APC / Km Recorridos'
    )

    # Sensores de Carga en Ejes (Protocolo J1939 CAN-bus)
    axle_weight_kg = fields.Float(string='Peso en Ejes (kg - CAN J1939)', default=0.0)
    max_gross_weight_kg = fields.Float(string='Peso Bruto Máximo Autorizado (kg)', default=18000.0)
    passenger_load_percentage = fields.Float(
        string='% Ocupación por Peso',
        compute='_compute_axle_load',
        store=True,
        digits=(5, 1)
    )
    structural_overload_alert = fields.Boolean(
        string='Alerta Sobrecarga Estructural',
        compute='_compute_axle_load',
        store=True,
        tracking=True
    )

    @api.depends('vehicle_id', 'vehicle_id.concessionaire_id', 'route_id', 'route_id.concessionaire_id')
    def _compute_concessionaire_id(self):
        for rec in self:
            rec.concessionaire_id = (
                rec.vehicle_id.concessionaire_id or
                rec.route_id.concessionaire_id or
                False
            )

    @api.depends('apc_boardings', 'ticket_ids', 'ticket_ids.state', 'km_traveled', 'route_id.distance_km')
    def _compute_apc_metrics(self):
        for rec in self:
            valid_tickets = rec.ticket_ids.filtered(lambda t: t.state != 'canceled')
            val_count = len(valid_tickets)
            rec.electronic_validations = val_count
            
            # Pasajeros APC: si se registran boardings usarlo, si no fallback a boletos
            passengers = rec.apc_boardings if rec.apc_boardings > 0 else val_count
            rec.apc_total_passengers = passengers

            # Brecha de evasión
            gap = max(0, passengers - val_count)
            rec.evasion_gap_passengers = gap
            if passengers > 0:
                rate = (gap / passengers) * 100.0
            else:
                rate = 0.0
            rec.evasion_rate = rate
            rec.evasion_alert = (rate > 10.0 and gap >= 3)

            # IPK (Índice Pasajero / Kilómetro)
            effective_km = rec.km_traveled or (rec.route_id.distance_km if rec.route_id else 0.0)
            if effective_km and effective_km > 0:
                rec.calculated_ipk = passengers / effective_km
            else:
                rec.calculated_ipk = 0.0

    @api.depends('axle_weight_kg', 'max_gross_weight_kg')
    def _compute_axle_load(self):
        for rec in self:
            if rec.max_gross_weight_kg and rec.max_gross_weight_kg > 0:
                pct = (rec.axle_weight_kg / rec.max_gross_weight_kg) * 100.0
            else:
                pct = 0.0
            rec.passenger_load_percentage = pct
            rec.structural_overload_alert = (pct >= 95.0)

    @api.depends('ticket_ids', 'ticket_ids.price', 'ticket_ids.state')
    def _compute_passengers_revenue(self):
        for rec in self:
            valid_tickets = rec.ticket_ids.filtered(lambda t: t.state != 'canceled')
            rec.total_passengers = len(valid_tickets)
            rec.total_revenue = sum(valid_tickets.mapped('price'))

    # Acciones de Flujo de Trabajo
    def action_inspect(self):
        """Valida checklist pre-operativo y regla de salida garantizada para buses eléctricos"""
        for rec in self:
            if not rec.vehicle_id:
                raise ValidationError("Debe asignar una Unidad/Bus antes de realizar la inspección técnica.")
            if not rec.inspection_passed:
                raise ValidationError(
                    "No se puede aprobar la inspección técnica. "
                    "Todos los puntos del checklist (neumáticos, frenos, luces, fluidos y validador) deben estar marcados."
                )
            # Validar que la licencia del chofer no esté vencida
            if rec.driver_id and rec.driver_id.driver_license_status == 'expired':
                raise ValidationError(
                    f"El chofer {rec.driver_id.name} tiene la licencia de conducir vencida o inhabilitada."
                )
            # Regla de Salida Garantizada Matutina para Buses Eléctricos
            if rec.vehicle_id and rec.vehicle_id.is_electric:
                if rec.vehicle_id.current_soc < (rec.vehicle_id.min_departure_soc or 90.0):
                    raise ValidationError(
                        f"BLOQUEO DE SALIDA GARANTIZADA: El bus eléctrico [{rec.vehicle_id.bus_internal_number}] "
                        f"cuenta con un SoC de {rec.vehicle_id.current_soc}%, inferior al umbral mínimo reglamentario ({rec.vehicle_id.min_departure_soc}%). "
                        f"La unidad debe permanecer en recarga en patio."
                    )
            rec.state = 'inspected'

    def action_dispatch(self):
        """Registra la salida efectiva en cabecera y verifica fatiga operacional del chofer"""
        for rec in self:
            if not rec.vehicle_id:
                raise ValidationError("Debe asignar una Unidad/Bus antes de despachar el servicio.")
            now = fields.Datetime.now()
            
            # Verificación de ergonomía y fatiga operacional del conductor (4.5h continuas)
            if rec.driver_id:
                recent_dispatches = self.search([
                    ('driver_id', '=', rec.driver_id.id),
                    ('id', '!=', rec.id),
                    ('state', 'in', ['in_transit', 'completed']),
                    ('actual_departure', '>=', now - timedelta(hours=4.5)),
                ])
                if len(recent_dispatches) >= 3:
                    rec.message_post(
                        body=f"⚠️ ADVERTENCIA DE FATIGA OPERACIONAL (Ergonomía Laboral): El chofer {rec.driver_id.name} "
                             f"acumula más de 3 servicios consecutivos en las últimas 4.5 horas. "
                             f"Se recomienda programar intervalo de descanso reglamentario de 45 minutos."
                    )

            vals = {
                'state': 'dispatched',
                'actual_departure': now,
            }
            if not rec.initial_odometer and rec.vehicle_id:
                latest_odometer = self.env['fleet.vehicle.odometer'].search(
                    [('vehicle_id', '=', rec.vehicle_id.id)],
                    order='value desc',
                    limit=1
                )
                if latest_odometer:
                    vals['initial_odometer'] = latest_odometer.value
            rec.write(vals)

    def action_transit(self):
        """Pasa la unidad a En Ruta"""
        self.write({'state': 'in_transit'})

    def action_complete(self):
        """Finaliza el viaje y actualiza el odómetro central de Odoo Fleet"""
        for rec in self:
            now = fields.Datetime.now()
            rec.write({
                'state': 'completed',
                'actual_arrival': now,
            })
            # Actualiza el odómetro oficial del ERP
            if rec.final_odometer and rec.final_odometer > rec.initial_odometer:
                self.env['fleet.vehicle.odometer'].create({
                    'vehicle_id': rec.vehicle_id.id,
                    'value': rec.final_odometer,
                    'date': rec.date,
                })

    def action_cancel(self):
        """Cancela el despacho"""
        self.write({'state': 'canceled'})
