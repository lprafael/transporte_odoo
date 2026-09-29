# -*- coding: utf-8 -*-
"""
Módulo de decodificación Protobuf para la Resolución GVMT N° 065/2024.
Decodifica tramas binarias MQTT enviadas por proveedores de GPS homologados
(EPAS, Sitrack, etc.) y las normaliza al modelo TelemetryPing interno.

Instalar dependencias: pip install protobuf>=4.24.0
"""
from __future__ import annotations

import logging
import struct
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("gps_broker.protobuf")

# ---------------------------------------------------------------------------
# Intentar importar el módulo protobuf generado por protoc.
# Si no está disponible (primera ejecución), usamos un parser binario
# mínimo de emergencia para no bloquear el servicio.
# ---------------------------------------------------------------------------
try:
    from google.protobuf import timestamp_pb2
    from google.protobuf.message import DecodeError
    _PROTOBUF_AVAILABLE = True
    
    # Si se ejecutó protoc y generó transit_pb2.py:
    try:
        from . import transit_pb2
        _GENERATED_AVAILABLE = True
        logger.info("Módulo transit_pb2 generado detectado. Protobuf nativo activo.")
    except ImportError:
        _GENERATED_AVAILABLE = False
        logger.warning("transit_pb2 no encontrado. Usando parser manual de emergencia. "
                       "Ejecuta: protoc --python_out=gps_broker/proto gps_broker/proto/transit.proto")
except ImportError:
    _PROTOBUF_AVAILABLE = False
    _GENERATED_AVAILABLE = False
    logger.warning("Librería 'protobuf' no instalada. Parser de emergencia activo.")


# ---------------------------------------------------------------------------
# Parser manual de emergencia (sin dependencia de protoc)
# Extrae lat/lon/speed/bearing/agency_id/mean_id de un varint Protobuf v3
# suficiente para no perder posiciones mientras se configura el entorno.
# ---------------------------------------------------------------------------
class OperationType:
    INICIADO = 0
    FINALIZADO = 1
    OPERANDO = 2
    SUSPENDIDO = 3


