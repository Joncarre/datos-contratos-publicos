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


def export_web_index() -> int:
    """Exporta el índice consultable por el navegador (DuckDB-WASM) a web/public/data/contratos.parquet.

    Columnas de investigación (sin `objeto`, para acotar tamaño) + `fichero` (ruta exacta del .atom,
    horneada uniendo el manifiesto). Row-groups de 100k para *range requests* eficientes.
    """
    import duckdb

    silver = silver_path()
    if not silver.exists():
        raise FileNotFoundError("No existe la capa Silver. Ejecuta primero: `silver`.")
    out = config.web_data_dir() / "contratos.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    man = manifest_path()
    if man.exists():
        m = f"read_parquet('{man.as_posix()}')"
        joins = (
            f" LEFT JOIN (SELECT source, basename, year_folder, relpath FROM {m}) me "
            f"   ON me.source = s.source AND me.basename = s.source_file AND me.year_folder = s.year"
            f" LEFT JOIN (SELECT source, basename, any_value(relpath) AS relpath FROM {m} "
            f"            GROUP BY source, basename) ma "
            f"   ON ma.source = s.source AND ma.basename = s.source_file"
        )
        fichero = "COALESCE(me.relpath, ma.relpath)"
    else:
        joins, fichero = "", "NULL"

    con.execute(f"""
        COPY (
            SELECT s.id_origen, s.source, s.source_file, {fichero} AS fichero, s.estado, s.year,
                   s.organo_nombre, s.organo_nif, s.org_id, s.organo_nivel, s.ccaa,
                   s.cpv, s.tipo_contrato, s.adjudicatario_nombre, s.adjudicatario_nif, s.adj_id,
                   s.fecha_adjudicacion, s.importe, s.importe_adjudicado,
                   s.importe_total_con_iva, s.importe_sin_iva,
                   s.es_acuerdo_marco, s.revisar_importe, s.link_detalle
            FROM read_parquet('{silver.as_posix()}') s
            {joins}
        ) TO '{out.as_posix()}' (FORMAT PARQUET, COMPRESSION zstd, ROW_GROUP_SIZE 100000)
    """)
    return con.execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0]


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


def _build_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
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
    return where, params


def find_contracts(filters: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    silver = silver_path()
    if not silver.exists():
        raise FileNotFoundError("No existe la capa Silver. Ejecuta primero: `silver`.")
    where, params = _build_where(filters)
    sql = (
        f"SELECT * FROM read_parquet('{silver.as_posix()}'){where} "
        f"ORDER BY importe DESC NULLS LAST LIMIT {int(limit)}"
    )
    return _query(sql, params)


def aggregate_stats(filters: dict[str, Any]) -> dict[str, Any]:
    """Conclusiones agregadas sobre el subconjunto filtrado (sobre la capa Silver canónica)."""
    import duckdb

    silver = silver_path()
    if not silver.exists():
        raise FileNotFoundError("No existe la capa Silver. Ejecuta primero: `silver`.")
    where, params = _build_where(filters)
    con = duckdb.connect()
    con.execute(
        f"CREATE TEMP TABLE f AS SELECT * FROM read_parquet('{silver.as_posix()}'){where}", params
    )
    total = con.execute("""
        SELECT count(*) AS contratos,
               round(sum(importe), 2) AS importe,
               count(DISTINCT adj_id) AS adjudicatarios,
               count(DISTINCT org_id) AS organos,
               count(*) FILTER (WHERE revisar_importe) AS a_verificar,
               count(*) FILTER (WHERE es_acuerdo_marco) AS acuerdos_marco
        FROM f
    """).fetchone()
    top_adj = con.execute("""
        SELECT any_value(adjudicatario_nombre) AS nombre, round(sum(importe), 2) AS importe,
               count(*) AS contratos
        FROM f WHERE adj_id IS NOT NULL
        GROUP BY adj_id ORDER BY importe DESC NULLS LAST LIMIT 10
    """).fetchall()
    por_anio = con.execute("""
        SELECT year, count(*) AS contratos, round(sum(importe), 2) AS importe
        FROM f WHERE year BETWEEN 2012 AND 2026 GROUP BY year ORDER BY year
    """).fetchall()
    return {"total": total, "top_adjudicatarios": top_adj, "por_anio": por_anio}


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
