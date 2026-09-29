# -*- coding: utf-8 -*-
"""
Simulador de Trayecto y Telemetría GPS en Tiempo Real
Envía coordenadas segundo a segundo al broker para simular el recorrido completo
de una unidad (Bus 104) a lo largo de la Línea 27 (Asunción -> Capiatá).
Demuestra la detección automática de geocercas, exceso de velocidad, desvío de ruta y llegada.
"""

import time
import requests
from datetime import datetime, timezone

BROKER_URL = "http://localhost:8088/api/v1/telemetry"

WAYPOINTS = [
    # 1. Cabecera Terminal Asuncion (Salida)
    {"lat": -25.3148, "lon": -57.5932, "speed": 0.0, "odo": 154200.0, "note": "En Cabecera Terminal Asuncion"},
    {"lat": -25.3149, "lon": -57.5925, "speed": 15.0, "odo": 154200.1, "note": "Saliendo del anden"},
    {"lat": -25.3155, "lon": -57.5900, "speed": 28.0, "odo": 154200.4, "note": "Cruce de geocerca origen -> SALIDA REGISTRADA"},
    
    # 2. Tramo Eusebio Ayala hacia Multiplaza
    {"lat": -25.3160, "lon": -57.5830, "speed": 45.0, "odo": 154201.2, "note": "Circulando por Av. Eusebio Ayala"},
    {"lat": -25.3168, "lon": -57.5750, "speed": 52.0, "odo": 154202.0, "note": "Trafico fluido"},
    {"lat": -25.3175, "lon": -57.5684, "speed": 10.0, "odo": 154202.8, "note": "Geocerca Parada Multiplaza -> CHECKPOINT 1 REGISTRADO"},
    
    # 3. Tramo Fernando de la Mora hacia San Lorenzo con Alerta de Velocidad
    {"lat": -25.3230, "lon": -57.5500, "speed": 58.0, "odo": 154204.5, "note": "Acelerando en zona habilitada"},
    {"lat": -25.3310, "lon": -57.5320, "speed": 78.5, "odo": 154206.2, "note": "EXCESO DE VELOCIDAD (78.5 km/h) -> Alerta disparada"},
    {"lat": -25.3360, "lon": -57.5220, "speed": 48.0, "odo": 154207.1, "note": "Velocidad normalizada"},
    
    # 4. Parada Campus UNA (San Lorenzo)
    {"lat": -25.3412, "lon": -57.5123, "speed": 0.0, "odo": 154208.5, "note": "Geocerca Campus UNA -> CHECKPOINT 2 REGISTRADO"},
    
    # 5. Tramo hacia Capiata con Desvio de Itinerario
    {"lat": -25.3450, "lon": -57.4900, "speed": 50.0, "odo": 154210.5, "note": "En Ruta 2 rumbo a Capiata"},
    {"lat": -25.3380, "lon": -57.4800, "speed": 35.0, "odo": 154211.8, "note": "Desvio por calle lateral (a 480m) -> ALERTA DE DESVIO"},
    {"lat": -25.3480, "lon": -57.4700, "speed": 42.0, "odo": 154213.0, "note": "Retornando a la ruta oficial"},
    
    # 6. Llegada a Cabecera Destino (Capiata Km 20)
    {"lat": -25.3520, "lon": -57.4400, "speed": 45.0, "odo": 154216.0, "note": "Aproximandose a Capiata"},
    {"lat": -25.3551, "lon": -57.4215, "speed": 5.0, "odo": 154218.4, "note": "Geocerca Terminal Capiata -> LLEGADA REGISTRADA Y ODOMETRO ACTUALIZADO"},
]

def run_simulation(interval_seconds=1.0):
    print("=" * 70)
    print(">>> INICIANDO SIMULACION DE TELEMETRIA GPS EN VIVO (BUS 104)")
    print(f"--> Enviando pings al Broker: {BROKER_URL}")
    print("=" * 70)

    for i, step in enumerate(WAYPOINTS, 1):
        payload = {
            "bus_id": "104",
            "license_plate": "ABC 123",
            "latitude": step["lat"],
            "longitude": step["lon"],
            "speed_kmh": step["speed"],
            "odometer_km": step["odo"],
            "heading_deg": 90.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        headers = {
            "X-Device-Token": "GPS_DEVICE_SECRET_2026"
        }
        try:
            res = requests.post(BROKER_URL, json=payload, headers=headers, timeout=3.0)
            data = res.json()
            status_symbol = "[RUTA]" if data.get("state") == "IN_TRANSIT" else "[DESTINO]" if data.get("state") == "AT_DESTINATION" else "[ORIGEN]"
            alert_str = ""
            if data.get("speed_alert"):
                alert_str += " [ALERTA VELOCIDAD]"
            if data.get("deviation_alert"):
                alert_str += " [ALERTA DESVIO]"

            print(f"[{i:02d}/{len(WAYPOINTS):02d}] {status_symbol} Pos: ({step['lat']}, {step['lon']}) | Vel: {step['speed']} km/h | Odom: {step['odo']} km{alert_str}")
            print(f"      Estado: {data.get('state')} | Geocerca: {data.get('geofence')}")
            print(f"      Nota: {step['note']}")
            print("-" * 70)
        except Exception as e:
            print(f"Error al conectar con el Broker: {e}")

        time.sleep(interval_seconds)

    print("\n>>> SIMULACION DE TRAYECTO COMPLETADA CON EXITO.")
    print("--> Puedes verificar en Odoo en 'Despachos Diarios' que el viaje quedo 'Completado' y el Odometro sincronizado.")

if __name__ == "__main__":
    run_simulation()
