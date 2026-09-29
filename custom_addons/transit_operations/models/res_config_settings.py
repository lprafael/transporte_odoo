# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Configuración de Conexión con Denarius / SIFEN
    denarius_api_url = fields.Char(
        string='URL API Denarius (Backend SIFEN)',
        config_parameter='transit.denarius_api_url',
        default='http://host.docker.internal:8085',
        help='URL del servicio backend de Denarius (ej: http://host.docker.internal:8085)'
    )
    denarius_api_token = fields.Char(
        string='Token de Autenticación Denarius',
        config_parameter='transit.denarius_api_token',
        help='Bearer Token para autenticación en la API de Denarius'
    )
    sifen_ambiente = fields.Selection([
        ('test', 'Test / Homologación (e-Kuatia)'),
        ('prod', 'Producción (SIFEN Oficial)'),
    ], string='Ambiente SIFEN', config_parameter='transit.sifen_ambiente', default='test')

    sifen_emisor_ruc = fields.Char(
        string='RUC de la Empresa Emisora',
        config_parameter='transit.sifen_emisor_ruc',
        default='80012345'
    )
    sifen_emisor_dv = fields.Char(
        string='Dígito Verificador (DV)',
        config_parameter='transit.sifen_emisor_dv',
        default='6',
        size=1
    )
    sifen_emisor_razon_social = fields.Char(
        string='Razón Social Emisor',
        config_parameter='transit.sifen_emisor_razon_social',
        default='EMPRESA DE TRANSPORTE S.A.'
    )
    sifen_tipo_contribuyente = fields.Selection([
        ('1', 'Persona Física'),
        ('2', 'Persona Jurídica'),
    ], string='Tipo de Contribuyente', config_parameter='transit.sifen_tipo_contribuyente', default='2')
