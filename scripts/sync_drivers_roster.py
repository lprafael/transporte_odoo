# -*- coding: utf-8 -*-
"""
Sincronización del Padrón Oficial de Choferes de las Planillas de Tránsito en Odoo 18
Lee la hoja 'Resumen ' de E1 PLANILLA PRINCIPAL TRANSITO E1 OCTUBRE 2026.xlsx
e inserta o actualiza en res_partner (is_driver = True, driver_code = XXX).
"""
import os
import sys
import openpyxl
import psycopg2

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5435))
PG_DB   = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def sync_drivers():
    print("=" * 70)
    print("SINCRONIZACIÓN DE CONDUCTORES DESDE PLANILLA DE TRÁNSITO A ODOO")
    print("=" * 70)

    xlsx_path = os.path.join("Informe_empresa", "E1 PLANILLA PRINCIPAL TRANSITO E1 OCTUBRE 2026.xlsx")
    if not os.path.exists(xlsx_path):
        print(f"[-] Archivo no encontrado: {xlsx_path}")
        return

    print(f"[*] Leyendo nómina desde {xlsx_path} hoja 'Resumen '...")
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb['Resumen ']
    
    drivers_list = []
    for r in ws.iter_rows(min_row=2, max_row=60, values_only=True):
        if r[1] and r[2]:
            code = str(r[1]).strip()
            # Si el código es numérico, formatear a 3 dígitos '002'
            if code.isdigit():
                code = f"{int(code):03d}"
            name = str(r[2]).strip()
            drivers_list.append((code, name))
    wb.close()

    print(f"[+] Total choferes detectados en plantilla: {len(drivers_list)}")

    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
    cur = conn.cursor()

    # Obtener ID de la concesionaria principal Consorcio Arapotí
    cur.execute("SELECT id FROM transit_concessionaire WHERE code = '004B' LIMIT 1;")
    concessionaire_row = cur.fetchone()
    concessionaire_id = concessionaire_row[0] if concessionaire_row else None

    # Verificar si columna driver_code existe en res_partner
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'res_partner' AND column_name = 'driver_code';
    """)
    if not cur.fetchone():
        print("[*] Creando columna driver_code en res_partner...")
        cur.execute("ALTER TABLE res_partner ADD COLUMN driver_code VARCHAR(32);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_res_partner_driver_code ON res_partner(driver_code);")
        conn.commit()

    synced_count = 0
    for code, full_name in drivers_list:
        # Buscar por driver_code o por name
        cur.execute("""
            SELECT id FROM res_partner 
            WHERE driver_code = %s OR name = %s OR name ILIKE %s
            LIMIT 1;
        """, (code, full_name, f"%{full_name[:15]}%"))
        existing = cur.fetchone()

        if existing:
            p_id = existing[0]
            cur.execute("""
                UPDATE res_partner 
                SET is_driver = true,
                    driver_code = %s,
                    name = %s,
                    concessionaire_id = COALESCE(concessionaire_id, %s)
                WHERE id = %s;
            """, (code, full_name, concessionaire_id, p_id))
        else:
            cur.execute("""
                INSERT INTO res_partner (
                    name, is_driver, driver_code, concessionaire_id,
                    driver_license_category, driver_license_expiry,
                    sifen_doc_type, active, autopost_bills, create_date, write_date
                ) VALUES (
                    %s, true, %s, %s,
                    'prof_b', '2028-12-31',
                    '1', true, 'ask', NOW(), NOW()
                ) RETURNING id;
            """, (full_name, code, concessionaire_id))
        synced_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"[✓] {synced_count} conductores sincronizados exitosamente en Odoo!")

if __name__ == '__main__':
    sync_drivers()
