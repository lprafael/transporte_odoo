# -*- coding: utf-8 -*-
import io
import zipfile
import base64
from odoo import api, fields, models

class TransitGtfsExportWizard(models.TransientModel):
    _name = 'transit.gtfs.export.wizard'
    _description = 'Asistente de Exportación GTFS Estático (Google Transit / Moovit)'

    agency_name = fields.Char(string='Nombre de la Agencia / Autoridad', default='Viceministerio de Transporte / Poliverso Transit', required=True)
    agency_url = fields.Char(string='Sitio Web Oficial', default='https://transporte.gov.py', required=True)
    agency_timezone = fields.Char(string='Zona Horaria', default='America/Asuncion', required=True)
    agency_lang = fields.Char(string='Idioma', default='es', required=True)
    
    file_data = fields.Binary(string='Archivo GTFS (.zip)', readonly=True)
    filename = fields.Char(string='Nombre del Archivo', default='gtfs_transit_feed.zip')
    state = fields.Selection([
        ('draft', 'Configuración'),
        ('done', 'Listo para Descarga'),
    ], default='draft')

    def action_generate_gtfs(self):
        self.ensure_one()
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. agency.txt
            agency_content = "agency_id,agency_name,agency_url,agency_timezone,agency_lang\n"
            agency_content += f"AGENCY_01,\"{self.agency_name}\",{self.agency_url},{self.agency_timezone},{self.agency_lang}\n"
            zf.writestr("agency.txt", agency_content)

            # 2. routes.txt
            routes = self.env['transit.route'].search([('active', '=', True)])
            routes_content = "route_id,agency_id,route_short_name,route_long_name,route_type,route_color\n"
            for r in routes:
                code = r.code or str(r.id)
                name = r.name or 'Ramal'
                routes_content += f"{r.id},AGENCY_01,\"{code}\",\"{name}\",3,1E3A8A\n"
            zf.writestr("routes.txt", routes_content)

            # 3. stops.txt
            stops = self.env['transit.route.checkpoint'].search([])
            stops_content = "stop_id,stop_name,stop_lat,stop_lon\n"
            stop_ids_seen = set()
            for s in stops:
                if s.name and (s.latitude, s.longitude) not in stop_ids_seen:
                    stop_ids_seen.add((s.latitude, s.longitude))
                    stops_content += f"{s.id},\"{s.name}\",{s.latitude:.6f},{s.longitude:.6f}\n"
            zf.writestr("stops.txt", stops_content)

            # 4. calendar.txt
            calendar_content = "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            calendar_content += "FULL_WEEK,1,1,1,1,1,1,1,20260101,20261231\n"
            zf.writestr("calendar.txt", calendar_content)

            # 5. trips.txt
            timetables = self.env['transit.timetable'].search([('active', '=', True)])
            trips_content = "route_id,service_id,trip_id,trip_headsign\n"
            for t in timetables:
                headsign = t.route_id.destination or 'Destino'
                trips_content += f"{t.route_id.id},FULL_WEEK,TRIP_{t.id},\"{headsign}\"\n"
            zf.writestr("trips.txt", trips_content)

            # 6. stop_times.txt
            stop_times_content = "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            for t in timetables:
                hours = int(t.departure_time_float)
                minutes = int(round((t.departure_time_float - hours) * 60))
                time_str = f"{hours:02d}:{minutes:02d}:00"
                # Si la ruta tiene paradas
                seq = 1
                for cp in t.route_id.checkpoint_ids:
                    stop_times_content += f"TRIP_{t.id},{time_str},{time_str},{cp.id},{seq}\n"
                    seq += 1
            zf.writestr("stop_times.txt", stop_times_content)

        zip_data = zip_buffer.getvalue()
        zip_buffer.close()

        self.write({
            'file_data': base64.b64encode(zip_data),
            'filename': 'gtfs_transit_feed.zip',
            'state': 'done'
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'transit.gtfs.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
