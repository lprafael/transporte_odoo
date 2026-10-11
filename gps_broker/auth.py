# -*- coding: utf-8 -*-
"""
Módulo de Autenticación Unificada y Multi-Tenant con Odoo ERP
Soporta sesión compartida transparente mediante cookie session_id (RFC 6265),
validación JSON-RPC contra Odoo (/web/session/get_session_info),
inicio de sesión unificado (/web/session/authenticate) y RBAC multi-empresa.
"""

import os
import time
import json
import logging
import urllib.parse
from typing import Dict, Any, Optional, Tuple

import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

logger = logging.getLogger("gps_auth")

# Configuración de Odoo y Base de Datos
ODOO_INTERNAL_URL = os.getenv("ODOO_URL", "http://web:8069")
ODOO_PUBLIC_URL = os.getenv("ODOO_PUBLIC_URL", "http://187.77.247.23:8069")
ODOO_DB = os.getenv("PG_DB", "flota_db")

PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

DEVICE_API_TOKEN = os.getenv("DEVICE_API_TOKEN", "GPS_DEVICE_SECRET_2026")
ODOO_API_TOKEN = os.getenv("ODOO_API_TOKEN", "GPS_SECRET_KEY_2026")

# Caché local en memoria de sesiones verificadas (TTL 45 segundos)
# Formato: {session_id: {"user": dict, "expires_at": float}}
_SESSION_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 45


def _get_cached_user(session_id: str) -> Optional[Dict[str, Any]]:
    """Recupera el usuario de la caché si la sesión no ha expirado."""
    cached = _SESSION_CACHE.get(session_id)
    if cached and cached.get("expires_at", 0) > time.time():
        return cached["user"]
    if cached:
        _SESSION_CACHE.pop(session_id, None)
    return None


def _set_cached_user(session_id: str, user_dict: Dict[str, Any]):
    """Almacena el usuario en caché para minimizar latencia en peticiones continuas."""
    _SESSION_CACHE[session_id] = {
        "user": user_dict,
        "expires_at": time.time() + CACHE_TTL_SECONDS
    }


def invalidate_session(session_id: Optional[str]):
    """Invalida la sesión local en caché."""
    if session_id and session_id in _SESSION_CACHE:
        _SESSION_CACHE.pop(session_id, None)


def _enrich_user_from_db(uid: int, base_user: Dict[str, Any]) -> Dict[str, Any]:
    """Consulta PostgreSQL para obtener roles y empresa concesionaria (Multi-Tenant)."""
    user_info = dict(base_user)
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=3
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT u.id, u.login, p.name, u.active,
                   c.id as concessionaire_id, c.name as concessionaire_name, c.code as concessionaire_code
            FROM res_users u
            LEFT JOIN res_partner p ON u.partner_id = p.id
            LEFT JOIN transit_concessionaire c ON u.concessionaire_id = c.id
            WHERE u.id = %s
            LIMIT 1;
        """, (uid,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            if row.get("name"):
                user_info["name"] = row["name"]
            conc_id = row.get("concessionaire_id")
            conc_name = row.get("concessionaire_name")
            user_info["concessionaire_id"] = conc_id
            user_info["concessionaire_name"] = conc_name or ("Todas las Empresas (Regulador / GVMT)" if user_info.get("is_admin") else "Consorcio Arapotí")
            user_info["agency_id"] = row.get("concessionaire_code") or ("004B" if not user_info.get("is_admin") else None)
    except Exception as e:
        logger.debug(f"Error enriqueciendo usuario desde DB: {e}")
        if user_info.get("is_admin"):
            user_info["concessionaire_name"] = "Todas las Empresas (Regulador / GVMT)"
        else:
            user_info["concessionaire_name"] = "Consorcio Arapotí"
            user_info["agency_id"] = "004B"
    return user_info


def validate_odoo_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Valida un session_id contra Odoo llamando a /web/session/get_session_info.
    Retorna el diccionario de usuario con información multi-tenant o None si es inválido.
    """
    if not session_id or not isinstance(session_id, str) or len(session_id) < 10:
        return None

    cached = _get_cached_user(session_id)
    if cached:
        return cached

    s = requests.Session()
    s.cookies.set("session_id", session_id)
    payload = {"jsonrpc": "2.0", "params": {}}

    try:
        url = f"{ODOO_INTERNAL_URL}/web/session/get_session_info"
        res = s.post(url, json=payload, timeout=4)
        if res.status_code != 200:
            return None
        
        data = res.json()
        if "error" in data:
            return None
        
        result = data.get("result", {})
        uid = result.get("uid")
        # En Odoo, uid == False o None significa no autenticado
        if not uid or not isinstance(uid, int):
            return None

        is_adm = bool(result.get("is_admin", False) or result.get("is_system", False) or uid == 2)
        base_user = {
            "id": uid,
            "uid": uid,
            "login": result.get("username") or str(uid),
            "name": result.get("name") or "Usuario Odoo",
            "is_admin": is_adm,
            "company_id": result.get("company_id"),
            "session_id": session_id,
            "server_version": result.get("server_version", "18.0"),
        }

        user_info = _enrich_user_from_db(uid, base_user)
        _set_cached_user(session_id, user_info)
        return user_info

    except Exception as e:
        logger.warning(f"Error contactando Odoo para validar sesión: {e}")
        return None


