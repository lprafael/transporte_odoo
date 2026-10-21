# -*- coding: utf-8 -*-
"""
Módulo de Gestión de Turnos y Cuadrantes Semanales de Conductores (Rostering)
=============================================================================
Permite la asignación visual y ágil de qué chofer conduce qué bus, a qué hora,
en qué sentido (Ida en Verde / Vuelta en Naranja), y qué días libres (francos)
tendrá cada conductor.

Incluye:
  - Detección de colisiones de horario (mismo chofer o mismo bus superpuesto)
  - Control de descanso reglamentario entre jornadas (mínimo 10 horas)
  - Banco de choferes de franco por día (para reemplazos rápidos con Drag & Drop)
  - Duplicación de cuadrante de una semana a otra
  - Exportación a Excel y Sincronización oficial con Despachos
"""

from datetime import datetime, date, timedelta, time
import logging
from io import BytesIO
import base64
import urllib.parse
import requests
import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

DAY_SELECTION = [
    ('0', 'Lunes'),
    ('1', 'Martes'),
    ('2', 'Miércoles'),
    ('3', 'Jueves'),
    ('4', 'Viernes'),
    ('5', 'Sábado'),
    ('6', 'Domingo'),
]

DAY_NAMES_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def float_to_hhmm(val):
    if val is None or val is False:
        return '00:00'
    total_min = int(round((val or 0.0) * 60))
    h = (total_min // 60) % 24
    m = total_min % 60
    return f"{h:02d}:{m:02d}"


def hhmm_to_float(hhmm_str):
    if not hhmm_str or ':' not in str(hhmm_str):
        return 0.0
    try:
        parts = str(hhmm_str).strip().split(':')
        h = int(parts[0])
        m = int(parts[1])
        return round(h + (m / 60.0), 2)
    except Exception:
        return 0.0


class TransitDriverRoster(models.Model):
    _name = 'transit.driver.roster'
    _description = 'Cuadrante Semanal de Turnos de Choferes (Roster)'
    _inherit = ['transit.tenant.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Código de Cuadrante',
        required=True,
        copy=False,
        default='Nuevo',
        tracking=True
    )
    date_start = fields.Date(
        string='Fecha Inicio (Lunes)',
        required=True,
        default=lambda self: fields.Date.today() - timedelta(days=fields.Date.today().weekday()),
        tracking=True,
        help='Fecha del primer día de la semana (Lunes)'
    )
    date_end = fields.Date(
        string='Fecha Fin (Domingo)',
        compute='_compute_date_end',
        store=True,
        readonly=False,
        tracking=True,
        help='Fecha del último día de la semana (Domingo)'
    )
    week_number = fields.Integer(
        string='Semana del Año',
        compute='_compute_week_number',
        store=True
    )
    shift_ids = fields.One2many(
        'transit.driver.shift',
        'roster_id',
        string='Turnos de la Semana',
        copy=True
    )
    state = fields.Selection([
        ('draft', 'Borrador (En Planificación)'),
        ('confirmed', 'Confirmado (Oficial Publicado)'),
        ('done', 'Ejecutado / Concluido'),
    ], string='Estado', default='draft', required=True, tracking=True)

    # Indicadores
    total_shifts = fields.Integer(string='Total Turnos', compute='_compute_metrics', store=True)
    assigned_shifts = fields.Integer(string='Turnos Cubiertos', compute='_compute_metrics', store=True)
    unassigned_shifts = fields.Integer(string='Turnos Vacantes', compute='_compute_metrics', store=True)
    conflict_count = fields.Integer(string='Conflictos Detectados', compute='_compute_metrics', store=True)
    coverage_percentage = fields.Float(string='% Cobertura', compute='_compute_metrics', store=True)

    excel_file = fields.Binary(string='Archivo Excel', readonly=True)
    excel_filename = fields.Char(string='Nombre Archivo Excel', readonly=True)

    notes = fields.Text(string='Observaciones de Tráfico')

    @api.depends('date_start')
    def _compute_date_end(self):
        for rec in self:
            if rec.date_start:
                rec.date_end = rec.date_start + timedelta(days=6)
            else:
                rec.date_end = False

    @api.depends('date_start')
    def _compute_week_number(self):
        for rec in self:
            if rec.date_start:
                rec.week_number = rec.date_start.isocalendar()[1]
            else:
                rec.week_number = 0

    @api.depends('shift_ids', 'shift_ids.state', 'shift_ids.driver_id')
    def _compute_metrics(self):
        for rec in self:
            total = len(rec.shift_ids)
            assigned = sum(1 for s in rec.shift_ids if s.driver_id)
            conflicts = sum(1 for s in rec.shift_ids if s.state == 'conflict')
            rec.total_shifts = total
            rec.assigned_shifts = assigned
            rec.unassigned_shifts = total - assigned
            rec.conflict_count = conflicts
            rec.coverage_percentage = round((assigned / total * 100.0), 1) if total else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'Nuevo':
                d_start = vals.get('date_start')
                if d_start:
                    d_dt = fields.Date.from_string(d_start)
                    w_num = d_dt.isocalendar()[1]
                    vals['name'] = f"CUADRANTE-S{w_num:02d}-{d_dt.year}"
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('transit.driver.roster') or 'CUADRANTE-SEMANAL'
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.conflict_count > 0:
                raise UserError(_("No puede confirmar el cuadrante si existen %d conflictos o superposiciones pendientes.") % rec.conflict_count)
            rec.action_sync_to_dispatches()
            rec.state = 'confirmed'
        return True

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_open_roster_board(self):
        """Abre la pantalla interactiva Drag & Drop en Odoo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'transit_roster_board',
            'name': f"Asignación de Turnos - {self.name}",
            'context': {
                'active_roster_id': self.id,
            }
        }

    # =========================================================================
    # Carga Automática desde la Programación Operativa
    # =========================================================================
    def action_load_from_operational_schedules(self):
        """
        Lee las hojas de ruta (transit.bus.schedule) o redondos (transit.service.roundtrip)
        comprendidos entre date_start y date_end, y genera o actualiza los turnos del cuadrante.
        """
        self.ensure_one()
        shift_obj = self.env['transit.driver.shift']
        start_d = self.date_start
        end_d = self.date_end or (start_d + timedelta(days=6))

        created_count = 0

        # 1. Cargar desde transit.bus.schedule (Hojas de ruta por bus)
        sched_lines = self.env['transit.bus.schedule.line'].search([
            ('schedule_id.date', '>=', start_d),
            ('schedule_id.date', '<=', end_d),
            ('schedule_id.concessionaire_id', '=', self.concessionaire_id.id) if self.concessionaire_id else (1, '=', 1)
        ])

        for line in sched_lines:
            # Verificar si ya existe este tramo en el cuadrante
            existing = shift_obj.search([
                ('roster_id', '=', self.id),
                ('bus_schedule_line_id', '=', line.id),
            ], limit=1)
            d_val = line.schedule_id.date
            day_idx = str(d_val.weekday())

            # Asignar chofer inicial si ya estaba en la hoja de ruta
            drv = line.driver_id or line.schedule_id.driver_id or False

            vals = {
                'roster_id': self.id,
                'date': d_val,
                'day_of_week': day_idx,
                'vehicle_id': line.schedule_id.vehicle_id.id,
                'service_id': line.service_id.id if line.service_id else (line.schedule_id.service_id.id if line.schedule_id.service_id else False),
                'route_id': line.route_id.id,
                'direction': line.direction or 'ida',
                'start_time': line.departure_time,
                'end_time': line.arrival_time,
                'bus_schedule_id': line.schedule_id.id,
                'bus_schedule_line_id': line.id,
                'driver_id': drv.id if drv else False,
                'state': 'assigned' if drv else 'unassigned',
            }

            if not existing:
                shift_obj.create(vals)
                created_count += 1
            else:
                existing.write(vals)

        # 2. Si no habían hojas de ruta de buses pero sí redondos en transit.service.roundtrip
        if not sched_lines:
            roundtrips = self.env['transit.service.roundtrip'].search([
                ('date', '>=', start_d),
                ('date', '<=', end_d),
                ('concessionaire_id', '=', self.concessionaire_id.id) if self.concessionaire_id else (1, '=', 1)
            ])
            for rt in roundtrips:
                d_val = rt.date
                day_idx = str(d_val.weekday())
                drv = rt.driver_id or False

                # Tramo Ida (Verde)
                if rt.departure_ida:
                    t_dep_ida = hhmm_to_float(rt.departure_ida)
                    t_arr_ida = hhmm_to_float(rt.arrival_ida) if rt.arrival_ida else (t_dep_ida + 1.25)
                    shift_obj.create({
                        'roster_id': self.id,
                        'date': d_val,
                        'day_of_week': day_idx,
                        'vehicle_id': rt.vehicle_id.id if rt.vehicle_id else False,
                        'service_id': rt.service_id.id if rt.service_id else False,
                        'direction': 'ida',
                        'start_time': t_dep_ida,
                        'end_time': t_arr_ida,
                        'roundtrip_id': rt.id,
                        'driver_id': drv.id if drv else False,
                        'state': 'assigned' if drv else 'unassigned',
                    })
                    created_count += 1

                # Tramo Vuelta (Naranja)
                if rt.departure_vuelta:
                    t_dep_vta = hhmm_to_float(rt.departure_vuelta)
                    t_arr_vta = hhmm_to_float(rt.arrival_vuelta) if rt.arrival_vuelta else (t_dep_vta + 1.25)
                    shift_obj.create({
                        'roster_id': self.id,
                        'date': d_val,
                        'day_of_week': day_idx,
                        'vehicle_id': rt.vehicle_id.id if rt.vehicle_id else False,
                        'service_id': rt.service_id.id if rt.service_id else False,
                        'direction': 'vuelta',
                        'start_time': t_dep_vta,
                        'end_time': t_arr_vta,
                        'roundtrip_id': rt.id,
                        'driver_id': drv.id if drv else False,
                        'state': 'assigned' if drv else 'unassigned',
                    })
                    created_count += 1

        # 3. Si no habían hojas de ruta ni redondos para esa semana, generar turnos base para la flota activa
        if not sched_lines and not created_count:
            created_count = self._generate_default_fleet_slots()

        self._check_all_conflicts()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Programación Operativa Cargada'),
                'message': _('Se prepararon %d turnos de servicio para la semana del %s al %s.') % (
                    len(self.shift_ids), self.date_start, self.date_end
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def _generate_default_fleet_slots(self):
        """Genera turnos base de servicio (Turno 1 Ida / Turno 2 Vuelta) para todos los buses en los 7 días"""
        shift_obj = self.env['transit.driver.shift']
        bus_domain = []
        if self.concessionaire_id:
            bus_domain.append(('concessionaire_id', '=', self.concessionaire_id.id))
        buses = self.env['fleet.vehicle'].search(bus_domain, order='bus_internal_number asc, name asc')

        created = 0
        for bus in buses:
            for day_idx in range(7):
                day_date = self.date_start + timedelta(days=day_idx)
                # Turno Mañana (Ida - Verde: 05:30 - 13:30)
                shift_obj.create({
                    'roster_id': self.id,
                    'date': day_date,
                    'day_of_week': str(day_idx),
                    'vehicle_id': bus.id,
                    'service_id': bus.service_id.id if bus.service_id else False,
                    'direction': 'ida',
                    'start_time': 5.5,
                    'end_time': 13.5,
                    'state': 'unassigned',
                })
                # Turno Tarde (Vuelta - Naranja: 13:30 - 21:30)
                shift_obj.create({
                    'roster_id': self.id,
                    'date': day_date,
                    'day_of_week': str(day_idx),
                    'vehicle_id': bus.id,
                    'service_id': bus.service_id.id if bus.service_id else False,
                    'direction': 'vuelta',
                    'start_time': 13.5,
                    'end_time': 21.5,
                    'state': 'unassigned',
                })
                created += 2
        return created

    # =========================================================================
    # Duplicar Planilla a la Semana Siguiente
    # =========================================================================
    def action_duplicate_next_week(self):
        """
        Copia íntegramente la estructura del cuadrante a los 7 días de la semana siguiente (+7 días).
        Mantiene los turnos, buses y choferes asignados.
        """
        self.ensure_one()
        next_start = self.date_start + timedelta(days=7)
        next_end = next_start + timedelta(days=6)
        w_num = next_start.isocalendar()[1]

        # Verificar si ya existe cuadrante para la próxima semana
        existing = self.search([
            ('date_start', '=', next_start),
            ('concessionaire_id', '=', self.concessionaire_id.id)
        ], limit=1)
        if existing:
            raise UserError(_("Ya existe un cuadrante para la semana %d (%s al %s): %s") % (
                w_num, next_start, next_end, existing.name
            ))

        new_roster = self.copy({
            'name': f"CUADRANTE-S{w_num:02d}-{next_start.year}",
            'date_start': next_start,
            'state': 'draft',
        })

        # Clonar los turnos ajustando la fecha a +7 días
        for shift in self.shift_ids:
            new_date = shift.date + timedelta(days=7) if shift.date else next_start
            shift.copy({
                'roster_id': new_roster.id,
                'date': new_date,
                'bus_schedule_id': False,
                'bus_schedule_line_id': False,
                'roundtrip_id': False,
                'dispatch_id': False,
            })

        new_roster._check_all_conflicts()

        return {
            'name': f'Cuadrante Duplicado - Semana {w_num}',
            'type': 'ir.actions.act_window',
            'res_model': 'transit.driver.roster',
            'view_mode': 'form',
            'res_id': new_roster.id,
        }

    # =========================================================================
    # Sincronización Oficial con Despachos y Hojas de Ruta
    # =========================================================================
    def action_sync_to_dispatches(self):
        """
        Aplica los choferes asignados en el cuadrante hacia las líneas de hoja de ruta
        y los despachos diarios oficiales.
        """
        self.ensure_one()
        count = 0
        for shift in self.shift_ids:
            if not shift.driver_id:
                continue

            # 1. Si está vinculado a bus_schedule_line
            if shift.bus_schedule_line_id:
                shift.bus_schedule_line_id.write({'driver_id': shift.driver_id.id})
                if shift.bus_schedule_line_id.dispatch_id:
                    shift.bus_schedule_line_id.dispatch_id.write({'driver_id': shift.driver_id.id})
                count += 1

            # 2. Si está vinculado a roundtrip
            if shift.roundtrip_id:
                shift.roundtrip_id.write({
                    'driver_id': shift.driver_id.id,
                    'driver_name': shift.driver_id.name,
                })
                count += 1

            # 3. Buscar despachos coincidentes por bus, fecha y hora de salida
            if shift.vehicle_id and shift.date:
                h_dep, m_dep = int(shift.start_time), int(round((shift.start_time % 1) * 60))
                disp = self.env['transit.dispatch'].search([
                    ('vehicle_id', '=', shift.vehicle_id.id),
                    ('date', '=', shift.date),
                ])
                for d in disp:
                    if d.scheduled_departure:
                        # Si coincide aproximadamente la hora de salida
                        d_time = d.scheduled_departure.time()
                        if d_time.hour == h_dep:
                            d.write({'driver_id': shift.driver_id.id})
                            count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Despachos Sincronizados'),
                'message': _('Se asignaron oficialmente %d conductores a la operativa.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    # =========================================================================
    # Validación Global de Conflictos
    # =========================================================================
    def _check_all_conflicts(self):
        """Recorre todos los turnos del cuadrante y recalcula conflictos"""
        for shift in self.shift_ids:
            shift._validate_shift_conflicts()

    # =========================================================================
    # Exportación a Excel (.xlsx)
    # =========================================================================
    def action_export_excel(self):
        self.ensure_one()
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise UserError(_("Se requiere la librería 'openpyxl' instalada en el entorno."))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Semana {self.week_number}"
        ws.views.sheetView[0].showGridLines = True

        # Estilos
        font_title = Font(name='Segoe UI', size=14, bold=True, color='1E293B')
        font_subtitle = Font(name='Segoe UI', size=10, bold=False, color='64748B')
        font_header = Font(name='Segoe UI', size=10, bold=True, color='FFFFFF')
        font_day_header = Font(name='Segoe UI', size=10, bold=True, color='FFFFFF')
        font_cell = Font(name='Segoe UI', size=9, color='0F172A')
        font_free = Font(name='Segoe UI', size=8, italic=True, color='0284C7')

        fill_header = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid') # Azul Tránsito
        fill_day = PatternFill(start_color='334155', end_color='334155', fill_type='solid')
        fill_ida = PatternFill(start_color='DCFCE7', end_color='DCFCE7', fill_type='solid') # Verde suave
        fill_vuelta = PatternFill(start_color='FFEDD5', end_color='FFEDD5', fill_type='solid') # Naranja suave
        fill_vacant = PatternFill(start_color='FEE2E2', end_color='FEE2E2', fill_type='solid') # Rojo suave

        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        # Encabezado General
        ws.merge_cells('A1:H1')
        ws['A1'] = f"PLANILLA OFICIAL DE ASIGNACIÓN DE TURNOS - {self.name}"
        ws['A1'].font = font_title
        ws['A1'].alignment = Alignment(vertical='center')

        ws.merge_cells('A2:H2')
        company_name = self.concessionaire_id.name if self.concessionaire_id else "TODAS LAS LÍNEAS"
        ws['A2'] = f"Empresa: {company_name} | Período: {self.date_start} al {self.date_end} (Semana {self.week_number})"
        ws['A2'].font = font_subtitle

        # Fila 4: Cabeceras de columnas (Buses + 7 días)
        headers = ['Bus / Unidad'] + [f"{DAY_NAMES_ES[i]}\n{(self.date_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(7)]
        for col_idx, h_text in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=h_text)
            cell.font = font_header
            cell.fill = fill_header if col_idx == 1 else fill_day
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = thin_border
        ws.row_dimensions[4].height = 28

        # Recopilar todos los buses de este cuadrante
        vehicles = self.shift_ids.mapped('vehicle_id').sorted(lambda v: v.bus_internal_number or '999')
        current_row = 5

        for veh in vehicles:
            ws.cell(row=current_row, column=1, value=f"Interno #{veh.bus_internal_number or veh.name}\n[{veh.license_plate or ''}]").font = Font(name='Segoe UI', size=9, bold=True)
            ws.cell(row=current_row, column=1).alignment = Alignment(vertical='center', wrap_text=True)
            ws.cell(row=current_row, column=1).border = thin_border

            # Para cada día (0 a 6)
            for day_idx in range(7):
                day_date = self.date_start + timedelta(days=day_idx)
                shifts_day = self.shift_ids.filtered(lambda s: s.vehicle_id == veh and s.date == day_date).sorted('start_time')
                cell = ws.cell(row=current_row, column=day_idx + 2)
                cell.border = thin_border
                cell.alignment = Alignment(vertical='top', wrap_text=True)

                if not shifts_day:
                    cell.value = "— Sin servicio —"
                    cell.font = Font(name='Segoe UI', size=8, color='94A3B8')
                else:
                    lines_text = []
                    for s in shifts_day:
                        tag = "IDA" if s.direction == 'ida' else ("VTA" if s.direction == 'vuelta' else "RED")
                        drv_name = s.driver_id.name if s.driver_id else "⚠️ VACANTE"
                        lines_text.append(f"[{tag} {s.start_time_str}-{s.end_time_str}] {drv_name}")
                    cell.value = "\n".join(lines_text)
                    cell.font = font_cell
                    # Fondo si todos son ida, vuelta o vacante
                    if any(not s.driver_id for s in shifts_day):
                        cell.fill = fill_vacant
                    elif all(s.direction == 'ida' for s in shifts_day):
                        cell.fill = fill_ida
                    elif all(s.direction == 'vuelta' for s in shifts_day):
                        cell.fill = fill_vuelta

            ws.row_dimensions[current_row].height = max(35, len(self.shift_ids.filtered(lambda s: s.vehicle_id == veh)) * 12)
            current_row += 1

        # Fila de Choferes de Franco por día
        current_row += 1
        ws.cell(row=current_row, column=1, value="CHOFERES DE FRANCO / LIBRES").font = Font(name='Segoe UI', size=9, bold=True, color='0284C7')
        ws.cell(row=current_row, column=1).border = thin_border
        ws.cell(row=current_row, column=1).alignment = Alignment(vertical='center', wrap_text=True)

        for day_idx in range(7):
            day_date = self.date_start + timedelta(days=day_idx)
            free_drivers = self._get_free_drivers_for_date(day_date)
            cell = ws.cell(row=current_row, column=day_idx + 2)
            cell.border = thin_border
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            cell.font = font_free
            if free_drivers:
                cell.value = "🏖️ " + "\n🏖️ ".join([d.name for d in free_drivers[:8]])
            else:
                cell.value = "Todos asignados"

        ws.row_dimensions[current_row].height = 45

        # Ajuste de anchos de columna
        ws.column_dimensions['A'].width = 18
        for col_idx in range(2, 9):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 24

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        file_base64 = base64.b64encode(output.read())

        filename = f"Cuadrante_Semanal_{self.name.replace(' ', '_')}.xlsx"
        self.write({
            'excel_file': file_base64,
            'excel_filename': filename,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=transit.driver.roster&id={self.id}&field=excel_file&download=true&filename={filename}',
            'target': 'self',
        }

    def _get_free_drivers_for_date(self, target_date):
        """Retorna los choferes que no tienen turno asignado en target_date"""
        domain = [('is_driver', '=', True)]
        if self.concessionaire_id:
            domain.append(('concessionaire_id', '=', self.concessionaire_id.id))
        all_drivers = self.env['res.partner'].search(domain)

        busy_driver_ids = self.shift_ids.filtered(lambda s: s.date == target_date and s.driver_id).mapped('driver_id').ids
        return all_drivers.filtered(lambda d: d.id not in busy_driver_ids)

    # =========================================================================
    # API Backend para Tablero Drag & Drop (OWL)
    # =========================================================================
    @api.model
    def get_or_create_current_roster(self):
        """Busca el cuadrante más reciente o crea automáticamente el de la semana en curso"""
        roster = self.search([], order='date_start desc, id desc', limit=1)
        if roster:
            return roster.id

        today = fields.Date.today()
        monday = today - timedelta(days=today.weekday())
        w_num = monday.isocalendar()[1]
        new_roster = self.create({
            'name': f"CUADRANTE-S{w_num:02d}-{monday.year}",
            'date_start': monday,
        })
        try:
            new_roster.action_load_from_operational_schedules()
        except Exception as e:
            _logger.warning(f"No se pudieron precargar schedules para el nuevo cuadrante: {e}")
        return new_roster.id

    @api.model
    def get_roster_board_data(self, roster_id=None):
        """
        Retorna la estructura completa de datos requerida para el componente interactivo:
        - Información del cuadrante
        - Días de la semana (Lunes a Domingo con fecha y formato)
        - Lista de Buses disponibles
        - Lista de Choferes (con horas asignadas, teléfono, avatar, estado)
        - Lista de Turnos (shifts) con id, horario, sentido, bus, chofer, alertas
        - Lista de Choferes de Franco por día
        """
        if not roster_id or not self.browse(roster_id).exists():
            roster_id = self.get_or_create_current_roster()

        roster = self.browse(roster_id)
        if not roster.exists():
            return {'error': 'No se pudo obtener o crear el cuadrante semanal.'}

        start_d = roster.date_start
        end_d = roster.date_end

        # Días
        days_data = []
        for i in range(7):
            d = start_d + timedelta(days=i)
            days_data.append({
                'index': i,
                'key': str(i),
                'name': DAY_NAMES_ES[i],
                'date_str': d.strftime('%Y-%m-%d'),
                'display_date': d.strftime('%d/%m'),
            })

        # Buses
        bus_domain = []
        if roster.concessionaire_id:
            bus_domain.append(('concessionaire_id', '=', roster.concessionaire_id.id))
        buses = self.env['fleet.vehicle'].search(bus_domain, order='bus_internal_number asc, name asc')
        buses_data = []
        for b in buses:
            buses_data.append({
                'id': b.id,
                'name': b.name,
                'internal_number': b.bus_internal_number or b.name or '',
                'bus_internal_number': b.bus_internal_number or b.name or '',
                'license_plate': b.license_plate or '',
                'service_code': b.service_id.code if b.service_id else '',
                'service_name': b.service_id.name if b.service_id else '',
            })

        # Choferes
        driver_domain = [('is_driver', '=', True)]
        if roster.concessionaire_id:
            driver_domain.append(('concessionaire_id', '=', roster.concessionaire_id.id))
        drivers = self.env['res.partner'].search(driver_domain, order='name asc')

        # Calcular horas semanales por chofer en este cuadrante
        shifts = roster.shift_ids
        drivers_data = []
        for d in drivers:
            d_shifts = shifts.filtered(lambda s: s.driver_id == d)
            tot_hours = sum(s.duration_hours for s in d_shifts)
            rest_days_count = 7 - len(set(s.date for s in d_shifts))
            drivers_data.append({
                'id': d.id,
                'name': d.name,
                'driver_code': d.driver_code or '',
                'license_number': d.driver_license_number or '',
                'license_category': d.driver_license_category or '',
                'phone': d.phone or d.mobile or '',
                'total_hours': round(tot_hours, 1),
                'total_hours_str': f"{int(tot_hours)}h {int(round((tot_hours % 1) * 60))}m",
                'shifts_count': len(d_shifts),
                'rest_days_count': rest_days_count,
            })

        # Turnos
        shifts_data = []
        for s in shifts:
            shifts_data.append({
                'id': s.id,
                'date': s.date.strftime('%Y-%m-%d') if s.date else '',
                'day_index': int(s.day_of_week or 0),
                'vehicle_id': s.vehicle_id.id if s.vehicle_id else False,
                'vehicle_name': s.vehicle_id.name if s.vehicle_id else 'Sin Bus',
                'internal_number': s.vehicle_id.bus_internal_number or s.vehicle_id.name if s.vehicle_id else '',
                'bus_internal_number': s.vehicle_id.bus_internal_number or s.vehicle_id.name if s.vehicle_id else '',
                'driver_id': s.driver_id.id if s.driver_id else False,
                'driver_name': s.driver_id.name if s.driver_id else '',
                'direction': s.direction or 'ida',
                'direction_label': 'Ida' if s.direction == 'ida' else ('Vuelta' if s.direction == 'vuelta' else 'Redondo'),
                'start_time': s.start_time,
                'end_time': s.end_time,
                'start_time_str': s.start_time_str,
                'end_time_str': s.end_time_str,
                'duration_hours': s.duration_hours,
                'service_code': s.service_id.code if s.service_id else '',
                'route_name': s.route_id.name if s.route_id else '',
                'state': s.state,
                'conflict_note': s.conflict_note or '',
                'whatsapp_sent': s.whatsapp_sent,
                'whatsapp_status': s.whatsapp_status,
                'whatsapp_url': s._get_whatsapp_url(),
            })

        # Choferes de Franco por día
        free_drivers_by_day = {}
        for d_info in days_data:
            t_date = datetime.strptime(d_info['date_str'], '%Y-%m-%d').date()
            free_list = roster._get_free_drivers_for_date(t_date)
            free_drivers_by_day[d_info['key']] = [{
                'id': drv.id,
                'name': drv.name,
                'driver_code': drv.driver_code or '',
            } for drv in free_list]

        return {
            'roster': {
                'id': roster.id,
                'name': roster.name,
                'date_start': roster.date_start.strftime('%Y-%m-%d'),
                'date_end': roster.date_end.strftime('%Y-%m-%d') if roster.date_end else '',
                'week_number': roster.week_number,
                'state': roster.state,
                'coverage_percentage': roster.coverage_percentage,
                'conflict_count': roster.conflict_count,
            },
            'days': days_data,
            'buses': buses_data,
            'drivers': drivers_data,
            'shifts': shifts_data,
            'free_drivers_by_day': free_drivers_by_day,
        }

    @api.model
    def rpc_assign_driver(self, shift_id, driver_id, force=False):
        """Asigna un chofer a un turno con validación de superposiciones y descanso"""
        shift = self.env['transit.driver.shift'].browse(shift_id)
        if not shift.exists():
            return {'success': False, 'message': 'Turno no encontrado'}

        driver = self.env['res.partner'].browse(driver_id)
        if not driver.exists():
            return {'success': False, 'message': 'Chofer no encontrado'}

        # Comprobar superposiciones el mismo día
        overlap_shifts = self.env['transit.driver.shift'].search([
            ('id', '!=', shift.id),
            ('roster_id', '=', shift.roster_id.id),
            ('date', '=', shift.date),
            ('driver_id', '=', driver.id),
            ('start_time', '<', shift.end_time),
            ('end_time', '>', shift.start_time),
        ])

        if overlap_shifts and not force:
            conflict_msg = _("¡Superposición de Turno! El conductor %s ya tiene asignado el Bus %s de %s a %s.") % (
                driver.name,
                overlap_shifts[0].vehicle_id.name if overlap_shifts[0].vehicle_id else 'S/N',
                overlap_shifts[0].start_time_str,
                overlap_shifts[0].end_time_str
            )
            return {
                'success': False,
                'conflict': True,
                'message': conflict_msg,
            }

        # Comprobar descanso mínimo reglamentario (ej. 10 horas) respecto al día anterior o siguiente
        rest_warning = False
        prev_date = shift.date - timedelta(days=1)
        prev_shifts = self.env['transit.driver.shift'].search([
            ('roster_id', '=', shift.roster_id.id),
            ('date', '=', prev_date),
            ('driver_id', '=', driver.id),
        ], order='end_time desc', limit=1)

        if prev_shifts:
            hours_rest = (24.0 - prev_shifts.end_time) + shift.start_time
            if hours_rest < 10.0:
                rest_warning = _("Descanso corto: El chofer solo tendrá %.1f horas de descanso entre el turno de ayer y hoy.") % hours_rest

        shift.write({
            'driver_id': driver.id,
            'state': 'assigned',
            'conflict_note': rest_warning or False,
        })
        shift._validate_shift_conflicts()

        return {
            'success': True,
            'warning': rest_warning,
            'shift': {
                'id': shift.id,
                'driver_id': driver.id,
                'driver_name': driver.name,
                'state': shift.state,
                'conflict_note': shift.conflict_note or '',
            }
        }

    @api.model
    def rpc_unassign_driver(self, shift_id):
        """Desasigna el conductor de un turno dejándolo vacante"""
        shift = self.env['transit.driver.shift'].browse(shift_id)
        if not shift.exists():
            return {'success': False, 'message': 'Turno no encontrado'}

        shift.write({
            'driver_id': False,
            'state': 'unassigned',
            'conflict_note': False,
        })
        shift._validate_shift_conflicts()
        return {'success': True}

    @api.model
    def rpc_quick_assign_or_create_shift(self, roster_id, vehicle_id, date_str, driver_id, force=False):
        """
        Asigna el conductor al turno vacante del bus en date_str,
        o crea automáticamente un turno nuevo si la celda estaba vacía ("Sin servicio").
        """
        roster = self.browse(roster_id)
        if not roster.exists():
            return {'success': False, 'message': 'Cuadrante no encontrado'}

        driver = self.env['res.partner'].browse(driver_id)
        if not driver.exists():
            return {'success': False, 'message': 'Conductor no encontrado'}

        vehicle = self.env['fleet.vehicle'].browse(vehicle_id)
        if not vehicle.exists():
            return {'success': False, 'message': 'Bus no encontrado'}

        target_date = fields.Date.from_string(date_str)
        day_idx = str(target_date.weekday())

        # 1. Buscar si hay un turno vacante en esa celda
        vacant_shift = self.env['transit.driver.shift'].search([
            ('roster_id', '=', roster.id),
            ('vehicle_id', '=', vehicle.id),
            ('date', '=', target_date),
            ('driver_id', '=', False),
        ], order='start_time asc', limit=1)

        if vacant_shift:
            return self.rpc_assign_driver(vacant_shift.id, driver.id, force=force)

        # 2. Si no hay turno vacante, crear un turno nuevo en esa celda
        existing_shifts = self.env['transit.driver.shift'].search([
            ('roster_id', '=', roster.id),
            ('vehicle_id', '=', vehicle.id),
            ('date', '=', target_date),
        ], order='end_time desc', limit=1)

        if existing_shifts:
            t_start = round(existing_shifts.end_time + 0.5, 2)
            t_end = round(t_start + 7.5, 2)
            direction = 'vuelta' if existing_shifts.direction == 'ida' else 'ida'
        else:
            t_start = 5.5
            t_end = 13.5
            direction = 'ida'

        # Validar colisión si no es forzada
        overlap_shifts = self.env['transit.driver.shift'].search([
            ('roster_id', '=', roster.id),
            ('date', '=', target_date),
            ('driver_id', '=', driver.id),
            ('start_time', '<', t_end),
            ('end_time', '>', t_start),
        ])

        if overlap_shifts and not force:
            conflict_msg = _("¡Superposición de Turno! El conductor %s ya tiene asignado el Bus %s de %s a %s.") % (
                driver.name,
                overlap_shifts[0].vehicle_id.name if overlap_shifts[0].vehicle_id else 'S/N',
                overlap_shifts[0].start_time_str,
                overlap_shifts[0].end_time_str
            )
            return {
                'success': False,
                'conflict': True,
                'message': conflict_msg,
                'pendingCell': {
                    'rosterId': roster.id,
                    'vehicleId': vehicle.id,
                    'dateStr': date_str,
                    'driverId': driver.id,
                }
            }

        new_shift = self.env['transit.driver.shift'].create({
            'roster_id': roster.id,
            'date': target_date,
            'day_of_week': day_idx,
            'vehicle_id': vehicle.id,
            'service_id': vehicle.service_id.id if vehicle.service_id else False,
            'direction': direction,
            'start_time': t_start,
            'end_time': t_end,
            'driver_id': driver.id,
            'state': 'assigned',
        })
        new_shift._validate_shift_conflicts()

        return {
            'success': True,
            'shift': {
                'id': new_shift.id,
                'driver_id': driver.id,
                'driver_name': driver.name,
            }
        }

    @api.model
    def rpc_send_shift_whatsapp(self, shift_id):
        """Dispara manualmente el aviso por WhatsApp para un turno específico"""
        shift = self.env['transit.driver.shift'].browse(shift_id)
        if not shift.exists():
            return {'success': False, 'message': 'Turno no encontrado'}
        return shift.action_send_whatsapp_reminder()

    # =========================================================================
    # Acción Planificada (Cron): Envío 20 min antes del turno
    # =========================================================================
    @api.model
    def cron_send_pre_shift_whatsapp_alerts(self):
        """
        Busca los turnos de la fecha de hoy cuyo horario de inicio sea dentro de los
        próximos 20 minutos (configurable), que tengan conductor y no se les haya
        enviado aún el recordatorio.
        """
        icp = self.env['ir.config_parameter'].sudo()
        enabled = icp.get_param('transit.whatsapp_enabled', default='True') == 'True'
        if not enabled:
            _logger.info("Avisos automáticos por WhatsApp desactivados en configuración.")
            return False

        minutes_before = int(icp.get_param('transit.whatsapp_minutes_before', default=20))

        today = fields.Date.today()
        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute

        # Turnos de hoy con conductor asignado que no hayan recibido el aviso
        shifts = self.env['transit.driver.shift'].search([
            ('date', '=', today),
            ('driver_id', '!=', False),
            ('whatsapp_sent', '=', False),
        ])

        sent_count = 0
        for shift in shifts:
            shift_minutes = int(round((shift.start_time or 0.0) * 60))
            diff_min = shift_minutes - now_minutes

            # Se dispara si está entre minutes_before - 5 y minutes_before + 5
            # O si ya está a menos de minutes_before pero aún antes del inicio
            if 0 <= diff_min <= (minutes_before + 5):
                _logger.info(f"Disparando aviso WhatsApp para Chofer {shift.driver_id.name} (Turno en {diff_min} min)")
                try:
                    res = shift.action_send_whatsapp_reminder()
                    if res.get('success'):
                        sent_count += 1
                except Exception as e:
                    _logger.error(f"Error al enviar WhatsApp a {shift.driver_id.name}: {e}")

        _logger.info(f"Cron WhatsApp Pre-Turno completado: {sent_count} avisos enviados.")
        return True


class TransitDriverShift(models.Model):
    _name = 'transit.driver.shift'
    _description = 'Turno Individual de Conducción en Cuadrante'
    _order = 'date asc, start_time asc, id asc'

    roster_id = fields.Many2one(
        'transit.driver.roster',
        string='Cuadrante Padre',
        required=True,
        ondelete='cascade',
        index=True
    )
    date = fields.Date(string='Fecha', required=True, index=True)
    day_of_week = fields.Selection(DAY_SELECTION, string='Día de la Semana', required=True)

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Bus / Unidad',
        required=True,
        index=True
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Conductor Asignado',
        domain="[('is_driver', '=', True)]",
        index=True
    )

    service_id = fields.Many2one('transit.service', string='Línea / Servicio')
    route_id = fields.Many2one('transit.route', string='Ruta / Itinerario')

    direction = fields.Selection([
        ('ida', 'Ida (Verde)'),
        ('vuelta', 'Vuelta / Retorno (Naranja)'),
        ('roundtrip', 'Redondo Completo'),
    ], string='Sentido de Marcha', default='ida', required=True)

    start_time = fields.Float(string='Hora Salida', required=True, default=6.0)
    end_time = fields.Float(string='Hora Llegada', required=True, default=7.5)

    start_time_str = fields.Char(string='Salida', compute='_compute_times_str', store=True)
    end_time_str = fields.Char(string='Llegada', compute='_compute_times_str', store=True)
    duration_hours = fields.Float(string='Duración (h)', compute='_compute_duration', store=True)

    # Trazabilidad Operativa
    bus_schedule_id = fields.Many2one('transit.bus.schedule', string='Hoja de Ruta', ondelete='set null')
    bus_schedule_line_id = fields.Many2one('transit.bus.schedule.line', string='Tramo Hoja de Ruta', ondelete='set null')
    roundtrip_id = fields.Many2one('transit.service.roundtrip', string='Redondo', ondelete='set null')
    dispatch_id = fields.Many2one('transit.dispatch', string='Despacho Diario', ondelete='set null')

    state = fields.Selection([
        ('unassigned', 'Vacante / Sin Chofer'),
        ('assigned', 'Asignado Conforme'),
        ('conflict', 'Conflicto / Superpuesto'),
    ], string='Estado', default='unassigned', required=True)

    conflict_note = fields.Char(string='Detalle de Conflicto')

    # =========================================================================
    # Alertas y Notificaciones por WhatsApp
    # =========================================================================
    whatsapp_sent = fields.Boolean(string='Aviso WhatsApp Enviado', default=False)
    whatsapp_sent_time = fields.Datetime(string='Hora Envío Aviso')
    whatsapp_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('sent', 'Enviado con Éxito'),
        ('failed', 'Error al Enviar'),
    ], string='Estado WhatsApp', default='pending')
    whatsapp_log = fields.Text(string='Bitácora de Envío')

    @api.depends('start_time', 'end_time')
    def _compute_times_str(self):
        for rec in self:
            rec.start_time_str = float_to_hhmm(rec.start_time)
            rec.end_time_str = float_to_hhmm(rec.end_time)

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            dur = (rec.end_time or 0.0) - (rec.start_time or 0.0)
            if dur < 0:
                dur += 24.0
            rec.duration_hours = round(dur, 2)

    def _validate_shift_conflicts(self):
        """Valida si este turno tiene superposición de bus o de chofer"""
        for rec in self:
            conflicts = []
            if rec.driver_id:
                # 1. Superposición de Chofer
                overlap_drv = self.search([
                    ('id', '!=', rec.id),
                    ('roster_id', '=', rec.roster_id.id),
                    ('date', '=', rec.date),
                    ('driver_id', '=', rec.driver_id.id),
                    ('start_time', '<', rec.end_time),
                    ('end_time', '>', rec.start_time),
                ])
                if overlap_drv:
                    conflicts.append(f"Chofer {rec.driver_id.name} superpuesto con Bus {overlap_drv[0].vehicle_id.name}")

            if rec.vehicle_id:
                # 2. Superposición de Bus
                overlap_veh = self.search([
                    ('id', '!=', rec.id),
                    ('roster_id', '=', rec.roster_id.id),
                    ('date', '=', rec.date),
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('start_time', '<', rec.end_time),
                    ('end_time', '>', rec.start_time),
                ])
                if overlap_veh:
                    conflicts.append(f"Bus {rec.vehicle_id.name} ya tiene salida a las {overlap_veh[0].start_time_str}")

            if conflicts:
                rec.state = 'conflict'
                rec.conflict_note = " | ".join(conflicts)
            elif rec.driver_id:
                rec.state = 'assigned'
                rec.conflict_note = False
            else:
                rec.state = 'unassigned'
                rec.conflict_note = False

    # =========================================================================
    # Métodos de Notificación WhatsApp
    # =========================================================================
    def _build_whatsapp_message(self):
        """Genera el texto de recordatorio para el chofer a partir de la plantilla"""
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()
        minutes = icp.get_param('transit.whatsapp_minutes_before', default=20)
        template = icp.get_param('transit.whatsapp_template', default="""👋 ¡Hola, *{driver_name}*! 🚌
Te recordamos que tu turno inicia en *{minutes} minutos* (a las *{departure_time}* hs).

📋 *Detalles del Servicio:*
• *Bus / Interno:* #{bus_number} (Placa: {license_plate})
• *Línea / Servicio:* {service_name}
• *Sentido:* {direction}
• *Tramo / Ruta:* {route_name}

⚠️ _Por favor preséntate en cabecera con uniforme para la inspección pre-operativa._ ¡Buen viaje! 🚦👍""")

        drv = self.driver_id
        veh = self.vehicle_id
        dir_label = "Ida" if self.direction == 'ida' else ("Vuelta" if self.direction == 'vuelta' else "Redondo")

        return template.format(
            driver_name=drv.name or 'Conductor',
            minutes=minutes,
            departure_time=self.start_time_str,
            bus_number=veh.internal_number or veh.name if veh else 'S/N',
            license_plate=veh.license_plate or '' if veh else '',
            service_name=self.service_id.name if self.service_id else (veh.service_id.name if veh and veh.service_id else 'Servicio Oficial'),
            direction=dir_label,
            route_name=self.route_id.name if self.route_id else 'Ruta Principal',
        )

    def _get_whatsapp_url(self):
        """Genera el enlace web de WhatsApp para apertura rápida"""
        self.ensure_one()
        if not self.driver_id:
            return False
        phone = self.driver_id.mobile or self.driver_id.phone or ''
        # Limpiar caracteres del teléfono
        clean_phone = "".join(filter(str.isdigit, phone))
        if not clean_phone:
            return False
        msg = self._build_whatsapp_message()
        encoded = urllib.parse.quote(msg)
        return f"https://wa.me/{clean_phone}?text={encoded}"

    def action_send_whatsapp_reminder(self):
        """Envía el aviso por WhatsApp utilizando el gateway REST o link"""
        self.ensure_one()
        if not self.driver_id:
            return {'success': False, 'message': 'No hay conductor asignado a este turno.'}

        phone = self.driver_id.mobile or self.driver_id.phone or ''
        clean_phone = "".join(filter(str.isdigit, phone))
        if not clean_phone:
            err_msg = f"El conductor {self.driver_id.name} no tiene número de teléfono registrado."
            self.write({
                'whatsapp_status': 'failed',
                'whatsapp_log': err_msg,
            })
            return {'success': False, 'message': err_msg}

        message_text = self._build_whatsapp_message()
        icp = self.env['ir.config_parameter'].sudo()
        provider = icp.get_param('transit.whatsapp_provider', default='custom_webhook')

        if provider == 'manual_wa_link':
            # Modo manual: Retorna la URL de WhatsApp Web
            wa_url = self._get_whatsapp_url()
            self.write({
                'whatsapp_sent': True,
                'whatsapp_sent_time': fields.Datetime.now(),
                'whatsapp_status': 'sent',
                'whatsapp_log': 'Enviado vía WhatsApp Web link.',
            })
            return {
                'type': 'ir.actions.act_url',
                'url': wa_url,
                'target': 'new',
                'success': True,
            }

        # Modo Gateway REST API / Webhook (Evolution API, Meta, etc.)
        api_url = icp.get_param('transit.whatsapp_api_url', default='http://localhost:8080/message/sendText')
        api_token = icp.get_param('transit.whatsapp_api_token', default='')
        instance = icp.get_param('transit.whatsapp_instance', default='transporte_bot')

        headers = {
            'Content-Type': 'application/json',
        }
        if api_token:
            headers['Authorization'] = f"Bearer {api_token}"
            headers['apikey'] = api_token

        payload = {
            'number': clean_phone,
            'text': message_text,
            'instance': instance,
            'options': {
                'delay': 1200,
                'presence': 'composing',
            }
        }

        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=8)
            if resp.status_code in [200, 201]:
                self.write({
                    'whatsapp_sent': True,
                    'whatsapp_sent_time': fields.Datetime.now(),
                    'whatsapp_status': 'sent',
                    'whatsapp_log': f"Mensaje enviado con éxito vía {provider} (HTTP {resp.status_code})",
                })
                return {'success': True, 'message': 'WhatsApp enviado correctamente.'}
            else:
                log_err = f"Error del gateway ({resp.status_code}): {resp.text}"
                self.write({
                    'whatsapp_status': 'failed',
                    'whatsapp_log': log_err,
                })
                return {'success': False, 'message': log_err}
        except Exception as e:
            log_err = f"Error de conexión con gateway WhatsApp: {str(e)}"
            self.write({
                'whatsapp_status': 'failed',
                'whatsapp_log': log_err,
            })
            return {'success': False, 'message': log_err}
