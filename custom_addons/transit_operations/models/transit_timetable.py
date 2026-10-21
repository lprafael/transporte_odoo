# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitTimetable(models.Model):
    _name = 'transit.timetable'
    _description = 'Horarios Planificados (Cuadro de Marcha)'
    _order = 'operational_time_float asc, service_number asc'

    route_id = fields.Many2one('transit.route', string='Ruta / Ramal', required=True, ondelete='cascade', index=True)
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        related='route_id.concessionaire_id',
        store=True,
        string='Empresa Concesionaria',
        index=True
    )
    service_id = fields.Many2one('transit.service', string='Servicio Especial / Concesión',
                                 related='route_id.service_id', store=True, index=True)
    service_code = fields.Char(string='Código de Servicio / Vuelta', help='Ej: S01, V04')
    service_number = fields.Integer(string='Nº Servicio Correlativo', default=1, index=True,
                                    help='Número correlativo de viaje en la jornada (ej. 1, 2, ... 46)')

    # Hora en formato decimal (ej: 6.5 = 06:30, 14.75 = 14:45)
    departure_time_float = fields.Float(string='Hora Salida Programada', required=True)
    # Eje operacional VMT / CID: La jornada comienza a las 04:00 y termina a las 03:30 del día siguiente
    operational_time_float = fields.Float(
        string='Hora Operativa (04:00 - 03:30)',
        compute='_compute_operational_time',
        store=True,
        index=True,
        help='Hora en el eje de la jornada operativa donde las salidas de 00:00 a 03:30 representan las horas 24.0 a 27.5 (+1 día)'
    )
    scheduled_duration_minutes = fields.Integer(
        string='Duración Estimada (min)',
        related='route_id.standard_duration_minutes',
        store=True,
        readonly=False
    )
    arrival_time_float = fields.Float(string='Hora Llegada Programada')

    horario_salida = fields.Char(string='Salida (HH:MM:SS)', compute='_compute_horarios_str', store=True)
    horario_llegada = fields.Char(string='Llegada (HH:MM:SS)', compute='_compute_horarios_str', store=True)

    # Régimen Oficial VMT / CID
    tipo_dia = fields.Selection([
        ('5', 'Laboral (Lunes a Viernes)'),
        ('6', 'Sábado'),
        ('7', 'Domingos y Feriados'),
    ], string='Régimen / Tipo de Día', default='5', required=True, index=True,
       help='5=Días hábiles laborales, 6=Sábados, 7=Domingos y Feriados oficiales')

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
    ], string='Día de la Semana (Compatibilidad)', default='all', required=True)

    direction = fields.Selection([
        ('ida', 'Ida'),
        ('vuelta', 'Vuelta'),
    ], string='Sentido', index=True)

    # Franjas Horarias Normativas para ICF (Decreto N° 710/2023)
    franja_horaria = fields.Selection([
        ('pico_manana', 'Pico Mañana (05:00–07:59)'),
        ('pos_pico_dia', 'Pos-Pico Día (08:00–15:59)'),
        ('pico_tarde', 'Pico Tarde (16:00–18:59)'),
        ('pos_pico_noche', 'Pos-Pico Noche (19:00–20:59)'),
        ('valle_noche', 'Valle / Nocturno'),
        ('fin_de_semana', 'Operación Fin de Semana / Feriado'),
    ], string='Franja Horaria Operativa', compute='_compute_franja_icf', store=True)

    tipo_franja_icf = fields.Selection([
        ('pico', 'Hora Pico'),
        ('pos_pico', 'Hora Pos-Pico'),
    ], string='Tipo Franja ICF (Apéndice 11)', compute='_compute_franja_icf', store=True)

    valid_from = fields.Date(string='Inicio Vigencia')
    valid_until = fields.Date(string='Fin Vigencia')
    cid_programacion_id = fields.Integer(string='ID Programación CID', index=True)

    active = fields.Boolean(default=True)

    @api.depends('departure_time_float')
    def _compute_operational_time(self):
        for rec in self:
            dep = rec.departure_time_float or 0.0
            # Jornada Eléctrica VMT: 04:00 a 03:30 (+1d). Si dep < 4.0, pasa al día siguiente (24.0 a 27.5)
            rec.operational_time_float = dep if dep >= 4.0 else (dep + 24.0)

    @api.depends('departure_time_float', 'arrival_time_float')
    def _compute_horarios_str(self):
        for rec in self:
            # Salida
            h_dep = int(rec.departure_time_float)
            m_dep = int(round((rec.departure_time_float - h_dep) * 60))
            if m_dep >= 60:
                h_dep += 1
                m_dep = 0
            rec.horario_salida = f"{h_dep:02d}:{m_dep:02d}:00"

            # Llegada
            if rec.arrival_time_float is not False and rec.arrival_time_float is not None:
                h_arr = int(rec.arrival_time_float)
                m_arr = int(round((rec.arrival_time_float - h_arr) * 60))
                if m_arr >= 60:
                    h_arr += 1
                    m_arr = 0
                rec.horario_llegada = f"{h_arr:02d}:{m_arr:02d}:00"
            else:
                rec.horario_llegada = False

    @api.depends('departure_time_float', 'tipo_dia')
    def _compute_franja_icf(self):
        for rec in self:
            dep = rec.departure_time_float or 0.0
            td = rec.tipo_dia or '5'

            if td in ('6', '7'):
                rec.franja_horaria = 'fin_de_semana'
                rec.tipo_franja_icf = 'pos_pico'
            else:
                # Días Laborales
                if 5.0 <= dep < 8.0:
                    rec.franja_horaria = 'pico_manana'
                    rec.tipo_franja_icf = 'pico'
                elif 8.0 <= dep < 16.0:
                    rec.franja_horaria = 'pos_pico_dia'
                    rec.tipo_franja_icf = 'pos_pico'
                elif 16.0 <= dep < 19.0:
                    rec.franja_horaria = 'pico_tarde'
                    rec.tipo_franja_icf = 'pico'
                elif 19.0 <= dep < 21.0:
                    rec.franja_horaria = 'pos_pico_noche'
                    rec.tipo_franja_icf = 'pos_pico'
                else:
                    rec.franja_horaria = 'valle_noche'
                    rec.tipo_franja_icf = 'pos_pico'

    def name_get(self):
        result = []
        for rec in self:
            hours = int(rec.departure_time_float)
            minutes = int(round((rec.departure_time_float - hours) * 60))
            time_str = f"{hours:02d}:{minutes:02d}"
            plus_day = " (+1d)" if rec.departure_time_float < 4.0 else ""
            route_code = rec.route_id.code if rec.route_id else 'Ruta'
            svc = rec.service_code or (f"S{rec.service_number:02d}" if rec.service_number else 'Servicio')
            name = f"[{route_code}] {time_str}{plus_day} ({svc})"
            result.append((rec.id, name))
        return result
