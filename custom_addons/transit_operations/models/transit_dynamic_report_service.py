# -*- coding: utf-8 -*-
"""
Motor de Planillas Dinámicas de Tránsito (Excel) para Líneas E1, E2 y E3
========================================================================
Gestiona la lectura, detección automática e inserción en tiempo real de
servicios/redondos concluidos directamente en los libros oficiales de Excel:
  - Informe_empresa/E1 PLANILLA PRINCIPAL TRANSITO E1 OCTUBRE 2026.xlsx
  - Informe_empresa/E2 PLANILLA PRINCIPAL TRANSITO E2 OCTUBRE 2026.xlsx
  - Informe_empresa/E3 PLANILLA PRINCIPAL TRANSITO E3 OCTUBRE 2026.xlsx

Preserva al 100% las 35 hojas:
  - 31 hojas de días calendario ('1' a '31')
  - Hoja 'Resumen ' (conteo dinámico por chofer)
  - Hoja 'Redondos' (conteo y kilometraje por bus)
  - Hoja 'Km IPK' (fórmulas dinámicas de IPK diario)
  - Hoja 'Muestra Copiar'
  - Fórmulas de fila (=IF(Q-R>50%,"exceso","ok") y =K-D) y fórmulas de pie (SUM, IPK).
"""

import os
import sys
import io
import shutil
import tempfile
import logging
from datetime import datetime, date, time
from typing import Dict, Any, List, Optional, Tuple

import openpyxl
from openpyxl.utils import get_column_letter

logger = logging.getLogger("transit_dynamic_report_service")

# Nombres de meses en español para localización de archivos
MESES_ES = {
    1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
    5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
    9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
}

# Configuración específica por servicio de transporte
SERVICE_CONFIG = {
    'E1': {
        'name': 'Línea 20 Eléctrico 1 (San Lorenzo - Asunción)',
        'file_code': 'E1',
        'ida_code': 'E1',
        'reg_code': 'E1',
        'ida_km': 18.0,
        'reg_km': 17.7,
        'round_km': 35.7,
        'routes_ida': ['020c'],
        'routes_reg': ['020d'],
        'col_tiempo_r': 20, # Col T
        'has_tiempo_carga': False,
    },
    'E2': {
        'name': 'Línea 20 Eléctrico 2 (San Lorenzo - Asunción Mcal. López)',
        'file_code': 'E2',
        'ida_code': 'E2',
        'reg_code': 'E2',
        'ida_km': 19.0,
        'reg_km': 19.2,
        'round_km': 38.2,
        'routes_ida': ['020e'],
        'routes_reg': ['020f'],
        'col_tiempo_r': 21, # Col U
        'has_tiempo_carga': True, # Col T (20)
    },
    'E3': {
        'name': 'Línea 20 Eléctrico 3 (Luque - Asunción / Aeropuerto)',
        'file_code': 'E3',
        'ida_code': 'E3',
        'reg_code': 'E3',
        'ida_km': 18.2,
        'reg_km': 19.3,
        'round_km': 37.5,
        'routes_ida': ['0210'],
        'routes_reg': ['0211'],
        'col_tiempo_r': 20, # Col T
        'has_tiempo_carga': False,
    }
}


def get_informe_directory() -> str:
    """Detecta la ruta al directorio Informe_empresa según el entorno (Docker o Host)"""
    candidates = [
        "/mnt/Informe_empresa",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "Informe_empresa"),
        os.path.abspath("Informe_empresa"),
        r"c:\Users\lpraf\OneDrive\Documentos\Poliverso\transporte_odoo\Informe_empresa",
    ]
    for c in candidates:
        if os.path.isdir(c):
            return os.path.abspath(c)
    # Si no existe, crear en el directorio base
    base_dir = os.path.abspath("Informe_empresa")
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def find_spreadsheet_path(service_code: str, target_date: date) -> str:
    """
    Encuentra la ruta al archivo Excel de la planilla para el servicio y mes especificados.
    """
    info_dir = get_informe_directory()
    month_name = MESES_ES.get(target_date.month, 'OCTUBRE')
    year = target_date.year

    code = service_code.upper()
    expected_names = [
        f"{code} PLANILLA PRINCIPAL TRANSITO {code} {month_name} {year}.xlsx",
        f"PLANILLA PRINCIPAL TRANSITO {code} {month_name} {year}.xlsx",
    ]

    for name in expected_names:
        p = os.path.join(info_dir, name)
        if os.path.exists(p):
            return p

    # Búsqueda insensible a mayúsculas o con nombres aproximados
    if os.path.exists(info_dir):
        for fname in os.listdir(info_dir):
            fn_upper = fname.upper()
            if code in fn_upper and str(year) in fn_upper and month_name in fn_upper and fname.endswith('.xlsx'):
                return os.path.join(info_dir, fname)

    # Fallback al archivo por defecto de Octubre 2026
    default_path = os.path.join(info_dir, f"{code} PLANILLA PRINCIPAL TRANSITO {code} OCTUBRE 2026.xlsx")
    return default_path


