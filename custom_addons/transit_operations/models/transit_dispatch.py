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
        required=False,
        tracking=True
    )
    route_id = fields.Many2one(
        'transit.route',
        string='Ruta / Ramal',
        required=True,
        index=True
    )
    service_id = fields.Many2one(
        'transit.service',
        string='Servicio Especial / Concesión',
        related='route_id.service_id',
        store=True,
        index=True
    )
    is_reinforcement = fields.Boolean(
        string='Salida de Refuerzo / Extra',
        default=False,
        tracking=True,
        help='Salida adicional no programada en cuadro de marcha, despachada para absorber picos o cubrir coche demorado'
    )
    is_incomplete = fields.Boolean(
        string='Viaje Incompleto (~80% del trayecto)',
        default=False,
        tracking=True,
        help='El bus llegó a la geocerca de retorno pero no completó la totalidad del itinerario oficial'
    )

    bus_schedule_id = fields.Many2one(
        'transit.bus.schedule',
        string='Hoja de Ruta / Turno del Bus',
        ondelete='set null',
        index=True,
        tracking=True,
        help='Hoja de ruta que agrupa y encadena la secuencia de viajes de este bus'
    )
    bus_schedule_line_id = fields.Many2one(
        'transit.bus.schedule.line',
        string='Tramo de Hoja de Ruta',
        ondelete='set null'
    )

    # Semáforo de Desempeño Operativo GPS
    semaphore_color = fields.Selection([
        ('green', 'Verde: A Tiempo (En Margen Correcto)'),
        ('yellow', 'Amarillo: Retraso / Adelanto Fuera de Tolerancia'),
        ('red', 'Rojo: Cancelado / Faltante'),
        ('blue', 'Azul: Cubierto por Bus de Reserva'),
        ('gray', 'Gris: Programado (En Espera)'),
    ], string='Semáforo Operativo GPS', compute='_compute_semaphore_color', store=True)

    # Buses de Reserva / Sustitución Técnica
    is_reserve_substituted = fields.Boolean(
        string='Cubierto por Bus de Reserva',
        default=False,
        tracking=True,
        help='Indica si este despacho fue cubierto por una unidad de reserva técnica'
    )
    substituted_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Bus de Reserva Asignado',
        tracking=True,
        domain="[('is_reserve_unit', '=', True)]",
        help='Unidad de reserva tomada de base para cubrir la salida'
    )

    # Telemetría de Batería EV (SoC)
    battery_soc_departure = fields.Float(string='% Batería Salida', default=90.0, help='SoC inicial al salir')
    battery_soc_arrival = fields.Float(string='% Batería Llegada', default=65.0, help='SoC registrado al arribar')
    battery_consumption_pct = fields.Float(
        string='Consumo Batería (%)',
        compute='_compute_battery_consumption',
        store=True
    )

    # Parada Técnica en Cabecera
    layover_type = fields.Selection([
        ('none', 'Salida Inmediata'),
        ('regulation', 'Regulación / Espera en Cabecera (mín. 10m)'),
        ('cleaning', 'Limpieza y Aseo de Unidad (mín. 15m)'),
        ('driver_rest', 'Descanso / Relevo de Chofer (mín. 20m)'),
        ('charging', 'Recarga de Baterías EV (mín. 30m)'),
        ('maintenance', 'Inspección Mecánica / Taller (mín. 30m)'),
    ], string='Actividad en Parada Técnica', default='regulation')
    layover_duration_minutes = fields.Integer(string='Tiempo en Parada (min)', default=15)
    layover_warning = fields.Char(string='Alerta Tiempo Parada')

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

    # Cumplimiento y Puntualidad (Auditoría VMT / CID)
    departure_delay_minutes = fields.Float(
        string='Desvío Salida (min)',
        compute='_compute_performance',
        store=True,
        help='Positivo indica retraso; negativo indica salida adelantada'
    )
    compliance_status = fields.Selection([
        ('pending', 'Pendiente de Salida'),
        ('on_time', 'Regular (En Tolerancia Oficial)'),
        ('delayed', 'Irregular (Salida Atrasada)'),
        ('early', 'Irregular (Salida Adelantada)'),
        ('reinforcement', 'Refuerzo / No Programado'),
        ('incomplete', 'Incompleto (Retorno al 80%)'),
        ('unperformed', 'No Realizado / Faltante'),
    ], string='Estado de Regularidad', compute='_compute_performance', store=True, tracking=True)

    tipo_dia = fields.Selection([
        ('5', 'Laboral (Lunes a Viernes)'),
        ('6', 'Sábado'),
        ('7', 'Domingos y Feriados'),
    ], string='Régimen / Tipo de Día', compute='_compute_tipo_dia_dispatch', store=True, index=True)

    franja_horaria = fields.Selection([
        ('pico_manana', 'Pico Mañana (05:00–07:59)'),
        ('pos_pico_dia', 'Pos-Pico Día (08:00–15:59)'),
        ('pico_tarde', 'Pico Tarde (16:00–18:59)'),
        ('pos_pico_noche', 'Pos-Pico Noche (19:00–20:59)'),
        ('valle_noche', 'Valle / Nocturno'),
        ('fin_de_semana', 'Operación Fin de Semana / Feriado'),
    ], string='Franja Horaria Operativa', compute='_compute_franja_icf', store=True)

    tipo_franja_icf = fields.Selection([
        ('pico', 'Hora Pico'),
        ('pos_pico', 'Hora Pos-Pico'),
    ], string='Tipo Franja ICF', compute='_compute_franja_icf', store=True)

    is_recognized_icf = fields.Boolean(
        string='Servicio Válido / Reconocido ICF',
        compute='_compute_icf_recognition',
        store=True,
        help='Cumple con los criterios de reconocimiento oficial del Decreto N° 710/2023 (Apéndice 11)'
    )

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

    @api.depends('vehicle_id.concessionaire_id', 'route_id.concessionaire_id')
    def _compute_concessionaire_id(self):
        for rec in self:
            rec.concessionaire_id = rec.vehicle_id.concessionaire_id or rec.route_id.concessionaire_id or False

    @api.depends('scheduled_departure', 'timetable_id.scheduled_duration_minutes')
    def _compute_scheduled_arrival(self):
        for rec in self:
            if rec.scheduled_departure and rec.timetable_id:
                rec.scheduled_arrival = rec.scheduled_departure + timedelta(
                    minutes=rec.timetable_id.scheduled_duration_minutes or 60
                )
            else:
                rec.scheduled_arrival = False

    @api.depends('date')
    def _compute_tipo_dia_dispatch(self):
        holiday_obj = self.env['transit.holiday']
        for rec in self:
            if rec.date:
                info = holiday_obj.get_day_type_info(rec.date)
                rec.tipo_dia = info['tipo_dia']
            else:
                rec.tipo_dia = '5'

    @api.depends('scheduled_departure', 'actual_departure', 'tipo_dia')
    def _compute_franja_icf(self):
        for rec in self:
            dep_dt = rec.actual_departure or rec.scheduled_departure
            if not dep_dt:
                rec.franja_horaria = 'pos_pico_dia'
                rec.tipo_franja_icf = 'pos_pico'
                continue

            # Hora decimal
            hour_float = dep_dt.hour + (dep_dt.minute / 60.0)
            td = rec.tipo_dia or '5'

            if td in ('6', '7'):
                rec.franja_horaria = 'fin_de_semana'
                rec.tipo_franja_icf = 'pos_pico'
            else:
                if 5.0 <= hour_float < 8.0:
                    rec.franja_horaria = 'pico_manana'
                    rec.tipo_franja_icf = 'pico'
                elif 8.0 <= hour_float < 16.0:
                    rec.franja_horaria = 'pos_pico_dia'
                    rec.tipo_franja_icf = 'pos_pico'
                elif 16.0 <= hour_float < 19.0:
                    rec.franja_horaria = 'pico_tarde'
                    rec.tipo_franja_icf = 'pico'
                elif 19.0 <= hour_float < 21.0:
                    rec.franja_horaria = 'pos_pico_noche'
                    rec.tipo_franja_icf = 'pos_pico'
                else:
                    rec.franja_horaria = 'valle_noche'
                    rec.tipo_franja_icf = 'pos_pico'

    @api.depends('scheduled_departure', 'actual_departure', 'is_reinforcement', 'is_incomplete', 'service_id', 'state')
    def _compute_performance(self):
        for rec in self:
            if rec.is_reinforcement:
                rec.departure_delay_minutes = 0.0
                rec.compliance_status = 'reinforcement'
                continue

            if rec.is_incomplete:
                rec.departure_delay_minutes = 0.0
                rec.compliance_status = 'incomplete'
                continue

            if rec.state == 'canceled':
                rec.departure_delay_minutes = 0.0
                rec.compliance_status = 'unperformed'
                continue

            # Obtener tolerancias configuradas para el servicio (con defaults oficiales de 5 y 10 min)
            t_antes = rec.service_id.tolerance_early_min if rec.service_id else 5
            t_despues = rec.service_id.tolerance_late_min if rec.service_id else 10

            if rec.scheduled_departure and rec.actual_departure:
                diff_seconds = (rec.actual_departure - rec.scheduled_departure).total_seconds()
                diff_minutes = diff_seconds / 60.0
                rec.departure_delay_minutes = round(diff_minutes, 1)

                if -float(t_antes) <= rec.departure_delay_minutes <= float(t_despues):
                    rec.compliance_status = 'on_time'
                elif rec.departure_delay_minutes > float(t_despues):
                    rec.compliance_status = 'delayed'
                else:
                    rec.compliance_status = 'early'
            else:
                rec.departure_delay_minutes = 0.0
                # Si la hora programada ya pasó hace más de 45 min y no salió, clasificar como no realizado
                if rec.scheduled_departure and fields.Datetime.now() > (rec.scheduled_departure + timedelta(minutes=45)) and rec.state == 'draft':
                    rec.compliance_status = 'unperformed'
                else:
                    rec.compliance_status = 'pending'

    @api.depends('compliance_status', 'state')
    def _compute_icf_recognition(self):
        for rec in self:
            # Los servicios regulares e irregulares ejecutados son computables en el ICF
            # Los no realizados y cancelados quedan sin reconocimiento
            rec.is_recognized_icf = rec.compliance_status in ('on_time', 'delayed', 'early', 'reinforcement') and rec.state in ('dispatched', 'in_transit', 'completed')

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

    def action_mark_incomplete(self):
        """Marca el viaje como incompleto (alcanzó el retorno al 80% pero no completó)"""
        for rec in self:
            rec.write({
                'is_incomplete': True,
                'compliance_status': 'incomplete',
                'state': 'completed',
                'actual_arrival': fields.Datetime.now(),
            })
            rec.message_post(body="⚠️ Viaje registrado como INCOMPLETO (el vehículo alcanzó el punto de retorno pero no completó el itinerario).")

    def action_cancel(self):
        """Cancela el despacho"""
        self.write({'state': 'canceled', 'compliance_status': 'unperformed'})

    @api.depends('state', 'compliance_status', 'is_reserve_substituted', 'actual_departure')
    def _compute_semaphore_color(self):
        for rec in self:
            if rec.is_reserve_substituted:
                rec.semaphore_color = 'blue'
            elif rec.state == 'canceled' or rec.compliance_status == 'unperformed':
                rec.semaphore_color = 'red'
            elif rec.compliance_status == 'on_time':
                rec.semaphore_color = 'green'
            elif rec.compliance_status in ('delayed', 'early'):
                rec.semaphore_color = 'yellow'
            elif rec.state in ('draft', 'inspected'):
                rec.semaphore_color = 'gray'
            else:
                rec.semaphore_color = 'green'

    @api.depends('battery_soc_departure', 'battery_soc_arrival')
    def _compute_battery_consumption(self):
        for rec in self:
            if rec.battery_soc_departure and rec.battery_soc_arrival:
                rec.battery_consumption_pct = max(0.0, round(rec.battery_soc_departure - rec.battery_soc_arrival, 1))
            else:
                rec.battery_consumption_pct = 0.0

    def action_assign_reserve_bus(self):
        """Abre asistente para asignar un bus de reserva técnica a este despacho."""
        self.ensure_one()
        return {
            'name': f'Asignar Bus de Reserva - Despacho {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'transit.dispatch.reserve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_dispatch_id': self.id,
                'default_concessionaire_id': self.concessionaire_id.id if self.concessionaire_id else False,
            }
        }


