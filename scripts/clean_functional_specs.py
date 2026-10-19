# -*- coding: utf-8 -*-
import re

files_to_clean = [
    'ESPECIFICACIONES_FUNCIONALES.html',
    'scripts/regen_funcionales_html.py'
]

replacements = [
    # Específicos pedidos por el usuario
    (r'340 Paradas Oficiales Homologadas por el CID / VMT', r'340 Paradas Oficiales Homologadas'),
    (r'Sincronizacion en tiempo real con la base de datos de monitoreo del VMT\.', r'Streaming y recepcion de telemetria GPS en tiempo real de alta frecuencia.'),
    (r'paradas CID', r'paradas oficiales'),
    (r'6 shapes oficiales del CID\.', r'6 trazados y shapes oficiales de los ramales.'),
    
    # Resto de menciones de CID / VMT / GVMT / Viceministerio
    (r'Cumplimiento VMT en Tiempo Real', r'Cumplimiento Normativo en Tiempo Real'),
    (r'Res\. GVMT 065/2024 &amp; SIFEN e-Kuatia', r'Normativa de Frecuencias &amp; SIFEN e-Kuatia'),
    (r'Res\. GVMT 065/2024', r'Normativa Operativa'),
    (r'&#10003; Cumplimiento VMT Res\.065/2024', r'&#10003; Cumplimiento Operativo de Frecuencias'),
    (r'las 692 frecuencias diarias exigidas por el Viceministerio de Transporte \(GVMT\)', r'las 692 frecuencias diarias homologadas para los servicios'),
    (r'<div class="kpi-value">VMT</div><div class="kpi-label">Cumplimiento 065/2024</div>', r'<div class="kpi-value">100%</div><div class="kpi-label">Cumplimiento de Frecuencias</div>'),
    (r'basadas en la <strong>Resolucion GVMT N&deg; 065/2024</strong>', r'basadas en la <strong>normativa de frecuencias y regularidad</strong>'),
    (r'<!-- 5\. NUEVO: Cumplimiento VMT -->', r'<!-- 5. NUEVO: Cumplimiento Operativo -->'),
    (r'5\. Dashboard de Cumplimiento VMT \(Res\. GVMT 065/2024\)', r'5. Dashboard de Cumplimiento Operativo de Frecuencias'),
    (r'exigida por la Resolucion GVMT N&deg; 065/2024\.', r'establecida para la operacion del servicio.'),
    (r'para auditorias del VMT\.', r'para auditorias operativas y de gestion.'),
    (r'reportes automatizados al Viceministerio\.', r'reportes automatizados de fiscalizacion y gestion.'),
    (r'<strong>Dashboard Cumplimiento VMT</strong>', r'<strong>Dashboard de Cumplimiento Operativo</strong>'),
    (r'antes de que sean criticos para el VMT\.', r'antes del cierre de la jornada.'),
    (r'<strong>Auditoria GVMT</strong>', r'<strong>Auditoria Operativa</strong>'),
    (r'fiscalizaciones del Viceministerio\.', r'auditorias e inspecciones de servicio.'),
    (r'GET /compliance</code> &mdash; Dashboard cumplimiento VMT', r'GET /compliance</code> &mdash; Dashboard de cumplimiento'),
    (r'Septiembre 2026 &bull; Res\. GVMT 065/2024', r'Septiembre 2026 &bull; Operacion Integral'),
    (r'CID / VMT', r'la Autoridad de Transporte'),
    (r'del CID', r'oficiales'),
    (r'al CID', r'al sistema central'),
    (r'del VMT', r'oficial'),
    (r'al VMT', r'de operacion'),
    (r'GVMT', r'Regulacion de Transporte'),
    (r'VMT', r'Transporte'),
    (r'CID', r'Itinerario'),
    (r'Viceministerio de Transporte', r'Autoridad de Aplicacion'),
    (r'Viceministerio', r'Autoridad Reguladora'),
]

for file_path in files_to_clean:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Procesado: {file_path}")

print("[*] Verificando remanentes en ESPECIFICACIONES_FUNCIONALES.html...")
with open('ESPECIFICACIONES_FUNCIONALES.html', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        for word in ['CID', 'VMT', 'GVMT', 'VICEMINISTERIO']:
            if word in line.upper():
                print(f"  Línea {i} [{word}]: {line.strip()}")
