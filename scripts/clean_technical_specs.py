# -*- coding: utf-8 -*-
import re

files = [
    'ESPECIFICACIONES_TECNICAS.html',
    'ESPECIFICACIONES_TECNICAS.md'
]

replacements = [
    # Títulos y encabezados
    (r'Telemetría MQTT/Protobuf \(Res\. GVMT 065/2024\)', r'Telemetría MQTT/Protobuf de Alta Frecuencia'),
    (r'Dashboard de Cumplimiento VMT', r'Dashboard de Cumplimiento Operativo'),
    (r'Cumplimiento VMT', r'Cumplimiento Operativo'),
    (r'Res\. GVMT 065/2024', r'Normativa Operativa'),
    (r'Res\. GVMT N° 065/2024', r'Normativa de Regularidad y Frecuencias'),
    (r'Resolución GVMT N° 065/2024', r'Normativa Operativa de Frecuencias'),
    (r'Resolución GVMT 065/2024', r'Normativa de Frecuencias'),
    (r'y Viceministerio de Transporte - GVMT', r'y Estándares de Transporte Metropolitano'),
    (r'Viceministerio de Transporte \(GVMT\)', r'Autoridad de Aplicación'),
    (r'Viceministerio de Transporte \(Paraguay\)', r'Autoridad Reguladora'),
    (r'Viceministerio de Transporte \(VMT\)', r'Entidad Central'),
    (r'Viceministerio de Transporte', r'Autoridad de Aplicación'),
    (r'Viceministerio', r'Autoridad Reguladora'),
    
    # Paradas y trazados
    (r'340 paradas oficiales del CID/VMT', r'340 paradas oficiales homologadas'),
    (r'340 paradas oficiales del CID', r'340 paradas oficiales homologadas'),
    (r'base central CID \(<code>bbdd-monitoreo-cid</code>\)', r'base de datos central de itinerarios'),
    (r'base del CID', r'base central de itinerarios'),
    (r'desde el CID', r'desde el repositorio oficial de itinerarios'),
    (r'del CID', r'de itinerarios'),
    (r'al CID', r'al sistema de itinerarios'),
    (r'Paradas CID', r'Paradas Oficiales'),
    (r'CID / VMT', r'Itinerarios Oficiales'),
    (r'CID/VMT', r'Oficiales'),
    (r'base central del VMT', r'servidores externos'),
    (r'del VMT', r'oficial'),
    (r'al VMT', r'al ente regulador'),
    (r'subsidio estatal VMT', r'liquidación de subsidio estatal'),
    (r'Topic MQTT GVMT', r'Topic MQTT'),
    (r'agency_vmt_id', r'agency_code_id'),
    (r'código GVMT', r'código de agencia'),
    (r'código CID', r'código de servicio'),
    (r'cid_service_id', r'ext_service_id'),
    (r'programacion CID', r'programacion de frecuencias'),
    (r'base productiva VMT', r'fuente externa de telemetria'),
    (r'Regulador \(VMT\)', r'Auditor Global'),
    (r'especificación VMT', r'especificación técnica'),
    
    # Siglas aisladas restantes
    (r'\bGVMT\b', r'Regulación'),
    (r'\bVMT\b', r'Transporte'),
    (r'\bCID\b', r'Itinerario'),
]

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Procesado: {file_path}")

print("\n[*] Verificando remanentes en ambos archivos...")
for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    matches = []
    for i, line in enumerate(lines, 1):
        found = re.findall(r'\b(CID|VMT|GVMT|Viceministerio)\b', line, re.IGNORECASE)
        if found:
            matches.append((i, found, line.strip()[:100]))
    print(f"[{file_path}] Coincidencias encontradas: {len(matches)}")
    for m in matches[:10]:
        print(f"  Línea {m[0]} {m[1]}: {m[2]}")
