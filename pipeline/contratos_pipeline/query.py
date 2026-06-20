"""Investigación a nivel de contrato sobre la capa Silver (expedientes canónicos).

`find`  — busca contratos por filtros (id, adjudicatario, órgano, importe, CPV, CCAA, año, ...).
`inspect` — ficha completa de un expediente.
Ambos resuelven el **fichero ATOM de origen y su carpeta**, para verificar el dato en disco.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contratos_pipeline import config


def silver_path() -> Path:
    return config.processed_root() / "_silver" / "contratos.parquet"


def manifest_path() -> Path:
    return config.processed_root() / "_silver" / "file_manifest.parquet"


def build_file_manifest() -> int:
    """Indexa los .atom en disco: (source, basename, año-carpeta, ruta relativa, tamaño)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for src in config.SOURCES.values():
        if not src.input_dir.exists():
            continue
        for path in src.input_dir.rglob("*.atom"):
            year_folder = path.parent.name
            rows.append({
                "source": src.name,
                "basename": path.name,
                "year_folder": int(year_folder) if year_folder.isdigit() else None,
                "relpath": path.relative_to(config.data_root()).as_posix(),
                "size_mb": round(path.stat().st_size / 1e6, 2),
            })

    out = manifest_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), out.as_posix())
    return len(rows)


def _load_manifest(con) -> dict[tuple[str, str], list[tuple[int | None, str]]]:
    m = manifest_path()
    if not m.exists():
        return {}
    cur = con.execute(
        f"SELECT source, basename, year_folder, relpath FROM read_parquet('{m.as_posix()}')"
    )
    out: dict[tuple[str, str], list[tuple[int | None, str]]] = {}
    for source, basename, year_folder, relpath in cur.fetchall():
        out.setdefault((source, basename), []).append((year_folder, relpath))
    return out


def _attach_files(con, rows: list[dict[str, Any]]) -> None:
    """Añade a cada fila la ruta del fichero origen (prefiriendo la carpeta del año del contrato)."""
    man = _load_manifest(con)
    for r in rows:
        cands = man.get((r.get("source"), r.get("source_file")), [])
        best = next((rel for yf, rel in cands if yf == r.get("year")), None)
        if best is None and cands:
            best = cands[0][1]
        r["fichero"] = best
        r["ficheros_candidatos"] = [rel for _, rel in cands]


_FILTERS = [
    # (clave, expresión SQL con ?, transform del valor)
    ("id", "id_origen = ?", str),
    ("adjudicatario", "adjudicatario_nombre ILIKE ?", lambda v: f"%{v}%"),
    ("organo", "organo_nombre ILIKE ?", lambda v: f"%{v}%"),
    ("objeto", "objeto ILIKE ?", lambda v: f"%{v}%"),
    ("cpv", "cpv LIKE ?", lambda v: f"{v}%"),
    ("ccaa", "ccaa ILIKE ?", lambda v: f"%{v}%"),
    ("source", "source = ?", str),
    ("estado", "estado = ?", str),
    ("year", "year = ?", int),
    ("min_importe", "importe >= ?", float),
    ("max_importe", "importe <= ?", float),
]


def _query(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    import duckdb

    con = duckdb.connect()
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    _attach_files(con, rows)
    return rows


def find_contracts(filters: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    silver = silver_path()
    if not silver.exists():
        raise FileNotFoundError("No existe la capa Silver. Ejecuta primero: `silver`.")

    conds: list[str] = []
    params: list[Any] = []
    for key, expr, cast in _FILTERS:
        val = filters.get(key)
        if val is None:
            continue
        conds.append(expr)
        params.append(cast(val))
    if filters.get("nif"):
        conds.append("(adjudicatario_nif = ? OR organo_nif = ?)")
        params += [filters["nif"], filters["nif"]]
    if filters.get("solo_revisar"):
        conds.append("revisar_importe")
    if filters.get("solo_acuerdo_marco"):
        conds.append("es_acuerdo_marco")

    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = (
        f"SELECT * FROM read_parquet('{silver.as_posix()}'){where} "
        f"ORDER BY importe DESC NULLS LAST LIMIT {int(limit)}"
    )
    return _query(sql, params)


def inspect_contract(id_origen: str, source: str | None = None) -> list[dict[str, Any]]:
    silver = silver_path()
    if not silver.exists():
        raise FileNotFoundError("No existe la capa Silver. Ejecuta primero: `silver`.")
    conds = ["id_origen = ?"]
    params: list[Any] = [id_origen]
    if source:
        conds.append("source = ?")
        params.append(source)
    sql = (
        f"SELECT * FROM read_parquet('{silver.as_posix()}') "
        f"WHERE {' AND '.join(conds)} ORDER BY importe DESC NULLS LAST LIMIT 20"
    )
    return _query(sql, params)
