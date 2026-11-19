"""Registro de auditoría: quién hizo qué y cuándo, sobre cada entidad."""
from __future__ import annotations

import uuid

from .tiempo import ahora, iso


def registrar(repo, accion: str, entidad: str, entidad_id: str, actor: str, detalle: dict | None = None) -> None:
    evento_id = str(uuid.uuid4())
    repo.put(
        "auditoria",
        evento_id,
        {
            "id": evento_id,
            "accion": accion,
            "entidad": entidad,
            "entidad_id": entidad_id,
            "actor": actor,
            "detalle": detalle or {},
            "ts": iso(ahora()),
        },
    )
