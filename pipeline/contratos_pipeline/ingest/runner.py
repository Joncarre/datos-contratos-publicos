"""Runner de ingestión: recorre los ATOM de una fuente y los vuelca a Bronze (Parquet).

Idempotente por hash de fichero: si el Parquet de salida ya existe para ese hash, se omite.
Esto habilita la actualización incremental (solo reprocesas ficheros nuevos/cambiados).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contratos_pipeline.config import Source, bronze_root
from contratos_pipeline.ingest.atom_parser import CANONICAL_FIELDS, parse_atom_file

# Extensiones de fichero de fuente aceptadas.
ATOM_GLOBS = ("*.atom", "*.xml")


@dataclass
class IngestStats:
    source: str
    files_total: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    records: int = 0
    errors: list[str] = field(default_factory=list)


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _derive_year(record: dict[str, Any]) -> int | None:
    for key in ("fecha_adjudicacion", "updated"):
        value = record.get(key)
        if value and len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    return None


def _output_path(source_name: str, file_hash: str) -> Path:
    return bronze_root() / source_name / f"part-{file_hash[:12]}.parquet"


def _write_parquet(rows: list[dict[str, Any]], target: Path) -> None:
    # Import diferido: el parser (solo lxml) se puede usar sin pyarrow instalado.
    import pyarrow as pa
    import pyarrow.parquet as pq

    target.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, target, compression="zstd")


def list_source_files(source: Source) -> list[Path]:
    if not source.input_dir.exists():
        return []
    files: list[Path] = []
    for pattern in ATOM_GLOBS:
        files.extend(source.input_dir.rglob(pattern))
    return sorted(files)


def ingest_file(source: Source, path: Path, *, overwrite: bool = False) -> tuple[int, bool]:
    """Procesa un ATOM a un Parquet Bronze. Devuelve (n_registros, escrito?)."""
    file_hash = sha256_file(path)
    target = _output_path(source.name, file_hash)
    if target.exists() and not overwrite:
        return 0, False

    ingested_at = datetime.now(timezone.utc).isoformat()
    # Columnas estables de metadatos/trazabilidad para todas las filas.
    meta_keys = ("source", "source_file", "source_file_hash", "ingested_at", "year")

    rows: list[dict[str, Any]] = []
    for record in parse_atom_file(path):
        record["source"] = source.name
        record["source_file"] = path.name
        record["source_file_hash"] = file_hash
        record["ingested_at"] = ingested_at
        record["year"] = _derive_year(record)
        # Garantiza esquema homogéneo (todas las claves presentes en todas las filas).
        for key in (*CANONICAL_FIELDS, "payload_json", *meta_keys):
            record.setdefault(key, None)
        rows.append(record)

    if not rows:
        return 0, False

    _write_parquet(rows, target)
    return len(rows), True


def ingest_source(source: Source, *, overwrite: bool = False) -> IngestStats:
    stats = IngestStats(source=source.name)
    files = list_source_files(source)
    stats.files_total = len(files)
    for path in files:
        try:
            n, written = ingest_file(source, path, overwrite=overwrite)
            if written:
                stats.files_processed += 1
                stats.records += n
            else:
                stats.files_skipped += 1
        except Exception as exc:  # noqa: BLE001 - registrar y seguir con el resto
            stats.errors.append(f"{path.name}: {exc}")
    return stats
