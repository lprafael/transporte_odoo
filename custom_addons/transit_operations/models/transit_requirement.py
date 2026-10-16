# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class TransitRequirement(models.Model):
    _name = 'transit.requirement'
    _description = 'Solicitud de Ajustes y Requerimientos al Sistema'
    _inherit = ['transit.tenant.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_submitted desc, id desc'

    name = fields.Char(
        string='Título de la Solicitud',
        required=True,
        tracking=True,
        help='Resumen conciso del ajuste, mejora o reporte'
    )
    code = fields.Char(
        string='Código',
        readonly=True,
        copy=False,
        default='Nuevo',
        tracking=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Solicitante',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    assigned_id = fields.Many2one(
        'res.users',
        string='Técnico Asignado',
        tracking=True,
        domain="[('share', '=', False)]",
        help='Responsable del equipo de desarrollo / administración que atiende el requerimiento.'
    )
    category = fields.Selection([
        ('adjustment', '🛠️ Ajuste Operativo (Rutas, Horarios, Flota)'),
        ('feature', '✨ Nueva Funcionalidad / Módulo'),
        ('bug', '🚨 Reporte de Falla / Error'),
        ('telemetry', '📡 Ajuste en Telemetría GPS / Headway'),
        ('data', '📊 Actualización / Importación de Datos'),
        ('support', '❓ Consulta / Asistencia Técnica'),
        ('other', '📝 Otro Requerimiento')
    ], string='Tipo de Solicitud', required=True, default='adjustment', tracking=True)

    module_affected = fields.Selection([
        ('radar_gps', '🗺️ Radar Satelital GPS (/map)'),
        ('headway', '⏱️ Tablero de Frecuencias (/headway)'),
        ('fleet', '🚍 Flota y Vehículos'),
        ('drivers', '👨‍✈️ Choferes y Conductores'),
        ('spreadsheets', '📋 Hojas de Ruta y Planillas Diarias'),
        ('routes', '🛣️ Rutas, Ramales e Itinerarios'),
        ('sifen', '🧾 Facturación Electrónica SIFEN'),
        ('general', '🌐 Plataforma / General')
    ], string='Módulo Afectado', required=True, default='radar_gps', tracking=True)

    priority = fields.Selection([
        ('0', 'Baja'),
        ('1', 'Normal'),
        ('2', 'Alta'),
        ('3', 'Urgente / Crítica')
    ], string='Prioridad', default='1', tracking=True)

    stage = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Recibido / En Cola'),
        ('evaluating', 'En Análisis Técnico'),
        ('in_progress', 'En Desarrollo'),
        ('done', 'Desplegado / Resuelto'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='submitted', tracking=True, group_expand='_read_group_stage_ids')

    description = fields.Html(
        string='Descripción Detallada',
        required=True,
        help='Explica con detalle qué necesitas ajustar, qué coches o rutas involucra, o qué problema se presentó.'
    )
    solution_notes = fields.Html(
        string='Respuesta del Equipo Técnico / Solución Aplicada',
        help='Notas técnicas y detalles de los cambios aplicados en el sistema.'
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'transit_requirement_attachment_rel',
        'req_id',
        'attachment_id',
        string='Capturas o Archivos Adjuntos'
    )
    date_submitted = fields.Datetime(
        string='Fecha de Envío',
        default=fields.Datetime.now,
        readonly=True
    )
    date_resolved = fields.Datetime(
        string='Fecha de Resolución',
        readonly=True
    )
    color = fields.Integer(string='Índice de Color', compute='_compute_color')

    @api.depends('stage', 'priority')
    def _compute_color(self):
        for rec in self:
            if rec.stage == 'done':
                rec.color = 10  # Verde
            elif rec.stage == 'cancelled':
                rec.color = 1   # Rojo / Gris
            elif rec.priority == '3':
                rec.color = 9   # Rojo alerta
            elif rec.stage == 'in_progress':
                rec.color = 4   # Azul
            elif rec.stage == 'evaluating':
                rec.color = 3   # Amarillo
            else:
                rec.color = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'Nuevo') == 'Nuevo':
                vals['code'] = self.env['ir.sequence'].next_by_code('transit.requirement') or 'REQ-NUEVO'
            if not vals.get('date_submitted'):
                vals['date_submitted'] = fields.Datetime.now()
        records = super().create(vals_list)
        for rec in records:
            # Notificar en el chatter la creación
            rec.message_post(
                body=_("📥 <b>Nueva solicitud recibida:</b> %s (Empresa: %s)") % (rec.name, rec.concessionaire_id.name),
                subtype_xmlid='mail.mt_comment'
            )
        return records

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        # Asegurar que todas las columnas aparezcan siempre en la vista Kanban
        return [key for key, _val in self._fields['stage'].selection]

    # --- Acciones de Cambio de Estado ---
    def action_submit(self):
        for rec in self:
            rec.write({'stage': 'submitted'})
            rec.message_post(body=_("Solicitud enviada a la cola de atención técnica."))

    def action_evaluate(self):
        for rec in self:
            rec.write({'stage': 'evaluating'})
            rec.message_post(body=_("Solicitud en fase de análisis y evaluación técnica."))

    def action_in_progress(self):
        for rec in self:
            rec.write({'stage': 'in_progress'})
            rec.message_post(body=_("Solicitud ingresó a desarrollo / ejecución activa."))

    def action_resolve(self):
        for rec in self:
            rec.write({
                'stage': 'done',
                'date_resolved': fields.Datetime.now()
            })
            rec.message_post(body=_("🚀 <b>Requerimiento resuelto y desplegado en producción.</b>"))

    def action_cancel(self):
        for rec in self:
            rec.write({'stage': 'cancelled'})
            rec.message_post(body=_("Solicitud cancelada."))

    def action_reopen(self):
        for rec in self:
            rec.write({'stage': 'submitted', 'date_resolved': False})
            rec.message_post(body=_("Solicitud reabierta para revisión técnica."))
