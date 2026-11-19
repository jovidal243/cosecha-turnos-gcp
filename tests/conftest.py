import os

import pytest

os.environ["MODO"] = "local"


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("MODO", "local")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient

    from common import contexto, semilla
    from scripts.run_local import app, fechas_demo
    from services.ms_validacion.app import registrar_en_bus_local

    contexto.reiniciar()
    registrar_en_bus_local()
    semilla.cargar(contexto.repo(), fechas_demo(3))
    with TestClient(app) as c:
        yield c
    contexto.reiniciar()


SUP = {"Authorization": "Bearer demo-supervisor"}
JEFE = {"Authorization": "Bearer demo-jefe"}
ANALISTA = {"Authorization": "Bearer demo-analista"}
