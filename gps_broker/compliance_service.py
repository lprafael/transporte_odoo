# -*- coding: utf-8 -*-
"""
Servicio de Cumplimiento VMT (Res. GVMT 065/2024)
==================================================
Dashboard en tiempo real del cumplimiento del cupo diario de 692 despachos
exigidos por la Resolucion GVMT 065/2024 para la Linea 20 Electrica.

Calcula:
  - Despachos ejecutados en el dia (salidas confirmadas desde cabecera)
  - Despachos programados en el dia (desde transit_timetable / CID)
  - Porcentaje de cumplimiento por ramal y total
  - Proyeccion de cierre del dia (tendencia)
  - Alertas cuando se acerca el limite de horas y hay deficit
  - Historial de cumplimiento de los ultimos 30 dias

Expone:
  - /compliance                     - Dashboard HTML interactivo
  - /api/v1/compliance/today        - JSON del dia actual
  - /api/v1/compliance/history      - Historial de 30 dias
  - /api/v1/compliance/alerts       - Alertas activas de deficit
"""

import os
import json
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("compliance_service")

PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB   = os.getenv("PG_DB", "flota_db")
PG_USER = os.getenv("PG_USER", "odoo")
PG_PASS = os.getenv("PG_PASS", "odoo_password")

# Cuota diaria total segun Res. GVMT 065/2024
DAILY_QUOTA_TOTAL = 692
# Cuota por ramal (aprox. - ajustar segun distribucion real del CID)
QUOTA_PER_RAMAL = {
    '020c': 116, '020d': 116,
    '020e': 115, '020f': 115,
    '0210': 115, '0211': 115,
}
ELECTRIC_ROUTES = ['020c', '020d', '020e', '020f', '0210', '0211']
# Umbral critico: si el cumplimiento proyectado esta por debajo de este %
CRITICAL_THRESHOLD_PCT = 85.0
WARNING_THRESHOLD_PCT = 95.0

COMPLIANCE_CACHE_TTL = 60  # segundos


def _pg_connect():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS, connect_timeout=3
    )


