"""Procesamiento de un evento AsistenciaRegistrada.

entrada -> valida traslape, geocerca, descanso y turno; abre la jornada.
salida  -> cierra la jornada, aplica reglas + Isolation Forest, define el
           estado (valido / observado / rechazado), pide a Gemini la
           explicación si hay hallazgos, registra en BigQuery y genera alerta.

Es idempotente: una marcación que ya no está en estado 'recibida' se ignora,
así un reintento de Pub/Sub no duplica jornadas.
"""
from __future__ import annotations

import logging
import uuid

from common import auditoria, contexto, geo, ia
from common.config import settings
from common.tiempo import ahora, fecha_local, hora_decimal, horas_entre, iso, parse

from . import anomalias
from .reglas import PARAMETROS, Hallazgo, estado_final, reglas_entrada, reglas_salida

log = logging.getLogger(__name__)
ACTOR = "ms-validacion"
ORIGEN_CARGA = "carga"  # marcaciones de prueba de carga: explicación con plantilla, sin consumir Gemini


def _turno_de(repo, codigo: str, fecha: str) -> dict | None:
    turnos = repo.query("turnos", [("fecha", "==", fecha), ("trabajadores", "array_contains", codigo)])
    return turnos[0] if turnos else None


def _cerrar_marcacion(repo, m: dict, estado: str, **extra) -> None:
    repo.update("marcaciones", m["id"], {"estado": estado, "procesada_en": iso(ahora()), **extra})


def _alerta(repo, bus, *, tipo: str, codigo: str, frente_id: str, fecha: str, ref_id: str, estado: str,
            hallazgos: list[dict], explicacion: dict) -> None:
    alerta_id = str(uuid.uuid4())
    doc = {
        "id": alerta_id,
        "tipo": tipo,
        "codigo_trabajador": codigo,
        "frente_id": frente_id,
        "fecha": fecha,
        "referencia_id": ref_id,
        "estado_registro": estado,
        "reglas": [h["regla"] for h in hallazgos],
        "explicacion_ia": explicacion["texto"],
        "origen_explicacion": explicacion["origen"],
        "atendida": False,
        "creada_en": iso(ahora()),
    }
    repo.put("alertas", alerta_id, doc)
    bus.publicar(settings().topic_alertas, {"tipo_evento": "AlertaGenerada", **doc}, clave_orden=frente_id)


def procesar_marcacion(marcacion_id: str) -> str:
    repo, bus = contexto.repo(), contexto.bus()
    m = repo.get("marcaciones", marcacion_id)
    if not m:
        log.warning("Marcación %s no existe", marcacion_id)
        return "no_encontrada"
    if m.get("estado") != "recibida":
        return "ya_procesada"

    codigo, ts = m["codigo_trabajador"], parse(m["ts"])
    trabajador = repo.get("trabajadores", codigo)
    frente = repo.get("frentes", m["frente_id"]) or {}
    radio = float(frente.get("radio_m", 1000))
    distancia = geo.distancia_a_frente(m.get("lat"), m.get("lon"), frente)

    if not trabajador:
        h = [Hallazgo("R10_TRABAJADOR_DESCONOCIDO", "rechazo", f"El código {codigo} no está registrado").a_dict()]
        return _rechazar_marcacion(repo, bus, m, h)

    jornadas = repo.query("jornadas", [("codigo_trabajador", "==", codigo)])
    abierta = next((j for j in jornadas if j.get("estado") == "abierta"), None)

    if m["tipo"] == "entrada":
        return _procesar_entrada(repo, bus, m, ts, trabajador, jornadas, abierta, distancia, radio)
    return _procesar_salida(repo, bus, m, ts, trabajador, abierta, distancia, radio)


def _rechazar_marcacion(repo, bus, m: dict, hallazgos: list[dict]) -> str:
    fecha = fecha_local(m["ts"])
    explicacion = ia.explicar_jornada(
        {"estado": "rechazado", "tipo_marcacion": m["tipo"], "codigo_trabajador": m["codigo_trabajador"],
         "frente_id": m["frente_id"], "hora": m["ts"], "hallazgos": hallazgos},
        usar_ia=m.get("origen") != ORIGEN_CARGA,
    )
    _cerrar_marcacion(repo, m, "rechazada", hallazgos=hallazgos, explicacion_ia=explicacion["texto"])
    _alerta(repo, bus, tipo="MarcacionRechazada", codigo=m["codigo_trabajador"], frente_id=m["frente_id"],
            fecha=fecha, ref_id=m["id"], estado="rechazado", hallazgos=hallazgos, explicacion=explicacion)
    auditoria.registrar(repo, "rechazar_marcacion", "marcacion", m["id"], ACTOR, {"reglas": [h["regla"] for h in hallazgos]})
    return "rechazada"


