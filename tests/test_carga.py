from common import ia
from scripts.prueba_carga import marcacion, percentil


def test_percentil():
    valores = list(range(1, 101))
    assert percentil(valores, 50) == 50
    assert percentil(valores, 95) == 95
    assert percentil([7.0], 99) == 7.0


def test_marcaciones_de_carga_alternan_y_no_tocan_la_demo():
    m0, m40 = marcacion(0), marcacion(40)
    assert m0["codigo_trabajador"] == m40["codigo_trabajador"] == "T001"
    assert (m0["tipo"], m40["tipo"]) == ("entrada", "salida")
    assert m0["ts"].startswith("2026-01-05T06:00") and m40["ts"].startswith("2026-01-05T14:00")
    assert m0["origen"] == "carga"


def test_explicacion_sin_ia_usa_plantilla():
    r = ia.explicar_jornada({"estado": "observado", "hallazgos": [{"mensaje": "x"}]}, usar_ia=False)
    assert r["origen"] == "plantilla" and r["texto"].startswith("Jornada observada: x")
