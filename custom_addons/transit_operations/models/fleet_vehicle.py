# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import api, fields, models

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    # Empresa Concesionaria / Operadora
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Concesionaria',
        tracking=True,
        help='Empresa operadora concesionada titular o responsable del bus'
    )
    service_id = fields.Many2one(
        'transit.service',
        string='Servicio Operativo Asignado',
        tracking=True,
        index=True,
        help='Línea o servicio especial al que está asignada prioritariamente la unidad'
    )

    # Identificación Operativa de la Unidad
    bus_internal_number = fields.Char(
        string='Nº de Coche / Interno',
        required=True,
        index=True,
        tracking=True,
        help='Número visible de la unidad para el servicio (ej: 04, 102)'
    )
    mean_id = fields.Char(
        string='ID Telemático GPS (Mean ID)',
        index=True,
        tracking=True,
        help='Identificador único transmitido por la telemetría GPS a la plataforma de monitoreo'
    )
    is_reinforcement_unit = fields.Boolean(
        string='Unidad de Refuerzo / Refuerzo Rápido',
        default=False,
        tracking=True,
        help='Indica si esta unidad está destinada a cubrir picos de demanda o suplir coches demorados'
    )
    is_reserve_unit = fields.Boolean(
        string='Unidad de Reserva Técnica (Standby)',
        default=False,
        tracking=True,
        help='Indica si esta unidad está asignada a la reserva técnica de base para sustituir buses averiados, en recarga o con retraso crítico'
    )
    reserve_status = fields.Selection([
        ('available', 'Disponible en Base'),
        ('active_substitute', 'En Calle (Sustituyendo Titular)'),
        ('charging', 'En Recarga de Baterías'),
        ('maintenance', 'En Taller / Mantenimiento'),
    ], string='Estado de Reserva', default='available', tracking=True)
    
    # Capacidad y Características
    seating_capacity = fields.Integer(string='Asientos', default=45, tracking=True)
    standing_capacity = fields.Integer(string='Pasajeros Parados', default=20, tracking=True)
    total_capacity = fields.Integer(
        string='Capacidad Total',
        compute='_compute_total_capacity',
        store=True
    )
    has_air_conditioning = fields.Boolean(string='Aire Acondicionado', default=True, tracking=True)
    has_wheelchair_ramp = fields.Boolean(string='Rampa de Accesibilidad', default=False, tracking=True)

    # Electrificación de Flotas (EV) & Gestión de Baterías
    is_electric = fields.Boolean(string='Bus 100% Eléctrico (Cero Emisiones)', default=False, tracking=True)
    battery_capacity_kwh = fields.Float(string='Capacidad de Batería (kWh)', default=350.0)
    connector_type = fields.Selection([
        ('gbt', 'GB/T (Estándar Flota Eléctrica Paraguay / BYD / Yutong)'),
        ('ccs2', 'CCS Combo 2 (Estándar Europeo)'),
        ('type2', 'Tipo 2 Mennekes'),
    ], string='Tipo de Conector', default='gbt')
    electric_range_km = fields.Float(string='Autonomía Teórica Estimada (km)', default=280.0)
    current_soc = fields.Float(string='Estado de Carga (SoC %)', default=100.0, tracking=True)
    current_soh = fields.Float(string='Salud de Batería (SoH %)', default=98.5)
    avg_energy_consumption_kwh_km = fields.Float(string='Consumo Medio (kWh/km)', default=1.15)
    min_departure_soc = fields.Float(
        string='SoC Mínimo Salida (%)',
        default=90.0,
        help='Umbral mínimo de carga requerido para habilitar el despacho matutino garantizado.'
    )
    thermal_preconditioning_ok = fields.Boolean(string='Cabina Pre-climatizada OK', default=True)
    charging_status = fields.Selection([
        ('idle', 'En Espera / Desconectado'),
        ('charging', 'En Proceso de Recarga'),
        ('completed', 'Carga Completa / Listo para Salida'),
    ], string='Estado de Carga en Patio', default='idle', tracking=True)
    
    # Tecnología y Billetaje
    validator_terminal_id = fields.Char(
        string='ID Validador Billetaje',
        tracking=True,
        help='Identificador del validador de cobro electrónico o expendedora'
    )

    # Documentación y Vencimientos
    itv_expiry_date = fields.Date(string='Vencimiento ITV / VTV', tracking=True)
    itv_status = fields.Selection([
        ('valid', 'Al Día'),
        ('warning', 'Por Vencer (30 días)'),
        ('expired', 'Vencida'),
    ], string='Estado ITV', compute='_compute_document_status')

    insurance_policy = fields.Char(string='Póliza de Seguro', tracking=True)
    insurance_expiry_date = fields.Date(string='Vencimiento Seguro', tracking=True)
    insurance_status = fields.Selection([
        ('valid', 'Vigente'),
        ('warning', 'Por Vencer (30 días)'),
        ('expired', 'Vencido'),
    ], string='Estado Seguro', compute='_compute_document_status')

    # Despachos vinculados
    dispatch_ids = fields.One2many('transit.dispatch', 'vehicle_id', string='Historial de Despachos')
    dispatch_count = fields.Integer(string='Cant. Despachos', compute='_compute_dispatch_count')

    @api.depends('seating_capacity', 'standing_capacity')
    def _compute_total_capacity(self):
        for rec in self:
            rec.total_capacity = (rec.seating_capacity or 0) + (rec.standing_capacity or 0)

    @api.depends('itv_expiry_date', 'insurance_expiry_date')
    def _compute_document_status(self):
        today = date.today()
        warning_delta = timedelta(days=30)
        for rec in self:
            # ITV Status
            if not rec.itv_expiry_date:
                rec.itv_status = 'expired'
            elif rec.itv_expiry_date < today:
                rec.itv_status = 'expired'
            elif rec.itv_expiry_date <= (today + warning_delta):
                rec.itv_status = 'warning'
            else:
                rec.itv_status = 'valid'

            # Seguro Status
            if not rec.insurance_expiry_date:
                rec.insurance_status = 'expired'
            elif rec.insurance_expiry_date < today:
                rec.insurance_status = 'expired'
            elif rec.insurance_expiry_date <= (today + warning_delta):
                rec.insurance_status = 'warning'
            else:
                rec.insurance_status = 'valid'

    def _compute_dispatch_count(self):
        for rec in self:
            rec.dispatch_count = len(rec.dispatch_ids)

    def name_get(self):
        res = []
        for vehicle in self:
            internal = vehicle.bus_internal_number or 'S/N'
            model = vehicle.model_id.name or ''
            plate = vehicle.license_plate or ''
            display = f"[{internal}] {model} ({plate})".strip()
            res.append((vehicle.id, display))
        return res

    def unlink(self):
        """Permitir eliminar buses limpiando previamente los logs y registros técnicos vinculados"""
        # 1. Odómetros y logs técnicos de flota
        odometers = self.env['fleet.vehicle.odometer'].sudo().search([('vehicle_id', 'in', self.ids)])
        if odometers:
            odometers.unlink()

        assignation_logs = self.env['fleet.vehicle.assignation.log'].sudo().search([('vehicle_id', 'in', self.ids)])
        if assignation_logs:
            assignation_logs.unlink()

        service_logs = self.env['fleet.vehicle.log.services'].sudo().search([('vehicle_id', 'in', self.ids)])
        if service_logs:
            service_logs.unlink()

        contracts = self.env['fleet.vehicle.log.contract'].sudo().search([('vehicle_id', 'in', self.ids)])
        if contracts:
            contracts.unlink()

        # 2. Sesiones de recarga eléctrica
        if 'transit.charging.session' in self.env:
            charging_sessions = self.env['transit.charging.session'].sudo().search([('vehicle_id', 'in', self.ids)])
            if charging_sessions:
                charging_sessions.unlink()

        # 3. Hojas de ruta / turnos programados del bus
        if 'transit.bus.schedule' in self.env:
            schedules = self.env['transit.bus.schedule'].sudo().search([('vehicle_id', 'in', self.ids)])
            if schedules:
                schedules.unlink()

        return super().unlink()


class FleetVehicleOdometer(models.Model):
    _inherit = 'fleet.vehicle.odometer'

    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehicle', required=True, ondelete='cascade')


class FleetVehicleAssignationLog(models.Model):
    _inherit = 'fleet.vehicle.assignation.log'

    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle", required=True, ondelete='cascade')


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehicle', required=True, ondelete='cascade')


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehicle', required=True, ondelete='cascade')

