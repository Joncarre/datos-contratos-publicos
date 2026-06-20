"""CLI del pipeline (Typer). Punto de entrada: `python -m contratos_pipeline`."""

from __future__ import annotations

import json
import os
import sys
from itertools import islice

import typer
from rich.console import Console
from rich.table import Table

from contratos_pipeline import config
from contratos_pipeline.aggregate.marts import build_marts
from contratos_pipeline.ingest.atom_parser import parse_atom_file
from contratos_pipeline.ingest.runner import ingest_source

# En consolas Windows legacy (cp1252) forzamos UTF-8: evita mojibake y UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

app = typer.Typer(
    add_completion=False,
    help="Pipeline de contratación pública: ATOM/CODICE -> Parquet -> marts.",
)
console = Console()


@app.command()
def info() -> None:
    """Muestra rutas y fuentes configuradas."""
    console.print(f"[bold]repo_root[/]      {config.repo_root()}")
    console.print(f"[bold]data_root[/]      {config.data_root()}")
    console.print(f"[bold]bronze_root[/]    {config.bronze_root()}")
    table = Table("fuente", "subcarpeta", "cobertura", "existe", title="Fuentes")
    for src in config.SOURCES.values():
        table.add_row(
            src.name, src.subpath, str(src.coverage_from),
            "sí" if src.input_dir.exists() else "no",
        )
    console.print(table)


@app.command("parse-file")
def parse_file(
    path: str = typer.Argument(..., help="Ruta a un fichero .atom"),
    limit: int = typer.Option(3, help="Número de entradas a mostrar"),
) -> None:
    """Inspecciona las primeras entradas de un ATOM (para validar contra muestras reales)."""
    for i, record in enumerate(islice(parse_atom_file(path), limit), start=1):
        preview = {k: v for k, v in record.items() if k != "payload_json"}
        console.rule(f"entry {i}")
        console.print_json(json.dumps(preview, ensure_ascii=False))


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Nombre de fuente: " + ", ".join(config.SOURCES)),
    overwrite: bool = typer.Option(False, help="Reprocesar aunque ya exista el Parquet"),
    workers: int = typer.Option(os.cpu_count() or 4, help="Procesos en paralelo (1 = secuencial)"),
) -> None:
    """Ingesta una fuente completa a Bronze (Parquet)."""
    src = config.get_source(source)
    if not src.input_dir.exists():
        console.print(f"[yellow]No existe {src.input_dir}. Coloca ahí los ATOM y reintenta.[/]")
        raise typer.Exit(code=1)

    console.print(f"Ingestando [bold]{src.name}[/] desde {src.input_dir} · {workers} workers ...")
    last = {"pct": -1}

    def progress(done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 100
        if pct >= last["pct"] + 10 or done == total:
            last["pct"] = pct
            console.print(f"  {done}/{total} ({pct}%)")

    stats = ingest_source(src, overwrite=overwrite, workers=workers, on_progress=progress)

    console.print(
        f"[bold green]{stats.source}[/]: {stats.records} registros · "
        f"{stats.files_processed} ficheros nuevos · {stats.files_skipped} omitidos · "
        f"{stats.files_total} totales · {len(stats.errors)} errores"
    )
    for err in stats.errors[:10]:
        console.print(f"[red]error[/] {err}")


@app.command()
def marts() -> None:
    """Construye los marts Gold (JSON en web/public/data + Parquet en _gold) desde el Bronze."""
    console.print("Construyendo marts desde el Bronze ...")
    counts = build_marts()
    for name, n in counts.items():
        console.print(f"  [bold green]{name}[/]: {n} filas -> web/public/data/{name}.json")
    console.print(f"Destino: {config.web_data_dir()}")


@app.command()
def compact() -> None:
    """Compacta el Bronze (miles de Parquet diminutos -> 1 por fuente) para acelerar los marts."""
    import duckdb

    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    out = config.bronze_compact_root()
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for src in config.SOURCES:
        src_dir = config.bronze_root() / src
        files = list(src_dir.glob("*.parquet")) if src_dir.exists() else []
        if not files:
            continue
        src_glob = (src_dir / "*.parquet").as_posix()
        target = (out / f"{src}.parquet").as_posix()
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{src_glob}', union_by_name=true)) "
            f"TO '{target}' (FORMAT PARQUET, COMPRESSION zstd)"
        )
        n = con.execute(f"SELECT count(*) FROM read_parquet('{target}')").fetchone()[0]
        total += n
        console.print(f"  [bold green]{src}[/]: {len(files)} ficheros -> 1 ({n:,} filas)")
    console.print(f"Bronze compactado en {out} · {total:,} filas. Los marts ya lo usarán.")


