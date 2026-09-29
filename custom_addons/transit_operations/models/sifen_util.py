# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
import random
import requests
from datetime import datetime

_logger = logging.getLogger(__name__)

def _left_zero(value: str | int, length: int) -> str:
    s = str(value).strip()
    if len(s) > length:
        return s[-length:]
    return s.zfill(length)


def calcular_dv_modulo11(cdc_sin_dv: str, base_max: int = 11) -> int:
    """
    Algoritmo oficial Módulo 11 (SET / e-Kuatia Paraguay).
    Entrada alfanumérica; dígitos no numéricos se reemplazan por código ASCII.
    """
    v_numero_al = ""
    for ch in cdc_sin_dv.upper():
        o = ord(ch)
        if 48 <= o <= 57:
            v_numero_al += ch
        else:
            v_numero_al += str(o)

    k = 2
    v_total = 0
    for i in range(len(v_numero_al), 0, -1):
        if k > base_max:
            k = 2
        v_numero_aux = int(v_numero_al[i - 1 : i])
        v_total += v_numero_aux * k
        k += 1

    v_resto = v_total % 11
    if v_resto > 1:
        return 11 - v_resto
    return 0


def generar_cdc_sifen(
    tipo_de: int,
    ruc_emisor: str,
    dv_emisor: str,
    establecimiento: str,
    punto_expedicion: str,
    numero_doc: str | int,
    tipo_contribuyente: int,
    fecha_emision: datetime,
    tipo_emision: int = 1,
    codigo_seguridad: str = None
) -> str:
    """
    Genera el CDC de 44 caracteres oficial de SIFEN Paraguay (43 dígitos base + 1 DV Módulo 11).
    """
    ruc_clean = _left_zero(''.join(c for c in str(ruc_emisor) if c.isdigit()), 8)
    dv_clean = str(dv_emisor).strip()[:1] or '0'
    est_clean = _left_zero(establecimiento, 3)
    pto_clean = _left_zero(punto_expedicion, 3)
    num_clean = _left_zero(numero_doc, 7)
    fec_str = fecha_emision.strftime('%Y%m%d')

    if not codigo_seguridad:
        codigo_seguridad = str(random.randint(100000000, 999999999))
    else:
        codigo_seguridad = _left_zero(codigo_seguridad, 9)

    parcial_43 = (
        _left_zero(tipo_de, 2)
        + ruc_clean
        + dv_clean
        + est_clean
        + pto_clean
        + num_clean
        + str(tipo_contribuyente)[0]
        + fec_str
        + str(tipo_emision)[0]
        + codigo_seguridad
    )

    if len(parcial_43) != 43:
        raise ValueError(f"Longitud base de CDC incorrecta: {len(parcial_43)} (Esperado: 43)")

    dv_cdc = calcular_dv_modulo11(parcial_43)
    cdc_44 = f"{parcial_43}{dv_cdc}"
    return cdc_44


def generar_url_qr_sifen(cdc: str, fecha_emision: datetime, total_operacion: float, total_iva: float, ambiente: str = 'test') -> str:
    """
    Genera la URL para el código QR de consulta pública en e-Kuatia (SIFEN).
    """
    base_url = (
        "https://ekuatia-roshka.set.gov.py/consultas/qr"
        if ambiente == 'test'
        else "https://ekuatia.set.gov.py/consultas/qr"
    )
    fecha_hex = fecha_emision.strftime('%Y-%m-%d %H:%M:%S').encode('utf-8').hex()
    total_str = f"{int(round(total_operacion))}"
    iva_str = f"{int(round(total_iva))}"
    
    url = (
        f"{base_url}?nVersion=150"
        f"&Id={cdc}"
        f"&dFeEmiDE={fecha_hex}"
        f"&dTotGIMp={total_str}"
        f"&dIVA={iva_str}"
        f"&cIdRec=0"
        f"&dDigVal=0000"
    )
    return url


def enviar_factura_a_denarius(denarius_url: str, token: str, payload: dict) -> dict:
    """
    Envía una factura electrónica al backend Denarius (FastAPI) para firma y envío a SIFEN.
    """
    endpoint = f"{denarius_url.rstrip('/')}/api/facturas"
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=25)
        if response.status_code in [200, 201]:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        _logger.warning("No se pudo conectar con el backend de Denarius: %s", str(e))
        return {"success": False, "error": str(e)}
