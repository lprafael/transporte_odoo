# -*- coding: utf-8 -*-
import math
from odoo import api, fields, models

class TransitSimulationWizard(models.TransientModel):
    _name = 'transit.simulation.wizard'
    _description = 'Simulador Predictivo What-If para Licitaciones y Expansión de Redes'

    name = fields.Char(string='Nombre de la Alternativa / Licitación', default='Simulación Red Troncal 2026', required=True)
    target_route_id = fields.Many2one('transit.route', string='Ramal Base (Opcional)')
    
    # Parámetros Operativos de Entrada
    route_distance_km = fields.Float(string='Longitud del Recorrido (km)', default=25.0, required=True)
    commercial_speed_kmh = fields.Float(string='Velocidad Comercial Estimada (km/h)', default=18.0, required=True)
    peak_headway_minutes = fields.Float(string='Intervalo en Hora Pico (min)', default=6.0, required=True)
    offpeak_headway_minutes = fields.Float(string='Intervalo en Hora Valle (min)', default=12.0, required=True)
    daily_operating_hours = fields.Float(string='Horas de Operación Diaria (h)', default=18.0, required=True)
    peak_hours_per_day = fields.Float(string='Horas Pico por Día (h)', default=6.0, required=True)
    reserve_fleet_percentage = fields.Float(string='% Flota de Reserva Técnica', default=10.0, required=True)

    # Parámetros de Costos Unitarios
    is_electric = fields.Boolean(string='Modelar con Flota 100% Eléctrica (EV)', default=True)
    energy_cost_per_km = fields.Float(string='Costo de Combustible / Energía (Gs./km)', default=650.0, help='Energía eléctrica (~650 Gs./km) vs Diésel (~2.400 Gs./km)')
    driver_hourly_cost = fields.Float(string='Costo Chofer por Hora (Gs./h)', default=28000.0)
    fixed_daily_depot_cost = fields.Float(string='Costo Fijo Diario por Bus (Gs./día)', default=120000.0)
    expected_daily_passengers = fields.Integer(string='Demanda Diaria Esperada (Pasajeros)', default=15000)

    # --------------------------------------------------------------------------
    # RESULTADOS DE LA SIMULACIÓN PREDICTIVA (OUTPUTS)
    # --------------------------------------------------------------------------
    cycle_time_minutes = fields.Float(string='Tiempo de Ciclo Completo (min)', compute='_compute_simulation', digits=(6, 1))
    required_peak_buses = fields.Integer(string='Buses Comerciales en Hora Pico', compute='_compute_simulation')
    reserve_buses = fields.Integer(string='Buses de Reserva Técnica', compute='_compute_simulation')
    total_fleet_needed = fields.Integer(string='Flota Total Necesaria', compute='_compute_simulation')
    drivers_needed = fields.Integer(string='Conductores Requeridos en Cuadrante', compute='_compute_simulation')

    daily_trips = fields.Integer(string='Expediciones / Salidas Diarias', compute='_compute_simulation')
    daily_commercial_km = fields.Float(string='Km Comerciales Diarios', compute='_compute_simulation', digits=(10, 1))
    daily_deadhead_km = fields.Float(string='Km en Vacío Estimados (Deadhead)', compute='_compute_simulation', digits=(10, 1))
    total_daily_km = fields.Float(string='Kilometraje Total Diario', compute='_compute_simulation', digits=(10, 1))

    daily_energy_cost = fields.Float(string='Costo Diario Energía (Gs.)', compute='_compute_simulation')
    daily_driver_cost = fields.Float(string='Costo Diario Choferes (Gs.)', compute='_compute_simulation')
    daily_depot_fixed_cost = fields.Float(string='Costo Fijo de Flota (Gs.)', compute='_compute_simulation')
    total_daily_operating_cost = fields.Float(string='Costo Operativo Total Diario (Gs.)', compute='_compute_simulation')

    breakeven_cost_per_km = fields.Float(string='Costo de Equilibrio por Km (Gs./km)', compute='_compute_simulation')
    breakeven_fare = fields.Float(string='Tarifa Técnica de Equilibrio por Pasaje (Gs.)', compute='_compute_simulation')

    @api.onchange('target_route_id')
    def _onchange_target_route_id(self):
        if self.target_route_id:
            self.route_distance_km = self.target_route_id.distance_km or 25.0
            if self.target_route_id.standard_duration_minutes:
                # Si hay duración estándar, estimar velocidad
                dur_hours = self.target_route_id.standard_duration_minutes / 60.0
                if dur_hours > 0:
                    self.commercial_speed_kmh = round(self.route_distance_km / dur_hours, 1)

    @api.depends(
        'route_distance_km', 'commercial_speed_kmh', 'peak_headway_minutes', 'offpeak_headway_minutes',
        'daily_operating_hours', 'peak_hours_per_day', 'reserve_fleet_percentage',
        'is_electric', 'energy_cost_per_km', 'driver_hourly_cost', 'fixed_daily_depot_cost',
        'expected_daily_passengers'
    )
    def _compute_simulation(self):
        for rec in self:
            speed = max(5.0, rec.commercial_speed_kmh or 18.0)
            dist = max(1.0, rec.route_distance_km or 25.0)

            # Tiempo de viaje en un sentido = (distancia / velocidad) * 60 minutos
            one_way_min = (dist / speed) * 60.0
            # Tiempo de ciclo (ida + vuelta + 10% tiempo de regulación en cabecera)
            cycle_min = (one_way_min * 2.0) * 1.10
            rec.cycle_time_minutes = cycle_min

            # Buses necesarios en pico = Tiempo de ciclo / Intervalo de paso en pico
            headway_peak = max(1.0, rec.peak_headway_minutes or 6.0)
            peak_buses = int(math.ceil(cycle_min / headway_peak))
            rec.required_peak_buses = peak_buses

            # Flota de reserva
            reserve_rate = (rec.reserve_fleet_percentage or 10.0) / 100.0
            res_buses = int(math.ceil(peak_buses * reserve_rate))
            rec.reserve_buses = res_buses
            total_fleet = peak_buses + res_buses
            rec.total_fleet_needed = total_fleet

            # Conductores necesarios en cuadrante (ratio 2.2 choferes por bus comercial en 18h)
            rec.drivers_needed = int(math.ceil(peak_buses * 2.2))

            # Expediciones diarias:
            # Horas pico salidas / hora = 60 / headway_peak
            # Horas valle salidas / hora = 60 / headway_offpeak
            peak_hours = min(rec.daily_operating_hours, rec.peak_hours_per_day or 6.0)
            offpeak_hours = max(0.0, rec.daily_operating_hours - peak_hours)
            headway_offpeak = max(1.0, rec.offpeak_headway_minutes or 12.0)

            daily_departures = int(
                (peak_hours * (60.0 / headway_peak)) +
                (offpeak_hours * (60.0 / headway_offpeak))
            )
            rec.daily_trips = daily_departures

            # Kilómetros comerciales diarios = salidas * distancia
            comm_km = daily_departures * dist
            # Km en vacío (deadhead) estimados en 8%
            deadhead_km = comm_km * 0.08
            total_km = comm_km + deadhead_km

            rec.daily_commercial_km = comm_km
            rec.daily_deadhead_km = deadhead_km
            rec.total_daily_km = total_km

            # Costos diarios
            c_energy = total_km * (rec.energy_cost_per_km or 650.0)
            c_driver = (rec.drivers_needed * 8.0) * (rec.driver_hourly_cost or 28000.0)
            c_fixed = total_fleet * (rec.fixed_daily_depot_cost or 120000.0)
            total_cost = c_energy + c_driver + c_fixed

            rec.daily_energy_cost = c_energy
            rec.daily_driver_cost = c_driver
            rec.daily_depot_fixed_cost = c_fixed
            rec.total_daily_operating_cost = total_cost

            # Costo de equilibrio por km
            rec.breakeven_cost_per_km = total_cost / total_km if total_km > 0 else 0.0

            # Tarifa técnica de pasaje
            pax = max(1, rec.expected_daily_passengers or 15000)
            rec.breakeven_fare = math.ceil(total_cost / pax)