class ParsedOperation:
    """Resultado normalizado de la decodificación de un mensaje Operation de Protobuf."""
    def __init__(self):
        self.identidad: int = 0
        self.agency_id: str = ""
        self.mean_id: str = ""
        self.route_id: str = ""
        self.driver_id: str = ""
        self.type: int = OperationType.OPERANDO
        self.accuracy: int = 0
        self.latitude: float = 0.0
        self.longitude: float = 0.0
        self.altitude: float = 0.0
        self.bearing: float = 0.0
        self.speed: float = 0.0
        self.datetime: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "identidad": self.identidad,
            "agency_id": self.agency_id,
            "mean_id": self.mean_id,
            "route_id": self.route_id,
            "driver_id": self.driver_id,
            "type": self.type,
            "accuracy": self.accuracy,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "bearing": self.bearing,
            "speed": self.speed,
            "datetime_utc": self.datetime.isoformat() if self.datetime else None,
        }

    @property
    def event_type_str(self) -> str:
        """Mapea el OperationType al nombre de evento para Odoo / sistema interno."""
        return {
            OperationType.INICIADO: "departure",
            OperationType.FINALIZADO: "arrival",
            OperationType.OPERANDO: "ping",
            OperationType.SUSPENDIDO: "suspended",
        }.get(self.type, "ping")

    @property
    def is_odoo_event(self) -> bool:
        """Solo INICIADO y FINALIZADO son eventos de negocio relevantes para Odoo."""
        return self.type in (OperationType.INICIADO, OperationType.FINALIZADO)


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Lee un varint de longitud variable desde la posición dada. Retorna (valor, nueva_pos)."""
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    raise ValueError("Varint inválido o truncado")


def _decode_64bit(data: bytes, pos: int) -> tuple[float, int]:
    """Lee un double (64 bits, little-endian) desde la posición dada."""
    val = struct.unpack_from("<d", data, pos)[0]
    return val, pos + 8


def _decode_string(data: bytes, pos: int) -> tuple[str, int]:
    """Lee una cadena de texto (length-delimited) desde la posición dada."""
    length, pos = _decode_varint(data, pos)
    text = data[pos:pos + length].decode("utf-8", errors="replace")
    return text, pos + length


def _decode_32bit_double_packed(data: bytes, pos: int) -> tuple[float, int]:
    """Decodifica un double de 64 bits (wire type 1 = fixed 64)."""
    return _decode_64bit(data, pos)


def decode_operation_emergency(payload: bytes) -> ParsedOperation:
    """
    Parser de emergencia manual sin dependencia de protoc/transit_pb2.
    Decodifica los campos más críticos (lat, lon, speed, bearing, agency_id, mean_id).
    """
    op = ParsedOperation()
    pos = 0
    
    while pos < len(payload):
        try:
            tag_byte, pos = _decode_varint(payload, pos)
        except (ValueError, IndexError):
            break
        
        field_number = tag_byte >> 3
        wire_type = tag_byte & 0x07

        try:
            if wire_type == 0:  # Varint
                val, pos = _decode_varint(payload, pos)
                if field_number == 1:
                    op.identidad = val
                elif field_number == 6:
                    op.type = val
                elif field_number == 7:
                    op.accuracy = val

            elif wire_type == 1:  # 64-bit (double)
                val, pos = _decode_64bit(payload, pos)
                if field_number == 8:
                    op.latitude = val
                elif field_number == 9:
                    op.longitude = val
                elif field_number == 10:
                    op.altitude = val
                elif field_number == 11:
                    op.bearing = val
                elif field_number == 12:
                    op.speed = val

            elif wire_type == 2:  # Length-delimited (string o embedded message)
                length, pos = _decode_varint(payload, pos)
                raw = payload[pos:pos + length]
                pos += length
                
                if field_number == 2:
                    op.agency_id = raw.decode("utf-8", errors="replace")
                elif field_number == 3:
                    op.mean_id = raw.decode("utf-8", errors="replace")
                elif field_number == 4:
                    op.route_id = raw.decode("utf-8", errors="replace")
                elif field_number == 5:
                    op.driver_id = raw.decode("utf-8", errors="replace")
                elif field_number == 13:
                    # Timestamp de Google (embedded message: seconds=varint, nanos=varint)
                    try:
                        sub_pos = 0
                        seconds = 0
                        while sub_pos < len(raw):
                            sub_tag, sub_pos = _decode_varint(raw, sub_pos)
                            sub_field = sub_tag >> 3
                            sub_wire = sub_tag & 0x07
                            if sub_wire == 0:
                                val2, sub_pos = _decode_varint(raw, sub_pos)
                                if sub_field == 1:
                                    seconds = val2
                        op.datetime = datetime.fromtimestamp(seconds, tz=timezone.utc)
                    except Exception:
                        op.datetime = datetime.now(tz=timezone.utc)

            elif wire_type == 5:  # 32-bit
                pos += 4
            else:
                break  # Wire type desconocido, abortar

        except Exception as e:
            logger.debug(f"Error decodificando campo {field_number} (wire={wire_type}): {e}")
            break

    if op.datetime is None:
        op.datetime = datetime.now(tz=timezone.utc)

    return op


def decode_operation(payload: bytes) -> ParsedOperation:
    """
    Punto de entrada principal. Usa transit_pb2 generado si está disponible,
    de lo contrario cae al parser de emergencia manual.
    """
    if _GENERATED_AVAILABLE:
        try:
            from . import transit_pb2
            msg = transit_pb2.Operation()
            msg.ParseFromString(payload)
            
            op = ParsedOperation()
            op.identidad = msg.identidad
            op.agency_id = msg.agency_id
            op.mean_id = msg.mean_id
            op.route_id = msg.route_id
            op.driver_id = msg.driver_id
            op.type = msg.type
            op.accuracy = msg.accuracy
            op.latitude = msg.latitude
            op.longitude = msg.longitude
            op.altitude = msg.altitude
            op.bearing = msg.bearing
            op.speed = msg.speed
            
            # Convertir google.protobuf.Timestamp a datetime
            if msg.HasField("datetime"):
                op.datetime = datetime.fromtimestamp(
                    msg.datetime.seconds + msg.datetime.nanos / 1e9,
                    tz=timezone.utc
                )
            else:
                op.datetime = datetime.now(tz=timezone.utc)
            
            return op
        except Exception as e:
            logger.warning(f"Error con transit_pb2, usando parser de emergencia: {e}")

    return decode_operation_emergency(payload)


def encode_test_operation(
    agency_id: str = "004B",
    mean_id: str = "00016",
    route_id: str = "020f",
    latitude: float = -25.2869,
    longitude: float = -57.6330,
    speed: float = 25.0,
    bearing: float = 120.0,
    op_type: int = OperationType.OPERANDO,
    driver_id: str = "",
    accuracy: int = 5,
    altitude: float = 0.0,
) -> bytes:
    """
    Genera un payload Protobuf binario de prueba (Resolución GVMT N° 065/2024).
    Usa el compilador nativo transit_pb2 si está disponible, o el serializador manual.
    """
    if _GENERATED_AVAILABLE:
        try:
            from . import transit_pb2
            import time
            msg = transit_pb2.Operation()
            msg.identidad = 1
            msg.agency_id = agency_id
            msg.mean_id = mean_id
            msg.route_id = route_id
            msg.driver_id = driver_id
            msg.type = op_type
            msg.accuracy = accuracy
            msg.latitude = latitude
            msg.longitude = longitude
            msg.altitude = altitude
            msg.bearing = bearing
            msg.speed = speed
            now_ts = time.time()
            msg.datetime.seconds = int(now_ts)
            msg.datetime.nanos = int((now_ts - int(now_ts)) * 1e9)
            return msg.SerializeToString()
        except Exception as e:
            logger.debug(f"Aviso serialización nativa transit_pb2: {e}")

    import struct

    def write_varint(value: int) -> bytes:
        result = b""
        while True:
            bits = value & 0x7F
            value >>= 7
            if value:
                result += bytes([bits | 0x80])
            else:
                result += bytes([bits])
                break
        return result

    def write_string(field_num: int, value: str) -> bytes:
        encoded = value.encode("utf-8")
        tag = write_varint((field_num << 3) | 2)
        return tag + write_varint(len(encoded)) + encoded

    def write_double(field_num: int, value: float) -> bytes:
        tag = write_varint((field_num << 3) | 1)
        return tag + struct.pack("<d", value)

    def write_varint_field(field_num: int, value: int) -> bytes:
        tag = write_varint((field_num << 3) | 0)
        return tag + write_varint(value)

    import time
    now = int(time.time())

    payload = b""
    payload += write_varint_field(1, 1)          # identidad
    payload += write_string(2, agency_id)         # agency_id
    payload += write_string(3, mean_id)           # mean_id
    payload += write_string(4, route_id)          # route_id
    payload += write_string(5, "")                # driver_id
    payload += write_varint_field(6, op_type)     # type
    payload += write_varint_field(7, 5)           # accuracy
    payload += write_double(8, latitude)          # latitude
    payload += write_double(9, longitude)         # longitude
    payload += write_double(11, bearing)          # bearing
    payload += write_double(12, speed)            # speed

    # Timestamp (field 13, embedded message: field 1 = seconds varint)
    ts_payload = write_varint_field(1, now)
    payload += write_varint((13 << 3) | 2) + write_varint(len(ts_payload)) + ts_payload

    return payload
