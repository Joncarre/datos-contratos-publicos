"""Configuración de rutas y fuentes. Sin estado: todo se deriva de la raíz del repo o de env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def repo_root() -> Path:
    """Raíz del repo = dos niveles por encima de este fichero (pipeline/contratos_pipeline/)."""
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    return Path(os.environ.get("DATA_ROOT") or (repo_root() / "data")).resolve()


def processed_root() -> Path:
    return Path(os.environ.get("PROCESSED_ROOT") or (data_root() / "_processed")).resolve()


def bronze_root() -> Path:
    return processed_root() / "_bronze"


@dataclass(frozen=True)
class Source:
    name: str
    subpath: str  # relativo a data_root()
    coverage_from: int  # primer año con cobertura

    @property
    def input_dir(self) -> Path:
        return data_root() / self.subpath


# Las cuatro fuentes del proyecto, en orden de prioridad analítica.
SOURCES: dict[str, Source] = {
    "contratos_menores": Source("contratos_menores", "contratos_menores", 2018),
    "perfil_contratante": Source("perfil_contratante", "placsp/perfil_contratante", 2012),
    "agregaciones": Source("agregaciones", "placsp/agregaciones", 2016),
    "encargos": Source("encargos", "placsp/encargos", 2022),
}


def get_source(name: str) -> Source:
    try:
        return SOURCES[name]
    except KeyError:
        valid = ", ".join(SOURCES)
        raise ValueError(f"Fuente desconocida: {name!r}. Válidas: {valid}") from None