def authenticate_odoo_user(login_str: str, password_str: str, db_name: str = ODOO_DB) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Autentica al usuario contra Odoo vía JSON-RPC (/web/session/authenticate).
    Retorna (success, session_id, user_dict, error_message).
    """
    login_clean = (login_str or "").strip()
    pass_clean = (password_str or "").strip()

    if not login_clean or not pass_clean:
        return False, None, None, "Debe ingresar usuario y contraseña."

    s = requests.Session()
    payload = {
        "jsonrpc": "2.0",
        "params": {
            "db": db_name,
            "login": login_clean,
            "password": pass_clean
        }
    }

    try:
        url = f"{ODOO_INTERNAL_URL}/web/session/authenticate"
        res = s.post(url, json=payload, timeout=6)
        if res.status_code != 200:
            return False, None, None, f"Error del servidor Odoo (HTTP {res.status_code})."

        data = res.json()
        if "error" in data:
            err_msg = data["error"].get("message", "Error de inicio de sesión.")
            return False, None, None, "Usuario o contraseña incorrectos en Odoo."

        result = data.get("result", {})
        uid = result.get("uid")
        if not uid or not isinstance(uid, int):
            return False, None, None, "Credenciales incorrectas o cuenta inactiva."

        session_id = s.cookies.get("session_id")
        if not session_id:
            # Fallback a cookies devueltas en la respuesta
            for cookie in res.cookies:
                if cookie.name == "session_id":
                    session_id = cookie.value
                    break

        if not session_id:
            return False, None, None, "No se pudo obtener el token de sesión de Odoo."

        is_adm = bool(result.get("is_admin", False) or result.get("is_system", False) or uid == 2)
        base_user = {
            "id": uid,
            "uid": uid,
            "login": result.get("username") or login_clean,
            "name": result.get("name") or login_clean,
            "is_admin": is_adm,
            "company_id": result.get("company_id"),
            "session_id": session_id,
        }

        user_info = _enrich_user_from_db(uid, base_user)
        _set_cached_user(session_id, user_info)
        return True, session_id, user_info, None

    except requests.exceptions.RequestException as e:
        logger.error(f"Fallo al conectar con servicio Odoo: {e}")
        return False, None, None, "No se pudo establecer conexión con el servidor Odoo ERP."


def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extrae la identidad del usuario desde la petición:
    1. Cookie session_id estándar de Odoo.
    2. Encabezado Authorization: Bearer <session_id>.
    """
    # 1. Cookie session_id
    session_id = request.cookies.get("session_id")
    if not session_id:
        # Fallback a session_token
        session_id = request.cookies.get("session_token")
    
    # 2. Encabezado Authorization
    if not session_id:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
            # Si el token es el API token de dispositivo o de Odoo, no es un session_id de usuario web
            if token not in (DEVICE_API_TOKEN, ODOO_API_TOKEN):
                session_id = token

    if session_id:
        user = validate_odoo_session(session_id)
        if user:
            return user

    return None


def is_device_or_internal_token(request: Request) -> bool:
    """Valida si la petición proviene de un dispositivo GPS o webhook interno autorizado por token."""
    device_token = request.headers.get("X-Device-Token") or request.headers.get("x-device-token")
    if device_token and device_token == DEVICE_API_TOKEN:
        return True
    
    auth_hdr = request.headers.get("Authorization", "")
    if auth_hdr.startswith("Bearer "):
        token = auth_hdr[7:].strip()
        if token in (DEVICE_API_TOKEN, ODOO_API_TOKEN):
            return True
            
    return False


