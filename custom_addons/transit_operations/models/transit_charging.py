# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TransitChargingStation(models.Model):
    _name = 'transit.charging.station'
    _description = 'Patio y Estación de Recarga Eléctrica (Depot Operations)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Nombre del Patio / Estación', required=True, tracking=True)
    code = fields.Char(string='Código de Estación', required=True, index=True)
    concessionaire_id = fields.Many2one('transit.concessionaire', string='Empresa Concesionaria / Operadora', tracking=True)
    
    # Capacidad Eléctrica y Gestión de Potencia (Peak-Shaving)
    contracted_power_kw = fields.Float(string='Potencia Máxima Contratada (kW)', default=1000.0, tracking=True)
    current_power_draw_kw = fields.Float(
        string='Demanda Actual Instantánea (kW)',
        compute='_compute_current_draw',
        store=True,
        digits=(10, 2)
    )
    power_utilization_rate = fields.Float(
        string='% Utilización de Acometida',
        compute='_compute_current_draw',
        store=True,
        digits=(5, 1)
    )
    peak_shaving_active = fields.Boolean(
        string='Algoritmo Peak-Shaving Activo',
        default=True,
        help='Modula la potencia de los cargadores para evitar penalizaciones por sobrepasar la potencia pico contratada.'
    )

    address = fields.Char(string='Ubicación / Dirección')
    latitude = fields.Float(string='Latitud', digits=(10, 6), default=-25.3400)
    longitude = fields.Float(string='Longitud', digits=(10, 6), default=-57.5100)

    charger_ids = fields.One2many('transit.charger', 'station_id', string='Dispensadores de Carga')
    charger_count = fields.Integer(string='Total Cargadores', compute='_compute_charger_counts')
    active_charging_count = fields.Integer(string='Cargadores en Uso', compute='_compute_charger_counts')

    session_ids = fields.One2many('transit.charging.session', 'station_id', string='Historial de Recargas')

    @api.depends('charger_ids.status', 'charger_ids.current_output_kw')
    def _compute_current_draw(self):
        for rec in self:
            total_draw = sum(rec.charger_ids.filtered(lambda c: c.status == 'charging').mapped('current_output_kw'))
            rec.current_power_draw_kw = total_draw
            if rec.contracted_power_kw and rec.contracted_power_kw > 0:
                rec.power_utilization_rate = (total_draw / rec.contracted_power_kw) * 100.0
            else:
                rec.power_utilization_rate = 0.0

    @api.depends('charger_ids', 'charger_ids.status')
    def _compute_charger_counts(self):
        for rec in self:
            rec.charger_count = len(rec.charger_ids)
            rec.active_charging_count = len(rec.charger_ids.filtered(lambda c: c.status == 'charging'))


class TransitCharger(models.Model):
    _name = 'transit.charger'
    _description = 'Dispensador Físico de Carga Eléctrica'
    _inherit = ['mail.thread']
    _order = 'station_id, name'

    name = fields.Char(string='Identificador del Dispensador', required=True)
    station_id = fields.Many2one('transit.charging.station', string='Patio / Estación', required=True, ondelete='cascade')
    ocpp_id = fields.Char(string='ID Protocolo OCPP', required=True, index=True, help='Identificador OCPP 1.6J / 2.0.1')
    
    charger_type = fields.Selection([
        ('dc_ultra', 'DC Ultra Rápido (150-300 kW)'),
        ('dc_fast', 'DC Rápido (60-120 kW)'),
        ('ac_heavy', 'AC Nocturno Lento (22-44 kW)'),
    ], string='Tipo de Cargador', default='dc_fast', required=True)

    connector_standard = fields.Selection([
        ('ccs2', 'CCS Combo 2 (Estándar Europeo)'),
        ('gbt', 'GB/T (Estándar Buses Chinos / BYD / Yutong)'),
        ('type2', 'Tipo 2 Mennekes'),
    ], string='Conector Físico', default='gbt', required=True)

    max_nominal_power_kw = fields.Float(string='Potencia Nominal (kW)', default=120.0, required=True)
    current_output_kw = fields.Float(string='Potencia de Salida Actual (kW)', default=0.0)

    status = fields.Selection([
        ('available', 'Disponible / Libre'),
        ('charging', 'Cargando Vehículo'),
        ('fault', 'Falla / Fuera de Servicio'),
        ('reserved', 'Reservado para Salida Matutina'),
    ], string='Estado en Vivo', default='available', tracking=True)

    current_vehicle_id = fields.Many2one('fleet.vehicle', string='Bus Conectado Actualmente')
    current_session_id = fields.Many2one('transit.charging.session', string='Sesión Activa')

    def action_start_charge(self, vehicle_id):
        self.ensure_one()
        if self.status != 'available':
            raise ValidationError(f"El dispensador {self.name} no está disponible.")
        vehicle = self.env['fleet.vehicle'].browse(vehicle_id)
        session = self.env['transit.charging.session'].create({
            'station_id': self.station_id.id,
            'charger_id': self.id,
            'vehicle_id': vehicle.id,
            'start_time': fields.Datetime.now(),
            'initial_soc': vehicle.current_soc or 20.0,
            'state': 'charging',
        })
        self.write({
            'status': 'charging',
            'current_vehicle_id': vehicle.id,
            'current_session_id': session.id,
            'current_output_kw': min(self.max_nominal_power_kw, 100.0),
        })

    def action_stop_charge(self):
        self.ensure_one()
        if self.current_session_id:
            now = fields.Datetime.now()
            vehicle = self.current_vehicle_id
            final_soc = min(100.0, (vehicle.current_soc or 80.0) + 15.0)
            if vehicle:
                vehicle.write({'current_soc': final_soc})
            self.current_session_id.write({
                'end_time': now,
                'final_soc': final_soc,
                'kwh_dispensed': 75.5,
                'state': 'completed',
            })
        self.write({
            'status': 'available',
            'current_vehicle_id': False,
            'current_session_id': False,
            'current_output_kw': 0.0,
        })


class TransitChargingSession(models.Model):
    _name = 'transit.charging.session'
    _description = 'Sesión Histórica de Recarga de Bus Eléctrico'
    _order = 'start_time desc'

    station_id = fields.Many2one('transit.charging.station', string='Patio / Estación', required=True)
    charger_id = fields.Many2one('transit.charger', string='Cargador', required=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Unidad / Bus Eléctrico', required=True)
    
    start_time = fields.Datetime(string='Inicio de Conexión', default=fields.Datetime.now, required=True)
    end_time = fields.Datetime(string='Fin de Conexión')
    
    initial_soc = fields.Float(string='SoC Inicial (%)', digits=(5, 1))
    final_soc = fields.Float(string='SoC Final (%)', digits=(5, 1))
    kwh_dispensed = fields.Float(string='Energía Suministrada (kWh)', digits=(10, 2))
    
    cost_per_kwh = fields.Float(string='Tarifa Eléctrica (Gs./kWh)', default=450.0)
    total_cost = fields.Float(string='Costo Total de Recarga (Gs.)', compute='_compute_cost', store=True)

    state = fields.Selection([
        ('charging', 'En Proceso de Carga'),
        ('completed', 'Carga Completada'),
        ('aborted', 'Interrumpida por Falla'),
    ], string='Estado', default='charging')

    @api.depends('kwh_dispensed', 'cost_per_kwh')
    def _compute_cost(self):
        for rec in self:
            rec.total_cost = (rec.kwh_dispensed or 0.0) * (rec.cost_per_kwh or 0.0)
