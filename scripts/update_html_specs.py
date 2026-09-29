"""Script para actualizar el HTML de especificaciones tecnicas con los nuevos features."""
import pathlib

html_path = pathlib.Path('ESPECIFICACIONES_TECNICAS.html')
html_content = html_path.read_text(encoding='utf-8')

# Update old title
old_title = 'Sistema Integral de Control de Flota de Buses, Despacho Operativo, Facturación Electrónica SIFEN, Telemetría MQTT/Protobuf (Res. GVMT 065/2024) y Motor Geoespacial PostGIS con Shapes de Vigencia Histórica'
new_title = 'Sistema Integral v3.0.0 | ETA Predictivo | Cumplimiento VMT | Bunching | Res. GVMT 065/2024'

html_updated = html_content.replace(old_title, new_title, 1)

# Also update page title tag
html_updated = html_updated.replace(
    '<title>Guía de Especificaciones Técnicas</title>',
    '<title>Especificaciones Técnicas v3.0.0 | Poliverso Transit</title>'
)

# Add new feature badges near top of body if not already present
if 'ETA Predictivo' not in html_updated:
    badge_html = '''
<div style="background:#0d1527;border:1px solid #1e293b;border-radius:12px;padding:12px 20px;margin:16px 0;display:flex;flex-wrap:wrap;gap:10px;">
  <span style="background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);color:#10b981;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">v3.0.0 Septiembre 2026</span>
  <span style="background:rgba(56,189,248,.15);border:1px solid rgba(56,189,248,.3);color:#38bdf8;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">NUEVO: ETA Predictivo por Parada</span>
  <span style="background:rgba(129,140,248,.15);border:1px solid rgba(129,140,248,.3);color:#818cf8;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">NUEVO: Cumplimiento VMT Res.065/2024</span>
  <span style="background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#ef4444;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">NUEVO: Bunching API REST</span>
  <span style="background:rgba(245,158,11,.15);border:1px solid rgba(245,158,11,.3);color:#f59e0b;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">Linea 20 Electrica - 692 despachos/dia</span>
</div>'''
    html_updated = html_updated.replace('<body>', '<body>' + badge_html, 1)

html_path.write_text(html_updated, encoding='utf-8')
print(f'HTML actualizado OK - {html_path.stat().st_size} bytes')
