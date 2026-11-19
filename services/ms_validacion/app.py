"""ms-validacion: consume eventos AsistenciaRegistrada desde Pub/Sub (push).

Desplegado en Cloud Run SIN acceso público: solo la cuenta de servicio de la
suscripción push de Pub/Sub (token OIDC) puede invocarlo.

Respuestas:
  204 -> procesado (o descartado de forma definitiva): Pub/Sub no reintenta.
  500 -> error transitorio: Pub/Sub reintenta con backoff y, tras 5 intentos,
         envía el mensaje a la cola dead-letter.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response

from common import contexto
from common.config import settings
from common.eventos import decodificar_push

from . import anomalias
from .procesador import procesar_marcacion

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ms-validacion")

app = FastAPI(title="ms-validacion", version="1.0.0")


@app.get("/salud")
def salud() -> dict:
    return {"servicio": "ms-validacion", "estado": "ok", "modelo": anomalias.version()}


@app.post("/pubsub/push", status_code=204)
async def pubsub_push(request: Request) -> Response:
    sobre = await request.json()
    try:
        evento = decodificar_push(sobre)
    except Exception:  # noqa: BLE001 - mensaje corrupto: no reintentar
        log.exception("Mensaje Pub/Sub ilegible")
        return Response(status_code=204)
    if evento.get("tipo_evento") != "AsistenciaRegistrada":
        return Response(status_code=204)
    resultado = procesar_marcacion(evento["marcacion_id"])
    log.info("marcacion=%s resultado=%s", evento["marcacion_id"], resultado)
    return Response(status_code=204)


def registrar_en_bus_local() -> None:
    """En MODO=local, suscribe el procesador al bus en memoria (simula Pub/Sub)."""
    contexto.bus().suscribir(
        settings().topic_marcaciones,
        lambda evento: procesar_marcacion(evento["marcacion_id"]),
    )
