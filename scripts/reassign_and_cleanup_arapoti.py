# -*- coding: utf-8 -*-
"""
Script de Consolidación y Limpieza Integral para Consorcio Arapotí.

Objetivos:
1. Asegurar la Concesionaria 'Consorcio Arapotí' (ID 4, código 004B).
2. Asignar los 30 buses eléctricos oficiales (IOT093 a IOT129) a Consorcio Arapotí.
3. Eliminar vehículos de prueba ajenos (ABC 123, XYZ 789) y sus registros dependientes.
4. Asignar todos los servicios operativos (E1, E2, E3) a Consorcio Arapotí.
5. Asignar todas las rutas oficiales (020c, 020d, 020e, 020f, 0210, 0211 y 0000) a Consorcio Arapotí (agencia 004B).
6. Eliminar la ruta ajena de prueba (L27-IDA) y sus paradas/horarios asociados.
7. Asignar todos los horarios (cuadro de marcha, 692 salidas) a Consorcio Arapotí.
8. Asignar estación de carga / patio de maniobras a Consorcio Arapotí.
9. Limpiar evaluaciones y liquidaciones de prueba de empresas ajenas.
10. Desactivar usuarios de otras empresas y vincular los usuarios operativos y de administración a Arapotí.
11. Eliminar empresas/concesionarias de prueba obsoletas (IDs 1, 2, 3).
12. Actualizar la compañía principal de Odoo (res_company) a 'Consorcio Arapotí'.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

def run_cleanup():
    conn = psycopg2.connect(
        host='localhost',
        port=5434,
        dbname='flota_db',
        user='odoo',
        password='odoo_password'
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        print("=" * 65)
        print(" INICIANDO CONSOLIDACIÓN Y LIMPIEZA - CONSORCIO ARAPOTÍ")
        print("=" * 65)

        # 1. Concesionaria Arapotí (ID 4)
        cur.execute("""
            UPDATE transit_concessionaire 
            SET name = 'Consorcio Arapotí', 
                code = '004B', 
                active = TRUE 
            WHERE id = 4;
        """)
        print("[+] Concesionaria ID 4 asegurada como 'Consorcio Arapotí' (Código: 004B)")

        # 2. Reasignar los 30 buses eléctricos
        cur.execute("""
            UPDATE fleet_vehicle 
            SET concessionaire_id = 4 
            WHERE license_plate LIKE 'IOT%';
        """)
        print(f"[+] {cur.rowcount} buses eléctricos (flota oficial) asignados a Consorcio Arapotí")

        # 3. Eliminar vehículos de prueba (ABC 123, XYZ 789) y sus dependencias
        cur.execute("""
            -- Limpiar checkpoints de despachos de prueba
            DELETE FROM transit_dispatch_checkpoint 
            WHERE dispatch_id IN (
                SELECT id FROM transit_dispatch 
                WHERE vehicle_id IN (SELECT id FROM fleet_vehicle WHERE license_plate IN ('ABC 123', 'XYZ 789'))
            );

            -- Limpiar boletos vinculados a despachos de prueba
            DELETE FROM transit_ticket 
            WHERE dispatch_id IN (
                SELECT id FROM transit_dispatch 
                WHERE vehicle_id IN (SELECT id FROM fleet_vehicle WHERE license_plate IN ('ABC 123', 'XYZ 789'))
            );

            -- Limpiar despachos de prueba
            DELETE FROM transit_dispatch 
            WHERE vehicle_id IN (SELECT id FROM fleet_vehicle WHERE license_plate IN ('ABC 123', 'XYZ 789'));

            -- Limpiar logs de vehículo
            DELETE FROM fleet_vehicle_log_services 
            WHERE vehicle_id IN (SELECT id FROM fleet_vehicle WHERE license_plate IN ('ABC 123', 'XYZ 789'));

            DELETE FROM fleet_vehicle_log_contract 
            WHERE vehicle_id IN (SELECT id FROM fleet_vehicle WHERE license_plate IN ('ABC 123', 'XYZ 789'));

            DELETE FROM fleet_vehicle_odometer 
            WHERE vehicle_id IN (SELECT id FROM fleet_vehicle WHERE license_plate IN ('ABC 123', 'XYZ 789'));

            -- Eliminar los vehículos de prueba
            DELETE FROM fleet_vehicle 
            WHERE license_plate IN ('ABC 123', 'XYZ 789');
        """)
        print("[+] Vehículos de prueba ajenos (ABC 123, XYZ 789) y sus registros eliminados exitosamente")

        # 4. Asignar Servicios Operativos (E1, E2, E3)
        cur.execute("""
            UPDATE transit_service 
            SET concessionaire_id = 4 
            WHERE code IN ('E1', 'E2', 'E3') OR id IN (1, 2, 3);
        """)
        print(f"[+] {cur.rowcount} servicios operativos (E1, E2, E3) asignados a Consorcio Arapotí")

        # 5. Reasignar todas las rutas oficiales a Consorcio Arapotí
        cur.execute("""
            UPDATE transit_route 
            SET concessionaire_id = 4, agency_id = '004B' 
            WHERE code IN ('020c', '020d', '020e', '020f', '0210', '0211', '0000');
        """)
        print(f"[+] {cur.rowcount} rutas oficiales asignadas a Consorcio Arapotí (agencia 004B)")

        # 6. Eliminar ruta de prueba ajena (L27-IDA)
        cur.execute("""
            DELETE FROM transit_route_checkpoint 
            WHERE route_id IN (SELECT id FROM transit_route WHERE code = 'L27-IDA');

            DELETE FROM transit_timetable 
            WHERE route_id IN (SELECT id FROM transit_route WHERE code = 'L27-IDA');

            DELETE FROM transit_route 
            WHERE code = 'L27-IDA';
        """)
        print("[+] Ruta de prueba ajena (L27-IDA) y sus paradas/horarios eliminados")

        # 7. Asignar todos los horarios del cuadro de marcha
        cur.execute("UPDATE transit_timetable SET concessionaire_id = 4;")
        print(f"[+] {cur.rowcount} horarios del cuadro de marcha asignados a Consorcio Arapotí")

        # 8. Asignar infraestructura de carga y patios
        cur.execute("UPDATE transit_charging_station SET concessionaire_id = 4;")
        print(f"[+] Estación de carga / cochera patio central asignada a Consorcio Arapotí")

        # 9. Limpiar registros de liquidaciones y evaluaciones de empresas ajenas
        cur.execute("""
            DELETE FROM transit_clearing_settlement WHERE concessionaire_id IN (1, 2, 3);
            DELETE FROM transit_concessionaire_evaluation WHERE concessionaire_id IN (1, 2, 3);
        """)
        print("[+] Liquidaciones y evaluaciones de empresas de prueba eliminadas")

        # 10. Actualizar usuarios del sistema
        cur.execute("""
            -- Desactivar operador de otra empresa
            UPDATE res_users 
            SET active = FALSE, concessionaire_id = NULL 
            WHERE login = 'operador_sanlorenzo';

            -- Asignar operador línea 20 a Arapotí
            UPDATE res_users 
            SET concessionaire_id = 4 
            WHERE login = 'operador_linea20';

            -- Limpiar relaciones de usuarios con concesionarias ajenas
            DELETE FROM transit_concessionaire_res_users_rel WHERE concessionaire_id IN (1, 2, 3);

            -- Vincular operador_linea20 (ID 9), admin (ID 2) y usuario principal (ID 6) a Arapotí
            INSERT INTO transit_concessionaire_res_users_rel (concessionaire_id, user_id)
            VALUES (4, 9)
            ON CONFLICT DO NOTHING;

            INSERT INTO transit_concessionaire_res_users_rel (concessionaire_id, user_id)
            VALUES (4, 2)
            ON CONFLICT DO NOTHING;

            INSERT INTO transit_concessionaire_res_users_rel (concessionaire_id, user_id)
            VALUES (4, 6)
            ON CONFLICT DO NOTHING;
        """)
        print("[+] Usuarios y permisos asignados a Consorcio Arapotí")

        # 11. Eliminar concesionarias de prueba (IDs 1, 2, 3)
        cur.execute("DELETE FROM transit_concessionaire WHERE id IN (1, 2, 3);")
        print(f"[+] {cur.rowcount} concesionarias ajenas eliminadas de transit_concessionaire")

        # 12. Actualizar compañía principal en Odoo ERP
        cur.execute("""
            UPDATE res_company 
            SET name = 'Consorcio Arapotí' 
            WHERE id = 1;

            UPDATE res_partner 
            SET name = 'Consorcio Arapotí' 
            WHERE id = (SELECT partner_id FROM res_company WHERE id = 1);
        """)
        print("[+] Empresa principal en Odoo ERP actualizada a 'Consorcio Arapotí'")

        # Commit final
        conn.commit()
        print("\n" + "=" * 65)
        print(" [SUCCESS] TRANSACCIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 65)

        # 13. Verificación de Auditoría
        print("\n--- RESUMEN FINAL DE LA BASE DE DATOS ---")
        
        cur.execute("SELECT id, name, code, active FROM transit_concessionaire ORDER BY id;")
        print("1. Concesionarias registradas:")
        for r in cur.fetchall():
            print(f"   • ID {r['id']}: {r['name']} (Código: {r['code']}, Activo: {r['active']})")

        cur.execute("SELECT COUNT(*) as count FROM fleet_vehicle WHERE concessionaire_id = 4;")
        v_count = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) as total FROM fleet_vehicle;")
        v_total = cur.fetchone()['total']
        print(f"2. Flota de Buses: {v_count} de {v_total} asignados a Consorcio Arapotí")

        cur.execute("SELECT id, code, name, concessionaire_id, agency_id FROM transit_route ORDER BY code;")
        print("3. Rutas activas:")
        for r in cur.fetchall():
            print(f"   • [{r['code'].upper()}] {r['name']} (Agencia: {r['agency_id']}, Concesionaria ID: {r['concessionaire_id']})")

        cur.execute("SELECT id, code, name, concessionaire_id FROM transit_service ORDER BY code;")
        print("4. Servicios operativos:")
        for r in cur.fetchall():
            print(f"   • [{r['code']}] {r['name']} (Concesionaria ID: {r['concessionaire_id']})")

        cur.execute("SELECT COUNT(*) as count FROM transit_route_checkpoint;")
        print(f"5. Puntos de control / Geocercas: {cur.fetchone()['count']} paradas")

        cur.execute("SELECT COUNT(*) as count FROM transit_route_shape;")
        print(f"6. Trazados de ruta (Shapes): {cur.fetchone()['count']} trazas")

        cur.execute("SELECT COUNT(*) as count FROM transit_timetable WHERE concessionaire_id = 4;")
        print(f"7. Cuadro de Marcha: {cur.fetchone()['count']} salidas horarias programadas")

        cur.execute("SELECT id, name FROM transit_charging_station;")
        print("8. Estaciones de carga:")
        for r in cur.fetchall():
            print(f"   • ID {r['id']}: {r['name']}")

        cur.execute("SELECT id, name FROM res_company WHERE id = 1;")
        print(f"9. Empresa Principal Odoo: {cur.fetchone()['name']}")
        print("=" * 65)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Falló la operación: {e}")
        raise e
    finally:
        conn.close()

if __name__ == '__main__':
    run_cleanup()
