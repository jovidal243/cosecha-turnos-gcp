"""Autenticación por token Bearer y control de acceso por rol.

Roles: supervisor (registra marcaciones), jefe_frente (aprueba/rechaza),
analista (consulta y asistente IA). Los tokens se guardan en Secret Manager
y se inyectan a Cloud Run como variable de entorno API_TOKENS.
"""
from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, status

from .config import settings


def usuario_actual(request: Request) -> dict:
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token Bearer")
    token = cabecera[7:].strip()
    for valido, rol in settings().api_tokens.items():
        if hmac.compare_digest(token, valido):
            return {"rol": rol, "usuario": f"{rol}:{valido[-4:]}"}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")


def requiere_rol(*roles: str):
    def _dep(usuario: dict = Depends(usuario_actual)) -> dict:
        if roles and usuario["rol"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Rol '{usuario['rol']}' sin permiso")
        return usuario

    return _dep