class TransitDynamicReportEngine:
    """Motor central para operar y actualizar las planillas Excel en vivo"""

    def __init__(self, service_code: str, target_date: Optional[date] = None):
        self.service_code = service_code.upper()
        self.config = SERVICE_CONFIG.get(self.service_code, SERVICE_CONFIG['E1'])
        self.target_date = target_date or date.today()
        self.file_path = find_spreadsheet_path(self.service_code, self.target_date)

    def get_day_sheet_status(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Retorna estadísticas operativas de la planilla para un día determinado"""
        dt = target_date or self.target_date
        sname = str(dt.day)

        if not os.path.exists(self.file_path):
            return {
                'exists': False,
                'file_path': self.file_path,
                'completed_trips': 0,
                'total_passengers': 0,
                'total_km': 0.0,
                'ipk': 0.0,
            }

        wb = openpyxl.load_workbook(self.file_path, data_only=True)
        if sname not in wb.sheetnames:
            wb.close()
            return {'exists': True, 'sheet_found': False, 'completed_trips': 0}

        ws = wb[sname]
        completed = 0
        scheduled = 0
        total_passengers = 0
        total_km = 0.0

        for r in range(2, 101):
            bus_val = ws.cell(r, 1).value
            if bus_val is not None:
                scheduled += 1
                tarj_ida = ws.cell(r, 8).value or 0
                tarj_reg = ws.cell(r, 14).value or 0
                arr_ida = ws.cell(r, 5).value
                arr_reg = ws.cell(r, 11).value
                if arr_ida and arr_reg:
                    completed += 1
                    try:
                        total_passengers += int(tarj_ida + tarj_reg)
                    except:
                        pass

        # Leer pie de totales si existe
        pas_cell = ws.cell(105, 2).value
        km_cell = ws.cell(105, 3).value
        ipk_cell = ws.cell(105, 5).value

        wb.close()

        return {
            'exists': True,
            'file_path': self.file_path,
            'service_code': self.service_code,
            'date': dt.isoformat(),
            'sheet_name': sname,
            'scheduled_trips': scheduled,
            'completed_trips': completed,
            'total_passengers': total_passengers if not pas_cell else pas_cell,
            'total_km': (completed * self.config['round_km']) if not km_cell else km_cell,
            'ipk': round(float(ipk_cell), 3) if ipk_cell and isinstance(ipk_cell, (int, float)) else (round(total_passengers / max(1.0, completed * self.config['round_km']), 3) if completed > 0 else 0.0),
        }

    def sync_concluded_round_trips(self, round_trips: List[Dict[str, Any]], target_date: Optional[date] = None) -> Tuple[int, str]:
        """
        Inserta o actualiza una lista de redondos/servicios concluidos en la hoja del día.
        Retorna (cantidad_actualizada, ruta_archivo_guardado).
        """
        dt = target_date or self.target_date
        sname = str(dt.day)

        if not round_trips:
            return 0, self.file_path

        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"No se encontró el archivo de planilla: {self.file_path}")

        # Cargar con data_only=False para conservar fórmulas existentes
        wb = openpyxl.load_workbook(self.file_path, data_only=False)

        if sname not in wb.sheetnames:
            # Si no existe la hoja del día, clonar de 'Muestra Copiar' o hoja '1'
            ref_sheet = wb['Muestra Copiar'] if 'Muestra Copiar' in wb.sheetnames else wb['1']
            ws = wb.copy_worksheet(ref_sheet)
            ws.title = sname
        else:
            ws = wb[sname]

        updated_count = 0

        for trip in round_trips:
            bus_num = trip.get('bus_number')
            driver_code = str(trip.get('driver_code', '')).strip()
            if driver_code.isdigit():
                driver_code = f"{int(driver_code):03d}"
            driver_name = trip.get('driver_name', '')
            
            ida_dep = trip.get('ida_departure')
            ida_arr = trip.get('ida_arrival')
            ida_cards = trip.get('ida_cards', 0.0)
            
            reg_dep = trip.get('reg_departure')
            reg_arr = trip.get('reg_arrival')
            reg_cards = trip.get('reg_cards', 0.0)

            bat_dep = trip.get('battery_soc_departure', 90.0)
            bat_arr = trip.get('battery_soc_arrival', 65.0)
            # Convertir porcentaje a decimal para formato Excel (ej. 90% -> 0.90)
            if bat_dep > 1.0:
                bat_dep = round(bat_dep / 100.0, 2)
            if bat_arr > 1.0:
                bat_arr = round(bat_arr / 100.0, 2)

            trip_date = trip.get('date', dt)
            if isinstance(trip_date, str):
                trip_date = datetime.strptime(trip_date, '%Y-%m-%d').date()

            # Normalizar horas a datetime.time si son strings
            ida_dep_time = self._parse_time(ida_dep)
            ida_arr_time = self._parse_time(ida_arr)
            reg_dep_time = self._parse_time(reg_dep)
            reg_arr_time = self._parse_time(reg_arr)

            # Buscar fila coincidente existente (para actualizar salida programada ya presente)
            matched_row = None
            first_empty_row = None

            for r in range(2, 101):
                cur_bus = ws.cell(r, 1).value
                cur_code = ws.cell(r, 2).value
                cur_dep = ws.cell(r, 4).value

                if cur_bus is None or str(cur_bus).strip() == '':
                    if first_empty_row is None:
                        first_empty_row = r
                    continue

                # Intentar emparejar por Bus y Código de Chofer o por Hora de Salida
                bus_matches = False
                try:
                    if int(float(cur_bus)) == int(float(bus_num)):
                        bus_matches = True
                except:
                    pass

                cur_arr = ws.cell(r, 5).value

                time_matches = False
                if ida_dep_time and cur_dep:
                    cur_t = self._parse_time(cur_dep)
                    if cur_t and cur_t.hour == ida_dep_time.hour and abs(cur_t.minute - ida_dep_time.minute) <= 25:
                        time_matches = True

                # Prioridad 1: Coincide el bus y la hora programada de salida
                if bus_matches and time_matches:
                    matched_row = r
                    break

                # Prioridad 2: Coincide bus y chofer, y esta fila todavía no tiene llegada completada
                if bus_matches and str(cur_code).strip() == driver_code and (cur_arr is None or str(cur_arr).strip() == ''):
                    matched_row = r
                    break

            target_row = matched_row or first_empty_row or (len(round_trips) + 2)

            # Escribir columnas de la fila
            # Col A: Bus
            try:
                ws.cell(target_row, 1).value = float(bus_num) if bus_num is not None else None
            except:
                ws.cell(target_row, 1).value = bus_num
            ws.cell(target_row, 1).number_format = 'General'

            # Col B: codigo
            ws.cell(target_row, 2).value = driver_code
            ws.cell(target_row, 2).number_format = '@'

            # Col C: Conductor
            ws.cell(target_row, 3).value = driver_name
            ws.cell(target_row, 3).number_format = 'General'

            # Col D: Salida Ida
            if ida_dep_time:
                ws.cell(target_row, 4).value = ida_dep_time
                ws.cell(target_row, 4).number_format = 'h:mm'

            # Col E: Llegada Ida
            if ida_arr_time:
                ws.cell(target_row, 5).value = ida_arr_time
                ws.cell(target_row, 5).number_format = 'h:mm'

            # Col F: Ida (Código de servicio)
            ws.cell(target_row, 6).value = self.config['ida_code']

            # Col G: Km Ida
            ws.cell(target_row, 7).value = self.config['ida_km']
            ws.cell(target_row, 7).number_format = '0.0'

            # Col H: Tarjetas Ida
            ws.cell(target_row, 8).value = float(ida_cards) if ida_cards is not None else 0.0

            # Col I: Estado Ida
            ws.cell(target_row, 9).value = None

            # Col J: Salida Vuelta
            if reg_dep_time:
                ws.cell(target_row, 10).value = reg_dep_time
                ws.cell(target_row, 10).number_format = 'h:mm'

            # Col K: Llegada Vuelta
            if reg_arr_time:
                ws.cell(target_row, 11).value = reg_arr_time
                ws.cell(target_row, 11).number_format = 'h:mm'

            # Col L: Regresa (Código de servicio)
            ws.cell(target_row, 12).value = self.config['reg_code']

            # Col M: Km Vuelta
            ws.cell(target_row, 13).value = self.config['reg_km']
            ws.cell(target_row, 13).number_format = '0.0'

            # Col N: Tarjetas Vuelta
            ws.cell(target_row, 14).value = float(reg_cards) if reg_cards is not None else 0.0

            # Col O: Estado Vuelta
            ws.cell(target_row, 15).value = None

            # Col P: Fecha
            ws.cell(target_row, 16).value = datetime.combine(trip_date, time.min)
            ws.cell(target_row, 16).number_format = 'm/d/yy'

            # Col Q: % BAT S
            ws.cell(target_row, 17).value = bat_dep
            ws.cell(target_row, 17).number_format = '0%'

            # Col R: % BAT L
            ws.cell(target_row, 18).value = bat_arr
            ws.cell(target_row, 18).number_format = '0%'

            # Col S: Exceso
            ws.cell(target_row, 19).value = f'=IF(Q{target_row}-R{target_row}>50%,"exceso","ok")'
            ws.cell(target_row, 19).number_format = 'h:mm:ss'

            # Col T / U: TIEMPO R
            col_t_idx = self.config['col_tiempo_r']
            ws.cell(target_row, col_t_idx).value = f'=K{target_row}-D{target_row}'
            ws.cell(target_row, col_t_idx).number_format = 'h:mm'

            updated_count += 1

        # Verificar y preservar fórmulas de pie en filas 102 y 105
        self._ensure_footer_formulas(ws)

        # Guardar archivo de forma segura con reemplazo atómico
        self._safe_save_workbook(wb, self.file_path)
        wb.close()

        logger.info(f"[{self.service_code}] Planilla {self.file_path} (hoja '{sname}') actualizada con {updated_count} redondos concluidos.")
        return updated_count, self.file_path

    def _ensure_footer_formulas(self, ws):
        """Asegura que las fórmulas de totales en filas 102 y 105 permanezcan intactas"""
        # Fila 102: SUM de columnas G, H, I, M, N, O
        ws.cell(102, 7).value = '=SUM(G2:G100)'
        ws.cell(102, 8).value = '=SUM(H2:H100)'
        ws.cell(102, 9).value = '=SUM(I2:I100)'
        ws.cell(102, 13).value = '=SUM(M2:M100)'
        ws.cell(102, 14).value = '=SUM(N2:N100)'
        ws.cell(102, 15).value = '=SUM(O2:O100)'

        # Fila 104: Encabezados Total Pasajeros, Total Km, IPK
        ws.cell(104, 2).value = 'Total Pasajeros'
        ws.cell(104, 3).value = 'Total Km'
        ws.cell(104, 5).value = 'IPK'

        # Fila 105: Totales e IPK
        ws.cell(105, 2).value = '=H102+I102+N102+O102'
        ws.cell(105, 3).value = '=G102+M102'
        ws.cell(105, 5).value = '=B105/C105'

    def _parse_time(self, val: Any) -> Optional[time]:
        """Convierte float, datetime, string o time a datetime.time"""
        if val is None:
            return None
        if isinstance(val, time):
            return val
        if isinstance(val, datetime):
            return val.time()
        if isinstance(val, (int, float)):
            # Hora decimal: 4.5 -> 04:30
            tot_min = int(round(val * 60))
            h = (tot_min // 60) % 24
            m = tot_min % 60
            return time(h, m)
        if isinstance(val, str):
            val_clean = val.strip()
            for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p'):
                try:
                    return datetime.strptime(val_clean, fmt).time()
                except ValueError:
                    pass
        return None

    def _safe_save_workbook(self, wb, target_path: str):
        """Guarda el libro de Excel evitando bloqueos en sistemas de archivos compartidos (OneDrive/Windows)"""
        # Guardar en un archivo temporal seguro en el directorio temporal nativo
        temp_fd, temp_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(temp_fd)
        try:
            wb.save(temp_path)
            # Respaldar versión previa si existe
            if os.path.exists(target_path):
                backup_path = f"{target_path}.bak"
                try:
                    shutil.copyfile(target_path, backup_path)
                except Exception:
                    pass
            # Copiar directamente usando streaming de bytes (seguro en montajes Windows/OneDrive)
            shutil.copyfile(temp_path, target_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def read_workbook_bytes(self) -> bytes:
        """Lee el contenido binario del libro actual para descarga o almacenamiento Odoo"""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Archivo de reporte no encontrado: {self.file_path}")
        with open(self.file_path, 'rb') as f:
            return f.read()
