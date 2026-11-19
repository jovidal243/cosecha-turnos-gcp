"""Motor de reglas de negocio parametrizable (funciones puras, fáciles de probar).

Severidad:
  rechazo     -> la marcación/jornada no es válida y debe corregirse.
  observacion -> la jornada queda 'observado' hasta que el jefe de frente decida.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Parametros:
    jornada_max_h: float = 10.0  # 8 h ordinarias + 2 h extra máximas al día
    descanso_min_h: float = 8.0  # descanso mínimo entre jornadas (detecta turnos "pegados")
    tolerancia_extra_h: float = 0.25  # 15 minutos de tolerancia
    horas_programadas_defecto: float = 8.0


PARAMETROS = Parametros()


@dataclass(frozen=True)
class Hallazgo:
    regla: str
    severidad: str
    mensaje: str

    def a_dict(self) -> dict:
        return asdict(self)


CATALOGO = {
    "R01_JORNADA_MAXIMA": "La jornada supera el máximo diario permitido",
    "R02_DESCANSO_MINIMO": "Descanso insuficiente entre jornadas (turno continuo)",
    "R03_TRASLAPE": "Entrada con una jornada abierta (marcación traslapada)",
    "R04_EXTRA_NO_AUTORIZADA": "Horas extra por encima de lo autorizado",
    "R05_FUERA_GEOCERCA": "Marcación fuera de la geocerca del frente",
    "R06_SALIDA_SIN_ENTRADA": "Salida sin entrada abierta",
    "R07_DURACION_INVALIDA": "Duración de jornada no válida",
    "R08_ANOMALIA_MODELO": "Patrón atípico detectado por el modelo de anomalías",
    "R09_SIN_TURNO": "Trabajador sin turno programado para la fecha",
    "R10_TRABAJADOR_DESCONOCIDO": "Código de trabajador no registrado",
}


def _geocerca(distancia_m: float | None, radio_m: float, momento: str) -> list[Hallazgo]:
    if distancia_m is not None and distancia_m > radio_m:
        return [
            Hallazgo(
                "R05_FUERA_GEOCERCA",
                "observacion",
                f"Marcación de {momento} a {distancia_m:,.0f} m del frente (radio permitido {radio_m:,.0f} m)",
            )
        ]
    return []


def reglas_entrada(
    *,
    distancia_m: float | None,
    radio_m: float,
    jornada_abierta: dict | None,
    descanso_h: float | None,
    tiene_turno: bool,
    p: Parametros = PARAMETROS,
) -> list[Hallazgo]:
    hs: list[Hallazgo] = []
    if jornada_abierta:
        hs.append(
            Hallazgo(
                "R03_TRASLAPE",
                "rechazo",
                f"Ya existe una jornada abierta desde {jornada_abierta['entrada_ts']}",
            )
        )
    hs += _geocerca(distancia_m, radio_m, "entrada")
    if descanso_h is not None and descanso_h < p.descanso_min_h:
        hs.append(
            Hallazgo(
                "R02_DESCANSO_MINIMO",
                "observacion",
                f"Solo {descanso_h:.1f} h de descanso desde la jornada anterior (mínimo {p.descanso_min_h:.0f} h)",
            )
        )
    if not tiene_turno:
        hs.append(Hallazgo("R09_SIN_TURNO", "observacion", "No tiene turno programado para esta fecha"))
    return hs


def reglas_salida(
    *,
    horas: float,
    horas_programadas: float,
    extra_autorizada_h: float,
    distancia_m: float | None,
    radio_m: float,
    p: Parametros = PARAMETROS,
) -> list[Hallazgo]:
    if horas <= 0 or horas > 24:
        return [Hallazgo("R07_DURACION_INVALIDA", "rechazo", f"Duración calculada de {horas:.2f} h")]
    hs: list[Hallazgo] = []
    if horas > p.jornada_max_h:
        hs.append(
            Hallazgo(
                "R01_JORNADA_MAXIMA",
                "observacion",
                f"Jornada de {horas:.1f} h supera el máximo de {p.jornada_max_h:.0f} h",
            )
        )
    extra = max(0.0, horas - horas_programadas)
    if extra - extra_autorizada_h > p.tolerancia_extra_h:
        hs.append(
            Hallazgo(
                "R04_EXTRA_NO_AUTORIZADA",
                "observacion",
                f"{extra:.1f} h extra frente a {extra_autorizada_h:.1f} h autorizadas",
            )
        )
    hs += _geocerca(distancia_m, radio_m, "salida")
    return hs


def estado_final(hallazgos: list[dict]) -> str:
    if any(h["severidad"] == "rechazo" for h in hallazgos):
        return "rechazado"
    if hallazgos:
        return "observado"
    return "valido"
