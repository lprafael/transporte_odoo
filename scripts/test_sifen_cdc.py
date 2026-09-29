# -*- coding: utf-8 -*-
"""
Script de Prueba: Verificación de CDC Módulo 11 y Conector Denarius
"""
import sys
import os
from datetime import datetime

# Añadir custom_addons al path para importar sifen_util
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'custom_addons', 'transit_operations', 'models')))

from sifen_util import generar_cdc_sifen, generar_url_qr_sifen, calcular_dv_modulo11

def main():
    print("=== TEST 1: Cálculo Dígito Verificador Módulo 11 ===")
    cadena_prueba = "018001234560010010000001220260924112345678"
    dv = calcular_dv_modulo11(cadena_prueba)
    print(f"Cadena base (43 dígitos): {cadena_prueba}")
    print(f"DV Calculado (Módulo 11): {dv}")
    assert isinstance(dv, int) and 0 <= dv <= 9, "DV fuera de rango"

    print("\n=== TEST 2: Generación de CDC Oficial SIFEN (44 Dígitos) ===")
    now = datetime.now()
    cdc = generar_cdc_sifen(
        tipo_de=1,
        ruc_emisor="80012345",
        dv_emisor="6",
        establecimiento="001",
        punto_expedicion="001",
        numero_doc="0000104",
        tipo_contribuyente=2,
        fecha_emision=now,
        tipo_emision=1,
        codigo_seguridad="12345678"
    )
    print(f"CDC Generado: {cdc}")
    print(f"Longitud CDC: {len(cdc)} dígitos (Esperado: 44)")
    assert len(cdc) == 44, f"Longitud incorrecta: {len(cdc)}"

    print("\n=== TEST 3: Generación de URL QR para e-Kuatia / SIFEN ===")
    qr_url = generar_url_qr_sifen(cdc, now, total_operacion=3400.0, total_iva=309.0, ambiente="test")
    print(f"URL QR: {qr_url}")
    assert "https://ekuatia-roshka.set.gov.py/consultas/qr" in qr_url

    print("\n Todos los tests de algoritmo SIFEN pasaron satisfactoriamente.")

if __name__ == "__main__":
    main()
