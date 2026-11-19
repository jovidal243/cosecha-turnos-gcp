"""Carga del modelo Isolation Forest y evaluación de una jornada.

Orden de búsqueda del modelo:
  1. MODEL_URI (gs://...) -> versión reentrenada publicada en Cloud Storage.
  2. ml/modelo/isolation_forest.joblib -> versión empaquetada en la imagen.
  3. Entrenamiento rápido en memoria con datos sintéticos (respaldo).
"""
from __future__ import annotations

import io
import logging
import os

import joblib
import numpy as np

from common.config import settings
from ml.datos_sinteticos import DESCANSO_TOPE_H, FEATURES, desfase_turno

log = logging.getLogger(__name__)

RUTA_LOCAL = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "modelo", "isolation_forest.joblib")

_artefacto: dict | None = None


def _cargar() -> dict:
    s = settings()
    if s.model_uri.startswith("gs://"):  # pragma: no cover - requiere GCP
        try:
            from common.objetos import leer_gs_uri

            return joblib.load(io.BytesIO(leer_gs_uri(s.model_uri)))
        except Exception:  # noqa: BLE001
            log.exception("No se pudo leer el modelo de %s; se usa el empaquetado", s.model_uri)
    if os.path.exists(RUTA_LOCAL):
        return joblib.load(RUTA_LOCAL)
    from ml.entrenar_isolation_forest import entrenar

    log.warning("Modelo no encontrado; entrenando en memoria con datos sintéticos")
    return entrenar()


def artefacto() -> dict:
    global _artefacto
    if _artefacto is None:
        _artefacto = _cargar()
    return _artefacto


def vector(horas: float, hora_entrada: float, descanso_h: float | None, distancia_m: float | None) -> list[float]:
    descanso = DESCANSO_TOPE_H if descanso_h is None else min(descanso_h, DESCANSO_TOPE_H)
    return [horas, float(desfase_turno(hora_entrada)), descanso, distancia_m or 0.0]


def evaluar(features: list[float]) -> tuple[float, bool]:
    """Devuelve (score, es_anomalia). Score < 0 indica anomalía."""
    a = artefacto()
    x = np.array([features], dtype=float)
    score = float(a["modelo"].decision_function(x)[0])
    return round(score, 4), score < 0


def version() -> str:
    a = artefacto()
    return f"isolation_forest:{a.get('version', 'desconocida')}"


assert FEATURES == ["horas_trabajadas", "desfase_turno_h", "descanso_previo_h", "distancia_entrada_m"]
