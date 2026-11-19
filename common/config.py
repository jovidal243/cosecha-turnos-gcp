"""Configuración centralizada leída de variables de entorno.

MODO=local  -> todo corre en memoria/disco local (demo y pruebas, sin GCP).
MODO=gcp    -> Firestore, Pub/Sub, BigQuery, Cloud Storage y Vertex AI (Gemini).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bogota")

# Tokens de demostración (solo MODO=local). En GCP los tokens vienen de Secret Manager.
TOKENS_DEMO = {
    "demo-supervisor": "supervisor",
    "demo-jefe": "jefe_frente",
    "demo-analista": "analista",
}


@dataclass(frozen=True)
class Settings:
    modo: str
    project_id: str
    region: str
    topic_marcaciones: str
    topic_alertas: str
    bucket: str
    bq_dataset: str
    gemini_model: str
    gemini_location: str
    model_uri: str
    data_dir: str
    api_tokens: dict = field(default_factory=dict)

    @property
    def es_gcp(self) -> bool:
        return self.modo == "gcp"


def settings() -> Settings:
    modo = os.getenv("MODO", "local").lower()
    raw_tokens = os.getenv("API_TOKENS", "").strip()
    if raw_tokens:
        tokens = json.loads(raw_tokens)
    else:
        tokens = TOKENS_DEMO if modo != "gcp" else {}
    return Settings(
        modo=modo,
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        region=os.getenv("REGION", "us-central1"),
        topic_marcaciones=os.getenv("TOPIC_MARCACIONES", "marcaciones"),
        topic_alertas=os.getenv("TOPIC_ALERTAS", "alertas"),
        bucket=os.getenv("BUCKET", ""),
        bq_dataset=os.getenv("BQ_DATASET", "cosecha_turnos"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        gemini_location=os.getenv("GEMINI_LOCATION", "global"),
        model_uri=os.getenv("MODEL_URI", ""),
        data_dir=os.getenv("DATA_DIR", ".datos_locales"),
        api_tokens=tokens,
    )
