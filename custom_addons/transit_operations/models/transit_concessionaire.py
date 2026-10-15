# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TransitConcessionaire(models.Model):
    _name = 'transit.concessionaire'
    _description = 'Empresa Concesionaria / Operadora de Transporte'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Nombre Comercial', required=True, tracking=True)
    code = fields.Char(string='Código Interno de Concesión', required=True, index=True, tracking=True)
    agency_id = fields.Char(
        string='Código Telemática / VMT (Agency ID)',
        required=True,
        index=True,
        tracking=True,
        help='Código oficial transmitido por los dispositivos GPS (ej: 004B). Debe ser único por empresa.'
    )
    legal_name = fields.Char(string='Razón Social', tracking=True)
    vat_ruc = fields.Char(string='RUC / Identificación Fiscal', tracking=True)
    
    partner_id = fields.Many2one('res.partner', string='Contacto / Empresa Vinculada', tracking=True)
    contact_email = fields.Char(string='Correo Electrónico', related='partner_id.email', readonly=False)
    contact_phone = fields.Char(string='Teléfono', related='partner_id.phone', readonly=False)
    address = fields.Char(string='Dirección Base / Patio Central')
    
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color')

    # Relaciones Operativas
    vehicle_ids = fields.One2many('fleet.vehicle', 'concessionaire_id', string='Flota de Vehículos')
    vehicle_count = fields.Integer(string='Total Unidades', compute='_compute_vehicle_count')

    route_ids = fields.One2many('transit.route', 'concessionaire_id', string='Rutas Asignadas')
    route_count = fields.Integer(string='Total Rutas', compute='_compute_route_count')

    user_ids = fields.Many2many(
        'res.users',
        'transit_concessionaire_res_users_rel',
        'concessionaire_id',
        'user_id',
        string='Usuarios Asignados'
    )

    evaluation_ids = fields.One2many('transit.concessionaire.evaluation', 'concessionaire_id', string='Historial de Evaluaciones')
    settlement_ids = fields.One2many('transit.clearing.settlement', 'concessionaire_id', string='Liquidaciones de Compensación')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Ya existe una empresa con este código de concesión.'),
        ('agency_id_unique', 'unique(agency_id)', 'El Código Telemática (Agency ID) debe ser único entre las empresas.'),
    ]

    @api.constrains('agency_id')
    def _check_agency_id(self):
        for rec in self:
            if rec.agency_id and len(rec.agency_id.strip()) == 0:
                raise ValidationError("El Código Telemática (Agency ID) no puede estar vacío.")

    @api.depends('vehicle_ids')
    def _compute_vehicle_count(self):
        for rec in self:
            rec.vehicle_count = len(rec.vehicle_ids)

    @api.depends('route_ids')
    def _compute_route_count(self):
        for rec in self:
            rec.route_count = len(rec.route_ids)

    def name_get(self):
        res = []
        for rec in self:
            agency = f"[{rec.agency_id}] " if rec.agency_id else (f"[{rec.code}] " if rec.code else "")
            display = f"{agency}{rec.name}"
            res.append((rec.id, display))
        return res
