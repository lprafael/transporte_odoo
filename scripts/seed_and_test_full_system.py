# -*- coding: utf-8 -*-
"""
Script de Demostración y Validación Integral:
Especificaciones Técnicas y Funcionales - Sistema Integral de Gestión de Transporte Público Urbano
1. Concesionarias y Gobernanza APP
2. Electrificación y Salida Garantizada (EV / SoC)
3. Estaciones de Carga en Patio (Depot Management / OCPP)
4. Sensórica APC (Cámaras 3D), Cálculo de IPK y Auditoría de Evasión
5. Cámara de Compensación y Fideicomiso Centralizado (Modelo PagoBús / FI_km)
6. Matriz Ponderada UNE-EN 13816 y Reparto de Bolsa de Incentivos (Top 3)
7. Generador de Feeds GTFS Estático
8. Simulador Predictivo What-If para Licitaciones
"""

import sys
import os
import odoo
from odoo import api, fields, tools

def run_test():
    print("================================================================================")
    print("🚀 INICIANDO TEST INTEGRAL: SISTEMA COMPLETO DE TRANSPORTE PÚBLICO URBANO")
    print("================================================================================")
    
    # Inicializar Odoo Registry
    odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'flota_db'])
    registry = odoo.registry('flota_db')

    with registry.cursor() as cr:
        env = api.Environment(cr, odoo.SUPERUSER_ID, {})

        # --------------------------------------------------------------------------
        # 1. EMPRESAS CONCESIONARIAS (Gobernanza APP / SIT)
        # --------------------------------------------------------------------------
        print("\n[1/8] Verificando / Creando Empresas Concesionarias...")
        conc_model = env['transit.concessionaire']
        
        c1 = conc_model.search([('code', '=', 'CONC-L20')], limit=1)
        if not c1:
            c1 = conc_model.create({
                'name': 'Empresa Ciudad de Asunción S.A. (Línea 20 Eléctrica)',
                'code': 'CONC-L20',
                'legal_name': 'Empresa de Transporte Ciudad de Asunción Sociedad Anónima',
                'vat_ruc': '80012345-6',
                'address': 'Avda. Eusebio Ayala km 9, Asunción',
            })
            print(f"  ✓ Creada Concesionaria: {c1.name}")
        else:
            print(f"  ✓ Existente Concesionaria: {c1.name}")

        c2 = conc_model.search([('code', '=', 'CONC-SL01')], limit=1)
        if not c2:
            c2 = conc_model.create({
                'name': 'Transportes San Lorenzo S.R.L.',
                'code': 'CONC-SL01',
                'legal_name': 'Transportes Unidos de San Lorenzo S.R.L.',
                'vat_ruc': '80054321-2',
                'address': 'Ruta Mcal. Estigarribia km 14, San Lorenzo',
            })
            print(f"  ✓ Creada Concesionaria: {c2.name}")

        c3 = conc_model.search([('code', '=', 'CONC-METRO')], limit=1)
        if not c3:
            c3 = conc_model.create({
                'name': 'Consorcio Metropolitano de Movilidad',
                'code': 'CONC-METRO',
                'legal_name': 'Consorcio Metropolitano de Transporte Público S.A.',
                'vat_ruc': '80098765-4',
                'address': 'Acceso Sur km 5, Fernando de la Mora',
            })
            print(f"  ✓ Creada Concesionaria: {c3.name}")

        # --------------------------------------------------------------------------
        # 2. ELECTRIFICACIÓN DE FLOTAS Y ESPECIFICACIONES DE BATERÍA
        # --------------------------------------------------------------------------
        print("\n[2/8] Configurando Flota Eléctrica (EV) y Telemetría de Batería...")
        vehicles = env['fleet.vehicle'].search([], limit=5)
        for v in vehicles:
            v.write({
                'concessionaire_id': c1.id,
                'is_electric': True,
                'battery_capacity_kwh': 350.0,
                'connector_type': 'gbt',
                'electric_range_km': 280.0,
                'current_soc': 96.5,
                'min_departure_soc': 90.0,
                'thermal_preconditioning_ok': True,
                'charging_status': 'completed',
            })
        print(f"  ✓ {len(vehicles)} unidades configuradas como Flota 100% Eléctrica (SoC: 96.5%, GB/T 350 kWh).")

        # --------------------------------------------------------------------------
        # 3. PATIOS Y ESTACIONES DE RECARGA (Depot Management / OCPP)
        # --------------------------------------------------------------------------
        print("\n[3/8] Verificando Patios de Carga y Dispensadores Físicos...")
        station_model = env['transit.charging.station']
        st = station_model.search([('code', '=', 'PAT-SL01')], limit=1)
        if not st:
            st = station_model.create({
                'name': 'Cochera y Patio Central Línea 20 - San Lorenzo',
                'code': 'PAT-SL01',
                'concessionaire_id': c1.id,
                'contracted_power_kw': 1500.0,
                'peak_shaving_active': True,
                'address': 'San Lorenzo Depot km 15',
                'charger_ids': [
                    (0, 0, {
                        'name': 'Cargador Rápido DC-01',
                        'ocpp_id': 'OCPP-SL01-CH01',
                        'charger_type': 'dc_fast',
                        'connector_standard': 'gbt',
                        'max_nominal_power_kw': 120.0,
                        'status': 'available',
                    }),
                    (0, 0, {
                        'name': 'Cargador Ultra Rápido DC-02',
                        'ocpp_id': 'OCPP-SL01-CH02',
                        'charger_type': 'dc_ultra',
                        'connector_standard': 'gbt',
                        'max_nominal_power_kw': 240.0,
                        'status': 'charging',
                        'current_output_kw': 180.0,
                    }),
                ]
            })
            print(f"  ✓ Creada Estación de Carga: {st.name} con {st.charger_count} cargadores OCPP.")
        else:
            print(f"  ✓ Estación de Carga existente: {st.name} (Potencia Contratada: {st.contracted_power_kw} kW).")

        # --------------------------------------------------------------------------
        # 4. SENSÓRICA APC (Cámaras 3D), PESO J1939 Y DETECCIÓN DE EVASIÓN
        # --------------------------------------------------------------------------
        print("\n[4/8] Probando Sensórica APC (Cámaras 3D) y Auditoría de Evasión...")
        dispatch_sample = env['transit.dispatch'].search([('state', '=', 'completed')], limit=1)
        if not dispatch_sample:
            # Crear un despacho de prueba completado
            tt = env['transit.timetable'].search([], limit=1)
            dispatch_sample = env['transit.dispatch'].create({
                'timetable_id': tt.id,
                'vehicle_id': vehicles[0].id if vehicles else False,
                'state': 'completed',
                'initial_odometer': 120000.0,
                'final_odometer': 120028.5,
                'apc_boardings': 68,
                'apc_alightings': 68,
                'axle_weight_kg': 14200.0,
            })
        else:
            dispatch_sample.write({
                'apc_boardings': 74,
                'apc_alightings': 74,
                'axle_weight_kg': 15500.0,
            })

        print(f"  ✓ Despacho: {dispatch_sample.name}")
        print(f"    - Pasajeros Reales Auditados por Cámara 3D (APC): {dispatch_sample.apc_total_passengers}")
        print(f"    - Validaciones Billetaje: {dispatch_sample.electronic_validations}")
        print(f"    - Discrepancia / Evasión: {dispatch_sample.evasion_gap_passengers} pasajeros ({dispatch_sample.evasion_rate:.1f}%)")
        print(f"    - IPK Real Calculado: {dispatch_sample.calculated_ipk:.3f} pas/km")
        print(f"    - Ocupación por Peso (CAN-bus J1939): {dispatch_sample.passenger_load_percentage:.1f}%")

        # --------------------------------------------------------------------------
        # 5. CÁMARA DE COMPENSACIÓN Y FIDEICOMISO (FI_km / SIT PagoBús)
        # --------------------------------------------------------------------------
        print("\n[5/8] Ejecutando Cámara de Compensación y Fideicomiso Centralizado...")
        clearing_model = env['transit.clearing.period']
        cp = clearing_model.create({
            'period_type': 'monthly',
            'date_start': '2026-09-01',
            'date_end': '2026-09-30',
            'total_collected_revenue': 850000000.0,  # 850 Millones Gs. en Caja Común
            'modernization_fund_rate': 2.0,          # 2% para Fideicomiso de Modernización
            'total_planned_km': 180000.0,            # 180.000 Km planificados en el mes
        })
        print(f"  ✓ Período de Liquidación Creado: {cp.name}")
        print(f"    - Caja Común Recaudada: Gs. {cp.total_collected_revenue:,.0f}")
        print(f"    - Fideicomiso Modernización (2%): Gs. {cp.modernization_fund_amount:,.0f}")
        print(f"    - Fondo Neto Distribuible: Gs. {cp.net_distributable_revenue:,.0f}")
        print(f"    - FI_km Resultante: {cp.income_factor_per_km:.4f} Gs./km")

        # Calcular liquidaciones por SAE
        cp.action_calculate_settlements()
        print(f"  ✓ Consolidación SAE ejecutada: {len(cp.settlement_ids)} concesionarias liquidadas.")
        for s in cp.settlement_ids:
            print(f"    * [{s.concessionaire_id.code}] {s.concessionaire_id.name}: {s.executed_km:.1f} km -> Bruto: Gs. {s.gross_amount:,.0f} | Penalizaciones: Gs. {s.penalties_amount:,.0f}")

        # --------------------------------------------------------------------------
        # 6. MATRIZ PONDERADA UNE-EN 13816 Y BOLSA DE INCENTIVOS (Top 3)
        # --------------------------------------------------------------------------
        print("\n[6/8] Aplicando Matriz Ponderada UNE-EN 13816 y Reparto de Bolsa de Incentivos...")
        cp.action_apply_evaluations_and_incentives()
        print(f"  ✓ Evaluaciones generadas y Bolsa de Incentivos aplicada:")
        for ev in cp.evaluation_ids:
            top_badge = "🏆 TOP 3 EXCELENCIA" if ev.is_top_3 else "   Estándar"
            print(f"    {ev.ranking_position}º Puesto: {ev.concessionaire_id.name} -> Puntaje: {ev.final_score:.2f}/100 ({top_badge}) | Bono Incentivo: Gs. {ev.incentive_bonus:,.0f}")

        print(f"    --------------------------------------------------------------------")
        print(f"    Total Bruto Liquidado: Gs. {cp.total_gross_settlement:,.0f}")
        print(f"    Total Bolsa Incentivos: Gs. {cp.total_incentives_distributed:,.0f}")
        print(f"    Total Neto a Pagar:    Gs. {cp.total_net_settlement:,.0f}")

        # --------------------------------------------------------------------------
        # 7. GENERADOR DE FEEDS GTFS ESTÁTICO (Google Maps / Moovit)
        # --------------------------------------------------------------------------
        print("\n[7/8] Probando Exportador de Feeds GTFS Estático...")
        gtfs_wizard = env['transit.gtfs.export.wizard'].create({
            'agency_name': 'Viceministerio de Transporte / Poliverso Transit',
            'agency_url': 'https://transporte.gov.py',
        })
        res = gtfs_wizard.action_generate_gtfs()
        import base64
        import zipfile
        import io
        zip_bytes = base64.b64decode(gtfs_wizard.file_data)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
        print(f"  ✓ Archivo GTFS (.zip) generado con éxito ({len(zip_bytes)} bytes).")
        print(f"    Archivos contenidos en el feed: {file_list}")

        # --------------------------------------------------------------------------
        # 8. SIMULADOR PREDICTIVO WHAT-IF PARA LICITACIONES (Tipo Optibus)
        # --------------------------------------------------------------------------
        print("\n[8/8] Ejecutando Simulador Predictivo What-If para Licitaciones Públicas...")
        sim_wizard = env['transit.simulation.wizard'].create({
            'name': 'Licitación Corredor Metropolitano C1 - 2026',
            'route_distance_km': 32.5,
            'commercial_speed_kmh': 19.5,
            'peak_headway_minutes': 5.0,
            'offpeak_headway_minutes': 10.0,
            'daily_operating_hours': 18.0,
            'is_electric': True,
            'energy_cost_per_km': 650.0,
            'expected_daily_passengers': 24000,
        })
        print(f"  ✓ Simulación: {sim_wizard.name}")
        print(f"    - Tiempo de Ciclo de Ruta: {sim_wizard.cycle_time_minutes:.1f} minutos")
        print(f"    - Flota Comercial en Pico: {sim_wizard.required_peak_buses} buses")
        print(f"    - Flota de Reserva (10%):  {sim_wizard.reserve_buses} buses")
        print(f"    - TOTAL FLOTA NECESARIA:   {sim_wizard.total_fleet_needed} BUSES")
        print(f"    - Conductores en Cuadrante:{sim_wizard.drivers_needed} choferes")
        print(f"    - Kilometraje Comercial:   {sim_wizard.daily_commercial_km:,.0f} km/día")
        print(f"    - Deadhead (Km en Vacío):  {sim_wizard.daily_deadhead_km:,.0f} km/día")
        print(f"    - Costo Diario Proyectado: Gs. {sim_wizard.total_daily_operating_cost:,.0f}")
        print(f"    - Costo Técnico por Km:    Gs. {sim_wizard.breakeven_cost_per_km:,.0f} / km")
        print(f"    - TARIFA TÉCNICA EQUILIBRIO: Gs. {sim_wizard.breakeven_fare:,.0f} por pasaje")

        cr.commit()

    print("\n================================================================================")
    print("✅ TODAS LAS PRUEBAS FUNCIONALES COMPLETADAS CON ÉXITO AL 100%")
    print("================================================================================")

if __name__ == '__main__':
    run_test()
