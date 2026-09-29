# -*- coding: utf-8 -*-
"""
Script de Prueba: Simulación de Eventos GPS / AVL para Odoo
Envía eventos de salida, cruce de parada y llegada a Odoo.
"""
import requests
import json
from datetime import datetime, timezone

ODOO_GPS_URL = "http://localhost:8069/api/v1/transit/events"

def send_event(event_type, internal_number="104", checkpoint="Parada Central"):
    payload = {
        "internal_number": internal_number,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "checkpoint_name": checkpoint,
            "latitude": -25.2867,
            "longitude": -57.6470
        },
        "telemetry": {
            "odometer_km": 154230.5,
            "speed_kmh": 32.0
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(ODOO_GPS_URL, json=payload, headers=headers, timeout=10)
        print(f"[{event_type.upper()}] Status Code: {response.status_code}")
        print("Respuesta:", json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error conectando a Odoo ({ODOO_GPS_URL}): {e}")

if __name__ == "__main__":
    print("--- Simulación de Telemetría GPS a Odoo ---")
    send_event("departure", internal_number="104")
    send_event("checkpoint", internal_number="104", checkpoint="Av. Eusebio Ayala y Choferes")
    send_event("arrival", internal_number="104", checkpoint="Terminal San Lorenzo")
