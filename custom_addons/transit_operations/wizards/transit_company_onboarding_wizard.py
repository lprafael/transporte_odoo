# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class TransitCompanyOnboardingWizard(models.TransientModel):
    _name = 'transit.company.onboarding.wizard'
    _description = 'Asistente de Alta y Provisión de Empresa de Transporte (Multi-Tenant)'

    # 1. Datos de la Empresa Concesionaria
    company_name = fields.Char(string='Nombre Comercial de la Empresa', required=True, placeholder='Ej: Consorcio Arapotí')
    agency_id = fields.Char(
        string='Código Telemática / VMT (Agency ID)',
        required=True,
        placeholder='Ej: 004B',
        help='Código que transmitirán los dispositivos GPS en el campo agency_id del payload.'
    )
    code = fields.Char(
        string='Código Interno de Concesión',
        required=True,
        placeholder='Ej: CONC-01',
        help='Identificador único interno dentro del ERP.'
    )
    legal_name = fields.Char(string='Razón Social Oficial', placeholder='Ej: Consorcio Arapotí S.A.')
    vat_ruc = fields.Char(string='RUC / Identificación Fiscal', placeholder='Ej: 80099887-1')
    address = fields.Char(string='Dirección Base / Patio Central')
    contact_phone = fields.Char(string='Teléfono de Contacto')
    contact_email = fields.Char(string='Correo Electrónico Institucional')

    # 2. Usuario Inicial Administrador / Jefe de Tráfico
    admin_name = fields.Char(string='Nombre del Responsable', required=True, placeholder='Ej: Juan Pérez')
    admin_login = fields.Char(string='Usuario de Acceso (Login / Email)', required=True, placeholder='Ej: trafico@arapoti.com.py')
    admin_password = fields.Char(string='Contraseña Inicial', required=True, default='Transporte2026!')

    def action_create_company(self):
        self.ensure_one()
        
        # Validar duplicados de agency_id o code
        existing = self.env['transit.concessionaire'].search([
            '|', ('agency_id', '=', self.agency_id.strip()),
                 ('code', '=', self.code.strip())
        ], limit=1)
        if existing:
            raise ValidationError(
                f"Ya existe una empresa registrada con Agency ID '{existing.agency_id}' o Código '{existing.code}': {existing.name}."
            )

        # 1. Crear la Concesionaria
        concessionaire = self.env['transit.concessionaire'].create({
            'name': self.company_name.strip(),
            'agency_id': self.agency_id.strip(),
            'code': self.code.strip(),
            'legal_name': self.legal_name.strip() if self.legal_name else self.company_name.strip(),
            'vat_ruc': self.vat_ruc.strip() if self.vat_ruc else False,
            'address': self.address.strip() if self.address else False,
            'contact_phone': self.contact_phone.strip() if self.contact_phone else False,
            'active': True,
        })

        # 2. Asignar grupos de Jefe de Tráfico
        group_user = self.env.ref('transit_operations.group_transit_user')
        group_company_mgr = self.env.ref('transit_operations.group_transit_company_manager')
        group_fleet_user = self.env.ref('fleet.fleet_group_user')
        group_base_user = self.env.ref('base.group_user')

        groups = [
            (4, group_base_user.id),
            (4, group_user.id),
            (4, group_company_mgr.id),
            (4, group_fleet_user.id),
        ]

        # 3. Crear el Usuario por el ORM oficial (genera hash de contraseña correcto y partner vinculado)
        user = self.env['res.users'].create({
            'name': self.admin_name.strip(),
            'login': self.admin_login.strip(),
            'password': self.admin_password,
            'email': self.admin_login.strip() if '@' in self.admin_login else False,
            'concessionaire_id': concessionaire.id,
            'concessionaire_ids': [(4, concessionaire.id)],
            'groups_id': groups,
            'notification_type': 'email',
        })

        # 4. Vincular el usuario a la concesionaria
        concessionaire.write({'user_ids': [(4, user.id)]})

        # Retornar la vista de la concesionaria recién creada
        return {
            'type': 'ir.actions.act_window',
            'name': f'Empresa: {concessionaire.name}',
            'res_model': 'transit.concessionaire',
            'res_id': concessionaire.id,
            'view_mode': 'form',
            'target': 'current',
        }
