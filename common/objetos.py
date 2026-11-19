"""Almacenamiento de objetos: Cloud Storage en GCP, carpeta local en desarrollo."""
from __future__ import annotations

import os


class AlmacenLocal:
    def __init__(self, data_dir: str) -> None:
        self.raiz = os.path.join(data_dir, "gcs")

    def escribir(self, ruta: str, contenido: str | bytes, tipo: str = "text/plain") -> str:
        destino = os.path.join(self.raiz, ruta)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        modo = "wb" if isinstance(contenido, bytes) else "w"
        with open(destino, modo, **({} if modo == "wb" else {"encoding": "utf-8", "newline": ""})) as f:
            f.write(contenido)
        return f"file://{os.path.abspath(destino)}"

    def leer_bytes(self, ruta: str) -> bytes:
        with open(os.path.join(self.raiz, ruta), "rb") as f:
            return f.read()


class AlmacenGCS:  # pragma: no cover - requiere GCP
    def __init__(self, bucket: str, project_id: str = "") -> None:
        from google.cloud import storage

        self.bucket = storage.Client(project=project_id or None).bucket(bucket)
        self.nombre = bucket

    def escribir(self, ruta: str, contenido: str | bytes, tipo: str = "text/plain") -> str:
        self.bucket.blob(ruta).upload_from_string(contenido, content_type=tipo)
        return f"gs://{self.nombre}/{ruta}"

    def leer_bytes(self, ruta: str) -> bytes:
        return self.bucket.blob(ruta).download_as_bytes()


def leer_gs_uri(uri: str) -> bytes:  # pragma: no cover - requiere GCP
    from google.cloud import storage

    sin_prefijo = uri.removeprefix("gs://")
    bucket, _, ruta = sin_prefijo.partition("/")
    return storage.Client().bucket(bucket).blob(ruta).download_as_bytes()
