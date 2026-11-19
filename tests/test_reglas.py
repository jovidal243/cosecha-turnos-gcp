from services.ms_validacion.reglas import estado_final, reglas_entrada, reglas_salida


def _reglas(hs):
    return {h.regla for h in hs}


def test_entrada_limpia_sin_hallazgos():
    hs = reglas_entrada(distancia_m=120, radio_m=800, jornada_abierta=None, descanso_h=15, tiene_turno=True)
    assert hs == []


def test_traslape_es_rechazo():
    hs = reglas_entrada(distancia_m=0, radio_m=800, jornada_abierta={"entrada_ts": "x"}, descanso_h=None, tiene_turno=True)
    assert "R03_TRASLAPE" in _reglas(hs)
    assert estado_final([h.a_dict() for h in hs]) == "rechazado"


def test_descanso_insuficiente_y_sin_turno():
    hs = reglas_entrada(distancia_m=0, radio_m=800, jornada_abierta=None, descanso_h=6.2, tiene_turno=False)
    assert _reglas(hs) == {"R02_DESCANSO_MINIMO", "R09_SIN_TURNO"}


def test_fuera_de_geocerca():
    hs = reglas_entrada(distancia_m=3000, radio_m=800, jornada_abierta=None, descanso_h=None, tiene_turno=True)
    assert _reglas(hs) == {"R05_FUERA_GEOCERCA"}


def test_jornada_maxima_y_extra_no_autorizada():
    hs = reglas_salida(horas=11.6, horas_programadas=8, extra_autorizada_h=2, distancia_m=0, radio_m=800)
    assert _reglas(hs) == {"R01_JORNADA_MAXIMA", "R04_EXTRA_NO_AUTORIZADA"}
    assert estado_final([h.a_dict() for h in hs]) == "observado"


def test_extra_dentro_de_lo_autorizado_y_tolerancia():
    assert reglas_salida(horas=9.9, horas_programadas=8, extra_autorizada_h=2, distancia_m=0, radio_m=800) == []
    assert reglas_salida(horas=8.2, horas_programadas=8, extra_autorizada_h=0, distancia_m=0, radio_m=800) == []


def test_duracion_invalida():
    hs = reglas_salida(horas=-1, horas_programadas=8, extra_autorizada_h=0, distancia_m=0, radio_m=800)
    assert _reglas(hs) == {"R07_DURACION_INVALIDA"}


def test_estado_valido_sin_hallazgos():
    assert estado_final([]) == "valido"
