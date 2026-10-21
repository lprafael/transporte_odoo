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

    # Configuración de Avisos Automáticos por WhatsApp a Choferes
    transit_whatsapp_enabled = fields.Boolean(
        string='Habilitar Avisos por WhatsApp',
        config_parameter='transit.whatsapp_enabled',
        default=True,
        help='Envía recordatorios automáticos por WhatsApp a los conductores antes de iniciar su turno'
    )
    transit_whatsapp_minutes_before = fields.Integer(
        string='Minutos de Anticipación',
        config_parameter='transit.whatsapp_minutes_before',
        default=20,
        help='Minutos previos al inicio del turno para disparar la alerta (por defecto 20 min)'
    )
    transit_whatsapp_provider = fields.Selection([
        ('custom_webhook', 'Gateway REST / Webhook HTTP (Evolution API, Baileys, etc.)'),
        ('meta_cloud', 'Meta WhatsApp Cloud API Oficial'),
        ('manual_wa_link', 'Enlace Directo WhatsApp Web (Solo Manual)'),
    ], string='Proveedor de WhatsApp', config_parameter='transit.whatsapp_provider', default='custom_webhook')

    transit_whatsapp_api_url = fields.Char(
        string='URL de la API / Webhook',
        config_parameter='transit.whatsapp_api_url',
        default='http://localhost:8080/message/sendText',
        help='Endpoint POST del gateway de WhatsApp'
    )
    transit_whatsapp_api_token = fields.Char(
        string='API Token / Apikey',
        config_parameter='transit.whatsapp_api_token',
        help='Token secreto de autorización para el gateway'
    )
    transit_whatsapp_instance = fields.Char(
        string='Instancia / Session ID',
        config_parameter='transit.whatsapp_instance',
        default='transporte_bot',
        help='Identificador de instancia para Evolution API o Z-API'
    )
    transit_whatsapp_template = fields.Text(
        string='Plantilla del Mensaje de Alerta',
        config_parameter='transit.whatsapp_template',
        default="""👋 ¡Hola, *{driver_name}*! 🚌
Te recordamos que tu turno inicia en *{minutes} minutos* (a las *{departure_time}* hs).

📋 *Detalles del Servicio:*
• *Bus / Interno:* #{bus_number} (Placa: {license_plate})
• *Línea / Servicio:* {service_name}
• *Sentido:* {direction}
• *Tramo / Ruta:* {route_name}

⚠️ _Por favor preséntate en cabecera con uniforme para la inspección pre-operativa._ ¡Buen viaje! 🚦👍""",
        help='Plantilla con variables: {driver_name}, {minutes}, {departure_time}, {bus_number}, {license_plate}, {service_name}, {direction}, {route_name}'
    )
