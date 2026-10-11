# -*- coding: utf-8 -*-
"""
Helper para retornar el informe HTML de la Base de Datos
"""
import os

def get_db_schema_html() -> str:
    html_file = os.path.join(os.path.dirname(__file__), "..", "docs", "informe_bd_transporte.html")
    if not os.path.exists(html_file):
        html_file = os.path.join(os.path.dirname(__file__), "informe_bd_transporte.html")
    
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Informe de Base de Datos no encontrado</h1>"