class TransitDispatchReserveWizard(models.TransientModel):
    _name = 'transit.dispatch.reserve.wizard'
    _description = 'Asistente de Asignación de Bus de Reserva para Despacho'

    dispatch_id = fields.Many2one(
        'transit.dispatch',
        string='Despacho Afectado',
        required=True
    )
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Operadora'
    )
    titular_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Bus Titular Afectado',
        related='dispatch_id.vehicle_id',
        readonly=True
    )
    reason = fields.Selection([
        ('breakdown', 'Avería Mecánica / Eléctrica'),
        ('delay', 'Retraso Crítico en Viaje Anterior'),
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
        disp = self.dispatch_id
        old_bus = disp.vehicle_id.name if disp.vehicle_id else 'Sin Bus'

        disp.write({
            'vehicle_id': self.reserve_vehicle_id.id,
            'is_reinforcement': True,
            'is_reserve_substituted': True,
            'substituted_vehicle_id': self.reserve_vehicle_id.id,
            'driver_id': self.driver_id.id if self.driver_id else disp.driver_id.id,
        })

        # Actualizar estado de la reserva
        self.reserve_vehicle_id.write({'reserve_status': 'active_substitute'})

        disp.message_post(
            body=f"🔁 COBERTURA CON BUS DE RESERVA: La unidad titular [{old_bus}] fue sustituida por el Bus de Reserva [{self.reserve_vehicle_id.name}]. "
                 f"Motivo: {dict(self._fields['reason'].selection).get(self.reason)}. {self.notes or ''}"
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bus de Reserva Asignado',
                'message': f"El despacho {disp.name} ahora será operado por la unidad de reserva {self.reserve_vehicle_id.name}.",
                'type': 'info',
                'sticky': False,
            }
        }

