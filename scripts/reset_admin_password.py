import odoo
from odoo import SUPERUSER_ID

registry = odoo.modules.registry.Registry('flota_db')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, SUPERUSER_ID, {})
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if not admin:
        admin = env['res.users'].search([('login', '=', 'admin')], limit=1)
    
    if admin:
        admin.write({'password': 'admin'})
        cr.commit()
        print('SUCCESS: Password for user [' + admin.login + '] has been reset to: admin')
    else:
        print('ERROR: User admin not found')
