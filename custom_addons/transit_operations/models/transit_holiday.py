# -*- coding: utf-8 -*-
from datetime import datetime, date
from odoo import api, fields, models

class TransitHoliday(models.Model):
    _name = 'transit.holiday'
    _description = 'Calendario Oficial de Feriados y Régimen Operativo'
    _order = 'date desc'

    name = fields.Char(string='Descripción del Feriado', required=True)
    date = fields.Date(string='Fecha', required=True, index=True)
    active = fields.Boolean(default=True)
    is_national = fields.Boolean(string='Feriado Nacional Oficial', default=True)
    notes = fields.Text(string='Observaciones / Decreto')

    _sql_constraints = [
        ('date_unique', 'unique(date)', 'Ya existe un feriado registrado para esta fecha.')
    ]

    @api.model
    def get_day_type_info(self, target_date):
        """
        Determina el tipo de día operativo para target_date según el modelo oficial del VMT / CID:
        - 7: Domingos y Feriados oficiales (aplica cuadro de marcha de domingo)
        - 6: Sábados no feriados
        - 5: Laboral (Lunes a Viernes no feriados)

        Retorna:
            dict con:
                'tipo_dia': '5' | '6' | '7',
                'tipo_dia_int': 5 | 6 | 7,
                'es_feriado': bool,
                'feriado_desc': str o None,
                'regimen': 'Lunes a Sábado' | 'Domingos y Feriados',
                'tipo_dia_desc': 'Laboral (L-V)' | 'Sábado' | 'Domingo' | 'Feriado (...)'
        """
        if isinstance(target_date, str):
            d_obj = fields.Date.to_date(target_date[:10])
        elif isinstance(target_date, datetime):
            d_obj = target_date.date()
        else:
            d_obj = target_date

        dow = d_obj.weekday()  # 0=Lunes ... 5=Sábado, 6=Domingo
        holiday = self.search([('date', '=', d_obj), ('active', '=', True)], limit=1)
        es_feriado = bool(holiday)
        feriado_desc = holiday.name if holiday else None

        if es_feriado or dow == 6:
            tipo_dia = '7'
            regimen = 'Domingos y Feriados'
            tipo_dia_desc = f"Feriado ({feriado_desc})" if es_feriado else "Domingo"
        elif dow == 5:
            tipo_dia = '6'
            regimen = 'Lunes a Sábado'
            tipo_dia_desc = "Sábado"
        else:
            tipo_dia = '5'
            regimen = 'Lunes a Sábado'
            tipo_dia_desc = "Laboral (L-V)"

        return {
            'tipo_dia': tipo_dia,
            'tipo_dia_int': int(tipo_dia),
            'es_feriado': es_feriado,
            'feriado_desc': feriado_desc,
            'regimen': regimen,
            'tipo_dia_desc': tipo_dia_desc,
        }
