"""Sumidero analítico: BigQuery en GCP, archivos JSONL en local."""
from __future__ import annotations

import json
import os


class SumideroLocal:
    def __init__(self, data_dir: str) -> None:
        self.dir = os.path.join(data_dir, "bigquery")
        self.filas: dict[str, list[dict]] = {}

    def insertar(self, tabla: str, filas: list[dict]) -> None:
        self.filas.setdefault(tabla, []).extend(filas)
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, f"{tabla}.jsonl"), "a", encoding="utf-8") as f:
            for fila in filas:
                f.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")


class SumideroBigQuery:  # pragma: no cover - requiere GCP
    def __init__(self, project_id: str, dataset: str) -> None:
        from google.cloud import bigquery

        self.cliente = bigquery.Client(project=project_id or None)
        self.prefijo = f"{self.cliente.project}.{dataset}"

    def insertar(self, tabla: str, filas: list[dict]) -> None:
        errores = self.cliente.insert_rows_json(f"{self.prefijo}.{tabla}", filas)
        if errores:
            raise RuntimeError(f"Errores insertando en BigQuery: {errores}")
