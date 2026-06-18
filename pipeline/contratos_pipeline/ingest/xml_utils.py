"""Utilidades XML agnósticas a namespaces.

Los ATOM/CODICE de PLACSP usan muchos namespaces (atom, cbc, cac, place-ext...) y estos
varían entre periodos. Trabajamos siempre por *local-name* para ser resistentes a esos cambios.
"""

from __future__ import annotations

from typing import Any

from lxml import etree


def local_name(tag: object) -> str:
    """'{ns}Name' -> 'Name'. Devuelve '' para comentarios/PIs (tag no es str)."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def child_by_local(elem: etree._Element, name: str) -> etree._Element | None:
    """Primer hijo *directo* cuyo local-name coincide."""
    for child in elem:
        if local_name(child.tag) == name:
            return child
    return None


def text_at_path(elem: etree._Element, path: list[str]) -> str | None:
    """Desciende por hijos directos siguiendo `path` (local-names) y devuelve el texto de la hoja.

    Descenso estricto por hijo directo: predecible y sin colisiones por nombres repetidos en
    ramas distintas. Devuelve None si algún paso falta o el texto está vacío.
    """
    cur: etree._Element | None = elem
    for name in path:
        if cur is None:
            return None
        cur = child_by_local(cur, name)
    if cur is None or cur.text is None:
        return None
    text = cur.text.strip()
    return text or None


def first_text(elem: etree._Element, candidates: list[list[str]]) -> str | None:
    """Primer valor no vacío entre varias rutas candidatas (tolerancia a esquemas variables)."""
    for path in candidates:
        value = text_at_path(elem, path)
        if value is not None:
            return value
    return None


def element_to_dict(elem: etree._Element) -> Any:
    """Conversión genérica y fiel del subárbol a dict (para `payload_json`).

    - Hijos repetidos -> lista.
    - Atributos -> clave '@attributes'.
    - Texto en nodo hoja -> el propio string; en nodo con hijos -> clave '#text'.
    """
    node: dict[str, Any] = {}

    if elem.attrib:
        node["@attributes"] = {local_name(k): v for k, v in elem.attrib.items()}

    for child in elem:
        key = local_name(child.tag)
        if not key:  # comentario / processing instruction
            continue
        value = element_to_dict(child)
        if key in node:
            existing = node[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                node[key] = [existing, value]
        else:
            node[key] = value

    text = (elem.text or "").strip()
    if text:
        if node:
            node["#text"] = text
        else:
            return text

    return node
