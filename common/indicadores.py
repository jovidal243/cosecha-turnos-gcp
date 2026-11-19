"""Indicadores agregados del día (base para tableros y para el asistente IA)."""
from __future__ import annotations

from collections import Counter

ESTADOS = ("abierta", "valido", "observado", "rechazado", "aprobado")


def calcular(jornadas: list[dict], alertas: list[dict] | None = None) -> dict:
    """alertas (opcional): permite contar las marcaciones rechazadas, que no generan jornada."""
    por_estado = Counter(j.get("estado") for j in jornadas)
    cerradas = [j for j in jornadas if j.get("horas_trabajadas") is not None]
    reglas = Counter(h["regla"] for j in jornadas for h in (j.get("hallazgos") or j.get("hallazgos_entrada") or []))
    rechazadas = [a for a in (alertas or []) if a.get("tipo") == "MarcacionRechazada"]
    reglas.update(r for a in rechazadas for r in a.get("reglas", []))
    por_frente: dict[str, dict] = {}
    for j in cerradas:
        f = por_frente.setdefault(j["frente_id"], {"jornadas": 0, "horas": 0.0, "horas_extra": 0.0, "observadas": 0})
        f["jornadas"] += 1
        f["horas"] += j.get("horas_trabajadas", 0)
        f["horas_extra"] += j.get("horas_extra", 0)
        f["observadas"] += j.get("estado") in ("observado", "rechazado")
    for f in por_frente.values():
        f["horas"] = round(f["horas"], 2)
        f["horas_extra"] = round(f["horas_extra"], 2)
    total_cerradas = len(cerradas)
    observadas = por_estado.get("observado", 0) + por_estado.get("rechazado", 0)
    return {
        "jornadas_total": len(jornadas),
        "por_estado": {e: por_estado.get(e, 0) for e in ESTADOS},
        "horas_trabajadas": round(sum(j.get("horas_trabajadas", 0) for j in cerradas), 2),
        "horas_extra": round(sum(j.get("horas_extra", 0) for j in cerradas), 2),
        "tasa_observacion": round(observadas / total_cerradas, 3) if total_cerradas else 0.0,
        "marcaciones_rechazadas": len(rechazadas),
        "anomalias_modelo": sum(1 for j in cerradas if j.get("es_anomalia")),
        "reglas_disparadas": dict(reglas.most_common()),
        "por_frente": por_frente,
    }
