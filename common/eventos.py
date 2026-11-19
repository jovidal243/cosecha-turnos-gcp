"""Mensajería orientada a eventos: Pub/Sub en GCP, bus en proceso en local."""
from __future__ import annotations

import base64
import json
import logging
from collections import defaultdict
from collections.abc import Callable

log = logging.getLogger(__name__)


class BusLocal:
    """Entrega síncrona a suscriptores registrados. Los fallos van a una 'DLQ' en memoria."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
        self.publicados: list[tuple[str, dict]] = []
        self.dead_letter: list[tuple[str, dict, str]] = []

    def suscribir(self, topic: str, fn: Callable[[dict], None]) -> None:
        self._subs[topic].append(fn)

    def publicar(self, topic: str, datos: dict, clave_orden: str | None = None) -> str:
        self.publicados.append((topic, datos))
        for fn in self._subs.get(topic, []):
            try:
                fn(datos)
            except Exception as exc:  # noqa: BLE001
                log.exception("Fallo procesando evento en %s", topic)
                self.dead_letter.append((topic, datos, str(exc)))
        return f"local-{len(self.publicados)}"


class PublicadorPubSub:  # pragma: no cover - requiere GCP
    """Publica con ordering key (código del trabajador) para conservar el orden entrada→salida."""

    def __init__(self, project_id: str) -> None:
        from google.cloud import pubsub_v1

        self.project_id = project_id
        self.cliente = pubsub_v1.PublisherClient(
            publisher_options=pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
        )

    def publicar(self, topic: str, datos: dict, clave_orden: str | None = None) -> str:
        ruta = self.cliente.topic_path(self.project_id, topic)
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        kwargs = {"ordering_key": clave_orden} if clave_orden else {}
        try:
            futuro = self.cliente.publish(ruta, cuerpo, tipo=datos.get("tipo_evento", ""), **kwargs)
            return futuro.result(timeout=15)
        except Exception:
            if clave_orden:  # con ordering keys, un fallo pausa la clave hasta reanudarla
                self.cliente.resume_publish(ruta, clave_orden)
            raise


def decodificar_push(sobre: dict) -> dict:
    """Extrae el JSON de un mensaje push de Pub/Sub."""
    mensaje = sobre.get("message", {})
    data = mensaje.get("data", "")
    if not data:
        return {}
    return json.loads(base64.b64decode(data).decode("utf-8"))


def sobre_push(datos: dict) -> dict:
    """Construye un sobre push como el que envía Pub/Sub (útil para pruebas)."""
    return {
        "message": {
            "data": base64.b64encode(json.dumps(datos).encode()).decode(),
            "messageId": "prueba",
        },
        "subscription": "projects/local/subscriptions/validacion-push",
    }
