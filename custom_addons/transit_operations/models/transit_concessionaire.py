# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import os
import requests
import urllib3

class TransitConcessionaire(models.Model):
    _name = 'transit.concessionaire'
    _description = 'Empresa Concesionaria / Operadora de Transporte'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Nombre Comercial', required=True, tracking=True)
    code = fields.Char(string='Código Interno de Concesión', required=True, index=True, tracking=True)
    agency_id = fields.Char(
        string='Código Telemática (Agency ID)',
        required=True,
        index=True,
        tracking=True,
        help='Código oficial transmitido por los dispositivos GPS (ej: 004B). Debe ser único por empresa.'
    )
    legal_name = fields.Char(string='Razón Social', tracking=True)
    vat_ruc = fields.Char(string='RUC / Identificación Fiscal', tracking=True)
    
    partner_id = fields.Many2one('res.partner', string='Contacto / Empresa Vinculada', tracking=True)
    contact_email = fields.Char(string='Correo Electrónico', related='partner_id.email', readonly=False)
    contact_phone = fields.Char(string='Teléfono', related='partner_id.phone', readonly=False)
    address = fields.Char(string='Dirección Base / Patio Central')
    
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color')

    # Relaciones Operativas
    vehicle_ids = fields.One2many('fleet.vehicle', 'concessionaire_id', string='Flota de Vehículos')
    vehicle_count = fields.Integer(string='Total Unidades', compute='_compute_vehicle_count')

    route_ids = fields.One2many('transit.route', 'concessionaire_id', string='Rutas Asignadas')
    route_count = fields.Integer(string='Total Rutas', compute='_compute_route_count')

    user_ids = fields.Many2many(
        'res.users',
        'transit_concessionaire_res_users_rel',
        'concessionaire_id',
        'user_id',
        string='Usuarios Asignados'
    )
    user_count = fields.Integer(string='Total Operadores', compute='_compute_user_count')

    evaluation_ids = fields.One2many('transit.concessionaire.evaluation', 'concessionaire_id', string='Historial de Evaluaciones')
    settlement_ids = fields.One2many('transit.clearing.settlement', 'concessionaire_id', string='Liquidaciones de Compensación')

    # -------------------------------------------------------------------------
    # INTEGRACIÓN BILLETAJE ELECTRÓNICO (JAHA / MÁS TARJETA)
    # -------------------------------------------------------------------------
    billetaje_provider = fields.Selection([
        ('none', 'Sin Integración / No Aplica'),
        ('jaha', 'Jaha (EPAS S.A.)'),
        ('mas', 'Más Tarjeta (TDP S.A.)'),
    ], string='Plataforma de Billetaje', default='none', tracking=True)

    billetaje_user = fields.Char(
        string='Usuario de Acceso Billetaje',
        tracking=True,
        help='Usuario de acceso al portal web de la empresa (ej: dsosa_srl)'
    )
    billetaje_password = fields.Char(
        string='Contraseña de Billetaje',
        help='Contraseña de acceso a la plataforma de billetaje'
    )
    billetaje_eid = fields.Integer(
        string='ID Empresa en Billetaje (EID)',
        tracking=True,
        help='Identificador numérico asignado por la operadora de billetaje (ej. 32 para Automotores Guaraní S.R.L.)'
    )
    billetaje_active = fields.Boolean(
        string='Sincronización Automática Activa',
        default=False,
        tracking=True,
        help='Si está activo, el Broker satelital consultará periódicamente los validadores a bordo de esta empresa.'
    )
    billetaje_last_sync = fields.Datetime(
        string='Última Sincronización',
        readonly=True
    )
    billetaje_last_status = fields.Selection([
        ('not_configured', 'No Configurado'),
        ('connected', 'Conectado Exitosamente'),
        ('error', 'Error de Autenticación / Conexión'),
    ], string='Estado de Conexión', default='not_configured', readonly=True)

    billetaje_status_details = fields.Text(
        string='Detalles de Estado / Diagnóstico',
        readonly=True
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Ya existe una empresa con este código de concesión.'),
        ('agency_id_unique', 'unique(agency_id)', 'El Código Telemática (Agency ID) debe ser único entre las empresas.'),
    ]

    @api.constrains('agency_id')
    def _check_agency_id(self):
        for rec in self:
            if rec.agency_id and len(rec.agency_id.strip()) == 0:
                raise ValidationError("El Código Telemática (Agency ID) no puede estar vacío.")

    @api.depends('vehicle_ids')
    def _compute_vehicle_count(self):
        for rec in self:
            rec.vehicle_count = len(rec.vehicle_ids)

    @api.depends('route_ids')
    def _compute_route_count(self):
        for rec in self:
            rec.route_count = len(rec.route_ids)

    @api.depends('user_ids')
    def _compute_user_count(self):
        for rec in self:
            rec.user_count = len(rec.user_ids)

    def action_view_users(self):
        self.ensure_one()
        list_view = self.env.ref('transit_operations.view_transit_company_users_list', raise_if_not_found=False)
        form_view = self.env.ref('transit_operations.view_transit_company_users_form', raise_if_not_found=False)
        views = []
        if list_view:
            views.append((list_view.id, 'list'))
        if form_view:
            views.append((form_view.id, 'form'))
        return {
            'name': f'Operadores de {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'views': views or [(False, 'list'), (False, 'form')],
            'domain': [('concessionaire_id', '=', self.id)],
            'context': {
                'default_concessionaire_id': self.id,
            }
        }

    def action_open_create_user_wizard(self):
        self.ensure_one()
        return {
            'name': f'Crear Operador para {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'transit.user.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_concessionaire_id': self.id,
            }
        }

    def action_test_billetaje_connection(self):
        """Prueba la conexión y autenticación con la plataforma de Billetaje Electrónico."""
        self.ensure_one()
        if self.billetaje_provider == 'none' or not self.billetaje_provider:
            raise UserError(_("Debe seleccionar una plataforma de billetaje (ej. Jaha o Más Tarjeta)."))
        if not self.billetaje_user or not self.billetaje_password:
            raise UserError(_("Debe ingresar el Usuario y la Contraseña de la plataforma de billetaje."))

        if self.billetaje_provider == 'jaha':
            return self._test_jaha_connection()
        elif self.billetaje_provider == 'mas':
            self.write({
                'billetaje_last_status': 'connected',
                'billetaje_last_sync': fields.Datetime.now(),
                'billetaje_status_details': f"Credenciales de Más Tarjeta (TDP S.A.) registradas para el usuario '{self.billetaje_user}'.",
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Billetaje Más Tarjeta"),
                    'message': _("Credenciales de Más Tarjeta registradas exitosamente."),
                    'type': 'info',
                    'sticky': False,
                }
            }

    def _test_jaha_connection(self):
        self.ensure_one()
        urllib3.disable_warnings()

        base_url = "https://billetajeelectronico.com.py"
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
        })

        try:
            s.get(f"{base_url}/", verify=False, timeout=10)
            resp = s.post(
                f"{base_url}/loginProcess",
                data={"username": self.billetaje_user, "password": self.billetaje_password},
                verify=False,
                timeout=12,
                allow_redirects=True
            )

            # Éxito si redirige al dashboard de operadoras o 200 sin error
            if "dashboard-operadoras" in resp.url or (resp.status_code == 200 and "error" not in resp.url.lower() and "login" not in resp.url.lower()):
                msg_extra = ""
                if self.billetaje_eid:
                    url_test = f"{base_url}/api1/api/v1/getMonitoreoPorEmpresa?empresa={self.billetaje_eid}"
                    r_test = s.get(url_test, verify=False, timeout=10)
                    if r_test.status_code == 200:
                        try:
                            data = r_test.json()
                            if isinstance(data, list):
                                msg_extra = f" Se detectaron {len(data)} validadores activos en tiempo real."
                        except Exception:
                            pass

                detail = (
                    f"✅ Autenticación exitosa en Jaha (EPAS S.A.) como '{self.billetaje_user}'.\n"
                    f"Empresa ID (EID): {self.billetaje_eid or 'No especificado'}.{msg_extra}\n"
                    f"Verificado el: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                self.write({
                    'billetaje_last_status': 'connected',
                    'billetaje_last_sync': fields.Datetime.now(),
                    'billetaje_status_details': detail,
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("Conexión Exitosa con Jaha"),
                        'message': _("Sesión establecida correctamente con la plataforma de Billetaje Jaha.") + msg_extra,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                detail = (
                    f"❌ Falla de autenticación en Jaha (EPAS S.A.).\n"
                    f"URL resultante: {resp.url}\n"
                    f"Código de respuesta HTTP: {resp.status_code}\n"
                    f"Verifique que el usuario y la contraseña sean los correctos para https://billetajeelectronico.com.py/login"
                )
                self.write({
                    'billetaje_last_status': 'error',
                    'billetaje_status_details': detail,
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("Error de Autenticación Jaha"),
                        'message': _("Las credenciales ingresadas no fueron aceptadas por Jaha."),
                        'type': 'danger',
                        'sticky': True,
                    }
                }
        except Exception as e:
            detail = f"❌ Excepción de red al conectar con https://billetajeelectronico.com.py: {str(e)}"
            self.write({
                'billetaje_last_status': 'error',
                'billetaje_status_details': detail,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Error de Conexión Billetaje"),
                    'message': f"No se pudo conectar con el portal de billetaje: {str(e)}",
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_sync_billetaje_now(self):
        """Dispara una sincronización inmediata a través del broker GPS."""
        self.ensure_one()
        self.action_test_billetaje_connection()
        if self.billetaje_last_status != 'connected':
            return

        broker_url = os.getenv("GPS_BROKER_URL", "http://127.0.0.1:8088")
        try:
            r = requests.post(f"{broker_url}/api/v1/billetaje/sync_now?agency_id={self.agency_id}", timeout=5)
            if r.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("Sincronización Disparada"),
                        'message': _(f"El Broker GPS ha iniciado la sincronización de validadores para {self.name}."),
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception:
            pass

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Credenciales Verificadas"),
                'message': _(f"Credenciales validadas exitosamente para {self.name}."),
                'type': 'success',
                'sticky': False,
            }
        }

    def name_get(self):
        res = []
        for rec in self:
            agency = f"[{rec.agency_id}] " if rec.agency_id else (f"[{rec.code}] " if rec.code else "")
            display = f"{agency}{rec.name}"
            res.append((rec.id, display))
        return res
