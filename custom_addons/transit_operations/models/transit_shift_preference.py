# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitShiftPreference(models.Model):
    _name = 'transit.shift.preference'
    _description = 'Preferencia y Licitación de Turnos de Chofer (Preference Bidding)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'seniority_years desc, id desc'

    name = fields.Char(string='Referencia de Solicitud', required=True, copy=False, default='Nuevo')
    driver_id = fields.Many2one(
        'res.partner',
        string='Conductor / Chofer',
        domain="[('is_driver', '=', True)]",
        required=True,
        tracking=True
    )
    seniority_years = fields.Float(string='Antigüedad Laboral (Años)', default=1.0, tracking=True)

    preferred_shift = fields.Selection([
        ('morning', 'Turno Mañana (04:30 - 13:00)'),
        ('afternoon', 'Turno Tarde (12:30 - 21:00)'),
        ('night', 'Turno Nocturno (20:30 - 05:00)'),
        ('split', 'Turno Cortado / Picos'),
    ], string='Turno Preferente', default='morning', required=True, tracking=True)

    preferred_rest_day = fields.Selection([
        ('0', 'Lunes'),
        ('1', 'Martes'),
        ('2', 'Miércoles'),
        ('3', 'Jueves'),
        ('4', 'Viernes'),
        ('5', 'Sábado'),
        ('6', 'Domingo'),
    ], string='Día de Descanso Preferente', default='6', required=True, tracking=True)

    preferred_route_id = fields.Many2one('transit.route', string='Ramal Preferido')
    comments = fields.Text(string='Observaciones / Motivos Ergonómicos')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Postulada / En Evaluación'),
        ('approved', 'Aprobada en Cuadrante'),
        ('rejected', 'No Asignada por Capacidad'),
    ], string='Estado de Asignación', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('transit.shift.preference') or 'PREF-AUTO'
        return super(TransitShiftPreference, self).create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})
