"""Fábrica de dependencias según MODO (inyección simple con caché)."""
from __future__ import annotations

from .almacen import RepoFirestore, RepoMemoria
from .analitica import SumideroBigQuery, SumideroLocal
from .config import settings
from .eventos import BusLocal, PublicadorPubSub
from .objetos import AlmacenGCS, AlmacenLocal

_cache: dict[str, object] = {}


def _obtener(nombre: str, local, nube):
    if nombre not in _cache:
        s = settings()
        _cache[nombre] = nube(s) if s.es_gcp else local(s)
    return _cache[nombre]


def repo():
    return _obtener("repo", lambda s: RepoMemoria(), lambda s: RepoFirestore(s.project_id))


def bus():
    return _obtener("bus", lambda s: BusLocal(), lambda s: PublicadorPubSub(s.project_id))


def sumidero():
    return _obtener(
        "sumidero",
        lambda s: SumideroLocal(s.data_dir),
        lambda s: SumideroBigQuery(s.project_id, s.bq_dataset),
    )


def almacen():
    return _obtener(
        "almacen",
        lambda s: AlmacenLocal(s.data_dir),
        lambda s: AlmacenGCS(s.bucket, s.project_id),
    )


def reiniciar() -> None:
    """Limpia las dependencias (usado por las pruebas)."""
    _cache.clear()