def require_authenticated_user(request: Request) -> Dict[str, Any]:
    """
    Dependencia FastAPI para endpoints protegidos.
    Lanza 401 si no hay usuario autenticado.
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sesión no iniciada o expirada. Por favor inicie sesión con sus credenciales de Odoo."
        )
    return user


def render_login_page(error_msg: Optional[str] = None, redirect_url: str = "/headway", current_user: Optional[Dict[str, Any]] = None) -> str:
    """Renderiza una interfaz de inicio de sesión moderna, elegante y unificada con Odoo."""
    safe_redirect = urllib.parse.quote(redirect_url or "/headway")
    
    error_html = ""
    if error_msg:
        error_html = f"""
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 10px; padding: 12px 16px; margin-bottom: 20px; color: #fca5a5; font-size: 13px; display: flex; align-items: center; gap: 10px; animation: shake 0.3s ease;">
            <span style="font-size: 18px;">⚠️</span>
            <span>{error_msg}</span>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso Unificado | Monitoreo y Telemetría Poliverso Transit</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        body {{
            background: radial-gradient(circle at 50% 0%, #1e293b 0%, #0f172a 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: #f8fafc;
        }}
        .login-card {{
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px rgba(56, 189, 248, 0.1);
            width: 100%;
            max-width: 440px;
            padding: 36px 32px;
            position: relative;
            overflow: hidden;
        }}
        .login-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        }}
        .brand-header {{
            text-align: center;
            margin-bottom: 28px;
        }}
        .brand-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: #38bdf8;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 14px;
        }}
        .brand-title {{
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #ffffff;
            margin-bottom: 6px;
        }}
        .brand-subtitle {{
            font-size: 13px;
            color: #94a3b8;
            line-height: 1.5;
        }}
        .form-group {{
            margin-bottom: 18px;
        }}
        .form-label {{
            display: block;
            font-size: 12px;
            font-weight: 600;
            color: #cbd5e1;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .form-input {{
            width: 100%;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 13px 16px;
            font-size: 14px;
            color: #ffffff;
            transition: all 0.2s ease;
            outline: none;
        }}
        .form-input:focus {{
            border-color: #38bdf8;
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
            background: rgba(15, 23, 42, 0.85);
        }}
        .btn-submit {{
            width: 100%;
            background: linear-gradient(135deg, #0284c7 0%, #4f46e5 100%);
            border: none;
            border-radius: 12px;
            padding: 14px;
            font-size: 14px;
            font-weight: 700;
            color: #ffffff;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.35);
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 24px;
        }}
        .btn-submit:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(2, 132, 199, 0.5);
            background: linear-gradient(135deg, #0369a1 0%, #4338ca 100%);
        }}
        .btn-submit:active {{
            transform: translateY(0);
        }}
        .tenant-info {{
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            text-align: center;
            font-size: 12px;
            color: #64748b;
            line-height: 1.6;
        }}
        .tenant-info a {{
            color: #38bdf8;
            text-decoration: none;
            font-weight: 600;
        }}
        .tenant-info a:hover {{
            text-decoration: underline;
        }}
        @keyframes shake {{
            0%, 100% {{ transform: translateX(0); }}
            25% {{ transform: translateX(-6px); }}
            75% {{ transform: translateX(6px); }}
        }}
    </style>
</head>
<body>
    <div class="login-card">
        <div class="brand-header">
            <div class="brand-badge">
                <span>🔐</span> Sesión Unificada ERP
            </div>
            <h1 class="brand-title">Poliverso Transit</h1>
            <p class="brand-subtitle">
                Monitoreo de Frecuencias, Cumplimiento y Telemetría VMT.<br>
                Inicie sesión con su usuario de <strong>Odoo ({ODOO_DB})</strong>.
            </p>
        </div>

        {error_html}

        <form action="/login" method="POST">
            <input type="hidden" name="redirect" value="{redirect_url}">

            <div class="form-group">
                <label class="form-label" for="login">Usuario / Correo Odoo</label>
                <input class="form-input" type="text" id="login" name="login" required placeholder="admin o usuario@empresa.com" autocomplete="username" autofocus>
            </div>

            <div class="form-group">
                <label class="form-label" for="password">Contraseña</label>
                <input class="form-input" type="password" id="password" name="password" required placeholder="••••••••" autocomplete="current-password">
            </div>

            <button type="submit" class="btn-submit">
                <span>Ingresar al Sistema</span>
                <span>➔</span>
            </button>
        </form>

        <div class="tenant-info">
            Sistema Multi-Tenant Consorcio Arapotí / VMT.<br>
            ¿Necesitas acceder al panel administrativo?<br>
            <a href="{ODOO_PUBLIC_URL}" target="_blank">Abrir Odoo ERP (:8069)</a>
        </div>
    </div>
</body>
</html>
"""
