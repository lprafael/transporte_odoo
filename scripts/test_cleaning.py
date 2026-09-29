#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de resolución de calles e intersecciones para el transporte público.
Genera estados descriptivos de alta precisión: "Circulando (Calle X aproximándose a Calle Y)"
"""

import re
import urllib.request
import json
import logging
from typing import Optional, Dict, Tuple, List

logger = logging.getLogger("street_service")

# Abreviaturas comunes en Gran Asunción
ROAD_REPLACEMENTS = [
    (r"\bAvenida Mariscal Francisco Solano L[oó]pez\b", "Av. Mcal. López"),
    (r"\bAvenida Aviadores del Chaco\b", "Av. Aviadores del Chaco"),
    (r"\bAvenida Eusebio Ayala\b", "Av. Eusebio Ayala"),
    (r"\bAvenida España\b", "Av. España"),
    (r"\bAvenida del Agr[oó]nomo\b", "Av. del Agrónomo"),
    (r"\bRuta Nacional Mariscal Estigarribia\b", "Ruta PY02 (Mcal. Estigarribia)"),
    (r"\bF[eé]lix de Azara\b", "Calle Azara"),
    (r"\bAvenida\b", "Av."),
    (r"\bGeneral\b", "Gral."),
    (r"\bCoronel\b", "Cnel."),
    (r"\bMariscal\b", "Mcal."),
]

def clean_road_name(name: str) -> str:
    if not name:
        return "Itinerario Principal"
    cleaned = name.strip()
    for pattern, repl in ROAD_REPLACEMENTS:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    # Quitar sufijos de líneas de bus si vienen en el nombre
    cleaned = re.sub(r"\s*\(Bus.*?\)", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def clean_cross_street(raw_name: str, current_road: str = "") -> str:
    if not raw_name:
        return "Próxima Intersección"
    name = raw_name.strip()
    # Quitar sufijos de líneas
    name = re.sub(r"\s*\(Bus.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^Bus Línea.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^\d+[\.\d, -]+", "", name) # quitar números de líneas iniciales
    
    # Si viene en formato "Calle X y Calle Y" o "Calle X Esq. Calle Y"
    if " esq. " in name.lower():
        parts = re.split(r"\s+esq\.?\s+", name, flags=re.IGNORECASE)
        name = parts[1] if len(parts) > 1 else parts[0]
    elif " y " in name.lower():
        parts = re.split(r"\s+y\s+", name, flags=re.IGNORECASE)
        # Si la primera parte es la calle actual, usar la segunda
        if len(parts) > 1:
            name = parts[1]
    elif " casi " in name.lower():
        parts = re.split(r"\s+casi\s+", name, flags=re.IGNORECASE)
        if len(parts) > 1:
            name = parts[1]

    name = clean_road_name(name)
    if not name or len(name) < 3 or name.lower() in ("parada", "parada urbana", "bus_stop"):
        return "Próxima Intersección"
    return name

print("--- TEST CLEANING ---")
print("1.", clean_road_name("Avenida Mariscal Francisco Solano López"))
print("2.", clean_cross_street("Azara y Pa'i Pérez"))
print("3.", clean_cross_street("Julia Miranda Cueto Esq. Saturios Rios"))
print("4.", clean_cross_street("P. Villamayor (Bus Línea 12, 13, 15-1)"))
print("5.", clean_cross_street("12. Aviadores del Chaco y Dr. Gustavo González"))