def _procesar_entrada(repo, bus, m, ts, trabajador, jornadas, abierta, distancia, radio) -> str:
    fecha = fecha_local(ts)
    cerradas = [j for j in jornadas if j.get("salida_ts")]
    ultima = max(cerradas, key=lambda j: parse(j["salida_ts"]), default=None)
    descanso = round(horas_entre(ultima["salida_ts"], ts), 2) if ultima else None
    turno = _turno_de(repo, trabajador["codigo"], fecha)

    hallazgos = [
        h.a_dict()
        for h in reglas_entrada(
            distancia_m=distancia, radio_m=radio, jornada_abierta=abierta,
            descanso_h=descanso, tiene_turno=turno is not None,
        )
    ]
    if any(h["severidad"] == "rechazo" for h in hallazgos):
        return _rechazar_marcacion(repo, bus, m, hallazgos)

    jornada = {
        "id": m["id"],
        "codigo_trabajador": trabajador["codigo"],
        "cargo": trabajador.get("cargo"),
        "frente_id": m["frente_id"],
        "fecha": fecha,
        "turno_id": turno["id"] if turno else None,
        "entrada_ts": iso(ts),
        "entrada_marcacion_id": m["id"],
        "salida_ts": None,
        "estado": "abierta",
        "hallazgos_entrada": hallazgos,
        "hallazgos": [],
        "descanso_previo_h": descanso,
        "distancia_entrada_m": distancia,
        "registrado_por": m.get("registrado_por"),
    }
    repo.put("jornadas", jornada["id"], jornada)
    _cerrar_marcacion(repo, m, "procesada", jornada_id=jornada["id"])
    auditoria.registrar(repo, "abrir_jornada", "jornada", jornada["id"], ACTOR, {"marcacion": m["id"]})
    return "jornada_abierta"


def _procesar_salida(repo, bus, m, ts, trabajador, abierta, distancia, radio) -> str:
    if not abierta:
        h = [Hallazgo("R06_SALIDA_SIN_ENTRADA", "rechazo", "No hay una entrada abierta para esta salida").a_dict()]
        return _rechazar_marcacion(repo, bus, m, h)

    horas = round(horas_entre(abierta["entrada_ts"], ts), 2)
    turno = repo.get("turnos", abierta["turno_id"]) if abierta.get("turno_id") else None
    programadas = float(turno["horas_programadas"]) if turno else PARAMETROS.horas_programadas_defecto
    autorizadas = float((turno or {}).get("extras_autorizadas", {}).get(trabajador["codigo"], 0.0))

    hallazgos = list(abierta.get("hallazgos_entrada", [])) + [
        h.a_dict()
        for h in reglas_salida(
            horas=horas, horas_programadas=programadas, extra_autorizada_h=autorizadas,
            distancia_m=distancia, radio_m=radio,
        )
    ]

    score, es_anomalia = None, False
    if 0 < horas <= 24:
        feats = anomalias.vector(horas, hora_decimal(abierta["entrada_ts"]), abierta.get("descanso_previo_h"),
                                 abierta.get("distancia_entrada_m"))
        score, es_anomalia = anomalias.evaluar(feats)
        if es_anomalia:
            hallazgos.append(
                Hallazgo("R08_ANOMALIA_MODELO", "observacion",
                         f"El modelo de anomalías marcó la jornada como atípica (score {score:.3f})").a_dict()
            )

    estado = estado_final(hallazgos)
    horas_extra = round(max(0.0, horas - programadas), 2)
    explicacion = {"texto": None, "origen": None}
    if estado != "valido":
        explicacion = ia.explicar_jornada(
            {
                "estado": estado,
                "codigo_trabajador": trabajador["codigo"],
                "cargo": trabajador.get("cargo"),
                "frente_id": abierta["frente_id"],
                "entrada": abierta["entrada_ts"],
                "salida": iso(ts),
                "horas_trabajadas": horas,
                "horas_programadas": programadas,
                "horas_extra_autorizadas": autorizadas,
                "descanso_previo_h": abierta.get("descanso_previo_h"),
                "score_anomalia": score,
                "hallazgos": hallazgos,
            },
            usar_ia=m.get("origen") != ORIGEN_CARGA,
        )

    cambios = {
        "salida_ts": iso(ts),
        "salida_marcacion_id": m["id"],
        "horas_trabajadas": horas,
        "horas_programadas": programadas,
        "horas_extra": horas_extra,
        "horas_extra_autorizadas": autorizadas,
        "hallazgos": hallazgos,
        "score_anomalia": score,
        "es_anomalia": es_anomalia,
        "modelo": anomalias.version(),
        "estado": estado,
        "explicacion_ia": explicacion["texto"],
        "origen_explicacion": explicacion["origen"],
        "validada_en": iso(ahora()),
    }
    repo.update("jornadas", abierta["id"], cambios)
    _cerrar_marcacion(repo, m, "procesada", jornada_id=abierta["id"])
    auditoria.registrar(repo, "validar_jornada", "jornada", abierta["id"], ACTOR,
                        {"estado": estado, "reglas": [h["regla"] for h in hallazgos]})

    contexto.sumidero().insertar("jornadas_validadas", [{
        "jornada_id": abierta["id"],
        "fecha": abierta["fecha"],
        "codigo_trabajador": trabajador["codigo"],
        "cargo": trabajador.get("cargo"),
        "frente_id": abierta["frente_id"],
        "entrada_ts": abierta["entrada_ts"],
        "salida_ts": iso(ts),
        "horas_trabajadas": horas,
        "horas_programadas": programadas,
        "horas_extra": horas_extra,
        "estado": estado,
        "reglas": [h["regla"] for h in hallazgos],
        "score_anomalia": score,
        "es_anomalia": es_anomalia,
        "validada_en": cambios["validada_en"],
    }])

    if estado != "valido":
        _alerta(repo, bus, tipo="JornadaObservada" if estado == "observado" else "JornadaRechazada",
                codigo=trabajador["codigo"], frente_id=abierta["frente_id"], fecha=abierta["fecha"],
                ref_id=abierta["id"], estado=estado, hallazgos=hallazgos, explicacion=explicacion)
    return f"jornada_{estado}"
