"""Prueba de carga contra ms-asistencia (local o Cloud Run).

Mide la latencia (p50, p95, p99) y la tasa de error por endpoint, la latencia de la
primera solicitud (arranque en frío si el servicio estaba en cero) y el rendimiento
total. Agrega los resultados a docs/resultados-carga.md.

    python -m scripts.prueba_carga --url https://ms-asistencia-xxxx.run.app \
        --token "$TOKEN_SUPERVISOR" --escenario mixto --solicitudes 1000 --concurrencia 25

Escenarios:
  lectura    GET de indicadores, jornadas y alertas (lo que hace el jefe de frente)
  escritura  POST /api/marcaciones (lo que hace la PWA al sincronizar)
  mixto      70 % lectura y 30 % escritura

Las marcaciones de la prueba usan origen "carga" y fechas de enero de 2026: no tocan
los días de la demo y su explicación se genera con plantilla, sin consumir Gemini.
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import random
import statistics
import time
import uuid
from datetime import date, datetime, timedelta

import httpx

from common.config import TZ

FECHA_DEMO = "2026-11-17"
FECHA_CARGA = date(2026, 1, 5)
OBJETIVO_P95_MS = 300
LECTURAS = [
    ("GET /api/kpis", f"/api/kpis?fecha={FECHA_DEMO}"),
    ("GET /api/jornadas", f"/api/jornadas?fecha={FECHA_DEMO}&estado=observado"),
    ("GET /api/alertas", f"/api/alertas?fecha={FECHA_DEMO}"),
]


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return float("nan")
    orden = sorted(valores)
    k = max(0, math.ceil(p / 100 * len(orden)) - 1)
    return orden[k]


def marcacion(i: int) -> dict:
    """Marcaciones deterministas: cada trabajador alterna entrada (06:00) y salida (14:00) día a día."""
    codigo = f"T{(i % 40) + 1:03d}"
    n = i // 40
    dia = FECHA_CARGA + timedelta(days=n // 2)
    entrada = n % 2 == 0
    hora = "06:00" if entrada else "14:00"
    ts = datetime.fromisoformat(f"{dia.isoformat()}T{hora}:00").replace(tzinfo=TZ)
    frente = f"F0{((i % 40) // 8) + 1}"
    return {"id": str(uuid.uuid4()), "codigo_trabajador": codigo, "tipo": "entrada" if entrada else "salida",
            "ts": ts.isoformat(), "frente_id": frente, "lat": None, "lon": None, "origen": "carga"}


async def ejecutar(url: str, token: str, escenario: str, total: int, concurrencia: int) -> dict:
    cabeceras = {"Authorization": f"Bearer {token}"}
    medidas: dict[str, list[float]] = {}
    errores: dict[str, int] = {}
    contador = {"i": 0, "escritura": 0}
    rnd = random.Random(7)

    async with httpx.AsyncClient(base_url=url, headers=cabeceras, timeout=30) as cliente:
        t0 = time.perf_counter()
        r = await cliente.get("/salud")
        primera_ms = (time.perf_counter() - t0) * 1000
        r.raise_for_status()

        async def una_solicitud() -> None:
            i = contador["i"]
            contador["i"] += 1
            es_escritura = escenario == "escritura" or (escenario == "mixto" and rnd.random() < 0.3)
            inicio = time.perf_counter()
            try:
                if es_escritura:
                    nombre = "POST /api/marcaciones"
                    j = contador["escritura"]
                    contador["escritura"] += 1
                    resp = await cliente.post("/api/marcaciones", json=marcacion(j))
                    ok = resp.status_code == 202
                else:
                    nombre, ruta = LECTURAS[i % len(LECTURAS)]
                    resp = await cliente.get(ruta)
                    ok = resp.status_code == 200
            except httpx.HTTPError:
                ok = False
            ms = (time.perf_counter() - inicio) * 1000
            medidas.setdefault(nombre, []).append(ms)
            if not ok:
                errores[nombre] = errores.get(nombre, 0) + 1

        semaforo = asyncio.Semaphore(concurrencia)

        async def limitada() -> None:
            async with semaforo:
                await una_solicitud()

        t_ini = time.perf_counter()
        await asyncio.gather(*(limitada() for _ in range(total)))
        duracion = time.perf_counter() - t_ini

    filas = []
    for nombre, valores in sorted(medidas.items()):
        filas.append({
            "endpoint": nombre, "n": len(valores), "errores": errores.get(nombre, 0),
            "p50": percentil(valores, 50), "p95": percentil(valores, 95), "p99": percentil(valores, 99),
            "max": max(valores), "media": statistics.fmean(valores),
        })
    todas = [v for vs in medidas.values() for v in vs]
    return {
        "url": url, "escenario": escenario, "total": total, "concurrencia": concurrencia,
        "duracion_s": duracion, "rps": total / duracion if duracion else 0,
        "primera_ms": primera_ms, "filas": filas,
        "global": {"p50": percentil(todas, 50), "p95": percentil(todas, 95), "p99": percentil(todas, 99),
                   "errores": sum(errores.values())},
    }


def a_markdown(res: dict) -> str:
    cuando = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    lineas = [
        f"## {cuando} · escenario {res['escenario']} · {res['total']} solicitudes · concurrencia {res['concurrencia']}",
        "",
        f"- Servicio: `{res['url']}`",
        f"- Duración: {res['duracion_s']:.1f} s · rendimiento: **{res['rps']:.1f} solicitudes/s**",
        f"- Primera solicitud (`/salud`, incluye arranque en frío si el servicio estaba en cero): {res['primera_ms']:.0f} ms",
        f"- Global: p50 {res['global']['p50']:.0f} ms · **p95 {res['global']['p95']:.0f} ms** · "
        f"p99 {res['global']['p99']:.0f} ms · errores {res['global']['errores']}",
        "",
        "| Endpoint | Solicitudes | Errores | p50 (ms) | p95 (ms) | p99 (ms) | Máx. (ms) |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in res["filas"]:
        lineas.append(f"| {f['endpoint']} | {f['n']} | {f['errores']} | {f['p50']:.0f} | {f['p95']:.0f} | "
                      f"{f['p99']:.0f} | {f['max']:.0f} |")
    escritura = next((f for f in res["filas"] if f["endpoint"].startswith("POST")), None)
    if escritura:
        cumple = "cumple" if escritura["p95"] < OBJETIVO_P95_MS else "no cumple"
        lineas += ["", f"Objetivo de registro (p95 < {OBJETIVO_P95_MS} ms en `POST /api/marcaciones`): "
                       f"**{cumple}** ({escritura['p95']:.0f} ms)."]
    return "\n".join(lineas) + "\n\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--escenario", choices=["lectura", "escritura", "mixto"], default="mixto")
    ap.add_argument("--solicitudes", type=int, default=1000)
    ap.add_argument("--concurrencia", type=int, default=25)
    ap.add_argument("--salida", default="docs/resultados-carga.md")
    args = ap.parse_args()

    res = asyncio.run(ejecutar(args.url.rstrip("/"), args.token, args.escenario, args.solicitudes, args.concurrencia))
    md = a_markdown(res)
    print(md)
    nuevo = not os.path.exists(args.salida)
    with open(args.salida, "a", encoding="utf-8") as f:
        if nuevo:
            f.write("# Resultados de las pruebas de carga\n\n"
                    "Generado por `scripts/prueba_carga.py`. Cada corrida se agrega al final.\n\n")
        f.write(md)
    print(f"Resultados agregados a {args.salida}")


if __name__ == "__main__":
    main()
