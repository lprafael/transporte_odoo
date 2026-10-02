# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Concesionaria Principal',
        help='Empresa de transporte asignada a este usuario. Limita el acceso a flota, despachos, rutas y choferes de su propia empresa.'
    )
    concessionaire_ids = fields.Many2many(
        'transit.concessionaire',
        'transit_concessionaire_res_users_rel',
        'user_id',
        'concessionaire_id',
        string='Empresas Autorizadas (Multi-Tenant)',
        help='Lista de empresas concesionarias a las que este usuario tiene permiso de acceso.'
    )

    @api.onchange('concessionaire_id')
    def _onchange_concessionaire_id(self):
        if self.concessionaire_id and self.concessionaire_id not in self.concessionaire_ids:
            self.concessionaire_ids = [(4, self.concessionaire_id.id)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('concessionaire_id') and not vals.get('concessionaire_ids'):
                vals['concessionaire_ids'] = [(4, vals['concessionaire_id'])]
        return super(ResUsers, self).create(vals_list)

    def write(self, vals):
        if vals.get('concessionaire_id') and 'concessionaire_ids' not in vals:
            c_id = vals['concessionaire_id']
            vals['concessionaire_ids'] = [(4, c_id)]
        return super(ResUsers, self).write(vals)
