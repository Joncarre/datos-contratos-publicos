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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
