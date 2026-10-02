# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitTimetable(models.Model):
    _name = 'transit.timetable'
    _description = 'Horarios Planificados (Cuadro de Marcha)'
    _order = 'departure_time_float asc'

    route_id = fields.Many2one('transit.route', string='Ruta / Ramal', required=True, ondelete='cascade')
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        related='route_id.concessionaire_id',
        store=True,
        string='Empresa Concesionaria',
        index=True
    )
    service_code = fields.Char(string='Código de Servicio / Vuelta', help='Ej: S01, V04')
    
    # Hora en formato decimal (ej: 6.5 = 06:30, 14.75 = 14:45)
    departure_time_float = fields.Float(string='Hora Salida Programada', required=True)
    scheduled_duration_minutes = fields.Integer(
        string='Duración Estimada (min)',
        related='route_id.standard_duration_minutes',
        store=True,
        readonly=False
    )

    day_of_week = fields.Selection([
        ('all', 'Todos los Días'),
        ('weekday', 'Lunes a Viernes'),
        ('weekend', 'Sábados y Domingos'),
        ('0', 'Lunes'),
        ('1', 'Martes'),
        ('2', 'Miércoles'),
        ('3', 'Jueves'),
        ('4', 'Viernes'),
        ('5', 'Sábado'),
        ('6', 'Domingo'),
    ], string='Día de Operación', default='all', required=True)

    direction = fields.Selection([
        ('ida', 'Ida'),
        ('vuelta', 'Vuelta'),
    ], string='Sentido')
    
    arrival_time_float = fields.Float(string='Hora Llegada Programada')
    valid_from = fields.Date(string='Inicio Vigencia')
    valid_until = fields.Date(string='Fin Vigencia')
    cid_programacion_id = fields.Integer(string='ID Programación CID', index=True)

    active = fields.Boolean(default=True)

    def name_get(self):
        result = []
        for rec in self:
            hours = int(rec.departure_time_float)
            minutes = int(round((rec.departure_time_float - hours) * 60))
            time_str = f"{hours:02d}:{minutes:02d}"
            route_code = rec.route_id.code if rec.route_id else 'Ruta'
            svc = rec.service_code or 'Servicio'
            name = f"[{route_code}] {time_str} ({svc})"
            result.append((rec.id, name))
        return result
