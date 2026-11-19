"""Cálculo de distancia para la geocerca de cada frente de cosecha."""
from __future__ import annotations

import math

RADIO_TIERRA_M = 6_371_000


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine en metros."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


def distancia_a_frente(lat: float | None, lon: float | None, frente: dict | None) -> float | None:
    if lat is None or lon is None or not frente:
        return None
    return round(distancia_m(lat, lon, frente["lat"], frente["lon"]), 1)
