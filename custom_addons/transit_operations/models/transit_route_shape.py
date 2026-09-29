# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitRouteShape(models.Model):
    _name = 'transit.route.shape'
    _description = 'Trazado Geométrico de Ruta con Vigencia Histórica'
    _order = 'route_id asc, valid_from desc, version desc'

    route_id = fields.Many2one('transit.route', string='Ruta / Ramal', required=True, ondelete='cascade')
    version = fields.Integer(string='Versión', default=1, required=True)
    valid_from = fields.Date(string='Válido Desde', required=True)
    valid_until = fields.Date(string='Válido Hasta', help='Vacío indica que es el trazado vigente actualmente')
    total_km = fields.Float(string='Longitud Oficial (km)', digits=(8, 2))
    shape_source = fields.Char(string='Origen del Trazado', default='CID_VMT')
    notes = fields.Text(string='Observaciones / Motivo de Desvío')
    is_active = fields.Boolean(string='Vigente', compute='_compute_is_active', store=False)

    @api.depends('valid_from', 'valid_until')
    def _compute_is_active(self):
        today = fields.Date.today()
        for rec in self:
            if rec.valid_from and rec.valid_from <= today and (not rec.valid_until or rec.valid_until >= today):
                rec.is_active = True
            else:
                rec.is_active = False

    def name_get(self):
        result = []
        for rec in self:
            vigencia = f"{rec.valid_from} -> {rec.valid_until or 'Actualidad'}"
            status = "[Vigente]" if rec.is_active else "[Histórico]"
            name = f"{rec.route_id.code} - v{rec.version} {status} ({vigencia})"
            result.append((rec.id, name))
        return result
