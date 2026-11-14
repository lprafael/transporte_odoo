# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class TransitUserCreateWizard(models.TransientModel):
    _name = 'transit.user.create.wizard'
    _description = 'Asistente de Creación de Operadores y Usuarios de Empresa (Multi-Tenant)'

    @api.model
    def default_get(self, fields_list):
        res = super(TransitUserCreateWizard, self).default_get(fields_list)
        user = self.env.user
        # Si el usuario actual pertenece a una concesionaria, precargarla
        if user.concessionaire_id:
            res['concessionaire_id'] = user.concessionaire_id.id
        elif user.concessionaire_ids:
            res['concessionaire_id'] = user.concessionaire_ids[0].id
        return res

    name = fields.Char(
        string='Nombre Completo',
        required=True
    )
    login = fields.Char(
        string='Usuario de Acceso / Email',
        required=True
    )
    password = fields.Char(
        string='Contraseña Inicial',
        required=True,
        default='Operador2026!'
    )
    phone = fields.Char(
        string='Teléfono / Móvil (Opcional)'
    )
    user_role = fields.Selection([
        ('operator', 'Operador / Despachador (Solo Despacho, Frecuencias y Flota)'),
        ('company_manager', 'Jefe de Tráfico / Administrador de Empresa (Gestión Integral de Flota, Rutas y Conductores)')
    ], string='Rol Asignado', required=True, default='operator')

    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Concesionaria',
        required=True,
        help='Empresa de transporte a la que quedará estrictamente limitado el nuevo usuario.'
    )
    is_global_manager = fields.Boolean(
        string='Es Administrador Global',
        compute='_compute_is_global_manager'
    )

    @api.depends_context('uid')
    def _compute_is_global_manager(self):
        is_mgr = self.env.user.has_group('transit_operations.group_transit_manager')
        for rec in self:
            rec.is_global_manager = is_mgr

    def action_create_user(self):
        self.ensure_one()
        current_user = self.env.user
        is_global = current_user.has_group('transit_operations.group_transit_manager')

        # 1. Validación estricta de seguridad Multi-Tenant
        if not is_global:
            # Un jefe de empresa solo puede crear usuarios para SU propia empresa
            allowed_conc_ids = current_user.concessionaire_ids.ids
            if current_user.concessionaire_id and current_user.concessionaire_id.id not in allowed_conc_ids:
                allowed_conc_ids.append(current_user.concessionaire_id.id)

            if not allowed_conc_ids:
                raise UserError("Su usuario no tiene ninguna Empresa Concesionaria asignada. Contacte al Administrador Global.")

            if self.concessionaire_id.id not in allowed_conc_ids:
                raise UserError("Operación denegada: Solo tiene autorización para crear usuarios dentro de su propia Empresa Concesionaria.")

            target_concessionaire = current_user.concessionaire_id or self.concessionaire_id
        else:
            target_concessionaire = self.concessionaire_id

        if not target_concessionaire:
            raise ValidationError("Debe especificar una Empresa Concesionaria válida.")

        # 2. Validar que el login no esté duplicado
        login_clean = self.login.strip().lower()
        existing = self.env['res.users'].sudo().search([('login', '=', login_clean)], limit=1)
        if existing:
            raise ValidationError(
                f"El usuario o correo '{login_clean}' ya está registrado en el sistema. Por favor elija un nombre de usuario diferente."
            )

        # 3. Armar lista de grupos seguros (estrictamente restringidos a la empresa)
        base_user = self.env.ref('base.group_user')
        transit_user = self.env.ref('transit_operations.group_transit_user')
        fleet_user = self.env.ref('fleet.fleet_group_user', raise_if_not_found=False)

        groups = [(4, base_user.id), (4, transit_user.id)]
        if fleet_user:
            groups.append((4, fleet_user.id))

        # Si se le asigna rol de Jefe de Tráfico de la Empresa
        if self.user_role == 'company_manager':
            transit_company_mgr = self.env.ref('transit_operations.group_transit_company_manager')
            groups.append((4, transit_company_mgr.id))
            fleet_mgr = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
            if fleet_mgr:
                groups.append((4, fleet_mgr.id))

        # 4. Crear el usuario en Odoo con sudo() para sobrepasar la restricción de crear res.users
        user_vals = {
            'name': self.name.strip(),
            'login': login_clean,
            'email': login_clean if '@' in login_clean else False,
            'password': self.password,
            'phone': self.phone.strip() if self.phone else False,
            'concessionaire_id': target_concessionaire.id,
            'concessionaire_ids': [(6, 0, [target_concessionaire.id])],
            'groups_id': groups,
            'notification_type': 'email',
            'active': True,
        }
        new_user = self.env['res.users'].sudo().create(user_vals)

        # 5. Asegurar vinculación bidireccional en la concesionaria
        target_concessionaire.sudo().write({
            'user_ids': [(4, new_user.id)]
        })

        # 6. Notificación y cierre
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Operador Creado Correctamente',
                'message': (
                    f"Se ha dado de alta al usuario '{new_user.name}' ({new_user.login}) "
                    f"vinculado exclusivamente a la empresa {target_concessionaire.name}."
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }
