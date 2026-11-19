"""Entrena el Isolation Forest y lo guarda (local y, opcionalmente, en Cloud Storage).

Uso:
  python -m ml.entrenar_isolation_forest --salida ml/modelo/isolation_forest.joblib
  python -m ml.entrenar_isolation_forest --gcs gs://BUCKET/modelos/isolation_forest.joblib

En producción el reentrenamiento mensual corre como Cloud Run Job con el
histórico de BigQuery (jornadas validadas como 'valido' o 'aprobado').
"""
from __future__ import annotations

import argparse
import io
import os
from datetime import UTC, datetime

import joblib
from sklearn.ensemble import IsolationForest

from ml.datos_sinteticos import FEATURES, generar


def entrenar(n: int = 4000, contaminacion: float = 0.01) -> dict:
    X = generar(n)
    modelo = IsolationForest(n_estimators=300, max_samples=1024, contamination=contaminacion, random_state=42)
    modelo.fit(X)
    return {
        "modelo": modelo,
        "features": FEATURES,
        "version": datetime.now(UTC).strftime("%Y%m%d%H%M"),
        "n_entrenamiento": int(n),
        "contaminacion": contaminacion,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="ml/modelo/isolation_forest.joblib")
    ap.add_argument("--gcs", default="", help="URI gs:// opcional para publicar el modelo")
    args = ap.parse_args()

    artefacto = entrenar()
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    joblib.dump(artefacto, args.salida)
    print(f"Modelo {artefacto['version']} guardado en {args.salida}")

    if args.gcs:  # pragma: no cover - requiere GCP
        from google.cloud import storage

        buf = io.BytesIO()
        joblib.dump(artefacto, buf)
        bucket, _, ruta = args.gcs.removeprefix("gs://").partition("/")
        storage.Client().bucket(bucket).blob(ruta).upload_from_string(buf.getvalue())
        print(f"Modelo publicado en {args.gcs}")


if __name__ == "__main__":
    main()
