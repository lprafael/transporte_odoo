# -*- coding: utf-8 -*-
import math
from odoo import api, fields, models
from odoo.exceptions import UserError

class TransitSimulationWizard(models.TransientModel):
    _name = 'transit.simulation.wizard'
    _description = 'Simulador de Operación, Frecuencias y Cobertura de Flota Actual'

    name = fields.Char(string='Nombre de la Simulación', default='Simulación de Cobertura Operativa 2026', required=True)
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        string='Empresa Concesionaria / Operadora',
        required=True,
        help='Empresa operadora titular de la flota y los servicios a simular'
    )
    service_ids = fields.Many2many(
        'transit.service',
        string='Servicios / Líneas a Simular',
        help='Servicios cubiertos por la empresa (ej: los 3 servicios eléctricos E1, E2, E3 o cualquier conjunto de líneas)'
    )
    simulation_day_type = fields.Selection([
        ('5', 'Día Laboral (Lunes a Viernes - Demanda Máxima)'),
        ('6', 'Sábado (Demanda Media)'),
        ('7', 'Domingos y Feriados (Demanda Reducida)'),
    ], string='Régimen Operativo a Simular', default='5', required=True)

    # --------------------------------------------------------------------------
    # FLOTA ACTUAL DISPONIBLE DE LA EMPRESA (Detectada o Simulada What-If)
    # --------------------------------------------------------------------------
    total_fleet_available = fields.Integer(
        string='Flota Total Disponible (Buses)',
        compute='_compute_fleet_available',
        readonly=False,
        store=True,
        help='Cantidad de unidades operativas disponibles para prestar servicio'
    )
    electric_fleet_available = fields.Integer(
        string='Flota Eléctrica (EV)',
        compute='_compute_fleet_available',
        readonly=False,
        store=True,
        help='Buses 100% eléctricos disponibles'
    )
    conventional_fleet_available = fields.Integer(
        string='Flota Convencional / Diésel',
        compute='_compute_fleet_available',
        readonly=False,
        store=True
    )
    depot_chargers_available = fields.Integer(
        string='Puntos de Recarga en Patio (EV)',
        default=8,
        help='Cantidad de dispensadores de carga rápida disponibles en cochera'
    )

    # Parámetros Globales de Simulación
    commercial_speed_kmh = fields.Float(string='Velocidad Comercial Media (km/h)', default=18.5, required=True)
    headway_buffer_pct = fields.Float(string='% Tiempo de Regulación en Cabeceras', default=12.0, required=True,
                                      help='Margen de seguridad en cabecera para regular intervalos y descanso')
    reserve_fleet_pct = fields.Float(string='% Reserva Técnica de Flota', default=10.0, required=True,
                                     help='Porcentaje de flota reservada para mantenimiento y contingencias (estándar 10%)')

    # Parámetros Energéticos EV
    avg_ev_consumption_kwh_km = fields.Float(string='Consumo EV Medio (kWh/km)', default=1.15)
    battery_usable_kwh = fields.Float(string='Capacidad Útil Batería por Bus (kWh)', default=320.0)
    min_departure_soc_pct = fields.Float(string='SoC Mínimo de Seguridad (%)', default=90.0)

    # Líneas de Simulación por Servicio
    line_ids = fields.One2many(
        'transit.simulation.wizard.line',
        'wizard_id',
        string='Desglose por Servicio'
    )

    # --------------------------------------------------------------------------
    # RESULTADOS CONSOLIDADOS DE LA SIMULACIÓN
    # --------------------------------------------------------------------------
    total_peak_buses_needed = fields.Integer(string='Buses Requeridos en Hora Pico', compute='_compute_results')
    total_reserve_buses_needed = fields.Integer(string='Buses de Reserva Técnica Requeridos', compute='_compute_results')
    total_fleet_needed = fields.Integer(string='Flota Total Necesaria', compute='_compute_results')

    fleet_balance = fields.Integer(
        string='Balance de Flota (Déficit / Superávit)',
        compute='_compute_results',
        help='Flota Actual Disponible menos Flota Necesaria. Positivo indica holgura; negativo indica déficit.'
    )
    coverage_percentage = fields.Float(
        string='% Cobertura de la Flota Actual',
        compute='_compute_results',
        digits=(5, 1)
    )
    coverage_status = fields.Selection([
        ('full', '✅ Cobertura Plena Garantizada (>= 100%)'),
        ('tight', '⚠️ Cobertura Ajustada (90% a 99% - Riesgo de Regularidad)'),
        ('deficit', '🚨 Déficit de Flota (< 90% - Requiere Refuerzos o Reducción de Frecuencia)'),
    ], string='Estado de Cobertura', compute='_compute_results')

    achievable_peak_headway_minutes = fields.Float(
        string='Frecuencia Factible con Flota Actual (min)',
        compute='_compute_results',
        digits=(4, 1),
        help='Intervalo promedio que la flota actual sí puede sostener sin generar quiebre de servicio'
    )

    total_daily_trips = fields.Integer(string='Total Salidas Diarias Requeridas', compute='_compute_results')
    total_daily_km = fields.Float(string='Kilometraje Total Diario (km)', compute='_compute_results', digits=(10, 1))
    total_daily_energy_kwh = fields.Float(string='Consumo Total Estimado (kWh)', compute='_compute_results', digits=(10, 1))
    avg_km_per_bus = fields.Float(string='Km Promedio por Unidad (km/día)', compute='_compute_results', digits=(6, 1))

    energy_feasibility = fields.Selection([
        ('feasible', '✅ Autonomía Suficiente con Carga Nocturna'),
        ('opportunity', '⚠️ Requiere Biberonaje / Carga Rápida Intermedia en Horas Valle'),
        ('insufficient', '🚨 Autonomía Crítica: Riesgo de Descarga en Calle'),
    ], string='Factibilidad Energética EV', compute='_compute_results')

    recommendation_notes = fields.Text(string='Dictamen y Recomendaciones Técnicas', compute='_compute_results')

    @api.onchange('concessionaire_id')
    def _onchange_concessionaire_id(self):
        if self.concessionaire_id:
            services = self.env['transit.service'].search([
                ('concessionaire_id', '=', self.concessionaire_id.id),
                ('active', '=', True)
            ])
            self.service_ids = services

    @api.depends('concessionaire_id')
    def _compute_fleet_available(self):
        for rec in self:
            if rec.concessionaire_id:
                vehicles = self.env['fleet.vehicle'].search([
                    ('concessionaire_id', '=', rec.concessionaire_id.id),
                    ('active', '=', True)
                ])
                rec.total_fleet_available = len(vehicles)
                rec.electric_fleet_available = len(vehicles.filtered(lambda v: v.is_electric))
                rec.conventional_fleet_available = len(vehicles.filtered(lambda v: not v.is_electric))
            else:
                rec.total_fleet_available = 30
                rec.electric_fleet_available = 30
                rec.conventional_fleet_available = 0

    def action_calculate_simulation(self):
        """Genera las líneas de simulación para cada servicio seleccionado y computa los resultados"""
        self.ensure_one()
        services = self.service_ids
        if not services and self.concessionaire_id:
            services = self.env['transit.service'].search([
                ('concessionaire_id', '=', self.concessionaire_id.id),
                ('active', '=', True)
            ])
        if not services:
            raise UserError("Debe seleccionar al menos un servicio operativo para la simulación.")

        # Limpiar líneas previas
        self.line_ids.unlink()

        lines_vals = []
        speed = max(5.0, self.commercial_speed_kmh or 18.5)
        buffer_mult = 1.0 + ((self.headway_buffer_pct or 12.0) / 100.0)

        for serv in services:
            # Obtener rutas de ida y vuelta
            routes_in = serv.route_ids.filtered(lambda r: r.direction in ('inbound', 'circular'))
            routes_out = serv.route_ids.filtered(lambda r: r.direction == 'outbound')

            dist_ida = sum(routes_in.mapped('distance_km')) if routes_in else 19.5
            dist_vta = sum(routes_out.mapped('distance_km')) if routes_out else 19.8
            dist_ciclo = dist_ida + dist_vta

            # Tiempo de ciclo en minutos
            tiempo_ida_min = (dist_ida / speed) * 60.0
            tiempo_vta_min = (dist_vta / speed) * 60.0
            tiempo_ciclo_min = (tiempo_ida_min + tiempo_vta_min) * buffer_mult

            # Contar salidas programadas en transit_timetable para este servicio y tipo_dia
            tt_domain = [
                ('route_id', 'in', serv.route_ids.ids),
                ('active', '=', True),
                ('tipo_dia', '=', self.simulation_day_type)
            ]
            tt_count = self.env['transit.timetable'].search_count(tt_domain)

            # Fallback de salidas si aún no hay timetable cargado
            if not tt_count:
                tt_count = serv.daily_target_departures or (92 if self.simulation_day_type == '5' else (48 if self.simulation_day_type == '6' else 36))

            # Intervalo requerido en hora pico según el servicio
            # E1: 6 min, E2: 5 min, E3: 8 min estándar, o default 6 min
            headway_peak = 5.0 if serv.code == 'E2' else (6.0 if serv.code == 'E1' else (8.0 if serv.code == 'E3' else 7.0))
            headway_offpeak = headway_peak * 1.8

            # Buses necesarios en hora pico = ceil(tiempo_ciclo / headway_peak)
            peak_buses = int(math.ceil(tiempo_ciclo_min / max(1.0, headway_peak)))
            reserve_buses = int(math.ceil(peak_buses * ((self.reserve_fleet_pct or 10.0) / 100.0)))
            total_buses = peak_buses + reserve_buses

            daily_km = tt_count * (dist_ciclo / 2.0)

            lines_vals.append((0, 0, {
                'service_id': serv.id,
                'service_code': serv.code,
                'service_name': serv.name,
                'cycle_distance_km': round(dist_ciclo, 2),
                'cycle_time_minutes': round(tiempo_ciclo_min, 1),
                'peak_headway_minutes': headway_peak,
                'offpeak_headway_minutes': headway_offpeak,
                'scheduled_departures': tt_count,
                'peak_buses_needed': peak_buses,
                'reserve_buses_needed': reserve_buses,
                'total_buses_needed': total_buses,
                'daily_commercial_km': round(daily_km, 1),
            }))

        self.write({'line_ids': lines_vals})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'transit.simulation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.depends('line_ids', 'total_fleet_available', 'electric_fleet_available', 'reserve_fleet_pct', 'avg_ev_consumption_kwh_km', 'battery_usable_kwh')
    def _compute_results(self):
        for rec in self:
            if not rec.line_ids:
                rec.total_peak_buses_needed = 0
                rec.total_reserve_buses_needed = 0
                rec.total_fleet_needed = 0
                rec.fleet_balance = 0
                rec.coverage_percentage = 0.0
                rec.coverage_status = 'deficit'
                rec.achievable_peak_headway_minutes = 0.0
                rec.total_daily_trips = 0
                rec.total_daily_km = 0.0
                rec.total_daily_energy_kwh = 0.0
                rec.avg_km_per_bus = 0.0
                rec.energy_feasibility = 'feasible'
                rec.recommendation_notes = "Haga clic en 'Calcular Simulación' para procesar los servicios seleccionados."
                continue

            sum_peak = sum(rec.line_ids.mapped('peak_buses_needed'))
            sum_res = sum(rec.line_ids.mapped('reserve_buses_needed'))
            total_needed = sum_peak + sum_res
            trips = sum(rec.line_ids.mapped('scheduled_departures'))
            km = sum(rec.line_ids.mapped('daily_commercial_km'))

            avail = rec.total_fleet_available or 0
            balance = avail - total_needed
            cov_pct = (avail / total_needed * 100.0) if total_needed > 0 else 100.0

            rec.total_peak_buses_needed = sum_peak
            rec.total_reserve_buses_needed = sum_res
            rec.total_fleet_needed = total_needed
            rec.fleet_balance = balance
            rec.coverage_percentage = round(min(cov_pct, 100.0), 1)

            if cov_pct >= 100.0:
                rec.coverage_status = 'full'
            elif cov_pct >= 90.0:
                rec.coverage_status = 'tight'
            else:
                rec.coverage_status = 'deficit'

            # Frecuencia alcanzable con flota actual
            # Si hay flota suficiente, el headway es el nominal; si hay déficit, se estira
            if avail > 0 and sum_peak > 0:
                fleet_factor = min(1.0, avail / float(total_needed))
                # Promedio ponderado de headway
                avg_headway = sum(l.peak_headway_minutes * l.peak_buses_needed for l in rec.line_ids) / float(sum_peak)
                rec.achievable_peak_headway_minutes = round(avg_headway / fleet_factor, 1)
            else:
                rec.achievable_peak_headway_minutes = 0.0

            rec.total_daily_trips = trips
            rec.total_daily_km = round(km, 1)

            energy = km * (rec.avg_ev_consumption_kwh_km or 1.15)
            rec.total_daily_energy_kwh = round(energy, 1)

            effective_buses = max(1, avail)
            km_per_bus = km / float(effective_buses)
            rec.avg_km_per_bus = round(km_per_bus, 1)

            # Factibilidad Energética
            usable_battery = (rec.battery_usable_kwh or 320.0) * ((rec.min_departure_soc_pct or 90.0) / 100.0)
            max_km_single_charge = usable_battery / (rec.avg_ev_consumption_kwh_km or 1.15)

            if km_per_bus <= max_km_single_charge * 0.85:
                rec.energy_feasibility = 'feasible'
            elif km_per_bus <= max_km_single_charge * 1.30:
                rec.energy_feasibility = 'opportunity'
            else:
                rec.energy_feasibility = 'insufficient'

            # Dictamen técnico
            dictamen = []
            dictamen.append(f"📊 EVALUACIÓN TÉCNICA DE COBERTURA (Régimen: {dict(rec._fields['simulation_day_type'].selection).get(rec.simulation_day_type)}):")
            dictamen.append(f"• Servicios analizados: {len(rec.line_ids)} ({', '.join(rec.line_ids.mapped('service_code'))})")
            dictamen.append(f"• Salidas programadas requeridas: {trips} salidas/día ({km:,.1f} km comerciales totales).")
            dictamen.append(f"• Flota requerida en punta: {sum_peak} buses + {sum_res} reserva técnica = {total_needed} buses necesarios.")
            dictamen.append(f"• Flota actual operativa: {avail} buses disponibles.")

            if balance >= 0:
                dictamen.append(f"✅ CAPACIDAD GARANTIZADA: La empresa cuenta con un superávit de {balance} unidades. Se garantiza el 100% de cumplimiento de frecuencias y despachos.")
            else:
                dictamen.append(f"⚠️ DÉFICIT DETECTADO: Faltan {abs(balance)} unidades para sostener simultáneamente el intervalo óptimo en hora pico en todos los ramales.")
                dictamen.append(f"   → Frecuencia recomendada con la flota actual: {rec.achievable_peak_headway_minutes} minutos en hora pico para evitar huecos en calle.")
                dictamen.append(f"   → Estrategia de Refuerzos: Despachar coches comodín en las horas punta de mayor carga (06:30–07:30 y 17:00–18:30).")

            if rec.energy_feasibility == 'opportunity':
                dictamen.append(f"⚡ RECARGA EN PATIO: Con un promedio de {km_per_bus:.1f} km/bus, las unidades requerirán 1 recarga rápida intermedia (biberonaje de 30-45 min) en los {rec.depot_chargers_available} cargadores de patio entre las 10:00 y las 14:00 hs.")
            elif rec.energy_feasibility == 'insufficient':
                dictamen.append(f"🚨 ALERTA BATERÍA: El kilometraje diario ({km_per_bus:.1f} km/bus) supera la autonomía de seguridad. Se requiere rotación escalonada con flota de relevo.")

            rec.recommendation_notes = "\n".join(dictamen)


class TransitSimulationWizardLine(models.TransientModel):
    _name = 'transit.simulation.wizard.line'
    _description = 'Línea de Desglose por Servicio en Simulación'

    wizard_id = fields.Many2one('transit.simulation.wizard', string='Simulador', ondelete='cascade', required=True)
    service_id = fields.Many2one('transit.service', string='Servicio', required=True)
    service_code = fields.Char(string='Código')
    service_name = fields.Char(string='Línea / Ramal')

    cycle_distance_km = fields.Float(string='Km Ciclo (Ida+Vta)', digits=(6, 2))
    cycle_time_minutes = fields.Float(string='Tiempo Ciclo (min)', digits=(5, 1))
    peak_headway_minutes = fields.Float(string='Intervalo Pico (min)', digits=(4, 1))
    offpeak_headway_minutes = fields.Float(string='Intervalo Valle (min)', digits=(4, 1))

    scheduled_departures = fields.Integer(string='Salidas Requeridas')
    peak_buses_needed = fields.Integer(string='Buses en Pico')
    reserve_buses_needed = fields.Integer(string='Reserva Técnica')
    total_buses_needed = fields.Integer(string='Flota Necesaria')
    daily_commercial_km = fields.Float(string='Km Diarios', digits=(10, 1))