@app.command()
def silver() -> None:
    """Materializa la capa Silver: expedientes canónicos consultables, con procedencia."""
    from contratos_pipeline.aggregate.marts import build_silver

    console.print("Materializando Silver (dedup canónico) ...")
    n = build_silver()
    dest = config.processed_root() / "_silver" / "contratos.parquet"
    console.print(f"[bold green]Silver[/]: {n:,} expedientes -> {dest}")


@app.command("index-files")
def index_files() -> None:
    """Indexa los ficheros ATOM en disco (carpeta/año + nombre) para resolver rutas exactas."""
    from contratos_pipeline.query import build_file_manifest

    n = build_file_manifest()
    console.print(f"[bold green]Manifiesto[/]: {n:,} ficheros .atom indexados")


@app.command("web-index")
def web_index() -> None:
    """Exporta el índice consultable por el navegador (DuckDB-WASM) a web/public/data/contratos.parquet."""
    from contratos_pipeline.query import export_web_index

    console.print("Exportando índice del navegador (puede tardar) ...")
    n = export_web_index()
    dest = config.web_data_dir() / "contratos.parquet"
    console.print(f"[bold green]Índice navegador[/]: {n:,} contratos -> {dest}")


def _print_contratos(rows: list) -> None:
    if not rows:
        console.print("[yellow]Sin resultados.[/]")
        return
    table = Table("importe", "id_origen", "adjudicatario", "órgano", "fuente/año", "fichero")
    for r in rows:
        imp = r.get("importe")
        table.add_row(
            f"{imp:,.0f}" if imp is not None else "-",
            (r.get("id_origen") or "-")[:22],
            (r.get("adjudicatario_nombre") or "-")[:26],
            (r.get("organo_nombre") or "-")[:26],
            f"{(r.get('source') or '')[:6]}/{r.get('year') or ''}",
            (r.get("fichero") or "?")[:48],
        )
    console.print(table)
    console.print(f"[dim]{len(rows)} resultado(s).[/]")


@app.command()
def find(
    id: str = typer.Option(None, help="id de expediente (ContractFolderID) exacto"),
    adjudicatario: str = typer.Option(None, help="adjudicatario (subcadena)"),
    organo: str = typer.Option(None, help="órgano (subcadena)"),
    nif: str = typer.Option(None, help="NIF de adjudicatario u órgano"),
    objeto: str = typer.Option(None, help="objeto del contrato (subcadena)"),
    cpv: str = typer.Option(None, help="prefijo de CPV"),
    ccaa: str = typer.Option(None, help="CCAA (subcadena)"),
    source: str = typer.Option(None, help="fuente: " + ", ".join(config.SOURCES)),
    estado: str = typer.Option(None, help="estado (RES, ADJ, PUB, EV, ...)"),
    year: int = typer.Option(None, help="año"),
    min_importe: float = typer.Option(None, "--min-importe", help="importe mínimo"),
    max_importe: float = typer.Option(None, "--max-importe", help="importe máximo"),
    revisar: bool = typer.Option(False, help="solo contratos 'a verificar'"),
    acuerdo_marco: bool = typer.Option(False, "--acuerdo-marco", help="solo acuerdos marco"),
    limit: int = typer.Option(40, help="máximo de resultados"),
) -> None:
    """Busca contratos por filtros sobre la capa Silver, con su fichero de origen."""
    from contratos_pipeline.query import find_contracts

    filters = {
        "id": id, "adjudicatario": adjudicatario, "organo": organo, "nif": nif,
        "objeto": objeto, "cpv": cpv, "ccaa": ccaa, "source": source, "estado": estado,
        "year": year, "min_importe": min_importe, "max_importe": max_importe,
        "solo_revisar": revisar, "solo_acuerdo_marco": acuerdo_marco,
    }
    _print_contratos(find_contracts(filters, limit=limit))


