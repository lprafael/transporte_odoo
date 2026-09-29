# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class TransitClearingPeriod(models.Model):
    _name = 'transit.clearing.period'
    _description = 'Período de Liquidación y Compensación Tarifaria (Modelo SIT / PagoBús)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Código de Liquidación',
        required=True,
        copy=False,
        readonly=True,
        default='Nuevo'
    )
    period_type = fields.Selection([
        ('monthly', 'Mensual'),
        ('biweekly', 'Quincenal'),
        ('weekly', 'Semanal'),
    ], string='Frecuencia', default='monthly', required=True)
    
    date_start = fields.Date(string='Fecha Inicio', required=True, tracking=True)
    date_end = fields.Date(string='Fecha Fin', required=True, tracking=True)

    # 1. Fideicomiso de Cobro Controlado (Caja Común)
    total_collected_revenue = fields.Float(
        string='Recaudación Total Bruta (Gs.)',
        required=True,
        tracking=True,
        help='Total de ingresos capturados en campo (ventas en efectivo, recargas y transacciones electrónicas).'
    )
    
    # 2. Fideicomiso de Modernización del Transporte
    modernization_fund_rate = fields.Float(
        string='% Fideicomiso Modernización',
        default=2.0,
        help='Porcentaje retenido para custodia de infraestructura ITS y renovación de flota.'
    )
    modernization_fund_amount = fields.Float(
        string='Fondo de Modernización (Gs.)',
        compute='_compute_clearing_factors',
        store=True
    )
    net_distributable_revenue = fields.Float(
        string='Fondo Neto Distribuible (Gs.)',
        compute='_compute_clearing_factors',
        store=True,
        help='Fondo resultante de la caja común a repartir entre concesionarias por kilómetros.'
    )

    # Kilometraje del Sistema
    total_planned_km = fields.Float(
        string='Km Totales Planificados',
        required=True,
        digits=(12, 2),
        tracking=True,
        help='Suma de distancias teóricas según cuadro de marchas del período.'
    )
    total_executed_km = fields.Float(
        string='Km Efectivamente Ejecutados',
        compute='_compute_executed_km_total',
        store=True,
        digits=(12, 2),
        tracking=True,
        help='Suma de kilómetros certificados por la bitácora SAE y odometría de viajes completados.'
    )

    # Factor de Ingreso por Kilómetro (FI_km)
    income_factor_per_km = fields.Float(
        string='Factor Ingreso por Km (FI_km)',
        compute='_compute_clearing_factors',
        store=True,
        digits=(10, 4),
        tracking=True,
        help='FI_km = Fondo Neto Distribuible / Km Totales Planificados'
    )

    # Fondo de Acumulación / Bolsa de Incentivos (Penalizaciones Retenidas)
    total_penalties_collected = fields.Float(
        string='Bolsa de Penalizaciones (Gs.)',
        compute='_compute_settlement_totals',
        store=True,
        help='Total de penalizaciones deducidas que conforman la bolsa de incentivos a la excelencia.'
    )
    total_incentives_distributed = fields.Float(
        string='Incentivos Distribuidos (Gs.)',
        compute='_compute_settlement_totals',
        store=True
    )

    # Líneas de liquidación por empresa operadora
    settlement_ids = fields.One2many(
        'transit.clearing.settlement',
        'period_id',
        string='Liquidación a Concesionarias'
    )
    evaluation_ids = fields.One2many(
        'transit.concessionaire.evaluation',
        'clearing_period_id',
        string='Evaluaciones Ponderadas UNE-EN 13816'
    )

    total_gross_settlement = fields.Float(
        string='Total Bruto Liquidado (Gs.)',
        compute='_compute_settlement_totals',
        store=True
    )
    total_net_settlement = fields.Float(
        string='Total Neto a Pagar (Gs.)',
        compute='_compute_settlement_totals',
        store=True
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Cálculo Realizado'),
        ('evaluated', 'Evaluación UNE-EN 13816 Aplicada'),
        ('approved', 'Aprobado por Autoridad'),
        ('settled', 'Liquidado / Pagado'),
        ('canceled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)

    notes = fields.Text(string='Observaciones Técnicas y Financieras')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('transit.clearing.period') or 'COMP-AUTO'
        return super(TransitClearingPeriod, self).create(vals_list)

    @api.depends('total_collected_revenue', 'modernization_fund_rate', 'total_planned_km')
    def _compute_clearing_factors(self):
        for rec in self:
            mod_fund = (rec.total_collected_revenue or 0.0) * ((rec.modernization_fund_rate or 0.0) / 100.0)
            net_dist = (rec.total_collected_revenue or 0.0) - mod_fund
            rec.modernization_fund_amount = mod_fund
            rec.net_distributable_revenue = net_dist

            if rec.total_planned_km and rec.total_planned_km > 0:
                rec.income_factor_per_km = net_dist / rec.total_planned_km
            else:
                rec.income_factor_per_km = 0.0

    @api.depends('settlement_ids.executed_km')
    def _compute_executed_km_total(self):
        for rec in self:
            rec.total_executed_km = sum(rec.settlement_ids.mapped('executed_km'))

    @api.depends(
        'settlement_ids.gross_amount',
        'settlement_ids.penalties_amount',
        'settlement_ids.incentive_bonus_amount',
        'settlement_ids.net_amount'
    )
    def _compute_settlement_totals(self):
        for rec in self:
            rec.total_gross_settlement = sum(rec.settlement_ids.mapped('gross_amount'))
            rec.total_penalties_collected = sum(rec.settlement_ids.mapped('penalties_amount'))
            rec.total_incentives_distributed = sum(rec.settlement_ids.mapped('incentive_bonus_amount'))
            rec.total_net_settlement = sum(rec.settlement_ids.mapped('net_amount'))

    def action_calculate_settlements(self):
        """Calcula el kilometraje real ejecutado por cada concesionaria y liquida según FI_km"""
        self.ensure_one()
        if not self.total_collected_revenue or self.total_collected_revenue <= 0:
            raise UserError("Debe registrar la recaudación total bruta en el Fideicomiso de Cobro Controlado.")
        if not self.total_planned_km or self.total_planned_km <= 0:
            raise UserError("Debe registrar los kilómetros planificados del período.")

        concessionaires = self.env['transit.concessionaire'].search([('active', '=', True)])
        if not concessionaires:
            raise UserError("No existen empresas concesionarias activas para liquidar.")

        # Obtener despachos completados en el rango de fechas
        domain = [
            ('date', '>=', self.date_start),
            ('date', '<=', self.date_end),
            ('state', '=', 'completed'),
        ]
        completed_dispatches = self.env['transit.dispatch'].search(domain)

        settlement_model = self.env['transit.clearing.settlement']
        self.settlement_ids.unlink()

        for conc in concessionaires:
            # Despachos de esta concesionaria
            conc_dispatches = completed_dispatches.filtered(
                lambda d: d.vehicle_id and d.vehicle_id.concessionaire_id.id == conc.id
            )
            # Sumar km de los despachos
            exec_km = sum(conc_dispatches.mapped('km_traveled'))
            # Si km_traveled es 0, usar distance_km de la ruta como fallback
            if exec_km == 0:
                exec_km = sum(conc_dispatches.mapped('route_id.distance_km'))

            # Proporción de km planificados para esta concesionaria
            conc_planned_km = sum(conc.route_ids.mapped('distance_km')) * 30.0  # estimación base si no hay tabla
            if conc_planned_km == 0:
                conc_planned_km = exec_km or 1.0

            # Calcular retrasos graves como penalizaciones iniciales
            delayed_dispatches = conc_dispatches.filtered(lambda d: d.departure_delay_minutes > 15.0)
            penalty = len(delayed_dispatches) * 50000.0  # Gs. 50.000 por salida con retraso severo

            gross = exec_km * self.income_factor_per_km
            retention = gross * 0.01  # 1% aporte a bolsa de contingencia

            settlement_model.create({
                'period_id': self.id,
                'concessionaire_id': conc.id,
                'planned_km': conc_planned_km,
                'executed_km': exec_km,
                'penalties_amount': penalty,
                'penalty_notes': f'{len(delayed_dispatches)} salidas con retraso mayor a 15 minutos.' if delayed_dispatches else 'Sin penalizaciones iniciales registradas.',
                'incentive_retention_amount': retention,
            })

        self.state = 'calculated'

    def action_apply_evaluations_and_incentives(self):
        """Distribuye la bolsa de penalizaciones (Fondo de Acumulación) según la Matriz Ponderada UNE-EN 13816:
           50% para las 3 mejores empresas clasificadas (Top 3)
           50% restante proporcional entre las demás empresas
        """
        self.ensure_one()
        evaluations = self.env['transit.concessionaire.evaluation'].search([
            ('clearing_period_id', '=', self.id)
        ], order='final_score desc')

        if not evaluations:
            # Si no hay evaluaciones creadas, generar borradores automáticos
            eval_model = self.env['transit.concessionaire.evaluation']
            for line in self.settlement_ids:
                compliance = (line.executed_km / (line.planned_km or 1.0)) * 100.0
                score_op = min(100.0, max(60.0, compliance))
                eval_model.create({
                    'name': f'EVAL-{self.name} - {line.concessionaire_id.name}',
                    'clearing_period_id': self.id,
                    'concessionaire_id': line.concessionaire_id.id,
                    'date_evaluation': fields.Date.today(),
                    'score_punctuality': score_op,
                    'score_itinerary_compliance': 90.0,
                    'score_ipk_goal': 85.0,
                    'score_mechanical_inspection': 95.0,
                    'score_maintenance_plan': 90.0,
                    'score_fleet_age': 80.0,
                    'score_vehicle_cleanliness': 88.0,
                    'score_accident_rate': 95.0,
                    'score_traffic_infractions': 92.0,
                    'score_citizen_complaints': 85.0,
                    'score_depot_cleanliness': 90.0,
                    'score_lighting_signage': 88.0,
                    'score_operator_welfare': 85.0,
                    'score_process_manuals': 90.0,
                    'score_audited_financials': 90.0,
                    'score_labor_compliance': 95.0,
                })
            evaluations = self.env['transit.concessionaire.evaluation'].search([
                ('clearing_period_id', '=', self.id)
            ], order='final_score desc')

        # Asignar ranking
        rank = 1
        for ev in evaluations:
            ev.ranking_position = rank
            ev.is_top_3 = (rank <= 3)
            rank += 1

        # Reparto del Fondo de Acumulación
        pool = self.total_penalties_collected or 0.0
        if pool > 0 and evaluations:
            pool_top3 = pool * 0.50
            pool_remaining = pool * 0.50

            top3_evals = evaluations.filtered(lambda e: e.is_top_3)
            other_evals = evaluations.filtered(lambda e: not e.is_top_3)

            # 50% dividido entre Top 3
            if top3_evals:
                top3_bonus_each = pool_top3 / len(top3_evals)
                for ev in top3_evals:
                    ev.incentive_bonus = top3_bonus_each
                    settlement = self.settlement_ids.filtered(lambda s: s.concessionaire_id.id == ev.concessionaire_id.id)
                    if settlement:
                        settlement.write({'incentive_bonus_amount': top3_bonus_each})

            # 50% proporcional entre las restantes
            if other_evals:
                total_points_other = sum(other_evals.mapped('final_score')) or 1.0
                for ev in other_evals:
                    ratio = ev.final_score / total_points_other
                    bonus = pool_remaining * ratio
                    ev.incentive_bonus = bonus
                    settlement = self.settlement_ids.filtered(lambda s: s.concessionaire_id.id == ev.concessionaire_id.id)
                    if settlement:
                        settlement.write({'incentive_bonus_amount': bonus})
        
        self.state = 'evaluated'

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_settle(self):
        for line in self.settlement_ids:
            line.payment_status = 'paid'
        self.write({'state': 'settled'})

    def action_cancel(self):
        self.write({'state': 'canceled'})


class TransitClearingSettlement(models.Model):
    _name = 'transit.clearing.settlement'
    _description = 'Detalle de Liquidación a Concesionaria'
    _order = 'net_amount desc'

    period_id = fields.Many2one('transit.clearing.period', string='Período de Liquidación', required=True, ondelete='cascade')
    concessionaire_id = fields.Many2one('transit.concessionaire', string='Empresa Concesionaria', required=True)
    
    planned_km = fields.Float(string='Km Planificados', digits=(10, 2), default=0.0)
    executed_km = fields.Float(string='Km Ejecutados (SAE)', digits=(10, 2), default=0.0)
    km_compliance_rate = fields.Float(string='% Cumplimiento Km', compute='_compute_compliance', store=True)

    income_factor_per_km = fields.Float(
        string='FI_km Aplicado',
        related='period_id.income_factor_per_km',
        digits=(10, 4),
        readonly=True
    )

    gross_amount = fields.Float(string='Monto Bruto Ganado (Gs.)', compute='_compute_amounts', store=True)
    penalties_amount = fields.Float(string='Penalizaciones Deducidas (Gs.)', default=0.0)
    penalty_notes = fields.Char(string='Motivo de Penalización')
    
    incentive_retention_amount = fields.Float(string='Retención Fondo Reserva (Gs.)', default=0.0)
    incentive_bonus_amount = fields.Float(
        string='Incentivo UNE-EN 13816 Ganado (Gs.)',
        default=0.0,
        help='Monto adjudicado del Fondo de Acumulación por excelencia operativa o cumplimiento.'
    )

    net_amount = fields.Float(string='Monto Neto a Liquidar (Gs.)', compute='_compute_amounts', store=True)
    payment_status = fields.Selection([
        ('pending', 'Pendiente de Pago'),
        ('ready', 'Aprobado para Pago'),
        ('paid', 'Transferido / Pagado'),
    ], string='Estado de Pago', default='pending')

    @api.depends('executed_km', 'planned_km')
    def _compute_compliance(self):
        for rec in self:
            if rec.planned_km and rec.planned_km > 0:
                rec.km_compliance_rate = (rec.executed_km / rec.planned_km) * 100.0
            else:
                rec.km_compliance_rate = 100.0 if rec.executed_km > 0 else 0.0

    @api.depends(
        'executed_km',
        'income_factor_per_km',
        'penalties_amount',
        'incentive_retention_amount',
        'incentive_bonus_amount'
    )
    def _compute_amounts(self):
        for rec in self:
            gross = (rec.executed_km or 0.0) * (rec.income_factor_per_km or 0.0)
            net = gross - (rec.penalties_amount or 0.0) - (rec.incentive_retention_amount or 0.0) + (rec.incentive_bonus_amount or 0.0)
            rec.gross_amount = gross
            rec.net_amount = max(0.0, net)
