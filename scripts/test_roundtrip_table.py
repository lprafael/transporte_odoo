import odoo
from odoo import api, SUPERUSER_ID
from datetime import date

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'flota_db'])
registry = odoo.registry('flota_db')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    roundtrip_model = env['transit.service.roundtrip']
    
    # 1. Sincronizar servicios del día 11 de octubre de 2026
    test_date = date(2026, 10, 11)
    synced = roundtrip_model.sync_from_excel_files(test_date)
    cr.commit()
    print(f"Total registros sincronizados para {test_date}: {synced}")

    # 2. Probar filtrado por Servicio E1
    e1_records = roundtrip_model.search([('service_code', '=', 'E1'), ('date', '=', test_date)])
    e1_pas = sum(r.total_passengers for r in e1_records)
    e1_km = sum(r.total_km for r in e1_records)
    print(f"FILTRO [E1] ({test_date}): {len(e1_records)} redondos | Pasajeros: {e1_pas} | Km: {e1_km:.1f} | IPK: {(e1_pas/e1_km if e1_km else 0):.3f}")

    # 3. Probar filtrado por Servicio E2
    e2_records = roundtrip_model.search([('service_code', '=', 'E2'), ('date', '=', test_date)])
    e2_pas = sum(r.total_passengers for r in e2_records)
    e2_km = sum(r.total_km for r in e2_records)
    print(f"FILTRO [E2] ({test_date}): {len(e2_records)} redondos | Pasajeros: {e2_pas} | Km: {e2_km:.1f} | IPK: {(e2_pas/e2_km if e2_km else 0):.3f}")

    # 4. Probar filtrado por Servicio E3
    e3_records = roundtrip_model.search([('service_code', '=', 'E3'), ('date', '=', test_date)])
    e3_pas = sum(r.total_passengers for r in e3_records)
    e3_km = sum(r.total_km for r in e3_records)
    print(f"FILTRO [E3] ({test_date}): {len(e3_records)} redondos | Pasajeros: {e3_pas} | Km: {e3_km:.1f} | IPK: {(e3_pas/e3_km if e3_km else 0):.3f}")

    # 5. Total general del día en la tabla
    all_today = roundtrip_model.search([('date', '=', test_date)])
    print(f"TOTAL GENERAL EN TABLA: {len(all_today)} redondos consolidados")

    # Muestra de los primeros 3 registros
    for r in all_today[:3]:
        print(f"  -> {r.name} | Chofer: {r.driver_code} {r.driver_name} | Salida: {r.departure_ida} | Llegada: {r.arrival_vuelta} | Pasajeros: {r.total_passengers} | Km: {r.total_km} | Batería: {r.battery_soc_start}% -> {r.battery_soc_end}% ({r.battery_consumption}%, {r.excess_consumption})")
