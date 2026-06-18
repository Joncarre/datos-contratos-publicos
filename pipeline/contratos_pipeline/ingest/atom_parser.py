"""Parser de ATOM/CODICE por *streaming*.

Clave para los 137 GB: `iterparse` lee una `<entry>` cada vez y libera memoria tras procesarla,
de modo que el consumo de RAM es constante aunque el fichero tenga cientos de miles de líneas.

La extracción de campos canónicos está dirigida por FIELD_PATHS (rutas de local-names). Es un
punto de ajuste: cuando lleguen las muestras reales se afinan aquí, sin tocar la mecánica.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lxml import etree

from contratos_pipeline.ingest.xml_utils import element_to_dict, first_text, text_at_path

# Rutas candidatas (local-names) relativas a <entry>. Varias por campo = tolerancia a variantes.
# Basado en la estructura CODICE de PLACSP; a confirmar/afinar con muestras reales.
FIELD_PATHS: dict[str, list[list[str]]] = {
    "id_origen": [
        ["ContractFolderStatus", "ContractFolderID"],
    ],
    "estado": [
        ["ContractFolderStatus", "ContractFolderStatusCode"],
    ],
    "organo_nombre": [
        ["ContractFolderStatus", "LocatedContractingParty", "Party", "PartyName", "Name"],
    ],
    "organo_id": [
        ["ContractFolderStatus", "LocatedContractingParty", "Party", "PartyIdentification", "ID"],
    ],
    "objeto": [
        ["ContractFolderStatus", "ProcurementProject", "Name"],
    ],
    "tipo_contrato": [
        ["ContractFolderStatus", "ProcurementProject", "TypeCode"],
    ],
    "cpv": [
        ["ContractFolderStatus", "ProcurementProject", "RequiredCommodityClassification",
         "ItemClassificationCode"],
    ],
    "territorio_code": [
        ["ContractFolderStatus", "ProcurementProject", "RealizedLocation", "CountrySubentityCode"],
    ],
    "importe_licitacion": [
        ["ContractFolderStatus", "ProcurementProject", "BudgetAmount", "TotalAmount"],
        ["ContractFolderStatus", "ProcurementProject", "BudgetAmount", "TaxExclusiveAmount"],
    ],
    "fecha_adjudicacion": [
        ["ContractFolderStatus", "TenderResult", "AwardDate"],
    ],
    "adjudicatario_nombre": [
        ["ContractFolderStatus", "TenderResult", "WinningParty", "PartyName", "Name"],
    ],
    "adjudicatario_id": [
        ["ContractFolderStatus", "TenderResult", "WinningParty", "PartyIdentification", "ID"],
    ],
    "importe_adjudicacion": [
        ["ContractFolderStatus", "TenderResult", "AwardedTenderedProject", "LegalMonetaryTotal",
         "PayableAmount"],
    ],
}

# Campos canónicos siempre presentes en el registro (None si faltan) -> esquema Parquet estable.
CANONICAL_FIELDS: tuple[str, ...] = (
    "entry_id",
    "title",
    "updated",
    *FIELD_PATHS.keys(),
)


def parse_entry(entry: etree._Element) -> dict[str, Any]:
    """Extrae los campos canónicos (best-effort) y conserva el original en `payload_json`."""
    record: dict[str, Any] = {
        "entry_id": text_at_path(entry, ["id"]),
        "title": text_at_path(entry, ["title"]),
        "updated": text_at_path(entry, ["updated"]),
    }
    for field, candidates in FIELD_PATHS.items():
        record[field] = first_text(entry, candidates)

    record["payload_json"] = json.dumps(element_to_dict(entry), ensure_ascii=False)
    return record


def parse_atom_file(path: str | Path) -> Iterator[dict[str, Any]]:
    """Itera registros de un fichero ATOM por streaming, con memoria constante.

    `recover=True` y `huge_tree=True` para tolerar ficheros grandes y ligeramente malformados.
    """
    context = etree.iterparse(
        str(path),
        events=("end",),
        tag="{*}entry",
        recover=True,
        huge_tree=True,
    )
    for _event, elem in context:
        try:
            yield parse_entry(elem)
        finally:
            # Liberar memoria: vaciar la entry y eliminar hermanos ya procesados.
            elem.clear()
            parent = elem.getparent()
            if parent is not None:
                while elem.getprevious() is not None:
                    del parent[0]
    del context
