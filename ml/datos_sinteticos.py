"""Genera jornadas 'normales' sintéticas para entrenar el detector de anomalías.

Variables (mismo orden que usa ms-validacion):
  horas_trabajadas      duración de la jornada (h)
  desfase_turno_h       distancia (h) entre la entrada y el inicio de turno más cercano (06, 14, 22)
  descanso_previo_h     horas desde la salida anterior (tope 24: más de un día = descanso completo)
  distancia_entrada_m   distancia al centro del frente al marcar entrada
"""
from __future__ import annotations

import numpy as np

FEATURES = ["horas_trabajadas", "desfase_turno_h", "descanso_previo_h", "distancia_entrada_m"]
INICIOS_TURNO = (6.0, 14.0, 22.0)
DESCANSO_TOPE_H = 24.0


def desfase_turno(hora_entrada):
    """Horas a la hora de inicio de turno más cercana (considera el cruce de medianoche)."""
    h = np.asarray(hora_entrada, dtype=float)
    d = np.min([np.minimum(np.abs(h - t), 24 - np.abs(h - t)) for t in INICIOS_TURNO], axis=0)
    return d


def generar(n: int = 4000, semilla: int = 42) -> np.ndarray:
    rng = np.random.default_rng(semilla)
    turno = rng.choice([6.0, 14.0], size=n, p=[0.75, 0.25])
    hora_entrada = turno + rng.normal(-0.15, 0.25, n)
    con_extra = rng.random(n) < 0.35
    horas = 8.0 + np.where(con_extra, rng.uniform(0.5, 2.0, n), 0.0) + rng.normal(0.05, 0.1, n)
    descanso = 24.0 - horas + rng.normal(0, 0.4, n)
    descanso = np.where(rng.random(n) < 0.3, DESCANSO_TOPE_H, descanso)
    distancia = np.abs(rng.normal(0, 180, n))
    return np.column_stack([horas, desfase_turno(hora_entrada), np.minimum(descanso, DESCANSO_TOPE_H), distancia])
