"""Levanta TODO el sistema en un solo proceso, sin GCP (demo y desarrollo).

    python -m scripts.run_local            # http://localhost:8080
    python -m scripts.run_local --simular  # además simula 2 días con casos atípicos

- Firestore  -> repositorio en memoria
- Pub/Sub    -> bus en proceso (ms-validacion suscrito)
- BigQuery   -> .datos_locales/bigquery/*.jsonl
- GCS        -> .datos_locales/gcs/
- Gemini     -> plantillas de respaldo
"""
from __future__ import annotations

import argparse
import os

os.environ.setdefault("MODO", "local")

import uvicorn  # noqa: E402

from common import contexto, semilla  # noqa: E402
from common.tiempo import ahora  # noqa: E402
from services.ms_asistencia.app import app  # noqa: E402
from services.ms_reportes.app import app as app_reportes  # noqa: E402
from services.ms_validacion.app import registrar_en_bus_local  # noqa: E402


def fechas_demo(dias: int = 3) -> list[str]:
    hoy = ahora().date()
    return [(hoy.fromordinal(hoy.toordinal() - k)).isoformat() for k in range(dias - 1, -1, -1)]


def preparar() -> None:
    registrar_en_bus_local()
    print("Semilla:", semilla.cargar(contexto.repo(), fechas_demo(3)))


# ms-reportes queda montado bajo /local/reportes solo en modo local
app.mount("/local/reportes", app_reportes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=int(os.getenv("PORT", "8080")))
    ap.add_argument("--simular", action="store_true", help="Carga dos días simulados con casos atípicos")
    args = ap.parse_args()
    preparar()
    if args.simular:
        from fastapi.testclient import TestClient

        from scripts.simular_dia import simular

        with TestClient(app) as cliente:
            simular(cliente, fechas_demo(3)[:2], token="demo-supervisor",
                    cierre=lambda f: cliente.post("/local/reportes/tareas/cierre-diario", json={"fecha": f}))
    print(f"Abra http://localhost:{args.puerto}/app/  (tokens: demo-supervisor, demo-jefe, demo-analista)")
    uvicorn.run(app, host="0.0.0.0", port=args.puerto)


if __name__ == "__main__":
    main()
