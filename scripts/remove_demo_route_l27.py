# -*- coding: utf-8 -*-
"""
Elimina la ruta demo 'Línea 27 - Asunción a Capiatá' (ID 4 / L27-IDA)
y sus despachos y horarios de prueba asociados.
Además, asigna el rol de Administrador de Tránsito (group_transit_manager)
al usuario operador_arapoti para que tenga permisos de gestión.
"""
import os
import sys
import psycopg2

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5437))
PG_DB   = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def clean_route_l27():
    print(f"[*] Conectando a {PG_HOST}:{PG_PORT}/{PG_DB}...")
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
    cur = conn.cursor()

    cur.execute("SELECT id, code, name FROM transit_route WHERE code ILIKE '%L27%' OR id = 4;")
    routes = cur.fetchall()

    for r_id, r_code, r_name in routes:
        print(f"[*] Procesando ruta demo ID {r_id} ({r_code}: {r_name})...")

        # 1. Eliminar checkpoints de despachos asociados
        cur.execute("""
            DELETE FROM transit_dispatch_checkpoint 
            WHERE dispatch_id IN (SELECT id FROM transit_dispatch WHERE route_id = %s);
        """, (r_id,))
        print(f"  -> Eliminados {cur.rowcount} checkpoints de despacho.")

        # 2. Eliminar tickets de viaje asociados
        cur.execute("""
            DELETE FROM transit_ticket 
            WHERE dispatch_id IN (SELECT id FROM transit_dispatch WHERE route_id = %s);
        """, (r_id,))
        print(f"  -> Eliminados {cur.rowcount} tickets.")

        # 3. Eliminar despachos
        cur.execute("DELETE FROM transit_dispatch WHERE route_id = %s;", (r_id,))
        print(f"  -> Eliminados {cur.rowcount} despachos.")

        # 4. Eliminar horarios planificados
        cur.execute("DELETE FROM transit_timetable WHERE route_id = %s;", (r_id,))
        print(f"  -> Eliminados {cur.rowcount} horarios de cuadro de marcha.")

        # 5. Eliminar checkpoints de ruta
        cur.execute("DELETE FROM transit_route_checkpoint WHERE route_id = %s;", (r_id,))
        print(f"  -> Eliminados {cur.rowcount} checkpoints de ruta.")

        # 6. Eliminar formas / shapes
        cur.execute("DELETE FROM transit_route_shape WHERE route_id = %s;", (r_id,))
        print(f"  -> Eliminadas {cur.rowcount} formas / shapes.")

        # 7. Eliminar la ruta
        cur.execute("DELETE FROM transit_route WHERE id = %s;", (r_id,))
        print(f"  -> Ruta '{r_name}' (ID {r_id}) eliminada exitosamente.")

    # Otorgar grupo group_transit_manager a operador_arapoti
    cur.execute("SELECT id FROM res_users WHERE login = 'operador_arapoti';")
    user_row = cur.fetchone()
    if user_row:
        user_id = user_row[0]
        cur.execute("""
            SELECT g.id FROM res_groups g 
            JOIN ir_model_data md ON md.res_id = g.id 
            WHERE md.module = 'transit_operations' AND md.name = 'group_transit_manager';
        """)
        group_row = cur.fetchone()
        if group_row:
            mgr_group_id = group_row[0]
            cur.execute("""
                INSERT INTO res_groups_users_rel (gid, uid)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (mgr_group_id, user_id))
            print(f"[✓] Asignado rol Administrador de Tránsito (group_transit_manager) a 'operador_arapoti'.")

    conn.commit()
    cur.close()
    conn.close()
    print("[✓] Proceso completado exitosamente.")

if __name__ == '__main__':
    clean_route_l27()
