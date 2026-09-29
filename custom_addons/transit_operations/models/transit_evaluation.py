# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TransitConcessionaireEvaluation(models.Model):
    _name = 'transit.concessionaire.evaluation'
    _description = 'Matriz Ponderada de Evaluación de Concesionarios (UNE-EN 13816 / APP)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'final_score desc, id desc'

    name = fields.Char(string='Referencia de Auditoría', required=True, copy=False)
    clearing_period_id = fields.Many2one('transit.clearing.period', string='Período Liquidado', ondelete='set null')
    concessionaire_id = fields.Many2one('transit.concessionaire', string='Empresa Concesionaria', required=True)
    date_evaluation = fields.Date(string='Fecha de Auditoría', default=fields.Date.context_today, required=True)
    auditor_id = fields.Many2one('res.users', string='Auditor Técnico Responsable', default=lambda self: self.env.user)

    # --------------------------------------------------------------------------
    # PILAR 1: OPERACIÓN (Ponderación 23%)
    # --------------------------------------------------------------------------
    score_punctuality = fields.Float(string='Puntualidad en Salidas (0-100)', default=100.0)
    score_itinerary_compliance = fields.Float(string='Cumplimiento de Itinerarios y Geocercas (0-100)', default=100.0)
    score_ipk_goal = fields.Float(string='Cumplimiento de Metas IPK (0-100)', default=100.0)
    subtotal_operation = fields.Float(
        string='Subtotal Operación (23%)',
        compute='_compute_scores',
        store=True,
        digits=(5, 2),
        help='Ponderación: 23% de la calificación general.'
    )

    # --------------------------------------------------------------------------
    # PILAR 2: CALIDAD DEL SERVICIO (Ponderación 22%)
    # --------------------------------------------------------------------------
    score_mechanical_inspection = fields.Float(string='Aprobación Revista Mecánica Semestral (0-100)', default=100.0)
    score_maintenance_plan = fields.Float(string='Ejecución de Mantenimiento Preventivo (0-100)', default=100.0)
    score_fleet_age = fields.Float(string='Edad Promedio y Renovación del Parque (0-100)', default=100.0)
    score_vehicle_cleanliness = fields.Float(string='Aseo e Imagen de Unidades y Uniformidad (0-100)', default=100.0)
    subtotal_quality = fields.Float(
        string='Subtotal Calidad de Servicio (22%)',
        compute='_compute_scores',
        store=True,
        digits=(5, 2),
        help='Ponderación: 22% de la calificación general.'
    )

    # --------------------------------------------------------------------------
    # PILAR 3: SEGURIDAD (Ponderación 24%)
    # --------------------------------------------------------------------------
    score_accident_rate = fields.Float(string='Baja Siniestralidad por 100.000 km (0-100)', default=100.0)
    score_traffic_infractions = fields.Float(string='Control de Infracciones de Tránsito (0-100)', default=100.0)
    score_citizen_complaints = fields.Float(string='Bajo Índice de Quejas Ciudadanas (0-100)', default=100.0)
    subtotal_security = fields.Float(
        string='Subtotal Seguridad (24%)',
        compute='_compute_scores',
        store=True,
        digits=(5, 2),
        help='Ponderación: 24% de la calificación general.'
    )

    # --------------------------------------------------------------------------
    # PILAR 4: INFRAESTRUCTURA (Ponderación 18%)
    # --------------------------------------------------------------------------
    score_depot_cleanliness = fields.Float(string='Limpieza en Patios y Terminales (0-100)', default=100.0)
    score_lighting_signage = fields.Float(string='Iluminación LED, Señalética y Extintores (0-100)', default=100.0)
    score_operator_welfare = fields.Float(string='Sanitarios, Agua y Descanso para Choferes (0-100)', default=100.0)
    subtotal_infrastructure = fields.Float(
        string='Subtotal Infraestructura (18%)',
        compute='_compute_scores',
        store=True,
        digits=(5, 2),
        help='Ponderación: 18% de la calificación general.'
    )

    # --------------------------------------------------------------------------
    # PILAR 5: ORGANIZACIÓN ADMINISTRATIVA (Ponderación 13%)
    # --------------------------------------------------------------------------
    score_process_manuals = fields.Float(string='Manuales de Procesos Formalizados (0-100)', default=100.0)
    score_audited_financials = fields.Float(string='Estados Financieros Auditados Presentados (0-100)', default=100.0)
    score_labor_compliance = fields.Float(string='Contratación Formal y Salud Ocupacional (0-100)', default=100.0)
    subtotal_administration = fields.Float(
        string='Subtotal Organización Administrativa (13%)',
        compute='_compute_scores',
        store=True,
        digits=(5, 2),
        help='Ponderación: 13% de la calificación general.'
    )

    # --------------------------------------------------------------------------
    # RESULTADO GLOBAL PONDERADO Y RANKING (Total 100%)
    # --------------------------------------------------------------------------
    final_score = fields.Float(
        string='Puntaje Total Ponderado',
        compute='_compute_scores',
        store=True,
        digits=(5, 2),
        tracking=True
    )
    ranking_position = fields.Integer(string='Posición en Ranking', default=1, tracking=True)
    is_top_3 = fields.Boolean(string='Galardón Top 3 a la Excelencia', default=False, tracking=True)

    performance_tier = fields.Selection([
        ('excellence', 'Excelencia Operativa (>= 90 pts - Premio Top 3)'),
        ('compliant', 'Cumplimiento Estándar (75 a 89.9 pts)'),
        ('warning', 'En Observación (60 a 74.9 pts)'),
        ('deficient', 'Deficiente (< 60 pts - Plan de Corrección Obligatorio)'),
    ], string='Nivel de Calificación', compute='_compute_scores', store=True, tracking=True)

    incentive_bonus = fields.Float(
        string='Bono Asignado del Fondo de Acumulación (Gs.)',
        default=0.0,
        tracking=True
    )

    evaluation_notes = fields.Text(string='Dictamen del Comité Técnico Auditor')

    @api.depends(
        'score_punctuality', 'score_itinerary_compliance', 'score_ipk_goal',
        'score_mechanical_inspection', 'score_maintenance_plan', 'score_fleet_age', 'score_vehicle_cleanliness',
        'score_accident_rate', 'score_traffic_infractions', 'score_citizen_complaints',
        'score_depot_cleanliness', 'score_lighting_signage', 'score_operator_welfare',
        'score_process_manuals', 'score_audited_financials', 'score_labor_compliance'
    )
    def _compute_scores(self):
        for rec in self:
            # Pilar 1: Operación (23%)
            avg_op = (rec.score_punctuality + rec.score_itinerary_compliance + rec.score_ipk_goal) / 3.0
            sub_op = (avg_op * 0.23)

            # Pilar 2: Calidad (22%)
            avg_qual = (rec.score_mechanical_inspection + rec.score_maintenance_plan + rec.score_fleet_age + rec.score_vehicle_cleanliness) / 4.0
            sub_qual = (avg_qual * 0.22)

            # Pilar 3: Seguridad (24%)
            avg_sec = (rec.score_accident_rate + rec.score_traffic_infractions + rec.score_citizen_complaints) / 3.0
            sub_sec = (avg_sec * 0.24)

            # Pilar 4: Infraestructura (18%)
            avg_inf = (rec.score_depot_cleanliness + rec.score_lighting_signage + rec.score_operator_welfare) / 3.0
            sub_inf = (avg_inf * 0.18)

            # Pilar 5: Administración (13%)
            avg_adm = (rec.score_process_manuals + rec.score_audited_financials + rec.score_labor_compliance) / 3.0
            sub_adm = (avg_adm * 0.13)

            total = sub_op + sub_qual + sub_sec + sub_inf + sub_adm

            rec.subtotal_operation = sub_op
            rec.subtotal_quality = sub_qual
            rec.subtotal_security = sub_sec
            rec.subtotal_infrastructure = sub_inf
            rec.subtotal_administration = sub_adm
            rec.final_score = round(total, 2)

            if total >= 90.0:
                rec.performance_tier = 'excellence'
            elif total >= 75.0:
                rec.performance_tier = 'compliant'
            elif total >= 60.0:
                rec.performance_tier = 'warning'
            else:
                rec.performance_tier = 'deficient'
