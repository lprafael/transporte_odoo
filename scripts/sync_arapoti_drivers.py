# -*- coding: utf-8 -*-
"""
Carga y Sincronización Oficial de Conductores - Consorcio Arapotí
Fuente: Referencias/CONDUCTORES (CI-IPS-MTESS) 10-2026.xlsx
Destino: Odoo 18 (res_partner y hr_employee)
"""
import os
import sys
import re
import datetime
import openpyxl
import psycopg2

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5437))
PG_DB   = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def clean_str(s):
    if s is None:
        return ""
    return str(s).strip()

def normalize_ci(ci_raw):
    if ci_raw is None:
        return ""
    s = str(ci_raw).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return re.sub(r'\D', '', s)

def parse_date(val):
    if not val:
        return None
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.date() if isinstance(val, datetime.datetime) else val
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ('x', '-', 'n/a'):
        return None
    val_str = re.sub(r'/+', '/', val_str)
    for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y'):
        try:
            return datetime.datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    print(f"[-] Advertencia: formato de fecha no reconocido: {val}")
    return None

def sync_arapoti_drivers():
    print("=" * 90)
    print("CARGA Y SINCRONIZACIÓN DE CONDUCTORES - CONSORCIO ARAPOTÍ (MTESS / IPS / CI / LICENCIAS)")
    print("=" * 90)

    xlsx_path = os.path.join("Referencias", "CONDUCTORES (CI-IPS-MTESS) 10-2026.xlsx")
    if not os.path.exists(xlsx_path):
        print(f"[-] Archivo no encontrado: {xlsx_path}")
        return

    print(f"[*] Leyendo archivo oficial: {xlsx_path}...")
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb['Hoja1']
    rows = list(ws.iter_rows(values_only=True))[1:]
    wb.close()

    excel_drivers = []
    for idx, r in enumerate(rows, start=1):
        if r[0] is None and r[1] is None:
            continue
        nro, apellido, nombres, ci_raw, venc_ci_raw, reg_raw, venc_reg_raw, mtess_raw, ips_raw = r[:9]
        ci = normalize_ci(ci_raw)
        venc_ci = parse_date(venc_ci_raw)
        reg = clean_str(reg_raw)
        if reg.lower() == 'x':
            reg = ""
        else:
            if reg.endswith('.0'):
                reg = reg[:-2]
            reg = normalize_ci(reg)
        venc_reg = parse_date(venc_reg_raw)
        mtess = parse_date(mtess_raw)
        ips = parse_date(ips_raw)
        full_name = f"{clean_str(nombres)} {clean_str(apellido)}".strip()

        excel_drivers.append({
            'nro': nro,
            'apellido': clean_str(apellido),
            'nombres': clean_str(nombres),
            'full_name': full_name,
            'ci': ci,
            'venc_ci': venc_ci,
            'registro': reg,
            'venc_reg': venc_reg,
            'mtess': mtess,
            'ips': ips,
        })

    print(f"[+] Total de conductores leídos en Excel: {len(excel_drivers)}")

    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
    cur = conn.cursor()

    # 1. Asegurar columnas en base de datos
    cur.execute("""
        ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS driver_ci_expiry DATE;
        ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS mtess_date DATE;
        ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS ips_date DATE;
        ALTER TABLE hr_employee ADD COLUMN IF NOT EXISTS driver_ci_expiry DATE;
        ALTER TABLE hr_employee ADD COLUMN IF NOT EXISTS mtess_date DATE;
        ALTER TABLE hr_employee ADD COLUMN IF NOT EXISTS ips_date DATE;
    """)
    conn.commit()

    # 2. Concesionaria Consorcio Arapotí
    cur.execute("SELECT id, name FROM transit_concessionaire WHERE code = '004B' OR name ILIKE '%Arapot%' LIMIT 1;")
    conc_row = cur.fetchone()
    if not conc_row:
        print("[-] Error: No se encontró la concesionaria Consorcio Arapotí.")
        return
    concessionaire_id = conc_row[0]
    concessionaire_name = conc_row[1]
    print(f"[✓] Concesionaria identificada: {concessionaire_name} (ID: {concessionaire_id})")

    # 3. Obtener conductores actuales en res_partner
    cur.execute("""
        SELECT id, name, driver_code, vat
        FROM res_partner
        WHERE is_driver = true AND (concessionaire_id = %s OR concessionaire_id IS NULL)
        ORDER BY driver_code, id;
    """, (concessionaire_id,))
    db_partners = cur.fetchall()

    def find_match(ed):
        ap_words = [w.lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace('ñ','n').replace('ü','u') for w in ed['apellido'].split() if len(w) > 2]
        nom_words = [w.lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace('ñ','n').replace('ü','u') for w in ed['nombres'].split() if len(w) > 2]

        # Casos especiales de ortografía / apodos
        if 'felix' in nom_words and any(x in ('alfonzo', 'alfonso') for x in ap_words):
            for p in db_partners:
                if str(p[2]).startswith('014'): return p
        if 'ruben' in nom_words and 'ruiz' in ap_words:
            for p in db_partners:
                if str(p[2]).startswith('036'): return p

        scored = []
        for p in db_partners:
            p_name_clean = p[1].lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace('ñ','n').replace('ü','u')
            p_words = p_name_clean.split()
            ap_match = any(w in p_words or w in p_name_clean for w in ap_words)
            nom_match = any(w in p_words for w in nom_words)
            if ap_match and nom_match:
                scored.append(p)

        if len(scored) == 1:
            return scored[0]
        elif len(scored) > 1:
            for s in scored:
                s_clean = s[1].lower()
                if ed['apellido'].lower() in s_clean:
                    return s
            return scored[0]
        return None

    # Encontrar código máximo actual para asignar nuevos
    cur.execute("""
        SELECT driver_code FROM res_partner 
        WHERE is_driver = true AND driver_code IS NOT NULL;
    """)
    existing_codes = []
    for r in cur.fetchall():
        c_str = str(r[0]).split('.')[0].strip()
        if c_str.isdigit():
            existing_codes.append(int(c_str))
    next_code_int = max(existing_codes) + 1 if existing_codes else 1

    synced_partners = []
    used_partner_ids = set()

    for ed in excel_drivers:
        match_p = find_match(ed)
        if match_p and match_p[0] not in used_partner_ids:
            p_id = match_p[0]
            used_partner_ids.add(p_id)
            # Conservar código existente normalizado a 3 dígitos
            orig_code = str(match_p[2]).split('.')[0].strip()
            if orig_code.isdigit():
                code = f"{int(orig_code):03d}"
            else:
                code = orig_code
        else:
            # Crear nuevo partner
            code = f"{next_code_int:03d}"
            next_code_int += 1
            cur.execute("""
                INSERT INTO res_partner (
                    name, is_driver, driver_code, ref, concessionaire_id,
                    driver_license_category, sifen_doc_type, active, autopost_bills,
                    create_date, write_date
                ) VALUES (
                    %s, true, %s, %s, %s,
                    'prof_b', '1', true, 'ask',
                    NOW(), NOW()
                ) RETURNING id;
            """, (ed['full_name'], code, code, concessionaire_id))
            p_id = cur.fetchone()[0]

        # Actualizar res_partner con todos los datos legales y laborales
        cur.execute("""
            UPDATE res_partner
            SET name = %s,
                is_driver = true,
                driver_code = %s,
                ref = %s,
                vat = %s,
                driver_ci_expiry = %s,
                driver_license_number = %s,
                driver_license_category = 'prof_b',
                driver_license_expiry = %s,
                mtess_date = %s,
                ips_date = %s,
                sifen_doc_type = '1',
                concessionaire_id = %s,
                write_date = NOW()
            WHERE id = %s;
        """, (
            ed['full_name'],
            code,
            code,
            ed['ci'],
            ed['venc_ci'],
            ed['registro'] if ed['registro'] else None,
            ed['venc_reg'],
            ed['mtess'],
            ed['ips'],
            concessionaire_id,
            p_id
        ))

        # Sincronizar en hr_employee
        cur.execute("""
            SELECT id FROM hr_employee
            WHERE work_contact_id = %s OR identification_id = %s OR driver_code = %s
            LIMIT 1;
        """, (p_id, ed['ci'], code))
        emp_row = cur.fetchone()

        if emp_row:
            emp_id = emp_row[0]
            cur.execute("""
                UPDATE hr_employee
                SET name = %s,
                    driver_code = %s,
                    identification_id = %s,
                    ssnid = %s,
                    driver_license_number = %s,
                    driver_license_category = 'prof_b',
                    driver_license_expiry = %s,
                    driver_ci_expiry = %s,
                    mtess_date = %s,
                    ips_date = %s,
                    concessionaire_id = %s,
                    transit_role = 'driver',
                    work_contact_id = %s,
                    write_date = NOW()
                WHERE id = %s;
            """, (
                ed['full_name'],
                code,
                ed['ci'],
                ed['ci'],
                ed['registro'] if ed['registro'] else None,
                ed['venc_reg'],
                ed['venc_ci'],
                ed['mtess'],
                ed['ips'],
                concessionaire_id,
                p_id,
                emp_id
            ))
        else:
            # Crear resource_resource para el empleado
            cur.execute("""
                INSERT INTO resource_resource (
                    name, resource_type, time_efficiency, active, company_id, tz, calendar_id, create_date, write_date
                ) VALUES (
                    %s, 'user', 100, true, 1, 'America/Asuncion', 1, NOW(), NOW()
                ) RETURNING id;
            """, (ed['full_name'],))
            res_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO hr_employee (
                    name, resource_id, work_contact_id, company_id, concessionaire_id,
                    transit_role, driver_code, identification_id, ssnid,
                    driver_license_number, driver_license_category, driver_license_expiry,
                    driver_ci_expiry, mtess_date, ips_date,
                    employee_type, marital, distance_home_work_unit, active,
                    create_date, write_date
                ) VALUES (
                    %s, %s, %s, 1, %s,
                    'driver', %s, %s, %s,
                    %s, 'prof_b', %s,
                    %s, %s, %s,
                    'employee', 'single', 'kilometers', true,
                    NOW(), NOW()
                ) RETURNING id;
            """, (
                ed['full_name'],
                res_id,
                p_id,
                concessionaire_id,
                code,
                ed['ci'],
                ed['ci'],
                ed['registro'] if ed['registro'] else None,
                ed['venc_reg'],
                ed['venc_ci'],
                ed['mtess'],
                ed['ips']
            ))

        synced_partners.append({
            'nro': ed['nro'],
            'partner_id': p_id,
            'code': code,
            'name': ed['full_name'],
            'ci': ed['ci'],
            'venc_ci': ed['venc_ci'],
            'registro': ed['registro'],
            'venc_reg': ed['venc_reg'],
            'mtess': ed['mtess'],
            'ips': ed['ips']
        })

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n[✓] ¡{len(synced_partners)} conductores de Consorcio Arapotí cargados y actualizados exitosamente en Odoo 18!")
    print("\nRESUMEN DE CONDUCTORES CARGADOS:")
    print("-" * 115)
    print(f"{'Ficha':<6} | {'Nombre y Apellidos':<35} | {'Cédula (CI)':<12} | {'Venc. CI':<10} | {'Venc. Reg':<10} | {'Alta MTESS':<10} | {'Alta IPS':<10}")
    print("-" * 115)
    for s in synced_partners:
        v_ci = str(s['venc_ci']) if s['venc_ci'] else 'N/A'
        v_reg = str(s['venc_reg']) if s['venc_reg'] else 'N/A'
        v_mtess = str(s['mtess']) if s['mtess'] else 'N/A'
        v_ips = str(s['ips']) if s['ips'] else 'N/A'
        print(f"[{s['code']}]  | {s['name']:<35} | {s['ci']:<12} | {v_ci:<10} | {v_reg:<10} | {v_mtess:<10} | {v_ips:<10}")
    print("-" * 115)

if __name__ == '__main__':
    sync_arapoti_drivers()