def get_today_compliance(redis_client=None) -> Dict[str, Any]:
    """
    Calcula el estado de cumplimiento del dia actual.

    Fuentes de datos:
      - transit_timetable: despachos programados para hoy
      - telemetry_ping type=0: pings de salida de cabecera (inicio de despacho)
      - Alternativa: eventos 'departure' registrados en el sistema
    """
    if redis_client:
        try:
            cached = redis_client.get("compliance:today")
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    now = datetime.now()
    today = now.date()
    current_hour = now.hour + now.minute / 60.0
    hours_remaining = max(0.0, 24.0 - current_hour)

    result = {
        "date": today.isoformat(),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "daily_quota": DAILY_QUOTA_TOTAL,
        "total_dispatched": 0,
        "total_scheduled": 0,
        "compliance_pct": 0.0,
        "projected_eod_pct": 0.0,
        "hours_elapsed": current_hour,
        "hours_remaining": hours_remaining,
        "status": "ON_TRACK",
        "status_label": "En Cumplimiento",
        "alerts": [],
        "by_ramal": {},
    }

    try:
        conn = _pg_connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Despachos programados para hoy por ramal (desde timetable CID)
        cur.execute("""
            SELECT
                r.code AS route_code,
                COUNT(*) AS scheduled_count
            FROM transit_timetable tt
            JOIN transit_route r ON r.id = tt.route_id
            WHERE r.code = ANY(%s)
              AND (
                  tt.valid_from IS NULL OR tt.valid_from <= %s
              )
              AND (
                  tt.valid_until IS NULL OR tt.valid_until >= %s
              )
            GROUP BY r.code
        """, (ELECTRIC_ROUTES, today, today))
        scheduled_rows = cur.fetchall()
        scheduled_by_ramal = {r["route_code"]: int(r["scheduled_count"]) for r in scheduled_rows}

        # 2. Despachos ejecutados hoy (tipo 0 = inicio de operacion / salida de cabecera)
        #    Tambien contamos transiciones AT_ORIGIN -> IN_TRANSIT del dia
        cur.execute("""
            SELECT
                route_id AS route_code,
                COUNT(DISTINCT bus_internal_code) AS buses_active,
                COUNT(*) AS ping_count
            FROM telemetry_ping
            WHERE DATE(recorded_at) = %s
              AND route_id = ANY(%s)
              AND operation_type = 0
            GROUP BY route_id
        """, (today, ELECTRIC_ROUTES))
        departure_rows = cur.fetchall()
        dispatched_by_ramal = {r["route_code"]: int(r["ping_count"]) for r in departure_rows}

        # 3. Historial de cumplimiento (ultimos 30 dias) para tendencia
        cur.execute("""
            SELECT
                DATE(recorded_at) AS day,
                COUNT(*) AS dispatches
            FROM telemetry_ping
            WHERE route_id = ANY(%s)
              AND operation_type = 0
              AND DATE(recorded_at) >= %s
            GROUP BY DATE(recorded_at)
            ORDER BY day DESC
            LIMIT 30
        """, (ELECTRIC_ROUTES, today - timedelta(days=30)))
        history_rows = cur.fetchall()

        cur.close()
        conn.close()

        # Calcular totales
        total_dispatched = sum(dispatched_by_ramal.values())
        total_scheduled = sum(scheduled_by_ramal.values()) or DAILY_QUOTA_TOTAL

        compliance_pct = round((total_dispatched / DAILY_QUOTA_TOTAL) * 100, 1) if DAILY_QUOTA_TOTAL > 0 else 0.0

        # Proyeccion al cierre del dia
        if current_hour > 0:
            dispatch_rate_per_hour = total_dispatched / current_hour
            projected_total = total_dispatched + (dispatch_rate_per_hour * hours_remaining)
            projected_eod_pct = round((projected_total / DAILY_QUOTA_TOTAL) * 100, 1)
        else:
            projected_eod_pct = 0.0

        # Estado general
        alerts = []
        if compliance_pct < CRITICAL_THRESHOLD_PCT and hours_remaining < 4:
            status = "CRITICAL"
            status_label = "Deficit Critico"
            deficit = DAILY_QUOTA_TOTAL - total_dispatched
            alerts.append({
                "level": "CRITICAL",
                "message": f"Deficit de {deficit} despachos. Menos de {round(hours_remaining, 1)}h para cierre.",
                "icon": "🚨"
            })
        elif projected_eod_pct < CRITICAL_THRESHOLD_PCT:
            status = "AT_RISK"
            status_label = "En Riesgo"
            alerts.append({
                "level": "WARNING",
                "message": f"Proyeccion de cierre: {projected_eod_pct}% del cupo. Reforzar despachos.",
                "icon": "⚠️"
            })
        elif compliance_pct >= WARNING_THRESHOLD_PCT:
            status = "COMPLIANT"
            status_label = "Cumplimiento Optimo"
        else:
            status = "ON_TRACK"
            status_label = "En Seguimiento"

        # Detalle por ramal
        by_ramal = {}
        for route in ELECTRIC_ROUTES:
            quota = QUOTA_PER_RAMAL.get(route, 115)
            dispatched = dispatched_by_ramal.get(route, 0)
            scheduled = scheduled_by_ramal.get(route, quota)
            pct = round((dispatched / quota) * 100, 1) if quota > 0 else 0.0

            ramal_status = "COMPLIANT" if pct >= WARNING_THRESHOLD_PCT else (
                "AT_RISK" if pct >= CRITICAL_THRESHOLD_PCT else "DEFICIT"
            )

            by_ramal[route] = {
                "route_code": route,
                "quota": quota,
                "scheduled": scheduled,
                "dispatched": dispatched,
                "compliance_pct": pct,
                "status": ramal_status,
                "missing": max(0, quota - dispatched),
            }

            if pct < CRITICAL_THRESHOLD_PCT and hours_remaining < 6:
                alerts.append({
                    "level": "WARNING",
                    "message": f"Ramal {route.upper()}: solo {dispatched}/{quota} despachos ({pct}%)",
                    "icon": "⚠️"
                })

        # Historial para grafico
        history = [
            {
                "date": str(r["day"]),
                "dispatches": int(r["dispatches"]),
                "compliance_pct": round((int(r["dispatches"]) / DAILY_QUOTA_TOTAL) * 100, 1)
            }
            for r in history_rows
        ]

        result.update({
            "total_dispatched": total_dispatched,
            "total_scheduled": total_scheduled,
            "compliance_pct": compliance_pct,
            "projected_eod_pct": projected_eod_pct,
            "status": status,
            "status_label": status_label,
            "alerts": alerts,
            "by_ramal": by_ramal,
            "history_30d": history,
        })

    except Exception as e:
        logger.error(f"Error calculando cumplimiento: {e}")
        result["error"] = str(e)
        result["alerts"] = [{"level": "ERROR", "message": f"Error al obtener datos: {e}", "icon": "❌"}]

    if redis_client:
        try:
            redis_client.set("compliance:today", json.dumps(result), ex=COMPLIANCE_CACHE_TTL)
        except Exception:
            pass

    return result


