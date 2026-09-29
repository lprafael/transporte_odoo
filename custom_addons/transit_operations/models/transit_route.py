# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitRoute(models.Model):
    _name = 'transit.route'
    _description = 'Línea e Itinerario de Transporte'
    _order = 'code asc, name asc'

    name = fields.Char(string='Nombre del Ramal / Línea', required=True)
    code = fields.Char(string='Código de Línea / Ramal', required=True, index=True)
    concessionaire_id = fields.Many2one('transit.concessionaire', string='Empresa Concesionaria Operadora', index=True)
    direction = fields.Selection([
        ('inbound', 'Ida'),
        ('outbound', 'Vuelta'),
        ('circular', 'Circular'),
    ], string='Sentido', default='inbound', required=True)

    origin = fields.Char(string='Cabecera Origen', required=True)
    destination = fields.Char(string='Cabecera Destino', required=True)
    distance_km = fields.Float(string='Distancia Total (km)', digits=(6, 2), default=0.0)
    standard_duration_minutes = fields.Integer(string='Tiempo Teórico de Viaje (minutos)', default=60)
    standard_fare = fields.Float(string='Tarifa Estándar (Gs.)', default=3400.0, help='Tarifa habitual de pasaje')

    # Coordenadas y Geocercas de Cabeceras
    origin_latitude = fields.Float(string='Latitud Origen', digits=(10, 6), default=-25.3412)
    origin_longitude = fields.Float(string='Longitud Origen', digits=(10, 6), default=-57.5123)
    origin_radius_meters = fields.Integer(string='Radio Cabecera Origen (m)', default=100)

    destination_latitude = fields.Float(string='Latitud Destino', digits=(10, 6), default=-25.2867)
    destination_longitude = fields.Float(string='Longitud Destino', digits=(10, 6), default=-57.6470)
    destination_radius_meters = fields.Integer(string='Radio Cabecera Destino (m)', default=100)

    checkpoint_ids = fields.One2many('transit.route.checkpoint', 'route_id', string='Puntos de Control / Geocercas')
    checkpoint_count = fields.Integer(string='Geocercas Configuradas', compute='_compute_checkpoint_count')

    shape_ids = fields.One2many('transit.route.shape', 'route_id', string='Historial de Trazados (Shapes)')
    shape_count = fields.Integer(string='Trazados / Desvíos', compute='_compute_shape_count')

    timetable_ids = fields.One2many('transit.timetable', 'route_id', string='Horarios Programados')
    timetable_count = fields.Integer(string='Frecuencias Programadas', compute='_compute_timetable_count')
    active = fields.Boolean(default=True)

    @api.depends('shape_ids')
    def _compute_shape_count(self):
        for rec in self:
            rec.shape_count = len(rec.shape_ids)

    @api.depends('checkpoint_ids')
    def _compute_checkpoint_count(self):
        for rec in self:
            rec.checkpoint_count = len(rec.checkpoint_ids)

    @api.depends('timetable_ids')
    def _compute_timetable_count(self):
        for rec in self:
            rec.timetable_count = len(rec.timetable_ids)

    def name_get(self):
        result = []
        for rec in self:
            direction_label = dict(rec._fields['direction'].selection).get(rec.direction, '')
            name = f"[{rec.code}] {rec.name} ({direction_label})"
            result.append((rec.id, name))
        return result
