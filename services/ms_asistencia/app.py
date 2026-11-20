"""ms-asistencia: API pública + app web progresiva (PWA) del supervisor.

- Recibe marcaciones (individuales o en lote desde la cola offline de la PWA),
  las guarda de forma idempotente (UUID generado en el dispositivo) y publica
  el evento AsistenciaRegistrada en Pub/Sub.
- Expone consultas de jornadas, alertas e indicadores, la decisión del jefe
  de frente (aprobar / rechazar) y el asistente de IA generativa (Gemini).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from common import auditoria, contexto, ia, indicadores
from common.auth import requiere_rol, usuario_actual
from common.config import settings
from common.tiempo import ahora, fecha_local, hoy, iso, parse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ms-asistencia")

@asynccontextmanager
async def calentar(_app: FastAPI):
    """Abre las conexiones con Firestore y Pub/Sub antes de aceptar tráfico.

    Uvicorn no abre el puerto hasta que termina este arranque, así que Cloud Run no envía solicitudes a una
    instancia nueva mientras obtiene credenciales y abre canales gRPC (la prueba de carga mostró que esa
    primera solicitud podía tardar 5-9 s).
    """
    try:
        contexto.repo().get("marcaciones", "_calentamiento")
        contexto.bus()
    except Exception:  # noqa: BLE001 - si falla, el servicio arranca igual y se conecta en la primera solicitud
        log.warning("No se pudo precalentar las conexiones", exc_info=True)
    yield


app = FastAPI(
    lifespan=calentar,
    title="ms-asistencia",
    version="1.0.0",
    description="Registro y consulta de turnos y asistencia - Gerencia de Cosecha (datos sintéticos)",
)

ESTATICOS = os.path.join(os.path.dirname(__file__), "static")
app.mount("/app", StaticFiles(directory=ESTATICOS, html=True), name="app")

TODOS = ("supervisor", "jefe_frente", "analista")


# ---------- modelos ----------
class MarcacionIn(BaseModel):
    id: str = Field(min_length=8, max_length=64, description="UUID generado en el dispositivo (idempotencia)")
    codigo_trabajador: str = Field(min_length=2, max_length=20)
    tipo: Literal["entrada", "salida"]
    ts: datetime
    frente_id: str
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    origen: str = "pwa"


class LoteIn(BaseModel):
    marcaciones: list[MarcacionIn] = Field(max_length=500)


class DecisionIn(BaseModel):
    decision: Literal["aprobar", "rechazar"]
    comentario: str = Field(default="", max_length=500)


class TurnoIn(BaseModel):
    fecha: str
    frente_id: str
    turno: str
    inicio: str
    fin: str
    horas_programadas: float = Field(gt=0, le=12)
    trabajadores: list[str]
    extras_autorizadas: dict[str, float] = {}


class PreguntaIn(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)
    fecha: str | None = None


# ---------- utilidades ----------
def _registrar(m: MarcacionIn, usuario: dict) -> dict:
    ts = parse(m.ts)
    if ts > ahora() + timedelta(minutes=5):
        return {"id": m.id, "resultado": "error", "detalle": "La hora de la marcación está en el futuro"}
    repo = contexto.repo()
    doc = {
        **m.model_dump(exclude={"ts"}),
        "ts": iso(ts),
        "fecha": fecha_local(ts),
        "estado": "recibida",
        "registrado_por": usuario["usuario"],
        "recibida_en": iso(ahora()),
    }
    creada = repo.create("marcaciones", m.id, doc)
    if creada:
        auditoria.registrar(repo, "registrar_marcacion", "marcacion", m.id, usuario["usuario"],
                            {"tipo": m.tipo, "codigo": m.codigo_trabajador})
    else:
        existente = repo.get("marcaciones", m.id) or {}
        if existente.get("estado") != "recibida":
            return {"id": m.id, "resultado": "duplicada"}
        # Reintento de una marcación cuyo evento no se alcanzó a publicar: se vuelve a publicar
        # (ms-validacion es idempotente, así que no hay riesgo de doble procesamiento).
    try:
        contexto.bus().publicar(
            settings().topic_marcaciones,
            {"tipo_evento": "AsistenciaRegistrada", "marcacion_id": m.id, "codigo_trabajador": m.codigo_trabajador},
            clave_orden=m.codigo_trabajador,
        )
    except Exception:  # noqa: BLE001 - el dispositivo conserva la marcación y reintenta
        log.exception("No se pudo publicar el evento de %s", m.id)
        return {"id": m.id, "resultado": "error", "detalle": "Evento no publicado; reintente"}
    return {"id": m.id, "resultado": "creada" if creada else "duplicada"}


# ---------- rutas ----------
@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/app/")


@app.get("/salud")
def salud() -> dict:
    return {"servicio": "ms-asistencia", "estado": "ok", "modo": settings().modo}


@app.get("/api/yo")
def yo(usuario: dict = Depends(usuario_actual)) -> dict:
    return usuario


@app.get("/api/catalogos")
def catalogos(_: dict = Depends(requiere_rol(*TODOS))) -> dict:
    repo = contexto.repo()
    return {
        "frentes": sorted(repo.query("frentes"), key=lambda f: f["id"]),
        "trabajadores": sorted(
            ({k: t[k] for k in ("codigo", "nombre", "cargo", "frente_id", "qr")} for t in repo.query("trabajadores")),
            key=lambda t: t["codigo"],
        ),
    }


@app.get("/api/turnos")
def listar_turnos(fecha: str = Query(default_factory=hoy), frente_id: str | None = None,
                  _: dict = Depends(requiere_rol(*TODOS))) -> list[dict]:
    filtros = [("fecha", "==", fecha)] + ([("frente_id", "==", frente_id)] if frente_id else [])
    return sorted(contexto.repo().query("turnos", filtros), key=lambda t: t["id"])


@app.post("/api/turnos", status_code=201)
def crear_turno(t: TurnoIn, usuario: dict = Depends(requiere_rol("jefe_frente", "analista"))) -> dict:
    doc = {"id": f"{t.fecha}_{t.frente_id}_{t.turno}", **t.model_dump()}
    contexto.repo().put("turnos", doc["id"], doc)
    auditoria.registrar(contexto.repo(), "programar_turno", "turno", doc["id"], usuario["usuario"])
    return doc


@app.post("/api/marcaciones", status_code=202)
def registrar_marcacion(m: MarcacionIn, usuario: dict = Depends(requiere_rol("supervisor", "jefe_frente"))) -> dict:
    r = _registrar(m, usuario)
    if r["resultado"] == "error":
        raise HTTPException(422, r["detalle"])
    return r


@app.post("/api/marcaciones/lote", status_code=202)
def registrar_lote(lote: LoteIn, usuario: dict = Depends(requiere_rol("supervisor", "jefe_frente"))) -> dict:
    """Sincronización de la cola offline: se procesa en orden cronológico."""
    resultados = [_registrar(m, usuario) for m in sorted(lote.marcaciones, key=lambda x: parse(x.ts))]
    return {"resultados": resultados}


@app.get("/api/marcaciones/{marcacion_id}")
def ver_marcacion(marcacion_id: str, _: dict = Depends(requiere_rol(*TODOS))) -> dict:
    m = contexto.repo().get("marcaciones", marcacion_id)
    if not m:
        raise HTTPException(404, "Marcación no encontrada")
    return m


@app.get("/api/jornadas")
def listar_jornadas(fecha: str = Query(default_factory=hoy), estado: str | None = None,
                    frente_id: str | None = None, _: dict = Depends(requiere_rol(*TODOS))) -> list[dict]:
    filtros = [("fecha", "==", fecha)]
    if estado:
        filtros.append(("estado", "==", estado))
    if frente_id:
        filtros.append(("frente_id", "==", frente_id))
    return sorted(contexto.repo().query("jornadas", filtros), key=lambda j: (j["frente_id"], j["entrada_ts"]))


@app.post("/api/jornadas/{jornada_id}/decision")
def decidir(jornada_id: str, d: DecisionIn, usuario: dict = Depends(requiere_rol("jefe_frente"))) -> dict:
    repo = contexto.repo()
    j = repo.get("jornadas", jornada_id)
    if not j:
        raise HTTPException(404, "Jornada no encontrada")
    if j["estado"] != "observado":
        raise HTTPException(409, f"Solo se deciden jornadas observadas (estado actual: {j['estado']})")
    nuevo = "aprobado" if d.decision == "aprobar" else "rechazado"
    cambios = {"estado": nuevo, "decision": {"por": usuario["usuario"], "comentario": d.comentario, "ts": iso(ahora())}}
    repo.update("jornadas", jornada_id, cambios)
    for a in repo.query("alertas", [("referencia_id", "==", jornada_id)]):
        repo.update("alertas", a["id"], {"atendida": True})
    auditoria.registrar(repo, f"{d.decision}_jornada", "jornada", jornada_id, usuario["usuario"],
                        {"comentario": d.comentario})
    contexto.sumidero().insertar("decisiones", [{
        "jornada_id": jornada_id, "fecha": j["fecha"], "frente_id": j["frente_id"],
        "decision": d.decision, "estado_resultante": nuevo, "decidido_por": usuario["usuario"],
        "ts": cambios["decision"]["ts"],
    }])
    return {**j, **cambios}


@app.get("/api/alertas")
def listar_alertas(fecha: str = Query(default_factory=hoy), solo_pendientes: bool = True,
                   _: dict = Depends(requiere_rol(*TODOS))) -> list[dict]:
    alertas = contexto.repo().query("alertas", [("fecha", "==", fecha)])
    if solo_pendientes:
        alertas = [a for a in alertas if not a.get("atendida")]
    return sorted(alertas, key=lambda a: a["creada_en"], reverse=True)


def _kpis(fecha: str) -> dict:
    repo = contexto.repo()
    return indicadores.calcular(repo.query("jornadas", [("fecha", "==", fecha)]),
                                repo.query("alertas", [("fecha", "==", fecha)]))


@app.get("/api/kpis")
def kpis(fecha: str = Query(default_factory=hoy), _: dict = Depends(requiere_rol(*TODOS))) -> dict:
    return {"fecha": fecha, **_kpis(fecha)}


@app.get("/api/resumenes/{fecha}")
def ver_resumen(fecha: str, _: dict = Depends(requiere_rol(*TODOS))) -> dict:
    r = contexto.repo().get("resumenes", fecha)
    if not r:
        raise HTTPException(404, "Aún no hay cierre diario para esa fecha")
    return r


@app.post("/api/asistente")
def asistente(p: PreguntaIn, usuario: dict = Depends(requiere_rol("jefe_frente", "analista"))) -> dict:
    fecha = p.fecha or hoy()
    respuesta = ia.responder_pregunta(p.pregunta, fecha, _kpis(fecha))
    auditoria.registrar(contexto.repo(), "consultar_asistente", "asistente", fecha, usuario["usuario"],
                        {"pregunta": p.pregunta[:200], "origen": respuesta["origen"]})
    return {"fecha": fecha, "pregunta": p.pregunta, **respuesta}
