# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class TransitUserPasswordWizard(models.TransientModel):
    _name = 'transit.user.password.wizard'
    _description = 'Asistente de Cambio / Restablecimiento de Contraseña para Operadores'

    user_id = fields.Many2one(
        'res.users',
        string='Usuario / Operador',
        required=True,
        readonly=True
    )
    user_name = fields.Char(related='user_id.name', string='Nombre del Operador', readonly=True)
    user_login = fields.Char(related='user_id.login', string='Login / Email', readonly=True)
    concessionaire_id = fields.Many2one(related='user_id.concessionaire_id', string='Empresa', readonly=True)
    new_password = fields.Char(
        string='Nueva Contraseña',
        required=True
    )

    def action_reset_password(self):
        self.ensure_one()
        current_user = self.env.user
        target_user = self.user_id

        # 1. Protección contra escalamiento: No se puede cambiar clave de administradores globales
        if target_user.has_group('base.group_system') or target_user.has_group('transit_operations.group_transit_manager'):
            raise UserError("No está permitido modificar la contraseña de un Administrador Global del Sistema desde este asistente.")

        # 2. Control Multi-Tenant estricto para Jefes de Empresa
        if not current_user.has_group('transit_operations.group_transit_manager'):
            allowed_conc_ids = current_user.concessionaire_ids.ids
            if current_user.concessionaire_id and current_user.concessionaire_id.id not in allowed_conc_ids:
                allowed_conc_ids.append(current_user.concessionaire_id.id)

            if target_user.concessionaire_id.id not in allowed_conc_ids:
                raise UserError("Operación denegada: Solo puede restablecer contraseñas de operadores de su propia Empresa Concesionaria.")

        if not self.new_password or len(self.new_password.strip()) < 6:
            raise ValidationError("La contraseña debe contener al menos 6 caracteres.")

        # 3. Aplicar cambio con sudo
        target_user.sudo().write({'password': self.new_password.strip()})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Contraseña Actualizada',
                'message': f"Se actualizó la contraseña para el usuario {target_user.name} ({target_user.login}).",
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }
