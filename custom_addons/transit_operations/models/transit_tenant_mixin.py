# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TransitTenantMixin(models.AbstractModel):
    _name = 'transit.tenant.mixin'
    _description = 'Mixin de Aislamiento Multi-Tenant para Transporte'

    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Concesionaria',
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self._default_concessionaire_id(),
        help='Empresa de transporte concesionada titular del registro.'
    )

    @api.model
    def _default_concessionaire_id(self):
        user = self.env.user
        if user.concessionaire_id:
            return user.concessionaire_id.id
        if user.concessionaire_ids:
            return user.concessionaire_ids[0].id
        return False

    @api.constrains('concessionaire_id')
    def _check_concessionaire_permission(self):
        # El Administrador Global / superusuario no tiene restricciones
        if self.env.is_superuser() or self.env.user.has_group('transit_operations.group_transit_manager'):
            return

        user_allowed_ids = set(self.env.user.concessionaire_ids.ids)
        if self.env.user.concessionaire_id:
            user_allowed_ids.add(self.env.user.concessionaire_id.id)

        for rec in self:
            if rec.concessionaire_id and rec.concessionaire_id.id not in user_allowed_ids:
                raise ValidationError(
                    f"Violación de Seguridad Multi-Tenant: No tiene permisos para asignar o manipular registros de la empresa '{rec.concessionaire_id.name}'."
                )
