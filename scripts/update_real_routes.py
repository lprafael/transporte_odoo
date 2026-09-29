#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualiza las cabeceras, nombres, coordenadas y sentidos reales de los ramales de la Línea 20 (004B)
en la base de datos local flota_db basándose en las coordenadas oficiales de los shapes CID.
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# Conexión local a PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    port=5434,
    dbname="flota_db",
    user="odoo",
    password="odoo_password"
)
conn.set_client_encoding('UTF8')
cur = conn.cursor(cursor_factory=RealDictCursor)

UPDATES = [
    {
        "code": "020c",
        "name": "Ramal 020C - San Lorenzo a Asunción",
        "direction": "inbound",
        "origin": "San Lorenzo (Azara)",
        "destination": "Asunción Centro (Puerto/Costanera)",
        "distance_km": 18.28,
        "origin_latitude": -25.341626,
        "origin_longitude": -57.502123,
        "destination_latitude": -25.274101,
        "destination_longitude": -57.645739,
        "description": "Trazado Oficial CID: San Lorenzo rumbo a Asunción Centro"
    },
    {
        "code": "020d",
        "name": "Ramal 020D - Asunción a San Lorenzo",
        "direction": "outbound",
        "origin": "Asunción Centro (Puerto/Costanera)",
        "destination": "San Lorenzo (Azara)",
        "distance_km": 18.02,
        "origin_latitude": -25.274438,
        "origin_longitude": -57.645172,
        "destination_latitude": -25.341707,
        "destination_longitude": -57.502077,
        "description": "Trazado Oficial CID: Retorno desde Asunción Centro a San Lorenzo"
    },
    {
        "code": "020e",
        "name": "Ramal 020E - San Lorenzo a Asunción (Variante)",
        "direction": "inbound",
        "origin": "San Lorenzo (Azara)",
        "destination": "Asunción Centro (Puerto/Costanera)",
        "distance_km": 18.92,
        "origin_latitude": -25.341773,
        "origin_longitude": -57.502040,
        "destination_latitude": -25.274135,
        "destination_longitude": -57.645693,
        "description": "Trazado Oficial CID: Variante San Lorenzo a Asunción"
    },
    {
        "code": "020f",
        "name": "Ramal 020F - Asunción a San Lorenzo (Variante)",
        "direction": "outbound",
        "origin": "Asunción Centro (Puerto/Costanera)",
        "destination": "San Lorenzo (Azara)",
        "distance_km": 18.91,
        "origin_latitude": -25.274435,
        "origin_longitude": -57.645177,
        "destination_latitude": -25.341780,
        "destination_longitude": -57.502036,
        "description": "Trazado Oficial CID: Retorno variante Asunción a San Lorenzo"
    },
    {
        "code": "0210",
        "name": "Ramal 0210 - Luque (Aeropuerto) a Asunción",
        "direction": "inbound",
        "origin": "Luque (Rotonda Aeropuerto)",
        "destination": "Asunción Centro (Puerto/Costanera)",
        "distance_km": 18.33,
        "origin_latitude": -25.243754,
        "origin_longitude": -57.512076,
        "destination_latitude": -25.274100,
        "destination_longitude": -57.645740,
        "description": "Trazado Oficial CID: Luque hacia Asunción Centro"
    },
    {
        "code": "0211",
        "name": "Ramal 0211 - Asunción a Luque (Aeropuerto)",
        "direction": "outbound",
        "origin": "Asunción Centro (Puerto/Costanera)",
        "destination": "Luque (Rotonda Aeropuerto)",
        "distance_km": 18.84,
        "origin_latitude": -25.274438,
        "origin_longitude": -57.645172,
        "destination_latitude": -25.243705,
        "destination_longitude": -57.511981,
        "description": "Trazado Oficial CID: Retorno Asunción hacia Luque"
    },
    {
        "code": "0000",
        "name": "Sin Ramal / En Depósito",
        "direction": "inbound",
        "origin": "Patio Maniobras",
        "destination": "Taller Central",
        "distance_km": 0.0,
        "origin_latitude": -25.341626,
        "origin_longitude": -57.502123,
        "destination_latitude": -25.341626,
        "destination_longitude": -57.502123,
        "description": "Unidades fuera de servicio comercial o en taller"
    }
]

print("[*] Actualizando rutas en transit_route con codificación UTF-8...")
for u in UPDATES:
    cur.execute("""
        UPDATE transit_route
        SET name = %(name)s,
            direction = %(direction)s,
            origin = %(origin)s,
            destination = %(destination)s,
            distance_km = %(distance_km)s,
            origin_latitude = %(origin_latitude)s,
            origin_longitude = %(origin_longitude)s,
            destination_latitude = %(destination_latitude)s,
            destination_longitude = %(destination_longitude)s,
            description = %(description)s
        WHERE code = %(code)s;
    """, u)
    print(f"  [+] Ruta {u['code']} actualizada: {u['name']} ({u['origin']} -> {u['destination']})")

conn.commit()

print("\n[*] Verificación en base de datos:")
cur.execute("SELECT id, code, name, direction, origin, destination, distance_km FROM transit_route ORDER BY code;")
for r in cur.fetchall():
    print(dict(r))

cur.close()
conn.close()
print("\n[OK] Actualización completada exitosamente.")
