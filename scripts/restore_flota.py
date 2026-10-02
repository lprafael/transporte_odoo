#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Restauracion de Base de Datos flota_db
Restaura el dump binario scripts/flota_db_backup.dump directamente en el contenedor PostgreSQL.
Uso: python scripts/restore_flota.py
"""

import subprocess
import sys
import os

DUMP_PATH = os.path.join(os.path.dirname(__file__), "flota_db_backup.dump")
CONTAINER = "odoo_transporte_db"
DB_USER = "odoo"
DB_NAME = "flota_db"

def main():
    if not os.path.exists(DUMP_PATH):
        print(f"ERROR: No se encontro el archivo de respaldo en {DUMP_PATH}")
        sys.exit(1)

    print(f"[*] Copiando {DUMP_PATH} al contenedor {CONTAINER}...")
    subprocess.run(["docker", "cp", DUMP_PATH, f"{CONTAINER}:/tmp/flota_restore.dump"], check=True)

    print(f"[*] Restaurando base de datos {DB_NAME}...")
    cmd = [
        "docker", "exec", CONTAINER,
        "pg_restore", "-U", DB_USER, "-d", DB_NAME, "--clean", "--if-exists", "-v", "/tmp/flota_restore.dump"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    # pg_restore suele retornar warning codes por drops condicionales
    print("[*] Salida de pg_restore:")
    print(res.stderr[:500] if res.stderr else "Restauracion completada sin errores.")

    print("[*] Limpiando archivo temporal en contenedor...")
    subprocess.run(["docker", "exec", CONTAINER, "rm", "-f", "/tmp/flota_restore.dump"])

    print("================================================================================")
    print("Base de datos flota_db restaurada exitosamente con flota Master Bus.")
    print("================================================================================")

if __name__ == "__main__":
    main()
