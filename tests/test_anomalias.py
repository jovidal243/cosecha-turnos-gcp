from services.ms_validacion import anomalias


def test_jornada_normal_no_es_anomalia():
    _, anom = anomalias.evaluar(anomalias.vector(8.1, 5.8, 15.8, 90))
    assert not anom


def test_entrada_de_madrugada_es_anomalia():
    _, anom = anomalias.evaluar(anomalias.vector(8.0, 2.17, 48, 50))
    assert anom


def test_jornada_extrema_es_anomalia():
    score, anom = anomalias.evaluar(anomalias.vector(15, 6, 3, 2500))
    assert anom and score < 0
