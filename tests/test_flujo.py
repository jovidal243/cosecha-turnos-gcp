"""Pruebas de punta a punta en MODO=local (API -> evento -> validación -> cierre)."""
import uuid
from datetime import datetime, timedelta

from common.config import TZ
from scripts.run_local import fechas_demo
from scripts.simular_dia import simular

from .conftest import ANALISTA, JEFE, SUP

AYER = fechas_demo(3)[1]
F01 = {"lat": 3.2702, "lon": -76.2291}


def _m(codigo, tipo, hhmm, minutos=0, fecha=AYER, frente="F01", **kw):
    ts = datetime.fromisoformat(f"{fecha}T{hhmm}:00").replace(tzinfo=TZ) + timedelta(minutes=minutos)
    return {"id": str(uuid.uuid4()), "codigo_trabajador": codigo, "tipo": tipo, "ts": ts.isoformat(),
            "frente_id": frente, **F01, **kw}


def _jornada(cliente, codigo, fecha=AYER):
    js = [j for j in cliente.get("/api/jornadas", params={"fecha": fecha}, headers=SUP).json()
          if j["codigo_trabajador"] == codigo]
    return js[0] if js else None


def test_autenticacion_y_roles(cliente):
    assert cliente.get("/api/catalogos").status_code == 401
    assert cliente.get("/api/catalogos", headers={"Authorization": "Bearer malo"}).status_code == 401
    r = cliente.post("/api/jornadas/x/decision", json={"decision": "aprobar"}, headers=SUP)
    assert r.status_code == 403


def test_jornada_valida(cliente):
    for m in (_m("T002", "entrada", "05:55"), _m("T002", "salida", "14:05")):
        assert cliente.post("/api/marcaciones", json=m, headers=SUP).json()["resultado"] == "creada"
    j = _jornada(cliente, "T002")
    assert j["estado"] == "valido" and j["horas_trabajadas"] == 8.17 and j["explicacion_ia"] is None


def test_idempotencia_misma_marcacion(cliente):
    m = _m("T003", "entrada", "06:00")
    assert cliente.post("/api/marcaciones", json=m, headers=SUP).json()["resultado"] == "creada"
    assert cliente.post("/api/marcaciones", json=m, headers=SUP).json()["resultado"] == "duplicada"
    assert len([j for j in cliente.get("/api/jornadas", params={"fecha": AYER}, headers=SUP).json()
                if j["codigo_trabajador"] == "T003"]) == 1


def test_jornada_larga_queda_observada_con_explicacion_y_alerta(cliente):
    lote = [_m("T004", "entrada", "06:00"), _m("T004", "salida", "06:00", minutos=11 * 60)]
    cliente.post("/api/marcaciones/lote", json={"marcaciones": lote}, headers=SUP)
    j = _jornada(cliente, "T004")
    reglas = {h["regla"] for h in j["hallazgos"]}
    assert j["estado"] == "observado"
    assert {"R01_JORNADA_MAXIMA", "R04_EXTRA_NO_AUTORIZADA"} <= reglas
    assert j["explicacion_ia"] and j["origen_explicacion"] == "plantilla"
    alertas = cliente.get("/api/alertas", params={"fecha": AYER}, headers=JEFE).json()
    assert any(a["referencia_id"] == j["id"] for a in alertas)


def test_traslape_y_salida_sin_entrada_se_rechazan(cliente):
    e1, e2 = _m("T005", "entrada", "06:00"), _m("T005", "entrada", "06:30")
    s = _m("T006", "salida", "14:00")
    cliente.post("/api/marcaciones/lote", json={"marcaciones": [e1, e2, s]}, headers=SUP)
    assert cliente.get(f"/api/marcaciones/{e2['id']}", headers=SUP).json()["estado"] == "rechazada"
    assert cliente.get(f"/api/marcaciones/{s['id']}", headers=SUP).json()["hallazgos"][0]["regla"] == "R06_SALIDA_SIN_ENTRADA"


def test_marcacion_futura_rechazada(cliente):
    futuro = (datetime.now(TZ) + timedelta(hours=2)).isoformat()
    m = {**_m("T002", "entrada", "06:00"), "ts": futuro}
    assert cliente.post("/api/marcaciones", json=m, headers=SUP).status_code == 422


def test_decision_del_jefe_y_cierre_para_nomina(cliente, tmp_path):
    lote = [_m("T004", "entrada", "06:00"), _m("T004", "salida", "06:00", minutos=11 * 60),
            _m("T002", "entrada", "06:00"), _m("T002", "salida", "14:00")]
    cliente.post("/api/marcaciones/lote", json={"marcaciones": lote}, headers=SUP)
    j = _jornada(cliente, "T004")
    r = cliente.post(f"/api/jornadas/{j['id']}/decision", json={"decision": "aprobar", "comentario": "Soporte OK"},
                     headers=JEFE)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"
    assert cliente.post(f"/api/jornadas/{j['id']}/decision", json={"decision": "aprobar"}, headers=JEFE).status_code == 409

    cierre = cliente.post("/local/reportes/tareas/cierre-diario", json={"fecha": AYER}).json()
    assert cierre["jornadas_pagables"] == 2
    csv_ = (tmp_path / "gcs" / "nomina" / f"fecha={AYER}" / "horas_validadas.csv").read_text(encoding="utf-8")
    assert "T004" in csv_ and "T002" in csv_
    assert csv_.splitlines()[1].split(",")[0]  # jornada_id presente
    assert cliente.get(f"/api/resumenes/{AYER}", headers=ANALISTA).json()["resumen"].startswith("- Jornadas")


def test_simulacion_detecta_todos_los_casos(cliente):
    dias = fechas_demo(3)[:2]
    simular(cliente, dias, token="demo-supervisor")
    ultimo = dias[-1]
    js = {j["codigo_trabajador"]: j for j in cliente.get("/api/jornadas", params={"fecha": ultimo}, headers=SUP).json()}

    def reglas(c):
        return {h["regla"] for h in js[c]["hallazgos"]}

    assert {"R01_JORNADA_MAXIMA", "R04_EXTRA_NO_AUTORIZADA"} <= reglas("T001")
    assert "R04_EXTRA_NO_AUTORIZADA" in reglas("T010")
    assert "R05_FUERA_GEOCERCA" in reglas("T015")
    assert "R02_DESCANSO_MINIMO" in reglas("T031")
    assert "R08_ANOMALIA_MODELO" in reglas("T034")
    kpis = cliente.get("/api/kpis", params={"fecha": ultimo}, headers=ANALISTA).json()
    assert kpis["por_estado"]["valido"] >= 25
    alertas = cliente.get("/api/alertas", params={"fecha": ultimo}, headers=JEFE).json()
    tipos = {a["tipo"] for a in alertas}
    assert {"MarcacionRechazada", "JornadaObservada"} <= tipos
    r = cliente.post("/api/asistente", json={"pregunta": "¿Cuántas horas extra hubo?", "fecha": ultimo}, headers=ANALISTA)
    assert r.status_code == 200 and r.json()["origen"] == "plantilla"
