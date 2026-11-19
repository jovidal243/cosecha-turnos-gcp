"""ms-reportes: tareas programadas invocadas por Cloud Scheduler (OIDC, sin acceso público).

POST /tareas/cierre-diario  {"fecha": "AAAA-MM-DD"}  (por defecto: ayer)
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel

from common.tiempo import ayer

from .cierre import cierre_diario

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="ms-reportes", version="1.0.0")


class CierreIn(BaseModel):
    fecha: str | None = None


@app.get("/salud")
def salud() -> dict:
    return {"servicio": "ms-reportes", "estado": "ok"}


@app.post("/tareas/cierre-diario")
def tarea_cierre(body: CierreIn | None = None) -> dict:
    fecha = (body.fecha if body else None) or ayer()
    return cierre_diario(fecha)
