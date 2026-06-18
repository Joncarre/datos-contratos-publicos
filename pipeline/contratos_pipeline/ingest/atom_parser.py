"""Parser de ATOM/CODICE por *streaming*.

Clave para los 137 GB: `iterparse` lee una `<entry>` cada vez y libera memoria tras procesarla,
de modo que el consumo de RAM es constante aunque el fichero tenga cientos de miles de líneas.

Extrae ~35 columnas tipadas y acotadas (NO un volcado JSON gigante): los `.atom` originales en
disco siguen siendo la capa cruda inmutable, así que el Parquet puede ser pequeño y eficiente.
El esquema CODICE es común a las 4 fuentes (ContractFolderStatus); las diferencias son qué
bloques opcionales aparecen, no las rutas.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lxml import etree

from contratos_pipeline.ingest.xml_utils import (
    attr_by_local,
    child_by_local,
    descendants_by_local,
    text_at_path,
)

# Columnas canónicas del Bronze (sin metadatos de trazabilidad, que añade el runner).
# tipo: "str" | "float" | "int"  -> usado para fijar el esquema Parquet (consistencia entre ficheros).
FIELD_TYPES: dict[str, str] = {
    # entry-level
    "entry_id": "str",
    "link_detalle": "str",
    "title": "str",
    "updated": "str",
    "summary": "str",
    # digest del <summary> (cruce robusto)
    "sum_id": "str",
    "sum_organo": "str",
    "sum_importe": "float",
    "sum_estado": "str",
    # ContractFolderStatus
    "id_origen": "str",
    "estado": "str",
    # órgano de contratación
    "organo_nombre": "str",
    "organo_id": "str",  # identificador genérico (NIF>DIR3>ID_OC_PLAT>ID_PLATAFORMA), clave de dedup
    "organo_nif": "str",
    "organo_dir3": "str",
    "organo_id_plataforma": "str",
    "organo_id_oc_plat": "str",
    "organo_ciudad": "str",
    "organo_cp": "str",
    "poder_tipo": "str",
    "actividad": "str",
    "admin_hierarchy": "str",
    # objeto del contrato
    "objeto": "str",
    "tipo_contrato": "str",
    "subtipo_contrato": "str",
    "importe_estimado": "float",
    "importe_sin_iva": "float",
    "importe_total_con_iva": "float",
    "cpv": "str",
    "territorio_nombre": "str",
    "territorio_code": "str",
    # resultado / adjudicación
    "n_resultados": "int",
    "result_code": "str",
    "fecha_adjudicacion": "str",
    "adjudicatario_nombre": "str",
    "adjudicatario_id": "str",
    "adjudicatario_nif": "str",
    "importe_adjudicado": "float",
    "importe_adjudicado_sin_iva": "float",
}

CANONICAL_FIELDS: tuple[str, ...] = tuple(FIELD_TYPES.keys())

# "Id licitación: X; Órgano de Contratación: Y; Importe: Z EUR; Estado: W"
# \w abarca letras acentuadas en modo unicode, así toleramos licitación/encargo y Órgano.
SUMMARY_RE = re.compile(
    r"Id\s+\w+:\s*(?P<id>.*?);\s*"
    r"\wrgano de Contrataci\wn:\s*(?P<organo>.*?);\s*"
    r"Importe:\s*(?P<importe>[-\d.,]*)\s*EUR;\s*"
    r"Estado:\s*(?P<estado>.+?)\s*$"
)


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(" ", ""))
    except (ValueError, AttributeError):
        return None


def _ids_by_scheme(party: etree._Element | None) -> dict[str, str]:
    """{'NIF': '...', 'DIR3': '...', 'ID_PLATAFORMA': '...'} a partir de los PartyIdentification."""
    out: dict[str, str] = {}
    if party is None:
        return out
    for child in party:
        if child.tag.rsplit("}", 1)[-1] != "PartyIdentification":
            continue
        idel = child_by_local(child, "ID")
        if idel is None or idel.text is None:
            continue
        scheme = attr_by_local(idel, "schemeName") or "_"
        out.setdefault(scheme, idel.text.strip())
    return out


def _best_id(ids: dict[str, str]) -> str | None:
    """Identificador preferente del órgano/adjudicatario, tolerante a fuentes sin NIF.

    Las plataformas agregadas (p. ej. contractaciopublica.cat) no traen NIF sino ID_OC_PLAT.
    """
    for scheme in ("NIF", "DIR3", "ID_OC_PLAT", "ID_PLATAFORMA"):
        if ids.get(scheme):
            return ids[scheme]
    return next(iter(ids.values()), None)


def _admin_chain(lcp: etree._Element | None) -> list[str]:
    """Cadena ParentLocatedParty: [municipio, tipo, provincia, CCAA, ..., Sector Público]."""
    names: list[str] = []
    node = child_by_local(lcp, "ParentLocatedParty")
    while node is not None:
        name = text_at_path(node, ["PartyName", "Name"])
        if name:
            names.append(name)
        node = child_by_local(node, "ParentLocatedParty")
    return names


def _empty_record() -> dict[str, Any]:
    rec = dict.fromkeys(CANONICAL_FIELDS, None)
    rec["n_resultados"] = 0
    return rec


def parse_entry(entry: etree._Element) -> dict[str, Any]:
    rec = _empty_record()

    # --- entry-level ---
    rec["entry_id"] = text_at_path(entry, ["id"])
    rec["link_detalle"] = attr_by_local(child_by_local(entry, "link"), "href")
    rec["title"] = text_at_path(entry, ["title"])
    rec["updated"] = text_at_path(entry, ["updated"])
    summary = text_at_path(entry, ["summary"])
    rec["summary"] = summary
    if summary:
        m = SUMMARY_RE.search(summary)
        if m:
            rec["sum_id"] = (m.group("id") or "").strip() or None
            rec["sum_organo"] = (m.group("organo") or "").strip() or None
            rec["sum_importe"] = _to_float(m.group("importe"))
            rec["sum_estado"] = (m.group("estado") or "").strip() or None

    cfs = child_by_local(entry, "ContractFolderStatus")
    if cfs is None:
        return rec

    rec["id_origen"] = text_at_path(cfs, ["ContractFolderID"])
    rec["estado"] = text_at_path(cfs, ["ContractFolderStatusCode"])

    # --- órgano de contratación ---
    lcp = child_by_local(cfs, "LocatedContractingParty")
    if lcp is not None:
        rec["poder_tipo"] = text_at_path(lcp, ["ContractingPartyTypeCode"])
        rec["actividad"] = text_at_path(lcp, ["ActivityCode"])
        party = child_by_local(lcp, "Party")
        if party is not None:
            ids = _ids_by_scheme(party)
            rec["organo_nif"] = ids.get("NIF")
            rec["organo_dir3"] = ids.get("DIR3")
            rec["organo_id_plataforma"] = ids.get("ID_PLATAFORMA")
            rec["organo_id_oc_plat"] = ids.get("ID_OC_PLAT")
            rec["organo_id"] = _best_id(ids)
            rec["organo_nombre"] = text_at_path(party, ["PartyName", "Name"])
            postal = child_by_local(party, "PostalAddress")
            rec["organo_ciudad"] = text_at_path(postal, ["CityName"])
            rec["organo_cp"] = text_at_path(postal, ["PostalZone"])
        chain = _admin_chain(lcp)
        rec["admin_hierarchy"] = " > ".join(chain) if chain else None

    # --- objeto ---
    pp = child_by_local(cfs, "ProcurementProject")
    if pp is not None:
        rec["objeto"] = text_at_path(pp, ["Name"])
        rec["tipo_contrato"] = text_at_path(pp, ["TypeCode"])
        rec["subtipo_contrato"] = text_at_path(pp, ["SubTypeCode"])
        budget = child_by_local(pp, "BudgetAmount")
        rec["importe_estimado"] = _to_float(text_at_path(budget, ["EstimatedOverallContractAmount"]))
        rec["importe_total_con_iva"] = _to_float(text_at_path(budget, ["TotalAmount"]))
        rec["importe_sin_iva"] = _to_float(text_at_path(budget, ["TaxExclusiveAmount"]))
        rec["cpv"] = text_at_path(
            pp, ["RequiredCommodityClassification", "ItemClassificationCode"]
        )
        loc = child_by_local(pp, "RealizedLocation")
        rec["territorio_nombre"] = text_at_path(loc, ["CountrySubentity"])
        rec["territorio_code"] = text_at_path(loc, ["CountrySubentityCode"])

    # --- resultado / adjudicación (puede haber varios TenderResult, uno por lote) ---
    results = descendants_by_local(cfs, "TenderResult")
    rec["n_resultados"] = len(results)
    if results:
        primary = results[0]
        rec["result_code"] = text_at_path(primary, ["ResultCode"])
        for tr in results:
            award_date = text_at_path(tr, ["AwardDate"])
            if award_date:
                rec["fecha_adjudicacion"] = award_date
                break
        winner = child_by_local(primary, "WinningParty")
        if winner is not None:
            wids = _ids_by_scheme(winner)
            rec["adjudicatario_nombre"] = text_at_path(winner, ["PartyName", "Name"])
            rec["adjudicatario_nif"] = wids.get("NIF")
            rec["adjudicatario_id"] = _best_id(wids)
        total_pay = 0.0
        total_excl = 0.0
        got_amount = False
        for tr in results:
            lmt = child_by_local(child_by_local(tr, "AwardedTenderedProject"), "LegalMonetaryTotal")
            if lmt is None:
                continue
            pay = _to_float(text_at_path(lmt, ["PayableAmount"]))
            excl = _to_float(text_at_path(lmt, ["TaxExclusiveAmount"]))
            if pay is not None:
                total_pay += pay
                got_amount = True
            if excl is not None:
                total_excl += excl
        if got_amount:
            rec["importe_adjudicado"] = total_pay
            rec["importe_adjudicado_sin_iva"] = total_excl or None

    return rec


def parse_atom_file(path: str | Path) -> Iterator[dict[str, Any]]:
    """Itera registros de un fichero ATOM por streaming, con memoria constante.

    `recover=True` y `huge_tree=True` para tolerar ficheros grandes y ligeramente malformados.
    Se ignoran los `<at:deleted-entry>` (tombstones) porque su local-name no es 'entry'.
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
            elem.clear()
            parent = elem.getparent()
            if parent is not None:
                while elem.getprevious() is not None:
                    del parent[0]
    del context
