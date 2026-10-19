# -*- coding: utf-8 -*-
from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa de Transporte',
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self._default_concessionaire_id(),
        help='Empresa concesionaria a la que pertenece el empleado.'
    )

    transit_role = fields.Selection([
        ('driver', 'Chofer / Conductor'),
        ('mechanic', 'Mecánico / Taller'),
        ('dispatcher', 'Despachador / Jefe de Tráfico'),
        ('inspector', 'Inspector de Línea'),
        ('admin', 'Administrativo / Finanzas'),
    ], string='Rol Operativo en Transporte', default='driver', required=True, tracking=True)

    # Datos específicos si es chofer
    driver_code = fields.Char(string='Código de Ficha / Chofer', tracking=True)
    driver_license_number = fields.Char(string='Nº Licencia de Conducir', tracking=True)
    driver_license_category = fields.Selection([
        ('prof_a', 'Profesional A (Transporte Pasajeros Internacional)'),
        ('prof_b', 'Profesional B (Transporte Público / Masivo)'),
        ('prof_c', 'Profesional C (Cargas Pesadas)'),
        ('particular', 'Particular'),
    ], string='Categoría de Licencia')
    driver_license_expiry = fields.Date(string='Vencimiento Licencia', tracking=True)
    driver_ci_expiry = fields.Date(string='Vencimiento Cédula', tracking=True)
    mtess_date = fields.Date(string='Fecha Registro MTESS', tracking=True)
    ips_date = fields.Date(string='Fecha Registro IPS', tracking=True)

    @api.model
    def _default_concessionaire_id(self):
        user = self.env.user
        if user.concessionaire_id:
            return user.concessionaire_id.id
        if user.concessionaire_ids:
            return user.concessionaire_ids[0].id
        return False

    @api.model_create_multi
    def create(self, vals_list):
        employees = super(HrEmployee, self).create(vals_list)
        for emp in employees:
            if emp.transit_role == 'driver':
                partner = emp.work_contact_id
                if not partner:
                    partner = self.env['res.partner'].sudo().create({
                        'name': emp.name,
                        'is_driver': True,
                        'concessionaire_id': emp.concessionaire_id.id,
                        'driver_code': emp.driver_code,
                        'driver_license_number': emp.driver_license_number,
                        'driver_license_category': emp.driver_license_category,
                        'driver_license_expiry': emp.driver_license_expiry,
                        'driver_ci_expiry': emp.driver_ci_expiry,
                        'mtess_date': emp.mtess_date,
                        'ips_date': emp.ips_date,
                    })
                    emp.sudo().write({'work_contact_id': partner.id})
                else:
                    partner.sudo().write({
                        'is_driver': True,
                        'concessionaire_id': emp.concessionaire_id.id,
                        'driver_code': emp.driver_code,
                        'driver_license_number': emp.driver_license_number,
                        'driver_license_category': emp.driver_license_category,
                        'driver_license_expiry': emp.driver_license_expiry,
                        'driver_ci_expiry': emp.driver_ci_expiry,
                        'mtess_date': emp.mtess_date,
                        'ips_date': emp.ips_date,
                    })
        return employees

    def write(self, vals):
        res = super(HrEmployee, self).write(vals)
        for emp in self:
            if emp.transit_role == 'driver' and emp.work_contact_id:
                update_vals = {}
                if 'concessionaire_id' in vals:
                    update_vals['concessionaire_id'] = emp.concessionaire_id.id
                if 'driver_code' in vals:
                    update_vals['driver_code'] = emp.driver_code
                if 'driver_license_number' in vals:
                    update_vals['driver_license_number'] = emp.driver_license_number
                if 'driver_license_category' in vals:
                    update_vals['driver_license_category'] = emp.driver_license_category
                if 'driver_license_expiry' in vals:
                    update_vals['driver_license_expiry'] = emp.driver_license_expiry
                if 'driver_ci_expiry' in vals:
                    update_vals['driver_ci_expiry'] = emp.driver_ci_expiry
                if 'mtess_date' in vals:
                    update_vals['mtess_date'] = emp.mtess_date
                if 'ips_date' in vals:
                    update_vals['ips_date'] = emp.ips_date
                if update_vals:
                    update_vals['is_driver'] = True
                    emp.work_contact_id.sudo().write(update_vals)
        return res
