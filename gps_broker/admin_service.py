# -*- coding: utf-8 -*-
"""
Servicio de Gestión de Usuarios y Concesionarias (Multi-Tenant Admin Service)
Provee las vistas HTML de Login, Administración y endpoints de control para el Broker GPS.
"""

import os
import logging
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("admin_service")

PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=3
    )

def list_concessionaires() -> List[Dict[str, Any]]:
    """Obtiene la lista oficial de empresas concesionarias registradas."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, code, COALESCE(short_name, name) as short_name
            FROM transit_concessionaire
            ORDER BY name;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error listando concesionarias en PG: {e}")
        return [
            {"id": 1, "name": "Consorcio Arapotí (Línea 20)", "code": "004B", "short_name": "Arapotí"},
            {"id": 2, "name": "Master Bus S.A.", "code": "005B", "short_name": "Master Bus"},
            {"id": 3, "name": "Transportes San Lorenzo S.R.L. (Línea 27)", "code": "CONC-SL01", "short_name": "San Lorenzo"}
        ]

def list_system_users() -> List[Dict[str, Any]]:
    """Lista todos los usuarios del sistema junto a su empresa concesionaria asociada."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT u.id, u.login, u.name, u.active,
                   c.id as concessionaire_id, c.name as concessionaire_name, c.code as concessionaire_code
            FROM res_users u
            LEFT JOIN transit_concessionaire c ON u.concessionaire_id = c.id
            WHERE u.login IS NOT NULL
            ORDER BY u.id;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        res = []
        for r in rows:
            is_adm = (r["login"] == "admin" or r["id"] == 1)
            res.append({
                "id": r["id"],
                "login": r["login"],
                "name": r["name"],
                "active": r["active"],
                "is_admin": is_adm,
                "concessionaire_id": r.get("concessionaire_id"),
                "concessionaire_name": r.get("concessionaire_name") or ("Administración Central" if is_adm else "Sin Asignar")
            })
        return res
    except Exception as e:
        logger.warning(f"Error listando usuarios en PG: {e}")
        return [
            {"id": 1, "login": "admin", "name": "Administrador Global", "active": True, "is_admin": True, "concessionaire_name": "Regulador GVMT"},
            {"id": 2, "login": "operador_linea20", "name": "Operador Arapotí", "active": True, "is_admin": False, "concessionaire_name": "Consorcio Arapotí"}
        ]

def create_system_user(login: str, password: str, concessionaire_id: Optional[int], is_admin: bool = False) -> Dict[str, Any]:
    """Crea un nuevo usuario de monitoreo en el sistema."""
    login_clean = login.strip().lower()
    if not login_clean:
        return {"status": "error", "message": "El nombre de usuario es obligatorio"}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO res_users (login, name, active, concessionaire_id)
            VALUES (%s, %s, TRUE, %s)
            ON CONFLICT (login) DO UPDATE
            SET active = TRUE, concessionaire_id = EXCLUDED.concessionaire_id
            RETURNING id;
        """, (login_clean, login.capitalize(), concessionaire_id if concessionaire_id else None))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "user_id": new_id, "login": login_clean}
    except Exception as e:
        logger.error(f"Error creando usuario: {e}")
        return {"status": "error", "message": str(e)}

def update_user_status(user_id: int, active: bool) -> Dict[str, Any]:
    """Habilita o deshabilita un usuario."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE res_users SET active = %s WHERE id = %s;", (active, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "user_id": user_id, "active": active}
    except Exception as e:
        logger.error(f"Error actualizando status de usuario: {e}")
        return {"status": "error", "message": str(e)}

