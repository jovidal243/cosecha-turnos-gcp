"""Carga los datos SINTÉTICOS en Firestore (MODO=gcp) o en memoria (MODO=local).

    MODO=gcp GOOGLE_CLOUD_PROJECT=mi-proyecto python -m scripts.cargar_semilla --dias 4
"""
from __future__ import annotations

import argparse
from datetime import timedelta

from common import contexto, semilla
from common.tiempo import ahora


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=4, help="Días de turnos a generar, terminando hoy")
    args = ap.parse_args()
    hoy = ahora().date()
    fechas = [(hoy - timedelta(days=k)).isoformat() for k in range(args.dias - 1, -1, -1)]
    print("Cargado:", semilla.cargar(contexto.repo(), fechas), "fechas:", fechas[0], "a", fechas[-1])


if __name__ == "__main__":
    main()
