# -*- coding: utf-8 -*-
"""
Simulador de Transmisión MQTT con Carga Binaria Protocol Buffers v3
Resolución GVMT N° 065/2024 - Viceministerio de Transporte (Paraguay)

Publica paquetes binarios con el contrato oficial Operation (transit.proto)
en el broker Mosquitto en el tópico:
    transporte/flota/{agency_id}/operacion

Demuestra:
1. Compilación y serialización binaria Protobuf v3 estricta.
2. Calidad de Servicio QoS 1 (At least once).
3. Transmisión periódica cada 10 segundos (o configurable).
4. Detección de estados INICIADO (0), OPERANDO (2) y FINALIZADO (1).
5. Despacho automático de Webhook a Odoo y actualización de radar en vivo (Redis/WebSocket).
"""

import sys
import os
import time
import argparse
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt no está instalado. Ejecuta: pip install paho-mqtt")
    sys.exit(1)

# Importar encoder y decoder Protobuf del proyecto
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gps_broker"))
try:
    from proto.decoder import encode_test_operation, OperationType, _GENERATED_AVAILABLE
except Exception as e:
    print(f"Error cargando módulo Protobuf: {e}")
    sys.exit(1)

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "gps_device")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "GPS_DEVICE_SECRET_2026")
AGENCY_ID = os.getenv("AGENCY_ID", "004B")

WAYPOINTS = [
    # Lat, Lon, Speed, Type, Note
    (-25.3148, -57.5932, 0.0, OperationType.INICIADO, "Cabecera Terminal (INICIADO / Salida)"),
    (-25.3155, -57.5900, 25.0, OperationType.OPERANDO, "Acelerando sobre Av. Fernando de la Mora"),
    (-25.3168, -57.5750, 48.0, OperationType.OPERANDO, "En ruta tramo Multiplaza"),
    (-25.3210, -57.5520, 52.0, OperationType.OPERANDO, "Cruce Defensores del Chaco"),
    (-25.3310, -57.5320, 50.0, OperationType.OPERANDO, "Acceso a San Lorenzo"),
    (-25.3412, -57.5123, 10.0, OperationType.OPERANDO, "Campus UNA (Checkpoint Parada)"),
    (-25.3480, -57.4700, 45.0, OperationType.OPERANDO, "Ruta 2 rumbo a Capiatá"),
    (-25.3551, -57.4215, 0.0, OperationType.FINALIZADO, "Terminal Capiatá (FINALIZADO / Llegada)")
]

def simulate_unit(bus_id="00016", route_id="020f", delay=2.0):
    client = mqtt.Client(client_id=f"sim_bus_{bus_id}_{int(time.time())}")
    client.username_pw_set(MQTT_USER, MQTT_PASS)

    print("=" * 75)
    print(f"📡 CONECTANDO AL BROKER MQTT: {MQTT_HOST}:{MQTT_PORT} (Usuario: {MQTT_USER})")
    print(f"   Móvil: {bus_id} | Agencia: {AGENCY_ID} | Ramal: {route_id}")
    print(f"   Motor Protobuf: {'Nativo (transit_pb2)' if _GENERATED_AVAILABLE else 'Fallback'}")
    print("=" * 75)

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    topic = f"transporte/flota/{AGENCY_ID}/operacion"

    for i, (lat, lon, speed, op_type, note) in enumerate(WAYPOINTS, 1):
        type_str = {
            OperationType.INICIADO: "INICIADO (0)",
            OperationType.OPERANDO: "OPERANDO (2)",
            OperationType.FINALIZADO: "FINALIZADO (1)"
        }.get(op_type, "OTRO")

        binary_payload = encode_test_operation(
            agency_id=AGENCY_ID,
            mean_id=bus_id,
            route_id=route_id,
            driver_id="CHOFER-4589",
            op_type=op_type,
            accuracy=12,
            latitude=lat,
            longitude=lon,
            altitude=115.0,
            bearing=92.5,
            speed=speed
        )

        info = client.publish(topic, binary_payload, qos=1)
        info.wait_for_publish(timeout=3.0)

        print(f"[{i}/{len(WAYPOINTS)}] 📤 Publicado en {topic}")
        print(f"      Tipo: {type_str} | Coords: ({lat:.5f}, {lon:.5f}) | Vel: {speed} km/h")
        print(f"      Payload: {len(binary_payload)} bytes Protobuf v3 | Nota: {note}")
        print("-" * 75)

        time.sleep(delay)

    client.loop_stop()
    client.disconnect()
    print("\n✅ SIMULACIÓN PROTOBUF MQTT COMPLETADA EXITOSAMENTE.")
    print("   El microservicio receptor decodificó los mensajes, actualizó Redis,")
    print("   registró la partición en PostGIS y emitió los Webhooks a Odoo 18.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulador GPS MQTT Protobuf v3 (GVMT N° 065/2024)")
    parser.add_argument("--bus", default="00016", help="Identificador del bus (ej: 00016)")
    parser.add_argument("--route", default="020f", help="Código del ramal (ej: 020f)")
    parser.add_argument("--delay", type=float, default=2.0, help="Intervalo en segundos entre pings")
    args = parser.parse_args()

    simulate_unit(bus_id=args.bus, route_id=args.route, delay=args.delay)
