"""Persistencia documental: Firestore en GCP, memoria en local.

Ambas implementaciones exponen la misma interfaz mínima (patrón repositorio),
así la lógica de negocio no depende del proveedor:

    get(col, id) -> dict | None
    put(col, id, doc)
    create(col, id, doc) -> bool      # False si ya existe (idempotencia)
    update(col, id, campos)
    query(col, filtros) -> list[dict] # filtros: [(campo, op, valor)]

Las consultas usan solo filtros de igualdad / array_contains; el orden se
resuelve en Python para no requerir índices compuestos en Firestore.
"""
from __future__ import annotations

import copy
import threading
from collections.abc import Iterable

Filtro = tuple[str, str, object]

_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "in": lambda a, b: a in b,
    "array_contains": lambda a, b: isinstance(a, list) and b in a,
}


class RepoMemoria:
    def __init__(self) -> None:
        self._datos: dict[str, dict[str, dict]] = {}
        self._lock = threading.Lock()

    def get(self, col: str, id_: str) -> dict | None:
        return copy.deepcopy(self._datos.get(col, {}).get(id_))

    def put(self, col: str, id_: str, doc: dict) -> None:
        with self._lock:
            self._datos.setdefault(col, {})[id_] = copy.deepcopy(doc)

    def create(self, col: str, id_: str, doc: dict) -> bool:
        with self._lock:
            coleccion = self._datos.setdefault(col, {})
            if id_ in coleccion:
                return False
            coleccion[id_] = copy.deepcopy(doc)
            return True

    def update(self, col: str, id_: str, campos: dict) -> None:
        with self._lock:
            self._datos.setdefault(col, {}).setdefault(id_, {}).update(copy.deepcopy(campos))

    def query(self, col: str, filtros: Iterable[Filtro] = ()) -> list[dict]:
        filtros = list(filtros)
        docs = self._datos.get(col, {}).values()
        return [
            copy.deepcopy(d)
            for d in docs
            if all(_OPS[op](d.get(campo), valor) for campo, op, valor in filtros)
        ]


class RepoFirestore:  # pragma: no cover - requiere GCP
    def __init__(self, project_id: str = "") -> None:
        from google.cloud import firestore

        self._fs = firestore
        self.db = firestore.Client(project=project_id or None)

    def get(self, col, id_):
        snap = self.db.collection(col).document(id_).get()
        return snap.to_dict() if snap.exists else None

    def put(self, col, id_, doc):
        self.db.collection(col).document(id_).set(doc)

    def create(self, col, id_, doc):
        from google.api_core.exceptions import AlreadyExists

        try:
            self.db.collection(col).document(id_).create(doc)
            return True
        except AlreadyExists:
            return False

    def update(self, col, id_, campos):
        self.db.collection(col).document(id_).set(campos, merge=True)

    def query(self, col, filtros=()):
        from google.cloud.firestore_v1.base_query import FieldFilter

        q = self.db.collection(col)
        for campo, op, valor in filtros:
            q = q.where(filter=FieldFilter(campo, op, valor))
        return [d.to_dict() for d in q.stream()]
