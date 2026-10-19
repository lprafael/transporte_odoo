# -*- coding: utf-8 -*-
"""
Elimina el chofer de prueba 'Juan Carlos Benítez' (no pertenece a la planilla oficial).
Limpia cualquier referencia previa en transit_service_roundtrip.
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

def remove_demo_driver():
    print(f"[*] Conectando a {PG_HOST}:{PG_PORT}/{PG_DB}...")
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM res_partner WHERE name ILIKE '%Juan Carlos Ben%tez%';")
    rows = cur.fetchall()
    if not rows:
        print("[!] No se encontró ningún chofer con nombre 'Juan Carlos Benítez'.")
        cur.close()
        conn.close()
        return

    for p_id, p_name in rows:
        print(f"[*] Procesando chofer de prueba ID {p_id}: '{p_name}'...")
        
        # 1. Desvincular de transit_service_roundtrip
        cur.execute("UPDATE transit_service_roundtrip SET driver_id = NULL, driver_name = NULL WHERE driver_id = %s;", (p_id,))
        print(f"  -> Desvinculado de {cur.rowcount} viajes en transit_service_roundtrip.")

        # 2. Desvincular de transit_dispatch
        cur.execute("UPDATE transit_dispatch SET driver_id = NULL WHERE driver_id = %s;", (p_id,))
        print(f"  -> Desvinculado de {cur.rowcount} despachos.")

        # 3. Desvincular de fleet_vehicle
        cur.execute("UPDATE fleet_vehicle SET driver_id = NULL WHERE driver_id = %s;", (p_id,))
        print(f"  -> Desvinculado de {cur.rowcount} vehículos.")

        # 4. Eliminar de hr_employee si existiera
        cur.execute("DELETE FROM hr_employee WHERE work_contact_id = %s;", (p_id,))
        print(f"  -> Eliminado de {cur.rowcount} registros de empleados.")

        # 5. Eliminar de res_partner
        cur.execute("DELETE FROM res_partner WHERE id = %s;", (p_id,))
        print(f"  -> Chofer '{p_name}' (ID {p_id}) eliminado exitosamente de res_partner.")

    conn.commit()
    cur.close()
    conn.close()
    print("[✓] Proceso de eliminación completado exitosamente.")

if __name__ == '__main__':
    remove_demo_driver()