@app.command()
def stats(
    adjudicatario: str = typer.Option(None, help="adjudicatario (subcadena)"),
    organo: str = typer.Option(None, help="órgano (subcadena)"),
    nif: str = typer.Option(None, help="NIF de adjudicatario u órgano"),
    objeto: str = typer.Option(None, help="objeto del contrato (subcadena)"),
    cpv: str = typer.Option(None, help="prefijo de CPV"),
    ccaa: str = typer.Option(None, help="CCAA (subcadena)"),
    source: str = typer.Option(None, help="fuente: " + ", ".join(config.SOURCES)),
    estado: str = typer.Option(None, help="estado (RES, ADJ, PUB, EV, ...)"),
    year: int = typer.Option(None, help="año"),
    min_importe: float = typer.Option(None, "--min-importe", help="importe mínimo"),
    max_importe: float = typer.Option(None, "--max-importe", help="importe máximo"),
    revisar: bool = typer.Option(False, help="solo 'a verificar'"),
    acuerdo_marco: bool = typer.Option(False, "--acuerdo-marco", help="solo acuerdos marco"),
) -> None:
    """Conclusiones agregadas sobre el subconjunto filtrado (total, top adjudicatarios, por año)."""
    from contratos_pipeline.query import aggregate_stats

    filters = {
        "adjudicatario": adjudicatario, "organo": organo, "nif": nif, "objeto": objeto,
        "cpv": cpv, "ccaa": ccaa, "source": source, "estado": estado, "year": year,
        "min_importe": min_importe, "max_importe": max_importe,
        "solo_revisar": revisar, "solo_acuerdo_marco": acuerdo_marco,
    }
    s = aggregate_stats(filters)
    t = s["total"]
    console.print(
        f"[bold]Contratos[/] {t[0]:,} · [bold]Importe[/] {(t[1] or 0):,.0f} EUR · "
        f"adjudicatarios {t[2]:,} · órganos {t[3]:,} · a verificar {t[4]:,} · "
        f"acuerdos marco {t[5]:,}"
    )
    tadj = Table("importe", "contratos", "adjudicatario", title="Top adjudicatarios")
    for nombre, imp, n in s["top_adjudicatarios"]:
        tadj.add_row(f"{(imp or 0):,.0f}", f"{n:,}", (nombre or "-")[:42])
    console.print(tadj)
    tyear = Table("año", "contratos", "importe", title="Por año")
    for y, n, imp in s["por_anio"]:
        tyear.add_row(str(y), f"{n:,}", f"{(imp or 0):,.0f}")
    console.print(tyear)


@app.command()
def inspect(
    id: str = typer.Argument(..., help="id de expediente (ContractFolderID)"),
    source: str = typer.Option(None, help="acotar a una fuente"),
) -> None:
    """Ficha completa de un contrato + su fichero ATOM de origen (carpeta y nombre)."""
    from contratos_pipeline.query import inspect_contract

    rows = inspect_contract(id, source)
    if not rows:
        console.print(f"[yellow]No se encontró el expediente {id!r}.[/]")
        raise typer.Exit(code=1)
    fields = [
        "estado", "organo_nombre", "organo_nif", "organo_nivel", "ccaa", "territorio_nombre",
        "objeto", "cpv", "tipo_contrato", "importe", "importe_adjudicado",
        "importe_total_con_iva", "importe_sin_iva", "fecha_adjudicacion", "year",
        "adjudicatario_nombre", "adjudicatario_nif", "es_acuerdo_marco", "revisar_importe",
    ]
    for r in rows:
        console.rule(f"{r.get('id_origen')} · {r.get('source')}")
        for k in fields:
            v = r.get(k)
            if v is not None and v != "":
                console.print(f"  [bold]{k}[/]  {v}")
        console.print(f"  [bold]link PLACSP[/]  {r.get('link_detalle')}")
        console.print(f"  [bold cyan]FICHERO[/]  {r.get('fichero')}")
        cands = r.get("ficheros_candidatos") or []
        if len(cands) > 1:
            console.print(f"  [dim]otros candidatos: {', '.join(cands)}[/]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
