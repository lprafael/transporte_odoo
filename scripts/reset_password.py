# -*- coding: utf-8 -*-
import odoo
from odoo import SUPERUSER_ID

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'flota_db'])
registry = odoo.modules.registry.Registry('flota_db')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, SUPERUSER_ID, {})
    user = env['res.users'].search([('login', '=', 'lprafael1710@gmail.com')], limit=1)
    if user:
        user.write({'password': 'admin'})
        cr.commit()
        print(f"Contraseña de {user.login} actualizada exitosamente a 'admin'")
    else:
        print("Usuario lprafael1710@gmail.com no encontrado")
