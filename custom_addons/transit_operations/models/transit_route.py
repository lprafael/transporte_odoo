# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitRoute(models.Model):
    _name = 'transit.route'
    _description = 'Línea e Itinerario de Transporte'
    _order = 'code asc, name asc'

    name = fields.Char(string='Nombre del Ramal / Línea', required=True)
    code = fields.Char(string='Código de Línea / Ramal', required=True, index=True)
    concessionaire_id = fields.Many2one('transit.concessionaire', string='Empresa Concesionaria Operadora', index=True)
    service_id = fields.Many2one('transit.service', string='Servicio Operativo / Concesión', index=True, ondelete='set null')
    line_name = fields.Char(string='Línea Comercial', compute='_compute_line_name', store=True, readonly=False, index=True,
                            help='Línea de transporte adjudicada (ej. Línea 15, Línea 47, Línea 20, Línea 187)')
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

    # Geocerca de Retorno al 80% (Detección de Servicios Incompletos - Tipo 5 CID)
    return_80_latitude = fields.Float(string='Latitud Punto de Retorno (80%)', digits=(10, 6))
    return_80_longitude = fields.Float(string='Longitud Punto de Retorno (80%)', digits=(10, 6))
    return_80_radius_meters = fields.Integer(string='Radio Punto de Retorno (m)', default=150)

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

    @api.depends('code', 'name', 'service_id', 'concessionaire_id')
    def _compute_line_name(self):
        for rec in self:
            if rec.line_name:
                continue
            c_code = (rec.concessionaire_id.code or '').upper()
            c_name = (rec.concessionaire_id.name or '').upper()
            r_code = (rec.code or '').lower()
            r_name = (rec.name or '').upper()
            s_name = (rec.service_id.name or '').upper() if rec.service_id else ''

            if '0008' in c_code or 'GUARANI' in c_name:
                if r_code in ('0052', '0053', '0054', '0055', '0056', '0057', '0058', '0059', '0185', '0186', '01a2', '01a3') or '47' in r_name or '47' in s_name:
                    rec.line_name = 'Línea 47'
                else:
                    rec.line_name = 'Línea 15'
            elif 'ARAPOTI' in c_code or 'ARAPOTÍ' in c_name:
                rec.line_name = 'Línea 20'
            elif '002A' in c_code or 'SAN JOSE' in c_name or '187' in r_name or '187' in s_name:
                rec.line_name = 'Línea 187'
            elif 'SL01' in c_code or 'SAN LORENZO' in c_name or '27' in r_name:
                rec.line_name = 'Línea 27'
            else:
                rec.line_name = rec.service_id.name if rec.service_id else (rec.concessionaire_id.name or 'Línea General')

    @api.depends('code', 'name', 'direction', 'line_name')
    def _compute_display_name(self):
        for rec in self:
            direction_label = dict(rec._fields['direction'].selection).get(rec.direction, '')
            prefix = f"[{rec.line_name}] " if rec.line_name else ""
            rec.display_name = f"{prefix}[{rec.code}] {rec.name} ({direction_label})"

    def name_get(self):
        result = []
        for rec in self:
            direction_label = dict(rec._fields['direction'].selection).get(rec.direction, '')
            prefix = f"[{rec.line_name}] " if rec.line_name else ""
            name = f"{prefix}[{rec.code}] {rec.name} ({direction_label})"
            result.append((rec.id, name))
        return result
