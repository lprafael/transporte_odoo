# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TransitService(models.Model):
    _name = 'transit.service'
    _description = 'Servicio Operativo / Concesión de Transporte'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code asc, name asc'

    name = fields.Char(string='Nombre del Servicio', required=True, tracking=True)
    code = fields.Char(string='Código de Servicio', required=True, index=True, tracking=True,
                       help='Código identificador del servicio (ej. E1, E2, E3, B1, B2, L20)')
    description = fields.Text(string='Descripción del Itinerario / Servicio')
    active = fields.Boolean(string='Activo', default=True, tracking=True)

    # Empresa Concesionaria / Operadora
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Concesionaria / Operadora',
        required=True,
        tracking=True,
        index=True,
        help='Empresa operadora adjudicada titular de este servicio'
    )

    # Vigencia de la Adjudicación / Concesión
    contract_start_date = fields.Date(string='Inicio de Vigencia', tracking=True)
    contract_end_date = fields.Date(string='Fin de Vigencia', tracking=True)
    external_dashboard_url = fields.Char(string='Enlace Dashboard CID / Externo')
    cid_service_id = fields.Integer(string='ID Servicio CID', index=True,
                                    help='Identificador en el schema servicios_especiales de CID')

    # Cuota Operativa Diaria
    daily_target_departures = fields.Integer(
        string='Cuota Diaria de Salidas',
        default=0,
        tracking=True,
        help='Cantidad de salidas requeridas por resolución o contrato para este servicio (0 para calcular según programación).'
    )

    # --------------------------------------------------------------------------
    # PARÁMETROS DE MONITOREO Y TOLERANCIA OPERACIONAL (Resolución GVMT / CID)
    # --------------------------------------------------------------------------
    geofence_radius_m = fields.Integer(
        string='Radio Geocerca Cabecera (m)',
        default=150,
        required=True,
        tracking=True,
        help='Radio en metros alrededor del punto de cabecera (G1/G2) para detectar entrada/salida.'
    )
    itinerary_buffer_m = fields.Integer(
        string='Buffer Itinerario Oficial (m)',
        default=50,
        required=True,
        tracking=True,
        help='Distancia máxima permitida respecto al eje de la traza oficial antes de computar desvío.'
    )
    compliance_threshold_pct = fields.Float(
        string='Umbral Mínimo Cumplimiento (%)',
        default=80.0,
        required=True,
        tracking=True,
        help='Porcentaje mínimo de pings GPS dentro del itinerario para considerar el servicio VÁLIDO.'
    )
    incomplete_threshold_pct = fields.Float(
        string='Umbral Retorno Incompleto (%)',
        default=80.0,
        required=True,
        help='Porcentaje de recorrido para considerar que el bus alcanzó el retorno pero no completó.'
    )
    tolerance_early_min = fields.Integer(
        string='Tolerancia Adelanto Salida (min)',
        default=5,
        required=True,
        tracking=True,
        help='Minutos de tolerancia antes del horario programado (-t_antes). Salida anterior se considera Irregular.'
    )
    tolerance_late_min = fields.Integer(
        string='Tolerancia Atraso Salida (min)',
        default=10,
        required=True,
        tracking=True,
        help='Minutos de tolerancia después del horario programado (+t_despues). Salida posterior se considera Irregular.'
    )

    # Franja Horaria Operativa
    operating_window_start = fields.Char(
        string='Franja Horaria Inicio (HH:MM:SS)',
        default='04:00:00',
        required=True,
        help='Hora de inicio de la jornada operativa del servicio'
    )
    operating_window_end = fields.Char(
        string='Franja Horaria Fin (HH:MM:SS)',
        default='03:30:59',
        required=True,
        help='Hora de cierre de la jornada operativa'
    )
    spans_next_day = fields.Boolean(
        string='Jornada Pasa al Día Siguiente',
        default=True,
        help='Marcar si la jornada operativa concluye en la madrugada del día calendario siguiente'
    )

    # Identificadores telemáticos VMT
    agency_vmt_id = fields.Char(string='Agency ID VMT (Hex)', help='Ej: 004B, 0006, etc.')
    emisor_id = fields.Integer(string='ID Emisor Telemetría')

    # Relaciones Operativas
    route_ids = fields.One2many('transit.route', 'service_id', string='Rutas / Ramales Asociados')
    route_count = fields.Integer(string='Cant. Rutas', compute='_compute_counts')

    vehicle_ids = fields.One2many('fleet.vehicle', 'service_id', string='Buses Asignados al Servicio')
    vehicle_count = fields.Integer(string='Flota Asignada', compute='_compute_counts')

    timetable_ids = fields.One2many('transit.timetable', 'service_id', string='Horarios Programados')
    timetable_count = fields.Integer(string='Salidas Programadas', compute='_compute_counts')

    dispatch_ids = fields.One2many('transit.dispatch', 'service_id', string='Despachos Históricos')
    dispatch_count = fields.Integer(string='Total Despachos', compute='_compute_counts')

    @api.depends('route_ids', 'vehicle_ids', 'timetable_ids', 'dispatch_ids')
    def _compute_counts(self):
        for rec in self:
            rec.route_count = len(rec.route_ids)
            rec.vehicle_count = len(rec.vehicle_ids)
            rec.timetable_count = len(rec.timetable_ids)
            rec.dispatch_count = len(rec.dispatch_ids)

    def name_get(self):
        res = []
        for rec in self:
            code_str = f"[{rec.code}] " if rec.code else ""
            res.append((rec.id, f"{code_str}{rec.name}"))
        return res

    def action_sync_cid_monitoring_parameters(self):
        """Sincroniza los parámetros de monitoreo desde servicios_especiales.parametro_monitoreo"""
        for rec in self:
            if not rec.cid_service_id:
                continue
            self.env.cr.execute("""
                SELECT radio_geocerca_m, radio_itinerario_m, rango_cumplimiento_pct,
                       franja_hora_inicio, franja_hora_fin, tolerancia_antes_min,
                       tolerancia_despues_min, agency_ids, pasa_al_dia_siguiente
                FROM servicios_especiales.parametro_monitoreo
                WHERE id_servicio_especial = %s
                ORDER BY id_parametro DESC LIMIT 1;
            """, (rec.cid_service_id,))
            row = self.env.cr.dictfetchone()
            if row:
                rec.write({
                    'geofence_radius_m': row['radio_geocerca_m'] or 250,
                    'itinerary_buffer_m': row['radio_itinerario_m'] or 50,
                    'compliance_threshold_pct': float(row['rango_cumplimiento_pct'] or 80.0),
                    'operating_window_start': row['franja_hora_inicio'] or '04:00:00',
                    'operating_window_end': row['franja_hora_fin'] or '03:30:59',
                    'tolerance_early_min': row['tolerancia_antes_min'] or 5,
                    'tolerance_late_min': row['tolerancia_despues_min'] or 10,
                    'spans_next_day': bool(row['pasa_al_dia_siguiente']),
                    'agency_vmt_id': row['agency_ids'] or '004B',
                })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Parámetros CID Sincronizados',
                'message': 'Se actualizaron las reglas de monitoreo oficiales (04:00 a 03:30, tolerancias -5/+10m, geocercas y cumplimientos).',
                'type': 'success',
                'sticky': False,
            }
        }

