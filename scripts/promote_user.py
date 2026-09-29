# -*- coding: utf-8 -*-
import odoo
from odoo import SUPERUSER_ID

registry = odoo.modules.registry.Registry('flota_db')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, SUPERUSER_ID, {})
    user = env['res.users'].search([('login', '=', 'lprafael1710@gmail.com')], limit=1)
    admin = env['res.users'].browse(2)
    
    if user:
        print(f"Modificando usuario {user.name} ({user.login})...")
        
        # Copiar todos los grupos del admin
        admin_groups = admin.groups_id
        
        # Quitar grupo portal si lo tiene
        portal_group = env.ref('base.group_portal', raise_if_not_found=False)
        
        # Grupos de transporte
        transit_mgr = env.ref('transit_operations.group_transit_manager', raise_if_not_found=False)
        
        new_groups = admin_groups
        if transit_mgr:
            new_groups = new_groups | transit_mgr
            
        if portal_group:
            user.write({
                'groups_id': [(3, portal_group.id)]
            })
            
        user.write({
            'groups_id': [(4, g.id) for g in new_groups]
        })
        
        # Asegurarse de que no sea portal (share = False)
        cr.execute("UPDATE res_users SET share = false WHERE id = %s", (user.id,))
        cr.commit()
        
        print("Usuario actualizado exitosamente como Usuario Interno y Administrador Total.")
        print(f"Grupos asignados: {[g.name for g in user.groups_id]}")
    else:
        print("Usuario no encontrado.")
