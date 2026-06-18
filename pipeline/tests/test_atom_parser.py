"""Verifica el parser contra el fixture sintético con estructura CODICE real (solo requiere lxml)."""

from pathlib import Path

from contratos_pipeline.ingest.atom_parser import parse_atom_file


def _records(path: Path) -> list[dict]:
    return list(parse_atom_file(path))


def test_skips_deleted_entries_and_parses_two(contratos_menores_atom: Path) -> None:
    # El feed tiene un <at:deleted-entry> que NO debe contarse como entry.
    assert len(_records(contratos_menores_atom)) == 2


def test_organo_picks_nif_not_dir3(contratos_menores_atom: Path) -> None:
    first = _records(contratos_menores_atom)[0]
    assert first["organo_nombre"] == "Ayuntamiento de Ejemplo"
    assert first["organo_nif"] == "P2807900B"          # NIF, no el primer ID (DIR3)
    assert first["organo_dir3"] == "L01280796"
    assert first["organo_id"] == "P2807900B"           # id genérico prefiere NIF
    assert first["organo_ciudad"] == "Madrid"


def test_summary_digest_parsed(contratos_menores_atom: Path) -> None:
    first = _records(contratos_menores_atom)[0]
    assert first["sum_id"] == "EXP-2021-0001"
    assert first["sum_organo"] == "Ayuntamiento de Ejemplo"
    assert first["sum_importe"] == 14500.00
    assert first["sum_estado"] == "RES"


def test_object_amounts_territory_and_hierarchy(contratos_menores_atom: Path) -> None:
    first = _records(contratos_menores_atom)[0]
    assert first["id_origen"] == "EXP-2021-0001"
    assert first["estado"] == "RES"
    assert "limpieza" in first["objeto"].lower()
    assert first["tipo_contrato"] == "2"
    assert first["cpv"] == "90910000"
    assert first["territorio_nombre"] == "Madrid"
    assert first["territorio_code"] == "ES300"
    assert first["importe_total_con_iva"] == 14500.00
    assert first["importe_sin_iva"] == 11983.47
    assert "Madrid" in first["admin_hierarchy"]


def test_award_extracted(contratos_menores_atom: Path) -> None:
    first = _records(contratos_menores_atom)[0]
    assert first["n_resultados"] == 1
    assert first["fecha_adjudicacion"] == "2021-03-10"
    assert first["adjudicatario_nombre"] == "Limpiezas Ejemplo S.L."
    assert first["adjudicatario_nif"] == "B12345678"
    assert first["adjudicatario_id"] == "B12345678"
    assert first["importe_adjudicado"] == 14350.00
    assert first["importe_adjudicado_sin_iva"] == 11859.50


def test_tolerates_missing_award(contratos_menores_atom: Path) -> None:
    second = _records(contratos_menores_atom)[1]
    assert second["id_origen"] == "EXP-2021-0002"
    assert second["estado"] == "EV"
    assert second["n_resultados"] == 0
    assert second["adjudicatario_nombre"] is None
    assert second["importe_adjudicado"] is None
    assert second["importe_total_con_iva"] == 5000.00
