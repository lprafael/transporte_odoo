# -*- coding: utf-8 -*-
"""
Test Unitario y Demostración de Lógica Operativa:
- Programación encadenada de itinerarios (Ida/Regresa)
- Validación de tiempos de parada técnica en cabeceras/terminales (regulación, recarga EV, limpieza, mantenimiento)
- Semáforo de despachos GPS (Verde, Amarillo, Rojo, Azul)
- Asignación de buses de reserva técnica (Standby)
- Monitoreo de batería EV (SoC Salida / Llegada y Consumo %)
Basado en datos de las planillas reales de Informe_empresa/PLANILLA PRINCIPAL TRANSITO E1/E2/E3 SEPTIEMBRE 2026.xlsx
"""

import sys
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def compute_semaphore(state, compliance_status, is_reserve_substituted):
    """Lógica semafórica de transit.dispatch y transit.bus.schedule.line"""
    if is_reserve_substituted:
        return 'blue'   # Azul: Cubierto por unidad de reserva técnica
    if state == 'canceled' or compliance_status == 'unperformed':
        return 'red'    # Rojo: Cancelado / Faltante
    if compliance_status == 'on_time':
        return 'green'  # Verde: Salida dentro de tolerancia horaria
    if compliance_status in ('delayed', 'early'):
        return 'yellow' # Amarillo: Fuera de tolerancia (retraso / adelanto)
    return 'gray'       # Gris: Programado / Borrador

def check_layover(layover_type, actual_minutes):
    """Lógica de validación de tiempos mínimos en cabecera"""
    min_requirements = {
        'regulation': 10,   # Regulación / intervalo
        'charging': 30,     # Recarga de baterías EV
        'cleaning': 15,     # Aseo y desinfección
        'driver_rest': 15,  # Descanso chofer
        'maintenance': 30,  # Chequeo preventivo
    }
    required = min_requirements.get(layover_type, 10)
    has_alert = actual_minutes < required
    alert_msg = f"Tiempo de parada insuficiente: {actual_minutes} min (mínimo {required} min para {layover_type})" if has_alert else ""
    return has_alert, alert_msg, required

def compute_battery_consumption(soc_dep, soc_arr):
    """Cálculo de consumo de batería EV según planilla de tránsito"""
    if soc_dep is not None and soc_arr is not None:
        return max(0.0, round(soc_dep - soc_arr, 1))
    return 0.0

