# -*- coding: utf-8 -*-
"""
Script para Cargar Datos de Demostración Iniciales en Odoo 18
Crea buses, conductores, rutas, horarios y un despacho activo para pruebas.
"""
import urllib.request
import json
from datetime import datetime, date, time

ODOO_URL = "http://localhost:8069/jsonrpc"
DB_NAME = "flota_db"
USER = "admin"
PASS = "admin"

def rpc_call(service, method, args):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": service,
            "method": method,
            "args": args
        },
        "id": 1
    }
    req = urllib.request.Request(
        ODOO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if res.get("error"):
            raise Exception(res["error"])
        return res.get("result")

def main():
    print("=== Conectando con Odoo 18 en", ODOO_URL, "===")
    uid = rpc_call("common", "login", [DB_NAME, USER, PASS])
    print("Autenticado con éxito. UID:", uid)

    def execute(model, method, *args, **kwargs):
        return rpc_call("object", "execute_kw", [DB_NAME, uid, PASS, model, method, list(args), kwargs])

    # 1. Crear Modelo de Vehículo si no existe
    models = execute("fleet.vehicle.model", "search_read", [[["name", "=", "OF-1722 / Marcopolo"]]], {"fields": ["id"]})
    if not models:
        # Crear Marca
        brands = execute("fleet.vehicle.model.brand", "search_read", [[["name", "=", "Mercedes-Benz"]]], {"fields": ["id"]})
        brand_id = brands[0]["id"] if brands else execute("fleet.vehicle.model.brand", "create", [{"name": "Mercedes-Benz"}])
        model_id = execute("fleet.vehicle.model", "create", [{
            "name": "OF-1722 / Marcopolo",
            "brand_id": brand_id,
            "vehicle_type": "car"
        }])
    else:
        model_id = models[0]["id"]

    # 2. Crear Buses
    bus104 = execute("fleet.vehicle", "search_read", [[["bus_internal_number", "=", "104"]]], {"fields": ["id"]})
    if not bus104:
        bus104_id = execute("fleet.vehicle", "create", [{
            "model_id": model_id,
            "license_plate": "ABC 123",
            "bus_internal_number": "104",
            "seating_capacity": 45,
            "standing_capacity": 20,
            "has_air_conditioning": True,
            "has_wheelchair_ramp": True,
            "validator_terminal_id": "VAL-PY-0104",
            "itv_expiry_date": "2027-06-30",
            "insurance_policy": "MAPFRE-POL-98421",
            "insurance_expiry_date": "2027-12-31"
        }])
        # Odómetro inicial
        execute("fleet.vehicle.odometer", "create", [{
            "vehicle_id": bus104_id,
            "value": 154200.0,
            "date": str(date.today())
        }])
        print("Bus Coche 104 creado. ID:", bus104_id)
    else:
        bus104_id = bus104[0]["id"]
        print("Bus Coche 104 ya existe. ID:", bus104_id)

    # 3. Crear Chofer
    chofer = execute("res.partner", "search_read", [[["name", "=", "Juan Carlos Benítez"]]], {"fields": ["id"]})
    if not chofer:
        chofer_id = execute("res.partner", "create", [{
            "name": "Juan Carlos Benítez",
            "is_driver": True,
            "driver_license_number": "LIC-PROF-89410",
            "driver_license_category": "prof_b",
            "driver_license_expiry": "2028-05-15",
            "vat_ruc": "3456789",
            "vat_dv": "1",
            "sifen_doc_type": "1"
        }])
        print("Chofer Juan Carlos Benítez creado. ID:", chofer_id)
    else:
        chofer_id = chofer[0]["id"]

    # 4. Crear Ruta
    ruta = execute("transit.route", "search_read", [[["code", "=", "L27-IDA"]]], {"fields": ["id"]})
    if not ruta:
        ruta_id = execute("transit.route", "create", [{
            "name": "Línea 27 - Asunción a Capiatá",
            "code": "L27-IDA",
            "direction": "inbound",
            "origin": "Terminal Asunción (Cabecera)",
            "destination": "Capiatá Km 20 (Cabecera)",
            "distance_km": 28.5,
            "standard_duration_minutes": 65,
            "standard_fare": 3400.0
        }])
        print("Ruta Línea 27 (Ida) creada. ID:", ruta_id)
    else:
        ruta_id = ruta[0]["id"]

    # 5. Crear Horario / Cuadro de Marcha
    horario = execute("transit.timetable", "search_read", [[["route_id", "=", ruta_id], ["service_code", "=", "S01"]]], {"fields": ["id"]})
    if not horario:
        horario_id = execute("transit.timetable", "create", [{
            "route_id": ruta_id,
            "service_code": "S01",
            "departure_time_float": 7.0,  # 07:00 AM
            "scheduled_duration_minutes": 65,
            "day_of_week": "all"
        }])
        print("Horario 07:00 (S01) creado. ID:", horario_id)
    else:
        horario_id = horario[0]["id"]

    # 6. Crear Despacho Diario para Hoy
    today_str = str(date.today())
    now_dt = datetime.now()
    scheduled_dep = datetime.combine(date.today(), time(7, 0)).strftime("%Y-%m-%d %H:%M:%S")

    despacho = execute("transit.dispatch", "search_read", [[["date", "=", today_str], ["vehicle_id", "=", bus104_id]]], {"fields": ["id", "name"]})
    if not despacho:
        despacho_id = execute("transit.dispatch", "create", [{
            "date": today_str,
            "timetable_id": horario_id,
            "vehicle_id": bus104_id,
            "driver_id": chofer_id,
            "scheduled_departure": scheduled_dep,
            "initial_odometer": 154200.0,
            "check_tires": True,
            "check_brakes": True,
            "check_lights": True,
            "check_fluids": True,
            "check_validator": True
        }])
        # Aprobar inspección previa
        execute("transit.dispatch", "action_inspect", [despacho_id])
        print("Despacho Diario para hoy creado e inspeccionado. ID:", despacho_id)
    else:
        print("Despacho para hoy ya existe:", despacho[0])

    print("\n Datos de demostración listos en Odoo 18!")

if __name__ == "__main__":
    main()
