"""Verifica el parser de streaming contra el fixture sintético (solo requiere lxml)."""

import json
from pathlib import Path

from contratos_pipeline.ingest.atom_parser import parse_atom_file


def test_parses_all_entries(contratos_menores_atom: Path) -> None:
    records = list(parse_atom_file(contratos_menores_atom))
    assert len(records) == 2


def test_extracts_canonical_fields(contratos_menores_atom: Path) -> None:
    first = list(parse_atom_file(contratos_menores_atom))[0]

    assert first["id_origen"] == "EXP-2021-0001"
    assert first["organo_nombre"] == "Ayuntamiento de Ejemplo"
    assert first["organo_id"] == "P2807900B"
    assert "limpieza" in first["objeto"].lower()
    assert first["cpv"] == "90910000"
    assert first["territorio_code"] == "ES300"
    assert first["adjudicatario_nombre"] == "Limpiezas Ejemplo S.L."
    assert first["adjudicatario_id"] == "B12345678"
    assert float(first["importe_adjudicacion"]) == 14350.00
    assert float(first["importe_licitacion"]) == 14500.00
    assert first["fecha_adjudicacion"] == "2021-03-10"


def test_tolerates_missing_award(contratos_menores_atom: Path) -> None:
    """La segunda entrada no tiene TenderResult: los campos de adjudicación deben ser None."""
    second = list(parse_atom_file(contratos_menores_atom))[1]

    assert second["id_origen"] == "EXP-2021-0002"
    assert second["adjudicatario_nombre"] is None
    assert second["adjudicatario_id"] is None
    assert second["importe_adjudicacion"] is None
    # Pero el de licitación sí está presente.
    assert float(second["importe_licitacion"]) == 5000.00


def test_payload_is_preserved(contratos_menores_atom: Path) -> None:
    first = list(parse_atom_file(contratos_menores_atom))[0]
    payload = json.loads(first["payload_json"])
    assert "ContractFolderStatus" in payload
    # El texto original se conserva en profundidad.
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "Limpiezas Ejemplo S.L." in dumped
