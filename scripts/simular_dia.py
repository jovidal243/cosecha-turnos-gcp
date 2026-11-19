"""Simula las marcaciones de uno o varios días completos, con casos atípicos inyectados.

Contra GCP:
  python -m scripts.simular_dia --url https://ms-asistencia-xxxx.run.app \
      --token "$TOKEN_SUPERVISOR" --fechas 2026-11-16 2026-11-17

Casos atípicos del ÚLTIMO día simulado (para la demo):
  T001  jornada de 11,6 h (supera máximo; tiene 2 h extra autorizadas)
  T010  9,8 h sin horas extra autorizadas
  T015  entrada a ~3 km del frente (fuera de geocerca)
  T021  doble entrada (traslape)
  T027  salida sin entrada
  T031  turno B el día anterior hasta 23:40 y entra a las 05:50 (turno continuo / descanso insuficiente)
  T034  entrada a las 02:10, jornada de 8 h (solo la detecta el modelo de anomalías)
"""
from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta

from common.config import TZ

DESPLAZAMIENTO_GRADOS = 0.0009  # ~100 m


def _ts(fecha: str, hhmm: str, minutos: float = 0) -> datetime:
    base = datetime.fromisoformat(f"{fecha}T{hhmm}:00").replace(tzinfo=TZ)
    return base + timedelta(minutes=minutos)


def _marcacion(codigo, tipo, ts, frente, rnd, lejos=False) -> dict:
    lat = frente["lat"] + rnd.uniform(-1, 1) * DESPLAZAMIENTO_GRADOS + (0.027 if lejos else 0)
    lon = frente["lon"] + rnd.uniform(-1, 1) * DESPLAZAMIENTO_GRADOS
    return {"id": str(uuid.uuid4()), "codigo_trabajador": codigo, "tipo": tipo, "ts": ts.isoformat(),
            "frente_id": frente["id"], "lat": round(lat, 6), "lon": round(lon, 6), "origen": "simulador"}


def generar_dia(fecha: str, turnos: list[dict], frentes: dict, ultimo: bool, rnd: random.Random,
                fecha_siguiente: str | None = None) -> list[dict]:
    ms: list[dict] = []
    for t in turnos:
        fr = frentes[t["frente_id"]]
        for codigo in t["trabajadores"]:
            if ultimo and codigo == "T031":
                continue  # se agrega abajo como caso de turno continuo
            entrada = _ts(fecha, t["inicio"], rnd.uniform(-20, 5))
            autorizada = t["extras_autorizadas"].get(codigo, 0)
            extra = autorizada if rnd.random() < 0.5 else 0
            horas = t["horas_programadas"] + extra + (rnd.uniform(-0.25, 0) if extra else rnd.uniform(-0.05, 0.2))
            lejos = False
            if ultimo:
                if codigo == "T001":
                    horas = 11.6
                elif codigo == "T010":
                    horas = 9.8
                elif codigo == "T015":
                    lejos = True
                elif codigo == "T027":
                    ms.append(_marcacion(codigo, "salida", entrada + timedelta(hours=8), fr, rnd))
                    continue
                elif codigo == "T034":
                    entrada = _ts(fecha, "02:10")
                    horas = 8.0
            if not ultimo and codigo == "T031" and fecha_siguiente:
                horas = 9.67  # sale 23:40 aprox.
                entrada = _ts(fecha, t["inicio"])
            ms.append(_marcacion(codigo, "entrada", entrada, fr, rnd, lejos=lejos))
            if ultimo and codigo == "T021":
                ms.append(_marcacion(codigo, "entrada", entrada + timedelta(minutes=40), fr, rnd))
            ms.append(_marcacion(codigo, "salida", entrada + timedelta(hours=horas), fr, rnd))
    if ultimo:
        # T031 vuelve a las 05:50 a otro frente, sin turno programado, tras salir 23:40 el día anterior
        fr = frentes["F01"]
        e = _ts(fecha, "05:50")
        ms += [_marcacion("T031", "entrada", e, fr, rnd), _marcacion("T031", "salida", e + timedelta(hours=8), fr, rnd)]
    return ms


def simular(cliente, fechas: list[str], token: str, cierre=None, semilla: int = 11) -> dict:
    rnd = random.Random(semilla)
    h = {"Authorization": f"Bearer {token}"}
    cat = cliente.get("/api/catalogos", headers=h).json()
    frentes = {f["id"]: f for f in cat["frentes"]}
    totales = {}
    for i, fecha in enumerate(fechas):
        ultimo = i == len(fechas) - 1
        turnos = cliente.get("/api/turnos", params={"fecha": fecha}, headers=h).json()
        siguiente = fechas[i + 1] if not ultimo else None
        marcas = generar_dia(fecha, turnos, frentes, ultimo, rnd, siguiente)
        r = cliente.post("/api/marcaciones/lote", json={"marcaciones": marcas}, headers=h)
        r.raise_for_status()
        res = r.json()["resultados"]
        totales[fecha] = {"enviadas": len(marcas), "creadas": sum(x["resultado"] == "creada" for x in res)}
        if cierre:
            cierre(fecha)
    print("Simulación:", totales)
    return totales


def main() -> None:  # pragma: no cover - uso manual contra GCP
    import httpx

    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--fechas", nargs="+", required=True)
    args = ap.parse_args()
    with httpx.Client(base_url=args.url, timeout=120) as c:
        simular(c, args.fechas, args.token)


if __name__ == "__main__":
    main()
