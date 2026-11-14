# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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
    transit_role_name = fields.Char(
        string='Rol Operativo',
        compute='_compute_transit_role_name'
    )

    def _compute_transit_role_name(self):
        mgr_global = self.env.ref('transit_operations.group_transit_manager', raise_if_not_found=False)
        mgr_company = self.env.ref('transit_operations.group_transit_company_manager', raise_if_not_found=False)
        user_transit = self.env.ref('transit_operations.group_transit_user', raise_if_not_found=False)

        for u in self:
            if mgr_global and mgr_global in u.groups_id:
                u.transit_role_name = 'Administrador Global / Regulador'
            elif mgr_company and mgr_company in u.groups_id:
                u.transit_role_name = 'Jefe de Tráfico / Administrador de Empresa'
            elif user_transit and user_transit in u.groups_id:
                u.transit_role_name = 'Operador / Despachador'
            else:
                u.transit_role_name = 'Usuario Interno'

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

    @api.model
    def action_open_company_users(self):
        """Abre la vista de operadores filtrada estrictamente por multi-tenant."""
        user = self.env.user
        domain = [('concessionaire_id', '!=', False)]

        if not user.has_group('transit_operations.group_transit_manager'):
            allowed = set(user.concessionaire_ids.ids)
            if user.concessionaire_id:
                allowed.add(user.concessionaire_id.id)
            domain = [('concessionaire_id', 'in', list(allowed))]

        list_view = self.env.ref('transit_operations.view_transit_company_users_list', raise_if_not_found=False)
        form_view = self.env.ref('transit_operations.view_transit_company_users_form', raise_if_not_found=False)

        views = []
        if list_view:
            views.append((list_view.id, 'list'))
        if form_view:
            views.append((form_view.id, 'form'))

        return {
            'name': 'Operadores y Usuarios de Empresa',
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'views': views or [(False, 'list'), (False, 'form')],
            'domain': domain,
            'context': {
                'default_concessionaire_id': user.concessionaire_id.id if user.concessionaire_id else False,
            }
        }

    def action_reset_password_wizard(self):
        """Abre el asistente de reseteo de contraseña para este operador."""
        self.ensure_one()
        current_user = self.env.user

        if not current_user.has_group('transit_operations.group_transit_manager'):
            allowed = set(current_user.concessionaire_ids.ids)
            if current_user.concessionaire_id:
                allowed.add(current_user.concessionaire_id.id)

            if self.concessionaire_id.id not in allowed:
                raise UserError("Solo puede modificar operadores que pertenezcan a su propia Empresa Concesionaria.")

        return {
            'name': f'Cambiar Contraseña: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'transit.user.password.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            }
        }
