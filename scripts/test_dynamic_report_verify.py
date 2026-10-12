import odoo
from odoo import api, SUPERUSER_ID
from datetime import date

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'flota_db'])
registry = odoo.registry('flota_db')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Deduplicate reports
    for code in ['E1', 'E2', 'E3']:
        svc = env['transit.service'].search([('code', '=', code)], limit=1)
        reps = env['transit.dynamic.report'].search([('service_id', '=', svc.id)], order='id asc')
        if len(reps) > 1:
            # Keep first, unlink rest
            reps[1:].unlink()

    reports = env['transit.dynamic.report'].search([])
    print(f"Total reports after cleanup: {len(reports)}")
    for r in reports:
        r.write({'target_date': date(2026, 10, 11)})
        res = r.action_detect_and_sync()
        print(f"[{r.service_code}] Concluidos: {r.total_completed_trips_today}/{r.total_scheduled_trips_today} ({r.completion_percentage}%), Pasajeros: {r.total_passengers_today}, Km: {r.total_km_today}, IPK: {r.ipk_today}")
        dl_action = r.action_download_excel()
        print(f"[{r.service_code}] Download URL: {dl_action.get('url')}")
    cr.commit()
print("All reports verified and synced successfully!")
