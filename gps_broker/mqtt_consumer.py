# -*- coding: utf-8 -*-
"""
Servicio Consumidor MQTT para el Broker de Telemetría GPS.
Escucha el broker Mosquitto en el topic oficial GVMT:
    transporte/flota/{agency_id}/operacion
Decodifica el payload Protobuf v3 (Res. GVMT N°065/2024) y lo reenvía
al endpoint interno del GPS Broker (FastAPI) para procesamiento unificado.

Protocolo soportado: MQTT v3.1.1 / v5.0
Payload: Protocol Buffers v3 (campo Operation)
"""

import os
import sys
import time
import json
import logging
import asyncio
import threading
from datetime import datetime, timezone

import requests

# MQTT client (paho-mqtt es la librería estándar de Python)
try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    logging.error("paho-mqtt no instalado. El consumidor MQTT no puede iniciar.")

# Decodificador Protobuf interno
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto.decoder import decode_operation, OperationType

# ---------------------------------------------------------------------------
# Configuración de entorno
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mqtt_consumer")

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "gps_device")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "GPS_DEVICE_SECRET_2026")
MQTT_TOPIC_PATTERN = os.getenv("MQTT_TOPIC_PATTERN", "transporte/flota/+/operacion")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "gps_broker_consumer")
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))

# URL interna del FastAPI Broker para reenvío
BROKER_INTERNAL_URL = os.getenv("BROKER_INTERNAL_URL", "http://127.0.0.1:8088/api/v1/telemetry")
BROKER_INTERNAL_TOKEN = os.getenv("DEVICE_API_TOKEN", "GPS_DEVICE_SECRET_2026")

# ---------------------------------------------------------------------------
# Callback: Mensaje MQTT recibido → decodificar Protobuf → reenviar al Broker
# ---------------------------------------------------------------------------
def on_message(client, userdata, message):
    topic = message.topic
    payload_bytes = message.payload

    logger.info(f"📡 MQTT recibido | Topic: {topic} | {len(payload_bytes)} bytes")

    try:
        # 1. Detectar si es Protobuf o JSON (JSON empieza con '{')
        if payload_bytes and payload_bytes[0] == ord('{'):
            # Payload JSON plano (modo compatibilidad / pruebas)
            data = json.loads(payload_bytes.decode("utf-8"))
            op_dict = data
        else:
            # Payload binario Protobuf (estándar GVMT N°065/2024)
            operation = decode_operation(payload_bytes)
            op_dict = operation.to_dict()
            logger.info(
                f"   ↳ Protobuf decodificado | Bus: {operation.mean_id} | "
                f"Agencia: {operation.agency_id} | Ruta: {operation.route_id} | "
                f"Tipo: {operation.event_type_str} | "
                f"Coords: ({operation.latitude:.6f}, {operation.longitude:.6f}) | "
                f"Vel: {operation.speed:.1f} km/h"
            )

        # 2. Reenviar al endpoint unificado del FastAPI Broker
        headers = {
            "Content-Type": "application/json",
            "X-Device-Token": BROKER_INTERNAL_TOKEN,
            "X-Source": "mqtt",
        }
        # Normalizar campos para el modelo TelemetryPing del Broker
        ping_payload = {
            "mean_id": op_dict.get("mean_id") or op_dict.get("bus_id", ""),
            "agency_id": op_dict.get("agency_id", ""),
            "route_id": op_dict.get("route_id", ""),
            "driver_id": op_dict.get("driver_id", ""),
            "latitude": float(op_dict.get("latitude", 0.0)),
            "longitude": float(op_dict.get("longitude", 0.0)),
            "velocidad": float(op_dict.get("speed", 0.0)),
            "rumbo": float(op_dict.get("bearing", 0.0)),
            "fecha_hora": op_dict.get("datetime_utc") or op_dict.get("fecha_hora") or datetime.now(timezone.utc).isoformat(),
            "type": op_dict.get("type", OperationType.OPERANDO),
            "precision": op_dict.get("accuracy"),
            "altitud": float(op_dict.get("altitude", 0.0)),
        }

        res = requests.post(
            BROKER_INTERNAL_URL,
            json=ping_payload,
            headers=headers,
            timeout=3.0
        )
        if res.status_code in (200, 201):
            logger.debug(f"   ✓ Ping reenviado al Broker HTTP → {res.status_code}")
        else:
            logger.warning(f"   ⚠ Broker HTTP devolvió {res.status_code}: {res.text[:200]}")

    except Exception as e:
        logger.error(f"Error procesando mensaje MQTT del topic '{topic}': {e}", exc_info=True)


def on_connect(client, userdata, flags, rc, properties=None):
    rc_desc = {
        0: "Conexión exitosa",
        1: "Protocolo rechazado",
        2: "Client ID rechazado",
        3: "Servidor no disponible",
        4: "Usuario/contraseña incorrectos",
        5: "No autorizado",
    }
    if rc == 0:
        logger.info(f"✅ Conectado a Mosquitto MQTT ({MQTT_BROKER_HOST}:{MQTT_BROKER_PORT})")
        client.subscribe(MQTT_TOPIC_PATTERN, qos=MQTT_QOS)
        logger.info(f"🔔 Suscrito al topic: {MQTT_TOPIC_PATTERN} (QoS {MQTT_QOS})")
    else:
        logger.error(f"❌ Error de conexión MQTT: {rc_desc.get(rc, f'Código {rc}')}")


def on_disconnect(client, userdata, rc, properties=None):
    if rc != 0:
        logger.warning(f"⚠ Desconexión inesperada de MQTT (rc={rc}). Reconectando en 5s...")


def run_mqtt_consumer():
    """Inicia el consumidor MQTT en modo loop bloqueante."""
    if not PAHO_AVAILABLE:
        logger.error("paho-mqtt no disponible. Saliendo.")
        return

    logger.info(f"🚀 Iniciando consumidor MQTT → {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    logger.info(f"   Topic: {MQTT_TOPIC_PATTERN}")
    logger.info(f"   Reenvío interno: {BROKER_INTERNAL_URL}")

    client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        clean_session=True,
        protocol=mqtt.MQTTv311
    )
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Reconexión automática con backoff
    retry_interval = 5
    max_retry = 60
    while True:
        try:
            client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
            retry_interval = 5  # reset backoff
            client.loop_forever()
        except Exception as e:
            logger.warning(f"Fallo en conexión MQTT: {e}. Reintentando en {retry_interval}s...")
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 2, max_retry)


def start_consumer_thread():
    """Lanza el consumidor MQTT en un hilo background (no bloqueante)."""
    thread = threading.Thread(target=run_mqtt_consumer, daemon=True, name="mqtt-consumer")
    thread.start()
    logger.info("🧵 Hilo MQTT consumer iniciado en background.")
    return thread


if __name__ == "__main__":
    run_mqtt_consumer()
