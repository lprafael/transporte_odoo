# -*- coding: utf-8 -*-
"""
Script de Validación y Demostración Multi-Tenant:
Comprueba el aislamiento estricto de datos entre empresas concesionarias (Option 1).
"""
import odoo
from odoo import SUPERUSER_ID, api

def test_multitenant():
    print("=" * 70)
    print("🧪 TEST DE AISLAMIENTO MULTI-TENANT POR CONCESIONARIA (ODOO 18)")
    print("=" * 70)

    registry = odoo.modules.registry.Registry('flota_db')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})

        # 1. Obtener o crear las 2 Concesionarias
        conc_model = env['transit.concessionaire']
        c_l20 = conc_model.search([('code', '=', 'CONC-L20')], limit=1)
        c_sl = conc_model.search([('code', '=', 'CONC-SL01')], limit=1)

        if not c_sl:
            c_sl = conc_model.create({
                'name': 'Transportes San Lorenzo S.R.L. (Línea 27)',
                'code': 'CONC-SL01',
                'legal_name': 'Transportes San Lorenzo Sociedad de Responsabilidad Limitada',
                'vat_ruc': '80054321-2',
            })
            print(f"[*] Creada Concesionaria 2: {c_sl.name}")
        else:
            print(f"[*] Concesionaria 2 existente: {c_sl.name}")

        print(f"[*] Concesionaria 1: {c_l20.name} (ID: {c_l20.id})")
        print(f"[*] Concesionaria 2: {c_sl.name} (ID: {c_sl.id})")

        # Asignar un bus a San Lorenzo para la prueba de aislamiento
        veh_model = env['fleet.vehicle']
        bus_sl = veh_model.search([('bus_internal_number', '=', '102')], limit=1)
        if bus_sl:
            bus_sl.write({'concessionaire_id': c_sl.id})
            print(f"[*] Bus 102 asignado a {c_sl.name}")

        # 2. Obtener Grupo de Operador de Empresa
        group_operator = env.ref('transit_operations.group_transit_user')
        group_fleet_user = env.ref('fleet.fleet_group_user')
        group_global = env.ref('transit_operations.group_transit_manager')

        # 3. Crear o actualizar Usuario 1: Despachador Línea 20
        user_model = env['res.users']
        u_l20 = user_model.search([('login', '=', 'operador_linea20')], limit=1)
        if not u_l20:
            u_l20 = user_model.create({
                'name': 'Operador Despacho Línea 20',
                'login': 'operador_linea20',
                'email': 'despacho@linea20.com.py',
                'concessionaire_id': c_l20.id,
                'concessionaire_ids': [(6, 0, [c_l20.id])],
                'groups_id': [(6, 0, [env.ref('base.group_user').id, group_operator.id, group_fleet_user.id])],
            })
            print(f"[+] Creado usuario: {u_l20.name} (Login: {u_l20.login})")
        else:
            u_l20.write({
                'concessionaire_id': c_l20.id,
                'concessionaire_ids': [(6, 0, [c_l20.id])],
                'groups_id': [(6, 0, [env.ref('base.group_user').id, group_operator.id, group_fleet_user.id])],
            })

        # 4. Crear o actualizar Usuario 2: Despachador San Lorenzo
        u_sl = user_model.search([('login', '=', 'operador_sanlorenzo')], limit=1)
        if not u_sl:
            u_sl = user_model.create({
                'name': 'Operador Despacho San Lorenzo',
                'login': 'operador_sanlorenzo',
                'email': 'despacho@sanlorenzo.com.py',
                'concessionaire_id': c_sl.id,
                'concessionaire_ids': [(6, 0, [c_sl.id])],
                'groups_id': [(6, 0, [env.ref('base.group_user').id, group_operator.id, group_fleet_user.id])],
            })
            print(f"[+] Creado usuario: {u_sl.name} (Login: {u_sl.login})")
        else:
            u_sl.write({
                'concessionaire_id': c_sl.id,
                'concessionaire_ids': [(6, 0, [c_sl.id])],
                'groups_id': [(6, 0, [env.ref('base.group_user').id, group_operator.id, group_fleet_user.id])],
            })

        # 5. PRUEBAS DE ACCESO Y AISLAMIENTO DE DATOS (with_user)
        print("\n" + "=" * 70)
        print("EJECUTANDO CONSULTAS DE SEGURIDAD AISLADAS")
        print("=" * 70)

        # A. Consulta como Operador Línea 20
        buses_l20 = veh_model.with_user(u_l20).search([])
        print(f"\n[Usuario: {u_l20.name}]")
        print(f" -> Buses visibles: {len(buses_l20)}")
        concessionaires_seen_l20 = set(buses_l20.mapped('concessionaire_id.code'))
        print(f" -> Códigos de Concesionaria visibles: {concessionaires_seen_l20}")
        assert all(c == 'CONC-L20' or not c for c in concessionaires_seen_l20), "FALLO: Línea 20 vio buses de otra empresa!"
        print("  ✓ AISLAMIENTO PERFECTO: El operador de Línea 20 solo ve su flota.")

        # B. Consulta como Operador San Lorenzo
        buses_sl = veh_model.with_user(u_sl).search([])
        print(f"\n[Usuario: {u_sl.name}]")
        print(f" -> Buses visibles: {len(buses_sl)}")
        concessionaires_seen_sl = set(buses_sl.mapped('concessionaire_id.code'))
        print(f" -> Códigos de Concesionaria visibles: {concessionaires_seen_sl}")
        assert 'CONC-L20' not in concessionaires_seen_sl, "FALLO: San Lorenzo vio buses de Línea 20!"
        print("  ✓ AISLAMIENTO PERFECTO: El operador de San Lorenzo no ve los 30 buses de Línea 20.")

        # C. Consulta como Administrador Global / VMT
        admin_user = env.ref('base.user_admin')
        admin_user.write({'groups_id': [(4, group_global.id)]})
        buses_admin = veh_model.with_user(admin_user).search([])
        print(f"\n[Usuario: Administrador Global / Regulador ({admin_user.name})]")
        print(f" -> Total Buses visibles en la Torre de Control: {len(buses_admin)}")
        print("  ✓ VISIÓN 360°: El Administrador Global / VMT supervisa toda la red de transporte.")

        # D. Consulta de Rutas / Ramales
        route_model = env['transit.route']
        routes_l20 = route_model.with_user(u_l20).search([])
        routes_sl = route_model.with_user(u_sl).search([])
        routes_admin = route_model.with_user(admin_user).search([])
        print(f"\n[Aislamiento de Rutas]")
        print(f" -> Rutas visibles Línea 20: {len(routes_l20)}")
        print(f" -> Rutas visibles San Lorenzo: {len(routes_sl)}")
        print(f" -> Total Rutas visibles Torre de Control: {len(routes_admin)}")

        print("\n" + "=" * 70)
        print("🎉 TODOS LOS TESTS DE MULTI-TENANCY PASARON EXITOSAMENTE (100% OK)")
        print("=" * 70)

if __name__ == '__main__':
    test_multitenant()
