# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campos de Conductor / Chofer y Concesionarias
    is_driver = fields.Boolean(string='Es Chofer / Conductor', default=False)
    is_concessionaire = fields.Boolean(string='Es Empresa Concesionaria / Operadora', default=False)
    driver_license_number = fields.Char(string='Nº Registro / Licencia')
    driver_license_category = fields.Selection([
        ('prof_a', 'Profesional A (Transporte Pasajeros Internacional)'),
        ('prof_b', 'Profesional B (Transporte Público / Masivo)'),
        ('prof_c', 'Profesional C (Cargas Pesadas)'),
        ('particular', 'Particular'),
    ], string='Categoría de Licencia')
    driver_license_expiry = fields.Date(string='Vencimiento Licencia')
    driver_license_status = fields.Selection([
        ('valid', 'Habilitada'),
        ('warning', 'Por Vencer (30 días)'),
        ('expired', 'Vencida / Inhabilitado'),
    ], string='Estado de Licencia', compute='_compute_license_status')

    # Campos Fiscales Paraguay (SIFEN / DNIT)
    vat_ruc = fields.Char(string='RUC Base', help='RUC sin dígito verificador')
    vat_dv = fields.Char(string='DV', size=1, help='Dígito Verificador del RUC')
    sifen_doc_type = fields.Selection([
        ('1', 'Cédula de Identidad Paraguaya'),
        ('2', 'Pasaporte'),
        ('3', 'RUC'),
        ('4', 'Innominado / Consumidor Final'),
    ], string='Tipo Doc. Fiscal', default='1')

    @api.depends('driver_license_expiry', 'is_driver')
    def _compute_license_status(self):
        today = date.today()
        warning_delta = timedelta(days=30)
        for rec in self:
            if not rec.is_driver:
                rec.driver_license_status = 'valid'
                continue
            if not rec.driver_license_expiry:
                rec.driver_license_status = 'expired'
            elif rec.driver_license_expiry < today:
                rec.driver_license_status = 'expired'
            elif rec.driver_license_expiry <= (today + warning_delta):
                rec.driver_license_status = 'warning'
            else:
                rec.driver_license_status = 'valid'