def update_user_concessionaire(user_id: int, concessionaire_id: Optional[int], new_password: Optional[str] = None) -> Dict[str, Any]:
    """Actualiza la concesionaria asignada a un usuario."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE res_users SET concessionaire_id = %s WHERE id = %s;", (concessionaire_id if concessionaire_id else None, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "user_id": user_id}
    except Exception as e:
        logger.error(f"Error actualizando concesionaria: {e}")
        return {"status": "error", "message": str(e)}

def create_concessionaire(name: str, code: str) -> Dict[str, Any]:
    """Crea una nueva empresa concesionaria."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transit_concessionaire (name, code, active)
            VALUES (%s, %s, TRUE)
            RETURNING id;
        """, (name, code))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "concessionaire_id": new_id, "code": code}
    except Exception as e:
        logger.error(f"Error creando concesionaria: {e}")
        return {"status": "error", "message": str(e)}

def get_login_html(error_msg: Optional[str] = None) -> str:
    """Retorna la página HTML estilizada de inicio de sesión."""
    error_box = f'<div style="background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #fca5a5; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 13px;">⚠️ {error_msg}</div>' if error_msg else ''
    
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso al Sistema | Centro de Control de Telemetría GPS</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: radial-gradient(circle at 50% 20%, #1e293b 0%, #0f172a 60%, #020617 100%);
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-card {{
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 16px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
            width: 100%;
            max-width: 440px;
            padding: 40px 32px;
        }}
        .brand {{
            text-align: center;
            margin-bottom: 28px;
        }}
        .brand-icon {{
            font-size: 42px;
            margin-bottom: 12px;
            display: inline-block;
        }}
        .brand h1 {{
            font-size: 22px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.5px;
        }}
        .brand p {{
            font-size: 12px;
            color: #94a3b8;
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-group label {{
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
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 12px 16px;
            color: #f8fafc;
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
        }}
        .form-input:focus {{
            border-color: #38bdf8;
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
            background: rgba(30, 41, 59, 0.9);
        }}
        .btn-submit {{
            width: 100%;
            background: linear-gradient(135deg, #0284c7, #2563eb);
            border: none;
            border-radius: 10px;
            padding: 13px;
            color: #ffffff;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
            transition: all 0.2s;
            margin-top: 8px;
        }}
        .btn-submit:hover {{
            background: linear-gradient(135deg, #0369a1, #1d4ed8);
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(37, 99, 235, 0.6);
        }}
        .quick-access {{
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid rgba(51, 65, 85, 0.6);
            text-align: center;
        }}
        .quick-access p {{
            font-size: 11px;
            color: #64748b;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .links-row {{
            display: flex;
            justify-content: center;
            gap: 12px;
        }}
        .quick-link {{
            background: rgba(51, 65, 85, 0.5);
            border: 1px solid #334155;
            color: #38bdf8;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 600;
            text-decoration: none;
            transition: background 0.2s;
        }}
        .quick-link:hover {{
            background: rgba(56, 189, 248, 0.2);
        }}
    </style>
</head>
<body>
    <div class="login-card">
        <div class="brand">
            <div class="brand-icon">🚌⚡</div>
            <h1>Centro de Control de Flota</h1>
            <p>Monitoreo GPS & Res. GVMT 065/2024</p>
        </div>
        {error_box}
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="login">Usuario o Cuenta Operativa</label>
                <input type="text" id="login" name="login" class="form-input" placeholder="admin / arapoti / operador" required autofocus value="admin">
            </div>
            <div class="form-group">
                <label for="password">Contraseña de Seguridad</label>
                <input type="password" id="password" name="password" class="form-input" placeholder="••••••••" required value="admin">
            </div>
            <button type="submit" class="btn-submit">Ingresar al Centro de Control ➔</button>
        </form>
        <div class="quick-access">
            <p>ACCESOS DIRECTOS SIN SESIÓN REQUERIDA</p>
            <div class="links-row">
                <a href="/map" class="quick-link">🗺️ Radar Satelital</a>
                <a href="/headway" class="quick-link">📏 Tablero Lineal</a>
                <a href="/compliance" class="quick-link">📊 VMT Res. 065</a>
            </div>
        </div>
    </div>
</body>
</html>"""

def get_admin_users_html(user: Dict[str, Any]) -> str:
    """Retorna la vista HTML de gestión de usuarios y concesionarias."""
    users = list_system_users()
    concessionaires = list_concessionaires()

    conc_options = "".join([f'<option value="{c["id"]}">[{c["code"]}] {c["name"]}</option>' for c in concessionaires])

    user_rows = ""
    for u in users:
        badge_adm = '<span style="background: #38bdf8; color: #020617; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 10px;">ADMIN</span>' if u.get("is_admin") else '<span style="background: #64748b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px;">OPERADOR</span>'
        status_badge = '<span style="color: #4ade80;">● Activo</span>' if u.get("active") else '<span style="color: #f87171;">● Inactivo</span>'
        user_rows += f"""
        <tr style="border-bottom: 1px solid #1e293b;">
            <td style="padding: 12px; font-weight: 600;">#{u['id']}</td>
            <td style="padding: 12px; font-family: monospace; font-size: 13px;">{u['login']}</td>
            <td style="padding: 12px;">{u['name']}</td>
            <td style="padding: 12px;">{badge_adm}</td>
            <td style="padding: 12px; color: #94a3b8;">{u.get('concessionaire_name', '--')}</td>
            <td style="padding: 12px;">{status_badge}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Administración de Usuarios y Concesionarias | Poliverso SIT</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background: #0b1120; color: #f8fafc; padding: 24px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
        .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; }}
        th {{ padding: 12px; background: #1e293b; color: #94a3b8; font-size: 11px; text-transform: uppercase; }}
        .btn {{ background: #0284c7; color: #fff; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 12px; border: none; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h2>👥 Panel de Administración Multi-Tenant</h2>
            <p style="color: #64748b; font-size: 12px;">Aislamiento por Concesionarias y Control de Acceso</p>
        </div>
        <div>
            <a href="/map" class="btn">🗺️ Volver al Radar</a>
            <a href="/headway" class="btn" style="background: #334155;">📏 Tablero Lineal</a>
        </div>
    </div>
    <div class="card">
        <h3 style="margin-bottom: 16px;">Usuarios del Sistema Registrados</h3>
        <table>
            <thead>
                <tr>
                    <th>ID</th><th>Usuario</th><th>Nombre</th><th>Rol</th><th>Concesionaria Asignada</th><th>Estado</th>
                </tr>
            </thead>
            <tbody>
                {user_rows}
            </tbody>
        </table>
    </div>
</body>
</html>"""
