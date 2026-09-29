# -*- coding: utf-8 -*-
import odoo
from odoo import SUPERUSER_ID

registry = odoo.modules.registry.Registry('flota_db')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, SUPERUSER_ID, {})
    users = env['res.users'].search([])
    for u in users:
        print(f"ID: {u.id} | Name: {u.name} | Login: {u.login} | Share (Portal): {u.share}")
        group_names = [g.name for g in u.groups_id]
        print(f"   Groups: {group_names[:5]}...")
