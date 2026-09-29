# -*- coding: utf-8 -*-
{
    'name': 'Gestión Integral de Flota de Buses y Facturación Electrónica SIFEN',
    'version': '18.0.1.0.0',
    'summary': 'Control operativo de rutas, horarios, despachos en tiempo real, telemetría GPS y facturación electrónica SIFEN Paraguay',
    'description': """
Sistema Integral de Transporte de Pasajeros y Flota de Buses:
=============================================================
- **Control Administrativo de Flota**:
    * Ficha técnica de buses: número de interno, chasis, motor, asientos, equipamiento, rampa de accesibilidad.
    * Control de vencimientos: póliza de seguro, inspección técnica vehicular (ITV/VTV).
    * Integración directa con odómetro central y planes de mantenimiento preventivo.
    * Ficha de choferes con control de vigencia de licencias de conducir.

- **Operación y Tráfico en Tiempo Real**:
    * Gestión de rutas, ramales, cabeceras origen y destino, tiempos estándar.
    * Cuadros de marcha y horarios programados por día de la semana.
    * Despacho diario con checklist pre-operativo de salida (neumáticos, luces, frenos, validador).
    * Control de puntualidad y cumplimiento automático (retrasos/adelantos).
    * Checkpoints y paradas intermedias para registro de pasos teóricos vs reales.
    * Venta y emisión de boletos/pasajes de viaje.

- **Integración con Telemetría GPS / AVL**:
    * Endpoint REST (/api/v1/transit/events) para recibir eventos de telemetría sin sobrecargar el ERP.

- **Facturación Electrónica SIFEN Paraguay (Integración Denarius)**:
    * Generación y validación de CDC (Código de Control de 44 dígitos) con módulo 11.
    * Generación de código QR para consulta pública en e-Kuatia / SIFEN (DNIT Paraguay).
    * Emisión de comprobantes electrónicos a través del conector con el backend Denarius o de forma autónoma.
    * Trazabilidad directa entre boletos de viaje y facturas electrónicas oficiales.
    """,
    'author': 'Poliverso / Antigravity',
    'website': 'https://poliverso.com',
    'category': 'Operations/Fleet',
    'depends': [
        'base',
        'fleet',
        'mail',
        'account',
    ],
    'data': [
        'security/transit_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/transit_concessionaire_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/res_partner_views.xml',
        'views/transit_route_views.xml',
        'views/transit_timetable_views.xml',
        'views/transit_dispatch_views.xml',
        'views/transit_ticket_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/transit_clearing_views.xml',
        'views/transit_evaluation_views.xml',
        'views/transit_charging_views.xml',
        'views/transit_shift_preference_views.xml',
        'wizards/transit_schedule_generator_views.xml',
        'wizards/transit_gtfs_wizard_views.xml',
        'wizards/transit_simulation_wizard_views.xml',
        'views/transit_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