def run_tests():
    print("=" * 75)
    print("TEST Y VALIDACIÓN: LÓGICA DE PROGRAMACIÓN OPERATIVA Y SEMÁFOROS GPS")
    print("=" * 75)

    # 1. Semáforo Operativo GPS
    print("\n[1] Verificación del Semáforo Operativo GPS:")
    assert compute_semaphore('dispatched', 'on_time', False) == 'green', "Fallo verde"
    print("  ✓ Salida en margen correcto (On Time): 🟢 VERDE")

    assert compute_semaphore('dispatched', 'delayed', False) == 'yellow', "Fallo amarillo delay"
    assert compute_semaphore('dispatched', 'early', False) == 'yellow', "Fallo amarillo early"
    print("  ✓ Salida fuera de margen (Retraso/Adelanto): 🟡 AMARILLO")

    assert compute_semaphore('canceled', 'canceled', False) == 'red', "Fallo rojo canceled"
    assert compute_semaphore('draft', 'unperformed', False) == 'red', "Fallo rojo unperformed"
    print("  ✓ Despacho cancelado / no realizado: 🔴 ROJO")

    assert compute_semaphore('dispatched', 'on_time', True) == 'blue', "Fallo azul reserva"
    assert compute_semaphore('dispatched', 'delayed', True) == 'blue', "Fallo azul reserva retrasada"
    print("  ✓ Cobertura con Bus de Reserva Técnica: 🔵 AZUL")

    # 2. Paradas Técnicas (Layover)
    print("\n[2] Verificación de Tiempos Mínimos de Parada Técnica:")
    # Caso 1: Regulación suficiente (15 min >= 10 min) - Como en O'Leary (ODG)
    alert, msg, req = check_layover('regulation', 15)
    assert not alert, "Falso positivo en regulación"
    print(f"  ✓ Parada cabecera ODG (15 min para regulación): VÁLIDA (Mínimo {req} min)")

    # Caso 2: Parada de recarga insuficiente (10 min < 30 min) -> ALERTA
    alert, msg, req = check_layover('charging', 10)
    assert alert, "No detectó tiempo insuficiente en recarga"
    print(f"  ✓ Alerta disparada correctamente: '{msg}'")

    # Caso 3: Parada de recarga suficiente en Terminal San Lorenzo (50 min >= 30 min)
    alert, msg, req = check_layover('charging', 50)
    assert not alert, "Falso positivo en recarga depot"
    print(f"  ✓ Parada terminal SL (50 min para recarga EV + limpieza): VÁLIDA (Mínimo {req} min)")

    # Caso 4: Limpieza insuficiente (5 min < 15 min) -> ALERTA
    alert, msg, req = check_layover('cleaning', 5)
    assert alert, "No detectó limpieza insuficiente"
    print(f"  ✓ Alerta disparada para limpieza apresurada: '{msg}'")

    # 3. Monitoreo Baterías EV (Planilla de Tránsito Real E1)
    print("\n[3] Verificación de Batería EV (Datos Planilla Tránsito E1):")
    # Bus 104: Salida SL con 91%, Llegada con 65%
    cons = compute_battery_consumption(91.0, 65.0)
    assert cons == 26.0, f"Consumo erróneo: {cons}"
    print(f"  ✓ Bus E1-104: Salida 91% SoC -> Llegada 65% SoC = Consumo: {cons}%")

    # Bus 105: Salida SL con 85%, Llegada con 58%
    cons2 = compute_battery_consumption(85.0, 58.0)
    assert cons2 == 27.0, f"Consumo erróneo: {cons2}"
    print(f"  ✓ Bus E1-105: Salida 85% SoC -> Llegada 58% SoC = Consumo: {cons2}%")

    # 4. Simulación de Cadena Operativa Diaria Completa (Bus X)
    print("\n[4] Simulación de Cadena Operativa Diaria (Bus 104 - Itinerarios Encadenados):")
    timeline = [
        {"seq": 1, "route": "E1 San Lorenzo -> ODG", "dep": "05:30", "arr": "06:45", "layover_next": 15, "layover_type": "regulation", "status": "on_time", "reserve": False},
        {"seq": 2, "route": "E1 ODG -> San Lorenzo", "dep": "07:00", "arr": "08:15", "layover_next": 50, "layover_type": "charging", "status": "on_time", "reserve": False},
        {"seq": 3, "route": "E1 San Lorenzo -> ODG", "dep": "09:05", "arr": "10:20", "layover_next": 15, "layover_type": "regulation", "status": "delayed", "reserve": False},
        {"seq": 4, "route": "E1 ODG -> San Lorenzo", "dep": "10:35", "arr": "11:50", "layover_next": 5, "layover_type": "cleaning", "status": "unperformed", "reserve": False},
        {"seq": 5, "route": "E1 San Lorenzo -> ODG", "dep": "12:10", "arr": "13:25", "layover_next": 20, "layover_type": "driver_rest", "status": "on_time", "reserve": True},
    ]

    for leg in timeline:
        sem = compute_semaphore(
            'canceled' if leg['status'] == 'unperformed' else 'dispatched',
            leg['status'],
            leg['reserve']
        )
        has_alert, msg, req = check_layover(leg['layover_type'], leg['layover_next'])
        sem_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴", "blue": "🔵"}[sem]
        alert_icon = "⚠️ [ALERTA PARADA INSUFICIENTE]" if has_alert else "✔️ [Parada OK]"
        reserve_icon = "[BUS RESERVA R-01 ASIGNADO]" if leg['reserve'] else ""

        print(f"  Paso {leg['seq']}: {leg['dep']} -> {leg['arr']} | {leg['route']} | Semáforo: {sem_icon} {sem.upper()} | Parada: {leg['layover_next']}m ({leg['layover_type']}) {alert_icon} {reserve_icon}")

    print("\n" + "=" * 75)
    print("✅ TODAS LAS PRUEBAS UNITARIAS Y DE NEGOCIO PASARON SATISFACTORIAMENTE")
    print("=" * 75)

if __name__ == '__main__':
    run_tests()
