"""Datos SINTÉTICOS de demostración: frentes, trabajadores y programación de turnos.

No contiene información real de trabajadores del Ingenio (Ley 1581 de 2012).
"""
from __future__ import annotations

import random

FRENTES = [
    {"id": "F01", "nombre": "Frente 01 - Corte manual Norte", "lat": 3.2702, "lon": -76.2291, "radio_m": 800},
    {"id": "F02", "nombre": "Frente 02 - Corte manual Sur", "lat": 3.2215, "lon": -76.2405, "radio_m": 800},
    {"id": "F03", "nombre": "Frente 03 - Mecanizado Oriente", "lat": 3.2489, "lon": -76.1978, "radio_m": 1000},
    {"id": "F04", "nombre": "Frente 04 - Mecanizado Occidente", "lat": 3.2551, "lon": -76.2702, "radio_m": 1000},
    {"id": "F05", "nombre": "Frente 05 - Alce y transporte", "lat": 3.2390, "lon": -76.2203, "radio_m": 1200},
]

CARGOS = ["Cortero", "Operador de cosechadora", "Tractorista", "Conductor de tractomula"]
_NOMBRES = ["Andrés", "Luisa", "Carlos", "Marta", "Jhon", "Diana", "Óscar", "Paula", "Wilmer", "Sandra"]
_APELLIDOS = ["Rojas", "Mina", "Carabalí", "Gómez", "Lucumí", "Valencia", "Ospina", "Balanta"]

TURNOS = {
    "A": {"inicio": "06:00", "fin": "14:00", "horas": 8.0},
    "B": {"inicio": "14:00", "fin": "22:00", "horas": 8.0},
}


def trabajadores() -> list[dict]:
    rnd = random.Random(7)
    lista = []
    for i in range(1, 41):
        frente = FRENTES[(i - 1) // 8]
        cargo = CARGOS[0] if frente["id"] in ("F01", "F02") else CARGOS[1 + (i % 3)]
        lista.append(
            {
                "codigo": f"T{i:03d}",
                "nombre": f"{rnd.choice(_NOMBRES)} {rnd.choice(_APELLIDOS)} (ficticio)",
                "cargo": cargo,
                "frente_id": frente["id"],
                "qr": f"INC-COS-T{i:03d}",
            }
        )
    return lista


def generar_turnos(fecha: str) -> list[dict]:
    """Por frente: turno A con 6 trabajadores y turno B con 2. El primero de cada turno tiene 2 h extra autorizadas."""
    turnos = []
    for idx, frente in enumerate(FRENTES):
        base = idx * 8
        grupos = {"A": [f"T{base + k:03d}" for k in range(1, 7)], "B": [f"T{base + k:03d}" for k in (7, 8)]}
        for nombre, codigos in grupos.items():
            t = TURNOS[nombre]
            turnos.append(
                {
                    "id": f"{fecha}_{frente['id']}_{nombre}",
                    "fecha": fecha,
                    "frente_id": frente["id"],
                    "turno": nombre,
                    "inicio": t["inicio"],
                    "fin": t["fin"],
                    "horas_programadas": t["horas"],
                    "trabajadores": codigos,
                    "extras_autorizadas": {codigos[0]: 2.0},
                }
            )
    return turnos


def cargar(repo, fechas: list[str]) -> dict:
    for f in FRENTES:
        repo.put("frentes", f["id"], f)
    ts = trabajadores()
    for t in ts:
        repo.put("trabajadores", t["codigo"], t)
    n = 0
    for fecha in fechas:
        for turno in generar_turnos(fecha):
            repo.put("turnos", turno["id"], turno)
            n += 1
    return {"frentes": len(FRENTES), "trabajadores": len(ts), "turnos": n}
