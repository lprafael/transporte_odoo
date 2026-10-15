# -*- coding: utf-8 -*-
"""
Planilla Unificada de Servicios de Tránsito (Redondos / Ciclos Operativos)
========================================================================
Tabla centralizada donde se registran todos los servicios redondos (Ida + Vuelta)
de las líneas E1, E2 y E3.

Permite filtrar instantáneamente por:
  - Servicio / Línea (E1, E2, E3)
  - Fecha del servicio (Hoy, Ayer, Mes, Rango de Fechas)
  - Conductor / Chofer
  - Bus / Unidad
  - Estado (Concluido, En Ruta, Programado)
  - Alerta de consumo de batería (>50%)

Muestra exactamente las mismas columnas y cálculos que las planillas Excel oficiales.
"""

import os
import logging
from datetime import datetime, date, time
import openpyxl

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Parámetros estándar por servicio
SERVICE_STANDARDS = {
    'E1': {'km_ida': 18.0, 'km_vuelta': 17.7, 'col_t': 20},
    'E2': {'km_ida': 19.0, 'km_vuelta': 19.2, 'col_t': 20},
    'E3': {'km_ida': 18.2, 'km_vuelta': 19.3, 'col_t': 20},
}


class TransitServiceRoundtrip(models.Model):
    _name = 'transit.service.roundtrip'
    _description = 'Registro Unificado de Servicios y Redondos de Tránsito'
    _inherit = ['transit.tenant.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date desc, departure_ida asc, id asc'

    name = fields.Char(string='Identificador', compute='_compute_name', store=True)

    # 1. Parámetros Principales
    date = fields.Date(
        string='Fecha del Servicio',
        required=True,
        default=fields.Date.today,
        index=True,
        tracking=True
    )
    service_id = fields.Many2one(
        'transit.service',
        string='Servicio / Línea',
        required=True,
        index=True,
        tracking=True
    )
    service_code = fields.Char(
        string='Línea',
        related='service_id.code',
        store=True,
        index=True
    )

    # 2. Asignación de Recursos (Bus y Chofer)
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Unidad / Bus',
        index=True,
        tracking=True
    )
    bus_internal_number = fields.Integer(
        string='Nº Bus',
        index=True,
        help='Número de interno del bus (Columna A en planilla)'
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Conductor Oficial',
        domain="[('is_driver', '=', True)]",
        index=True,
        tracking=True
    )
    driver_code = fields.Char(
        string='Código Chofer (@)',
        index=True,
        help='Código único del conductor (Columna B en planilla)'
    )
    driver_name = fields.Char(
        string='Nombre Chofer',
        help='Nombre completo del chofer (Columna C en planilla)'
    )

    # 3. Tramo de Ida
    departure_ida = fields.Char(
        string='Salida Ida',
        size=10,
        help='Hora de salida desde la cabecera inicial (Columna D)'
    )
    arrival_ida = fields.Char(
        string='Llegada Ida',
        size=10,
        help='Hora estimada o real de llegada del tramo de ida'
    )
    km_ida = fields.Float(
        string='Km Ida',
        digits=(6, 2),
        default=18.0,
        help='Distancia recorrida en la ida (Columna F)'
    )
    passengers_ida = fields.Integer(
        string='Pasajeros Ida',
        default=0,
        help='Total pasajeros transportados en la ida (Columna G)'
    )
    validations_ida = fields.Integer(
        string='Tarjetas Ida',
        default=0,
        help='Validaciones electrónicas con tarjeta en la ida (Columna H)'
    )
    cash_ida = fields.Integer(
        string='Efectivo Ida',
        default=0,
        help='Boletos manuales / efectivo en la ida (Columna I)'
    )

    # 4. Tramo de Vuelta / Retorno
    departure_vuelta = fields.Char(
        string='Retorno Vuelta',
        size=10,
        help='Hora de salida del tramo de retorno (Columna J)'
    )
    arrival_vuelta = fields.Char(
        string='Llegada Vuelta',
        size=10,
        help='Hora de culminación del viaje redondo (Columna K)'
    )
    km_vuelta = fields.Float(
        string='Km Vuelta',
        digits=(6, 2),
        default=17.7,
        help='Distancia recorrida en la vuelta (Columna L)'
    )
    passengers_vuelta = fields.Integer(
        string='Pasajeros Vuelta',
        default=0,
        help='Total pasajeros transportados en el regreso (Columna M)'
    )
    validations_vuelta = fields.Integer(
        string='Tarjetas Vuelta',
        default=0,
        help='Validaciones electrónicas con tarjeta en la vuelta (Columna N)'
    )
    cash_vuelta = fields.Integer(
        string='Efectivo Vuelta',
        default=0,
        help='Boletos manuales / efectivo en la vuelta (Columna O)'
    )

    # 5. Métricas Totales del Redondo (Cálculos automáticos)
    total_km = fields.Float(
        string='Km Total Redondo',
        compute='_compute_totals',
        store=True,
        digits=(6, 2),
        help='Suma de Km Ida + Km Vuelta'
    )
    total_passengers = fields.Integer(
        string='Total Pasajeros',
        compute='_compute_totals',
        store=True,
        help='Suma de Pasajeros Ida + Pasajeros Vuelta'
    )
    total_validations = fields.Integer(
        string='Total Tarjetas',
        compute='_compute_totals',
        store=True,
        help='Suma de Validaciones Tarjeta Ida + Vuelta'
    )
    ipk_round = fields.Float(
        string='IPK del Viaje',
        compute='_compute_totals',
        store=True,
        digits=(6, 3),
        help='Pasajeros por Kilómetro del ciclo redondo (Total Pasajeros / Total Km)'
    )

    # 6. Eficiencia Energética (Batería y Consumo)
    battery_soc_start = fields.Float(
        string='SoC Salida (%)',
        default=90.0,
        digits=(5, 1),
        help='Nivel de batería al iniciar el servicio (Columna Q)'
    )
    battery_soc_end = fields.Float(
        string='SoC Llegada (%)',
        default=65.0,
        digits=(5, 1),
        help='Nivel de batería al culminar el redondo (Columna R)'
    )
    battery_consumption = fields.Float(
        string='Consumo Batería (%)',
        compute='_compute_battery',
        store=True,
        digits=(5, 1),
        help='Porcentaje consumido en el redondo: SoC Salida - SoC Llegada'
    )
    excess_consumption = fields.Selection([
        ('ok', 'OK'),
        ('exceso', 'Exceso (>50%)'),
    ], string='Alerta Batería', compute='_compute_battery', store=True,
       help='Alerta si el consumo supera el 50% (Columna S en planilla)')

    # 7. Tiempo de Viaje Redondo
    duration_str = fields.Char(
        string='Tiempo Redondo',
        compute='_compute_duration',
        store=True,
        help='Tiempo total de viaje en formato hh:mm (Columna T: =K-D)'
    )
    duration_hours = fields.Float(
        string='Duración (Horas)',
        compute='_compute_duration',
        store=True,
        digits=(5, 2)
    )

    # 8. Estado y Trazabilidad Operativa
    state = fields.Selection([
        ('scheduled', 'Programado'),
        ('in_transit', 'En Ruta'),
        ('completed', 'Concluido'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='completed', index=True, tracking=True)

    dispatch_ida_id = fields.Many2one('transit.dispatch', string='Despacho Ida')
    dispatch_vuelta_id = fields.Many2one('transit.dispatch', string='Despacho Vuelta')
    excel_row = fields.Integer(string='Fila en Planilla Excel')
    source = fields.Selection([
        ('excel_sync', 'Sincronizado de Excel'),
        ('odoo_dispatch', 'Despacho Odoo'),
        ('manual', 'Registro Manual')
    ], string='Origen', default='excel_sync')

    @api.depends('service_code', 'bus_internal_number', 'date', 'departure_ida')
    def _compute_name(self):
        for rec in self:
            code = rec.service_code or 'SRV'
            bus = rec.bus_internal_number or 0
            d = rec.date or fields.Date.today()
            dep = rec.departure_ida or '--:--'
            rec.name = f"[{code}] Bus {bus} | {d} {dep}"

    @api.depends('km_ida', 'km_vuelta', 'passengers_ida', 'passengers_vuelta', 'validations_ida', 'validations_vuelta')
    def _compute_totals(self):
        for rec in self:
            rec.total_km = round((rec.km_ida or 0.0) + (rec.km_vuelta or 0.0), 2)
            rec.total_passengers = (rec.passengers_ida or 0) + (rec.passengers_vuelta or 0)
            rec.total_validations = (rec.validations_ida or 0) + (rec.validations_vuelta or 0)
            if rec.total_km > 0.0:
                rec.ipk_round = round(rec.total_passengers / rec.total_km, 3)
            else:
                rec.ipk_round = 0.0

    @api.depends('battery_soc_start', 'battery_soc_end')
    def _compute_battery(self):
        for rec in self:
            start = rec.battery_soc_start or 0.0
            end = rec.battery_soc_end or 0.0
            consumption = start - end
            rec.battery_consumption = round(consumption, 1)
            rec.excess_consumption = 'exceso' if consumption > 50.0 else 'ok'

    @api.depends('departure_ida', 'arrival_vuelta')
    def _compute_duration(self):
        for rec in self:
            dep_str = rec.departure_ida
            arr_str = rec.arrival_vuelta
            if not dep_str or not arr_str:
                rec.duration_str = False
                rec.duration_hours = 0.0
                continue
            try:
                # Parse "HH:MM"
                dep_parts = [int(p) for p in dep_str.strip().split(':')[:2]]
                arr_parts = [int(p) for p in arr_str.strip().split(':')[:2]]
                dep_min = dep_parts[0] * 60 + dep_parts[1]
                arr_min = arr_parts[0] * 60 + arr_parts[1]

                diff_min = arr_min - dep_min
                if diff_min < 0:
                    diff_min += 24 * 60  # Pasa medianoche

                h = diff_min // 60
                m = diff_min % 60
                rec.duration_str = f"{h:02d}:{m:02d}"
                rec.duration_hours = round(diff_min / 60.0, 2)
            except Exception:
                rec.duration_str = False
                rec.duration_hours = 0.0

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id and self.service_id.code in SERVICE_STANDARDS:
            cfg = SERVICE_STANDARDS[self.service_id.code]
            self.km_ida = cfg['km_ida']
            self.km_vuelta = cfg['km_vuelta']

    @api.onchange('driver_id')
    def _onchange_driver_id(self):
        if self.driver_id:
            self.driver_code = self.driver_id.driver_code or ''
            self.driver_name = self.driver_id.name or ''

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and hasattr(self.vehicle_id, 'bus_internal_number'):
            try:
                self.bus_internal_number = int(self.vehicle_id.bus_internal_number)
            except (ValueError, TypeError):
                pass

    @api.model
    def sync_from_excel_files(self, target_date=None):
        """
        Lee los libros de Excel oficiales de E1, E2 y E3 en Informe_empresa/
        e importa/sincroniza en esta tabla todos los viajes redondos concluidos
        para la fecha indicada (por defecto el día actual o todo el mes).
        """
        from .transit_dynamic_report_service import get_informe_directory, find_spreadsheet_path, MESES_ES

        eval_date = target_date or fields.Date.today()
        day_str = str(eval_date.day)

        services = self.env['transit.service'].search([('code', 'in', ['E1', 'E2', 'E3'])])
        service_map = {s.code: s for s in services}
        created_or_updated = 0

        for code, svc in service_map.items():
            try:
                excel_path = find_spreadsheet_path(code, eval_date)
            except Exception as e:
                _logger.warning(f"No se encontró libro Excel para {code}: {e}")
                continue

            if not os.path.exists(excel_path):
                continue

            try:
                wb = openpyxl.load_workbook(excel_path, data_only=True)
            except Exception as e:
                _logger.error(f"Error abriendo Excel {excel_path}: {e}")
                continue

            if day_str not in wb.sheetnames:
                wb.close()
                continue

            ws = wb[day_str]
            std_cfg = SERVICE_STANDARDS.get(code, SERVICE_STANDARDS['E1'])
            cnt = self._sync_worksheet_rows(ws, eval_date, svc, std_cfg)
            wb.close()
            created_or_updated += cnt

        _logger.info(f"Sincronizados {created_or_updated} redondos en transit.service.roundtrip para {eval_date}")
        return created_or_updated

    def _sync_worksheet_rows(self, ws, eval_date, svc, std_cfg, driver_by_code=None, driver_by_name=None, vehicle_by_bus=None):
        """Lee y sincroniza las filas de una hoja de día"""
        created_or_updated = 0

        def _fmt_time(val):
            if isinstance(val, time):
                return val.strftime('%H:%M')
            if isinstance(val, str) and ':' in val:
                return val.strip()
            if isinstance(val, (int, float)):
                total_m = int(round(val * 24 * 60))
                return f"{(total_m // 60) % 24:02d}:{total_m % 60:02d}"
            return None

        def _safe_float(val, default):
            if val is None or val == '':
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def _safe_int(val, default=0):
            if val is None or val == '':
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def _fmt_pct(val, default):
            if val is None or val == '':
                return default
            try:
                f = float(val)
                return f * 100.0 if f <= 1.0 else f
            except (ValueError, TypeError):
                return default

        for row_idx in range(2, 101):
            bus_val = ws.cell(row_idx, 1).value
            if not bus_val:
                continue

            try:
                bus_num = int(bus_val)
            except (ValueError, TypeError):
                continue

            driver_code = str(ws.cell(row_idx, 2).value or '').strip()
            driver_name = str(ws.cell(row_idx, 3).value or '').strip()

            dep_ida = _fmt_time(ws.cell(row_idx, 4).value)
            if not dep_ida:
                continue
            arr_ida = _fmt_time(ws.cell(row_idx, 5).value)

            km_ida = _safe_float(ws.cell(row_idx, 7).value, std_cfg['km_ida'])
            tarj_ida = _safe_int(ws.cell(row_idx, 8).value)
            cash_ida = _safe_int(ws.cell(row_idx, 9).value)
            pas_ida = tarj_ida + cash_ida

            dep_vuelta = _fmt_time(ws.cell(row_idx, 10).value)
            arr_vuelta = _fmt_time(ws.cell(row_idx, 11).value)
            km_vuelta = _safe_float(ws.cell(row_idx, 13).value, std_cfg['km_vuelta'])
            tarj_vuelta = _safe_int(ws.cell(row_idx, 14).value)
            cash_vuelta = _safe_int(ws.cell(row_idx, 15).value)
            pas_vuelta = tarj_vuelta + cash_vuelta

            soc_start = _fmt_pct(ws.cell(row_idx, 17).value, 90.0)
            soc_end = _fmt_pct(ws.cell(row_idx, 18).value, 65.0)
            state = 'completed' if arr_vuelta else ('in_transit' if dep_ida else 'scheduled')

            driver = None
            if driver_by_code and driver_code in driver_by_code:
                driver = driver_by_code[driver_code]
            elif driver_by_name and driver_name.lower() in driver_by_name:
                driver = driver_by_name[driver_name.lower()]
            else:
                driver = self.env['res.partner'].search([
                    ('is_driver', '=', True),
                    '|',
                    ('driver_code', '=', driver_code),
                    ('name', 'ilike', driver_name)
                ], limit=1)

            vehicle = None
            if vehicle_by_bus and str(bus_num) in vehicle_by_bus:
                vehicle = vehicle_by_bus[str(bus_num)]
            else:
                vehicle = self.env['fleet.vehicle'].search([
                    ('bus_internal_number', '=', str(bus_num))
                ], limit=1)

            existing = self.search([
                ('date', '=', eval_date),
                ('service_id', '=', svc.id),
                ('bus_internal_number', '=', bus_num),
                ('departure_ida', '=', dep_ida),
            ], limit=1)

            vals = {
                'date': eval_date,
                'service_id': svc.id,
                'bus_internal_number': bus_num,
                'vehicle_id': vehicle.id if vehicle else False,
                'driver_id': driver.id if driver else False,
                'driver_code': driver_code,
                'driver_name': driver_name or (driver.name if driver else ''),
                'departure_ida': dep_ida,
                'arrival_ida': arr_ida,
                'km_ida': km_ida,
                'passengers_ida': pas_ida,
                'validations_ida': tarj_ida,
                'cash_ida': cash_ida,
                'departure_vuelta': dep_vuelta,
                'arrival_vuelta': arr_vuelta,
                'km_vuelta': km_vuelta,
                'passengers_vuelta': pas_vuelta,
                'validations_vuelta': tarj_vuelta,
                'cash_vuelta': cash_vuelta,
                'battery_soc_start': soc_start,
                'battery_soc_end': soc_end,
                'state': state,
                'excel_row': row_idx,
                'source': 'excel_sync',
            }

            if existing:
                existing.write(vals)
            else:
                self.create(vals)
            created_or_updated += 1

        return created_or_updated

    def action_sync_today(self):
        """Acción desde botón de interfaz para sincronizar servicios del día"""
        cnt = self.sync_from_excel_files(fields.Date.today())
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización Completada'),
                'message': _(f'Se sincronizaron con éxito {cnt} redondos de tránsito.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def sync_month_from_excel(self, year=None, month=None):
        """
        Sincroniza todos los días del mes indicado desde los libros Excel oficiales,
        abriendo cada archivo solo una vez para máxima velocidad.
        """
        from .transit_dynamic_report_service import find_spreadsheet_path
        today = fields.Date.today()
        y = year or today.year
        m = month or today.month

        services = self.env['transit.service'].search([('code', 'in', ['E1', 'E2', 'E3'])])
        service_map = {s.code: s for s in services}
        total_synced = 0

        # Caches en memoria para acelerar búsquedas
        all_drivers = self.env['res.partner'].search([('is_driver', '=', True)])
        driver_by_code = {d.driver_code: d for d in all_drivers if d.driver_code}
        driver_by_name = {d.name.lower(): d for d in all_drivers if d.name}

        all_vehicles = self.env['fleet.vehicle'].search([])
        vehicle_by_bus = {getattr(v, 'bus_internal_number', ''): v for v in all_vehicles}

        for code, svc in service_map.items():
            sample_date = date(y, m, 1)
            try:
                excel_path = find_spreadsheet_path(code, sample_date)
            except Exception as e:
                _logger.warning(f"No se encontró libro Excel para {code}: {e}")
                continue

            if not os.path.exists(excel_path):
                continue

            try:
                wb = openpyxl.load_workbook(excel_path, data_only=True)
            except Exception as e:
                _logger.error(f"Error abriendo Excel {excel_path}: {e}")
                continue

            std_cfg = SERVICE_STANDARDS.get(code, SERVICE_STANDARDS['E1'])

            for sname in wb.sheetnames:
                if not sname.isdigit():
                    continue
                day_num = int(sname)
                if day_num < 1 or day_num > 31:
                    continue
                try:
                    cur_date = date(y, m, day_num)
                except ValueError:
                    continue

                ws = wb[sname]
                cnt = self._sync_worksheet_rows(ws, cur_date, svc, std_cfg, driver_by_code, driver_by_name, vehicle_by_bus)
                total_synced += cnt

            wb.close()

        _logger.info(f"Sincronización mensual completada: {total_synced} redondos para {m}/{y}")
        return total_synced

    def action_sync_current_month(self):
        """Acción de interfaz para sincronizar todo el mes actual desde Excel"""
        cnt = self.sync_month_from_excel()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización Mensual Completada'),
                'message': _(f'Se sincronizaron con éxito {cnt} redondos para el mes.'),
                'type': 'success',
                'sticky': False,
            }
        }
