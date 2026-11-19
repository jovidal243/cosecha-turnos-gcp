"""Cierre diario: archivo de horas validadas para nómina + resumen con Gemini."""
from __future__ import annotations

import csv
import io

from common import auditoria, contexto, ia, indicadores
from common.tiempo import ahora, iso

COLUMNAS_NOMINA = [
    "jornada_id", "fecha", "codigo_trabajador", "frente_id", "entrada_ts", "salida_ts",
    "horas_trabajadas", "horas_programadas", "horas_extra", "horas_extra_autorizadas", "estado",
]


def cierre_diario(fecha: str) -> dict:
    repo, almacen = contexto.repo(), contexto.almacen()
    jornadas = repo.query("jornadas", [("fecha", "==", fecha)])
    pagables = sorted((j for j in jornadas if j.get("estado") in ("valido", "aprobado")),
                      key=lambda j: (j["frente_id"], j["codigo_trabajador"]))
    pendientes = [j for j in jornadas if j.get("estado") in ("observado", "abierta")]

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNAS_NOMINA, extrasaction="ignore")
    w.writeheader()
    for j in pagables:
        w.writerow({**j, "jornada_id": j["id"]})
    uri_nomina = almacen.escribir(f"nomina/fecha={fecha}/horas_validadas.csv", buf.getvalue(), "text/csv")

    todas_alertas = repo.query("alertas", [("fecha", "==", fecha)])
    kpis = indicadores.calcular(jornadas, todas_alertas)
    alertas = [
        {k: a.get(k) for k in ("tipo", "frente_id", "codigo_trabajador", "reglas", "estado_registro")}
        for a in todas_alertas if not a.get("atendida")
    ]
    resumen = ia.resumen_diario(fecha, kpis, alertas)
    uri_resumen = almacen.escribir(f"resumenes/{fecha}.md", f"# Cierre {fecha}\n\n{resumen['texto']}\n", "text/markdown")

    doc = {
        "fecha": fecha,
        "generado_en": iso(ahora()),
        "jornadas_pagables": len(pagables),
        "jornadas_pendientes": len(pendientes),
        "archivo_nomina": uri_nomina,
        "archivo_resumen": uri_resumen,
        "resumen": resumen["texto"],
        "origen_resumen": resumen["origen"],
        "kpis": kpis,
    }
    repo.put("resumenes", fecha, doc)
    contexto.sumidero().insertar("cierres_diarios", [{
        "fecha": fecha, "generado_en": doc["generado_en"], "jornadas_total": kpis["jornadas_total"],
        "jornadas_pagables": len(pagables), "jornadas_pendientes": len(pendientes),
        "horas_trabajadas": kpis["horas_trabajadas"], "horas_extra": kpis["horas_extra"],
        "tasa_observacion": kpis["tasa_observacion"], "origen_resumen": resumen["origen"],
    }])
    auditoria.registrar(repo, "cierre_diario", "resumen", fecha, "ms-reportes",
                        {"pagables": len(pagables), "pendientes": len(pendientes)})
    return doc