def get_compliance_alerts(redis_client=None) -> List[Dict]:
    """Retorna solo las alertas activas de cumplimiento."""
    data = get_today_compliance(redis_client)
    return data.get("alerts", [])


# ==============================================================================
# HTML del Dashboard de Cumplimiento VMT
# ==============================================================================
def get_compliance_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cumplimiento VMT | Res. GVMT 065/2024 | Poliverso Transit</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #060b14; --card: #0d1527; --card2: #111c35; --border: #1e293b;
            --primary: #38bdf8; --accent: #818cf8; --success: #10b981;
            --warning: #f59e0b; --danger: #ef4444; --text: #f8fafc; --muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

        header {
            background: rgba(13,21,39,.9);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            padding: 14px 28px;
            display: flex; align-items: center; justify-content: space-between;
            position: sticky; top: 0; z-index: 100;
        }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-icon {
            width: 38px; height: 38px; border-radius: 10px;
            background: linear-gradient(135deg, #0284c7, #6366f1);
            display: flex; align-items: center; justify-content: center; font-size: 20px;
        }
        .brand-title { font-size: 16px; font-weight: 800; letter-spacing: -.02em; }
        .brand-sub { font-size: 11px; color: var(--muted); }
        .nav-links { display: flex; gap: 8px; }
        .nav-btn {
            background: #1e293b; color: #cbd5e1; border: 1px solid #334155;
            padding: 7px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;
            text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
            transition: all .2s;
        }
        .nav-btn:hover { background: #334155; color: #fff; border-color: var(--primary); }

        .page-container { max-width: 1400px; margin: 0 auto; padding: 28px 24px; }

        /* Big KPI banner */
        .kpi-banner {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 28px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 32px;
            flex-wrap: wrap;
        }
        .kpi-main { flex: 1; min-width: 200px; }
        .kpi-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 6px; }
        .kpi-value { font-size: 72px; font-weight: 900; letter-spacing: -.04em; line-height: 1; }
        .kpi-sub { font-size: 14px; color: var(--muted); margin-top: 6px; }
        .kpi-status-badge {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 8px 18px; border-radius: 24px; font-size: 13px; font-weight: 700;
            margin-top: 12px;
        }
        .kpi-status-badge.compliant { background: rgba(16,185,129,.15); color: var(--success); border: 1px solid rgba(16,185,129,.3); }
        .kpi-status-badge.on_track { background: rgba(56,189,248,.15); color: var(--primary); border: 1px solid rgba(56,189,248,.3); }
        .kpi-status-badge.at_risk { background: rgba(245,158,11,.15); color: var(--warning); border: 1px solid rgba(245,158,11,.3); }
        .kpi-status-badge.critical { background: rgba(239,68,68,.15); color: var(--danger); border: 1px solid rgba(239,68,68,.3); }

        /* Gauge */
        .gauge-wrap { display: flex; flex-direction: column; align-items: center; gap: 8px; }
        .gauge-container { position: relative; width: 160px; height: 80px; overflow: hidden; }
        .gauge-bg { fill: none; stroke: #1e293b; stroke-width: 16; }
        .gauge-fill { fill: none; stroke-width: 16; stroke-linecap: round; transition: stroke-dashoffset 1s ease; }
        .gauge-text { font-size: 11px; color: var(--muted); text-align: center; font-weight: 600; }

        /* KPI cards row */
        .kpi-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .kpi-card {
            background: var(--card); border: 1px solid var(--border); border-radius: 14px;
            padding: 18px 20px; position: relative; overflow: hidden;
        }
        .kpi-card-label { font-size: 11px; text-transform: uppercase; letter-spacing: .07em; color: var(--muted); font-weight: 600; }
        .kpi-card-value { font-size: 32px; font-weight: 900; letter-spacing: -.03em; margin-top: 6px; }
        .kpi-card-detail { font-size: 12px; color: var(--muted); margin-top: 4px; }
        .kpi-card-accent { position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: 14px 14px 0 0; }

        /* Alerts */
        .alerts-section { margin-bottom: 24px; }
        .alert-item {
            display: flex; align-items: flex-start; gap: 12px;
            background: var(--card); border-radius: 12px; padding: 14px 16px;
            margin-bottom: 10px; border-left: 4px solid;
        }
        .alert-item.critical { border-color: var(--danger); background: rgba(239,68,68,.05); }
        .alert-item.warning { border-color: var(--warning); background: rgba(245,158,11,.05); }
        .alert-icon { font-size: 18px; flex-shrink: 0; }
        .alert-msg { font-size: 13px; line-height: 1.5; }
        .alert-level { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; font-weight: 800; margin-bottom: 2px; }

        /* Ramal table */
        .section-title { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 14px; }
        .ramal-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .ramal-card {
            background: var(--card); border: 1px solid var(--border); border-radius: 14px;
            padding: 18px; position: relative;
        }
        .ramal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
        .ramal-code { font-size: 16px; font-weight: 900; letter-spacing: .02em; }
        .ramal-pct { font-size: 24px; font-weight: 900; }
        .ramal-bar-bg { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; margin: 10px 0; }
        .ramal-bar-fill { height: 100%; border-radius: 4px; transition: width 1s ease; }
        .ramal-stats { display: flex; gap: 10px; flex-wrap: wrap; }
        .ramal-stat { font-size: 12px; color: var(--muted); }
        .ramal-stat strong { color: var(--text); }

        /* History chart area */
        .chart-section { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 22px; margin-bottom: 24px; }
        .history-bars { display: flex; align-items: flex-end; gap: 6px; height: 100px; margin-top: 16px; }
        .h-bar-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
        .h-bar { width: 100%; border-radius: 4px 4px 0 0; transition: height .5s ease; min-height: 4px; cursor: pointer; position: relative; }
        .h-bar:hover::after {
            content: attr(data-tooltip);
            position: absolute; bottom: 110%; left: 50%; transform: translateX(-50%);
            background: #1e293b; color: #fff; padding: 4px 8px; border-radius: 6px;
            font-size: 10px; white-space: nowrap; pointer-events: none;
        }
        .h-bar-label { font-size: 9px; color: var(--muted); text-align: center; transform: rotate(-45deg); white-space: nowrap; }

        .live-indicator { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--success); }
        .live-indicator::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--success); animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:.5; transform:scale(1.4); } }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="brand-icon">&#9989;</div>
            <div>
                <div class="brand-title">Cumplimiento VMT</div>
                <div class="brand-sub">Res. GVMT 065/2024 &middot; Linea 20 Electrica</div>
            </div>
        </div>
        <nav class="nav-links">
            <a href="/map" class="nav-btn">&#128506; Mapa</a>
            <a href="/headway" class="nav-btn">&#128202; Frecuencias</a>
            <div class="live-indicator">EN VIVO</div>
        </nav>
    </header>

    <div class="page-container">
        <!-- Banner principal KPI -->
        <div class="kpi-banner" id="kpi-banner">
            <div class="kpi-main">
                <div class="kpi-label">Cumplimiento del dia</div>
                <div class="kpi-value" id="kpi-pct-main">—</div>
                <div class="kpi-sub" id="kpi-dispatched-sub">Cargando...</div>
                <div class="kpi-status-badge on_track" id="kpi-status-badge">Cargando...</div>
            </div>
            <div class="gauge-wrap">
                <svg viewBox="0 0 160 80" width="160" height="80">
                    <path d="M 16 80 A 64 64 0 0 1 144 80" class="gauge-bg"/>
                    <path id="gauge-arc" d="M 16 80 A 64 64 0 0 1 144 80" class="gauge-fill" stroke="#10b981"
                          stroke-dasharray="201" stroke-dashoffset="201"/>
                </svg>
                <div class="gauge-text" id="gauge-label">—</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:14px;">
                <div>
                    <div class="kpi-label">Cuota diaria (Res. 065/2024)</div>
                    <div style="font-size:28px;font-weight:900;color:var(--primary)">692</div>
                    <div style="font-size:12px;color:var(--muted)">despachos requeridos</div>
                </div>
                <div>
                    <div class="kpi-label">Proyeccion al cierre</div>
                    <div style="font-size:28px;font-weight:900;" id="kpi-projected">—</div>
                    <div style="font-size:12px;color:var(--muted)" id="kpi-hours-remaining">—</div>
                </div>
            </div>
        </div>

        <!-- KPI Cards row -->
        <div class="kpi-cards">
            <div class="kpi-card">
                <div class="kpi-card-accent" style="background:#10b981"></div>
                <div class="kpi-card-label">Despachos Ejecutados</div>
                <div class="kpi-card-value" id="kpi-dispatched" style="color:#10b981">—</div>
                <div class="kpi-card-detail" id="kpi-dispatched-detail">hoy</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-card-accent" style="background:#38bdf8"></div>
                <div class="kpi-card-label">Despachos Programados</div>
                <div class="kpi-card-value" id="kpi-scheduled" style="color:#38bdf8">—</div>
                <div class="kpi-card-detail">segun timetable CID</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-card-accent" style="background:#f59e0b"></div>
                <div class="kpi-card-label">Deficit Actual</div>
                <div class="kpi-card-value" id="kpi-deficit" style="color:#f59e0b">—</div>
                <div class="kpi-card-detail">despachos faltantes</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-card-accent" style="background:#818cf8"></div>
                <div class="kpi-card-label">Horas Restantes</div>
                <div class="kpi-card-value" id="kpi-hours" style="color:#818cf8">—</div>
                <div class="kpi-card-detail">hasta cierre operativo</div>
            </div>
        </div>

        <!-- Alertas -->
        <div id="alerts-section" class="alerts-section" style="display:none">
            <div class="section-title">&#128680; Alertas Activas</div>
            <div id="alerts-container"></div>
        </div>

        <!-- Detalle por ramal -->
        <div class="section-title">&#128202; Detalle por Ramal</div>
        <div class="ramal-grid" id="ramal-grid">
            <div style="color:var(--muted);padding:20px">Cargando ramales...</div>
        </div>

        <!-- Historico 30 dias -->
        <div class="chart-section">
            <div class="section-title">&#128200; Historial de Cumplimiento (ultimos 30 dias)</div>
            <div class="history-bars" id="history-bars">
                <div style="color:var(--muted);font-size:12px">Cargando historial...</div>
            </div>
        </div>
    </div>

    <script>
        let refreshInterval = null;

        function statusClass(s) {
            const m = {COMPLIANT:'compliant', ON_TRACK:'on_track', AT_RISK:'at_risk', CRITICAL:'critical'};
            return m[s] || 'on_track';
        }
        function statusLabel(s) {
            const m = {COMPLIANT:'Cumplimiento Optimo', ON_TRACK:'En Seguimiento', AT_RISK:'En Riesgo', CRITICAL:'Deficit Critico'};
            return m[s] || s;
        }
        function pctColor(p) {
            if (p >= 95) return '#10b981';
            if (p >= 85) return '#38bdf8';
            if (p >= 70) return '#f59e0b';
            return '#ef4444';
        }

        function updateGauge(pct) {
            const arc = document.getElementById('gauge-arc');
            const total = 201;
            const fill = total - (pct / 100) * total;
            arc.style.strokeDashoffset = fill;
            arc.style.stroke = pctColor(pct);
            document.getElementById('gauge-label').textContent = pct.toFixed(1) + '% del cupo';
        }

        function renderData(d) {
            const pct = d.compliance_pct || 0;
            document.getElementById('kpi-pct-main').textContent = pct.toFixed(1) + '%';
            document.getElementById('kpi-pct-main').style.color = pctColor(pct);
            document.getElementById('kpi-dispatched-sub').textContent =
                `${d.total_dispatched} de ${d.daily_quota} despachos ejecutados hoy`;

            const badge = document.getElementById('kpi-status-badge');
            badge.textContent = (d.alerts && d.alerts.length > 0 ? d.alerts[0].icon + ' ' : '') + statusLabel(d.status);
            badge.className = 'kpi-status-badge ' + statusClass(d.status);

            document.getElementById('kpi-projected').textContent = (d.projected_eod_pct || 0).toFixed(1) + '%';
            document.getElementById('kpi-projected').style.color = pctColor(d.projected_eod_pct || 0);
            document.getElementById('kpi-hours-remaining').textContent = `${(d.hours_remaining || 0).toFixed(1)}h restantes del dia`;

            document.getElementById('kpi-dispatched').textContent = d.total_dispatched || '0';
            document.getElementById('kpi-dispatched-detail').textContent = `de ${d.daily_quota} requeridos hoy`;
            document.getElementById('kpi-scheduled').textContent = d.total_scheduled || '0';
            document.getElementById('kpi-deficit').textContent = Math.max(0, (d.daily_quota || 692) - (d.total_dispatched || 0));
            document.getElementById('kpi-hours').textContent = (d.hours_remaining || 0).toFixed(1) + 'h';

            updateGauge(pct);

            // Alertas
            const alertsSection = document.getElementById('alerts-section');
            const alertsContainer = document.getElementById('alerts-container');
            if (d.alerts && d.alerts.length > 0) {
                alertsSection.style.display = 'block';
                alertsContainer.innerHTML = d.alerts.map(a => `
                    <div class="alert-item ${a.level.toLowerCase()}">
                        <div class="alert-icon">${a.icon}</div>
                        <div>
                            <div class="alert-level" style="color:${a.level==='CRITICAL'?'#ef4444':'#f59e0b'}">${a.level}</div>
                            <div class="alert-msg">${a.message}</div>
                        </div>
                    </div>`).join('');
            } else {
                alertsSection.style.display = 'none';
            }

            // Ramales
            const ramalGrid = document.getElementById('ramal-grid');
            const ramales = Object.values(d.by_ramal || {});
            if (ramales.length > 0) {
                ramalGrid.innerHTML = ramales.map(r => {
                    const color = pctColor(r.compliance_pct);
                    return `
                    <div class="ramal-card">
                        <div class="ramal-header">
                            <div>
                                <div class="ramal-code">${r.route_code.toUpperCase()}</div>
                                <div style="font-size:11px;color:var(--muted);margin-top:2px">Cuota: ${r.quota} despachos</div>
                            </div>
                            <div class="ramal-pct" style="color:${color}">${r.compliance_pct.toFixed(1)}%</div>
                        </div>
                        <div class="ramal-bar-bg">
                            <div class="ramal-bar-fill" style="width:${Math.min(100,r.compliance_pct)}%;background:${color}"></div>
                        </div>
                        <div class="ramal-stats">
                            <div class="ramal-stat">Ejecutados: <strong>${r.dispatched}</strong></div>
                            <div class="ramal-stat">Faltantes: <strong style="color:${r.missing>0?'#f59e0b':'#10b981'}">${r.missing}</strong></div>
                        </div>
                    </div>`;
                }).join('');
            }

            // Historial
            const histBars = document.getElementById('history-bars');
            const history = d.history_30d || [];
            if (history.length > 0) {
                const maxDisp = Math.max(...history.map(h => h.dispatches), 1);
                histBars.innerHTML = history.slice(0, 30).reverse().map(h => {
                    const h_pct = h.compliance_pct || 0;
                    const color = pctColor(h_pct);
                    const barH = Math.max(4, (h.dispatches / maxDisp) * 100);
                    const label = h.date ? h.date.slice(5) : '';
                    return `
                    <div class="h-bar-wrap">
                        <div class="h-bar" style="height:${barH}px;background:${color}"
                             data-tooltip="${h.date}: ${h.dispatches} despachos (${h_pct}%)"></div>
                        <div class="h-bar-label">${label}</div>
                    </div>`;
                }).join('');
            }
        }

        async function fetchCompliance() {
            try {
                const r = await fetch('/api/v1/compliance/today');
                const d = await r.json();
                renderData(d);
            } catch(e) {
                console.warn('Compliance fetch error:', e);
            }
        }

        fetchCompliance();
        refreshInterval = setInterval(fetchCompliance, 60000);
    </script>
</body>
</html>
"""
