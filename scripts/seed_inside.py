# -*- coding: utf-8 -*-
"""
Carga datos de demostración directamente usando el ORM de Odoo 18
"""
import odoo
from odoo import SUPERUSER_ID, fields
from datetime import datetime, date, time

registry = odoo.modules.registry.Registry('flota_db')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, SUPERUSER_ID, {})

    print("=== Inicializando Datos Demo en flota_db (Odoo 18) ===")

    # 1. Marca y Modelo de Bus
    brand = env['fleet.vehicle.model.brand'].search([('name', '=', 'Mercedes-Benz')], limit=1)
    if not brand:
        brand = env['fleet.vehicle.model.brand'].create({'name': 'Mercedes-Benz'})

    model = env['fleet.vehicle.model'].search([('name', '=', 'OF-1722 / Marcopolo')], limit=1)
    if not model:
        model = env['fleet.vehicle.model'].create({
            'name': 'OF-1722 / Marcopolo',
            'brand_id': brand.id,
            'vehicle_type': 'car'
        })

    # 2. Vehículos / Buses
    bus104 = env['fleet.vehicle'].search([('bus_internal_number', '=', '104')], limit=1)
    if not bus104:
        bus104 = env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': 'ABC 123',
            'bus_internal_number': '104',
            'seating_capacity': 45,
            'standing_capacity': 20,
            'has_air_conditioning': True,
            'has_wheelchair_ramp': True,
            'validator_terminal_id': 'VAL-PY-0104',
            'itv_expiry_date': '2027-06-30',
            'insurance_policy': 'MAPFRE-POL-98421',
            'insurance_expiry_date': '2027-12-31'
        })
        env['fleet.vehicle.odometer'].create({
            'vehicle_id': bus104.id,
            'value': 154200.0,
            'date': date.today()
        })
        print(f"Bus Coche 104 creado. ID: {bus104.id}")
    else:
        print(f"Bus Coche 104 ya existe. ID: {bus104.id}")

    bus102 = env['fleet.vehicle'].search([('bus_internal_number', '=', '102')], limit=1)
    if not bus102:
        bus102 = env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': 'XYZ 789',
            'bus_internal_number': '102',
            'seating_capacity': 50,
            'standing_capacity': 15,
            'has_air_conditioning': True,
            'has_wheelchair_ramp': False,
            'validator_terminal_id': 'VAL-PY-0102',
            'itv_expiry_date': '2027-08-15',
            'insurance_policy': 'ASEG-PY-44120',
            'insurance_expiry_date': '2027-11-30'
        })
        env['fleet.vehicle.odometer'].create({
            'vehicle_id': bus102.id,
            'value': 210450.0,
            'date': date.today()
        })
        print(f"Bus Coche 102 creado. ID: {bus102.id}")

    # 3. Chofer
    chofer = env['res.partner'].search([('name', '=', 'Juan Carlos Benítez')], limit=1)
    if not chofer:
        chofer = env['res.partner'].create({
            'name': 'Juan Carlos Benítez',
            'is_driver': True,
            'driver_license_number': 'LIC-PROF-89410',
            'driver_license_category': 'prof_b',
            'driver_license_expiry': '2028-05-15',
            'vat_ruc': '3456789',
            'vat_dv': '1',
            'sifen_doc_type': '1'
        })
        print(f"Chofer creado. ID: {chofer.id}")

    # 4. Ruta
    ruta = env['transit.route'].search([('code', '=', 'L27-IDA')], limit=1)
    if not ruta:
        ruta = env['transit.route'].create({
            'name': 'Línea 27 - Asunción a Capiatá',
            'code': 'L27-IDA',
            'direction': 'inbound',
            'origin': 'Terminal Asunción (Cabecera)',
            'destination': 'Capiatá Km 20 (Cabecera)',
            'distance_km': 28.5,
            'standard_duration_minutes': 65,
            'standard_fare': 3400.0
        })
        print(f"Ruta creada. ID: {ruta.id}")

    # 5. Horario
    horario = env['transit.timetable'].search([('route_id', '=', ruta.id), ('service_code', '=', 'S01')], limit=1)
    if not horario:
        horario = env['transit.timetable'].create({
            'route_id': ruta.id,
            'service_code': 'S01',
            'departure_time_float': 7.0,  # 07:00 AM
            'scheduled_duration_minutes': 65,
            'day_of_week': 'all'
        })
        print(f"Horario S01 creado. ID: {horario.id}")

    # 6. Despacho Diario
    today = date.today()
    scheduled_dt = datetime.combine(today, time(7, 0))
    despacho = env['transit.dispatch'].search([('date', '=', today), ('vehicle_id', '=', bus104.id)], limit=1)
    if not despacho:
        despacho = env['transit.dispatch'].create({
            'date': today,
            'timetable_id': horario.id,
            'vehicle_id': bus104.id,
            'driver_id': chofer.id,
            'scheduled_departure': scheduled_dt,
            'initial_odometer': 154200.0,
            'check_tires': True,
            'check_brakes': True,
            'check_lights': True,
            'check_fluids': True,
            'check_validator': True
        })
        despacho.action_inspect()
        print(f"Despacho para hoy creado e inspeccionado. ID: {despacho.id} (Nombre: {despacho.name})")

        # Crear 2 boletos de muestra
        t1 = env['transit.ticket'].create({
            'dispatch_id': despacho.id,
            'passenger_name': 'María González',
            'passenger_doc': '4512301',
            'seat_number': '12',
            'price': 3400.0
        })
        # Asegurar Diario de Ventas
        sale_journal = env['account.journal'].search([('type', '=', 'sale')], limit=1)
        if not sale_journal:
            sale_journal = env['account.journal'].create({
                'name': 'Facturas de Pasajes y Cargas',
                'type': 'sale',
                'code': 'VTA'
            })

        # Emitir factura electrónica para el primer boleto
        inv_action = t1.action_create_electronic_invoice()
        inv_id = t1.invoice_id
        inv_id.action_post()
        inv_id.action_send_sifen_denarius()
        print(f"Boleto {t1.name} facturado electrónicamente con CDC: {inv_id.sifen_cdc}")

    cr.commit()
    print("=== Datos de demostración y Factura Electrónica SIFEN creados con éxito! ===")
