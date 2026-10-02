# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class TransitTicket(models.Model):
    _name = 'transit.ticket'
    _description = 'Boleto / Pasaje de Viaje'
    _order = 'id desc'

    name = fields.Char(string='Número de Boleto', required=True, copy=False, readonly=True, default='Nuevo')
    dispatch_id = fields.Many2one('transit.dispatch', string='Despacho / Viaje', required=True, ondelete='cascade')
    concessionaire_id = fields.Many2one(
        'transit.concessionaire',
        related='dispatch_id.concessionaire_id',
        store=True,
        string='Empresa Concesionaria',
        index=True
    )
    route_id = fields.Many2one('transit.route', string='Ruta', related='dispatch_id.route_id', store=True, readonly=True)
    date = fields.Datetime(string='Fecha y Hora', default=fields.Datetime.now, required=True)

    passenger_id = fields.Many2one('res.partner', string='Pasajero Registrado')
    passenger_name = fields.Char(string='Nombre del Pasajero', default='Consumidor Final')
    passenger_doc = fields.Char(string='Nº C.I. / RUC', default='0')
    seat_number = fields.Char(string='Asiento')

    price = fields.Float(string='Precio del Pasaje (Gs.)', required=True, default=3400.0)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Emitido'),
        ('invoiced', 'Facturado Electrónicamente'),
        ('canceled', 'Anulado'),
    ], string='Estado', default='confirmed')

    invoice_id = fields.Many2one('account.move', string='Factura Electrónica SIFEN', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('transit.ticket') or 'BOL-AUTO'
        return super(TransitTicket, self).create(vals_list)

    @api.onchange('dispatch_id')
    def _onchange_dispatch_id(self):
        if self.dispatch_id and self.dispatch_id.route_id:
            self.price = self.dispatch_id.route_id.standard_fare

    @api.onchange('passenger_id')
    def _onchange_passenger_id(self):
        if self.passenger_id:
            self.passenger_name = self.passenger_id.name
            self.passenger_doc = self.passenger_id.vat_ruc or self.passenger_id.vat or '0'

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_create_electronic_invoice(self):
        """Genera la Factura Electrónica legal para este boleto"""
        self.ensure_one()
        if self.invoice_id:
            raise UserError("Este pasaje ya tiene una factura electrónica generada.")

        # Obtener o crear el cliente en Odoo
        partner = self.passenger_id
        if not partner:
            partner = self.env['res.partner'].search([
                ('name', '=', self.passenger_name)
            ], limit=1)
            if not partner:
                partner = self.env['res.partner'].create({
                    'name': self.passenger_name,
                    'vat_ruc': self.passenger_doc,
                    'vat': self.passenger_doc,
                    'sifen_doc_type': '1' if self.passenger_doc != '0' else '4',
                })

        # Asegurar cuenta de cliente (Cuentas por Cobrar)
        if not partner.property_account_receivable_id:
            rec_account = self.env['account.account'].search([('account_type', '=', 'asset_receivable')], limit=1)
            if not rec_account:
                rec_account = self.env['account.account'].create({
                    'name': 'Clientes por Pasajes a Cobrar',
                    'code': '1.1.02.01',
                    'account_type': 'asset_receivable',
                    'reconcile': True,
                })
            partner.property_account_receivable_id = rec_account.id

        # Buscar o crear cuenta de ingresos de pasajes
        income_account = self.env['account.account'].search([('account_type', '=', 'income')], limit=1)
        if not income_account:
            income_account = self.env['account.account'].create({
                'name': 'Ingresos por Venta de Pasajes',
                'code': '4.1.01.01',
                'account_type': 'income',
            })

        # Crear factura en account.move
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.context_today(self),
            'sifen_tipo_documento': '1',  # Factura Electrónica
            'invoice_line_ids': [(0, 0, {
                'name': f"Pasaje en {self.route_id.name} - Boleto {self.name}",
                'quantity': 1,
                'price_unit': self.price,
                'account_id': income_account.id,
            })],
        }
        invoice = self.env['account.move'].create(invoice_vals)
        self.write({
            'invoice_id': invoice.id,
            'state': 'invoiced',
        })

        # Devolver acción para abrir la factura recién creada
        return {
            'name': 'Factura Electrónica de Pasaje',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'type': 'ir.actions.act_window',
        }

    def action_create_consolidated_invoice(self):
        """
        Genera una Factura Electrónica Mensual Consolidada para el lote de boletos seleccionados.
        Diseñado para transporte público donde se emite una factura global de alto valor por período/mes
        en lugar de micro-facturas por cada pasajero individual.
        """
        if not self:
            raise UserError("Debe seleccionar al menos un boleto para facturar.")

        tickets_to_invoice = self.filtered(lambda t: t.state == 'confirmed' and not t.invoice_id)
        if not tickets_to_invoice:
            raise UserError("Todos los boletos seleccionados ya se encuentran facturados o están en estado borrador/cancelado.")

        total_amount = sum(tickets_to_invoice.mapped('price'))
        ticket_count = len(tickets_to_invoice)
        dates = tickets_to_invoice.mapped('date')
        min_date = min(dates)
        max_date = max(dates)
        period_str = min_date.strftime('%m/%Y') if min_date.strftime('%m/%Y') == max_date.strftime('%m/%Y') else f"{min_date.strftime('%d/%m/%Y')} al {max_date.strftime('%d/%m/%Y')}"

        # Partner genérico para facturación global / Consumidor Final
        partner = self.env['res.partner'].search([('name', '=', 'Consumidor Final (Recaudación Mensual Consolidada)')], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': 'Consumidor Final (Recaudación Mensual Consolidada)',
                'vat_ruc': '44444401-7',
                'vat': '44444401-7',
                'sifen_doc_type': '4',  # Consumidor Final / Innominado
            })

        # Cuenta de cliente
        if not partner.property_account_receivable_id:
            rec_account = self.env['account.account'].search([('account_type', '=', 'asset_receivable')], limit=1)
            if not rec_account:
                rec_account = self.env['account.account'].create({
                    'name': 'Clientes por Pasajes a Cobrar',
                    'code': '1.1.02.01',
                    'account_type': 'asset_receivable',
                    'reconcile': True,
                })
            partner.property_account_receivable_id = rec_account.id

        # Cuenta de ingresos
        income_account = self.env['account.account'].search([('account_type', '=', 'income')], limit=1)
        if not income_account:
            income_account = self.env['account.account'].create({
                'name': 'Ingresos por Venta de Pasajes',
                'code': '4.1.01.01',
                'account_type': 'income',
            })

        # Crear líneas de factura agrupadas por ramal/ruta para prolijidad contable
        invoice_lines = []
        routes = tickets_to_invoice.mapped('route_id')
        for route in routes:
            route_tickets = tickets_to_invoice.filtered(lambda t: t.route_id == route)
            route_total = sum(route_tickets.mapped('price'))
            route_qty = len(route_tickets)
            invoice_lines.append((0, 0, {
                'name': f"Recaudación Consolidada de Pasajes - {route.name or 'Línea 20'} (Período {period_str}) - {route_qty} pasajes",
                'quantity': 1,
                'price_unit': route_total,
                'account_id': income_account.id,
            }))

        if not invoice_lines:
            invoice_lines.append((0, 0, {
                'name': f"Recaudación Mensual Consolidada de Pasajes (Período {period_str}) - {ticket_count} pasajes",
                'quantity': 1,
                'price_unit': total_amount,
                'account_id': income_account.id,
            }))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.context_today(self),
            'sifen_tipo_documento': '1',  # Factura Electrónica SIFEN
            'invoice_line_ids': invoice_lines,
        }
        invoice = self.env['account.move'].create(invoice_vals)

        # Vincular todos los boletos a la factura mensual y actualizar su estado
        tickets_to_invoice.write({
            'invoice_id': invoice.id,
            'state': 'invoiced',
        })

        return {
            'name': 'Factura Electrónica Mensual Consolidada',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'type': 'ir.actions.act_window',
        }
