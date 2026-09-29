# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitDispatchCheckpoint(models.Model):
    _name = 'transit.dispatch.checkpoint'
    _description = 'Punto de Control / Parada de Itinerario'
    _order = 'sequence asc, id asc'

    dispatch_id = fields.Many2one('transit.dispatch', string='Despacho', ondelete='cascade', required=True)
    sequence = fields.Integer(string='Orden', default=10)
    name = fields.Char(string='Nombre Parada / Checkpoint', required=True)
    checkpoint_type = fields.Selection([
        ('origin', 'Cabecera Salida'),
        ('stop', 'Parada de Control Intermedia'),
        ('destination', 'Cabecera Llegada'),
    ], string='Tipo', default='stop')

    latitude = fields.Float(string='Latitud', digits=(10, 6))
    longitude = fields.Float(string='Longitud', digits=(10, 6))
    radius_meters = fields.Integer(string='Radio Geocerca (m)', default=60)

    scheduled_time = fields.Datetime(string='Hora Teórica de Paso')
    actual_time = fields.Datetime(string='Hora Real de Paso')
    delay_minutes = fields.Float(string='Desvío (min)', compute='_compute_delay', store=True)
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('crossed', 'Registrado / Cruzado'),
        ('skipped', 'Omitido / No detectado'),
    ], string='Estado de Paso', default='pending')

    @api.depends('scheduled_time', 'actual_time')
    def _compute_delay(self):
        for rec in self:
            if rec.scheduled_time and rec.actual_time:
                diff_seconds = (rec.actual_time - rec.scheduled_time).total_seconds()
                rec.delay_minutes = round(diff_seconds / 60.0, 1)
            else:
                rec.delay_minutes = 0.0
