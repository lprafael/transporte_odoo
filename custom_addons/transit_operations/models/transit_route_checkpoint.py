# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitRouteCheckpoint(models.Model):
    _name = 'transit.route.checkpoint'
    _description = 'Punto de Control / Geocerca de Ruta'
    _order = 'route_id, sequence asc, id asc'

    route_id = fields.Many2one('transit.route', string='Ruta / Ramal', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Orden / Secuencia', default=10)
    name = fields.Char(string='Nombre de Parada / Geocerca', required=True)
    checkpoint_type = fields.Selection([
        ('origin', 'Cabecera de Salida'),
        ('stop', 'Parada de Control Intermedia'),
        ('destination', 'Cabecera de Llegada'),
    ], string='Tipo de Geocerca', default='stop', required=True)

    latitude = fields.Float(string='Latitud GPS', digits=(10, 6), required=True, default=-25.2867)
    longitude = fields.Float(string='Longitud GPS', digits=(10, 6), required=True, default=-57.6470)
    radius_meters = fields.Integer(string='Radio Geocerca (m)', default=60, help='Radio circular de detección para la geocerca')
    offset_minutes = fields.Integer(string='Minutos desde Salida', default=10, help='Tiempo estimado de llegada desde la hora de salida de cabecera')
    active = fields.Boolean(default=True)
