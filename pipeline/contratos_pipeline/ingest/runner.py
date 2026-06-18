"""Runner de ingestión: recorre los ATOM de una fuente y los vuelca a Bronze (Parquet).

- Idempotente por hash de fichero: si el Parquet de salida ya existe para ese hash, se omite
  (habilita la actualización incremental: solo reprocesas ficheros nuevos/cambiados).
- Esquema Parquet explícito y fijo: garantiza tipos consistentes entre miles de ficheros,
  para poder leerlos con un único `read_parquet('.../*.parquet')` en DuckDB.
- Paralelizable por fichero (los ficheros son independientes): un worker por núcleo.
"""

from __future__ import annotations

import hashlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contratos_pipeline.config import Source, bronze_root
from contratos_pipeline.ingest.atom_parser import CANONICAL_FIELDS, FIELD_TYPES, parse_atom_file

ATOM_GLOBS = ("*.atom",)

# Metadatos de trazabilidad que añade el runner a cada fila.
META_TYPES: dict[str, str] = {
    "source": "str",
    "source_file": "str",
    "source_file_hash": "str",
    "ingested_at": "str",
    "year": "int",
}


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


def _arrow_schema():
    import pyarrow as pa

    type_map = {"str": pa.string(), "float": pa.float64(), "int": pa.int64()}
    fields = [pa.field(name, type_map[t]) for name, t in FIELD_TYPES.items()]
    fields += [pa.field(name, type_map[t]) for name, t in META_TYPES.items()]
    return pa.schema(fields)


def _derive_year(record: dict[str, Any]) -> int | None:
    # `updated` (timestamp de sindicación) es siempre ISO y fiable; `fecha_adjudicacion`
    # (AwardDate) puede venir vacía o malformada en origen, así que va de respaldo.
    for key in ("updated", "fecha_adjudicacion"):
        value = record.get(key)
        if value and len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    return None


def _output_path(source_name: str, file_hash: str) -> Path:
    return bronze_root() / source_name / f"part-{file_hash[:12]}.parquet"


def ingest_file(source: Source, path: Path, *, overwrite: bool = False) -> tuple[int, bool]:
    """Procesa un ATOM a un Parquet Bronze. Devuelve (n_registros, escrito?)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    file_hash = sha256_file(path)
    target = _output_path(source.name, file_hash)
    if target.exists() and not overwrite:
        return 0, False

    ingested_at = datetime.now(timezone.utc).isoformat()
    all_keys = (*CANONICAL_FIELDS, *META_TYPES.keys())

    rows: list[dict[str, Any]] = []
    for record in parse_atom_file(path):
        record["source"] = source.name
        record["source_file"] = path.name
        record["source_file_hash"] = file_hash
        record["ingested_at"] = ingested_at
        record["year"] = _derive_year(record)
        for key in all_keys:
            record.setdefault(key, None)
        rows.append(record)

    if not rows:
        return 0, False

    target.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=_arrow_schema())
    pq.write_table(table, target, compression="zstd")
    return len(rows), True


def list_source_files(source: Source) -> list[Path]:
    if not source.input_dir.exists():
        return []
    files: list[Path] = []
    for pattern in ATOM_GLOBS:
        files.extend(source.input_dir.rglob(pattern))
    return sorted(files)


def ingest_source(
    source: Source,
    *,
    overwrite: bool = False,
    workers: int = 1,
    on_progress=None,
) -> IngestStats:
    stats = IngestStats(source=source.name)
    files = list_source_files(source)
    stats.files_total = len(files)

    def _record(path: Path, result: tuple[int, bool] | None, error: str | None) -> None:
        if error is not None:
            stats.errors.append(f"{path.name}: {error}")
        elif result is not None:
            n, written = result
            if written:
                stats.files_processed += 1
                stats.records += n
            else:
                stats.files_skipped += 1
        if on_progress is not None:
            done = stats.files_processed + stats.files_skipped + len(stats.errors)
            on_progress(done, stats.files_total)

    if workers and workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(ingest_file, source, path, overwrite=overwrite): path
                for path in files
            }
            for fut in as_completed(futures):
                path = futures[fut]
                try:
                    _record(path, fut.result(), None)
                except Exception as exc:  # noqa: BLE001 - registrar y continuar
                    _record(path, None, str(exc))
    else:
        for path in files:
            try:
                _record(path, ingest_file(source, path, overwrite=overwrite), None)
            except Exception as exc:  # noqa: BLE001
                _record(path, None, str(exc))

    return stats
