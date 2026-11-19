"""Utilidades de fecha y hora (zona America/Bogota)."""
from __future__ import annotations

from datetime import date, datetime

from .config import TZ


def ahora() -> datetime:
    return datetime.now(TZ)


def parse(ts: str | datetime) -> datetime:
    """Convierte ISO-8601 a datetime con zona; si no trae zona, asume Bogotá."""
    dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def iso(dt: datetime) -> str:
    return parse(dt).isoformat(timespec="seconds")


def fecha_local(dt: str | datetime) -> str:
    return parse(dt).date().isoformat()


def horas_entre(inicio: str | datetime, fin: str | datetime) -> float:
    return (parse(fin) - parse(inicio)).total_seconds() / 3600.0


def hora_decimal(dt: str | datetime) -> float:
    d = parse(dt)
    return d.hour + d.minute / 60.0


def hoy() -> str:
    return ahora().date().isoformat()


def ayer() -> str:
    return date.fromordinal(ahora().date().toordinal() - 1).isoformat()
