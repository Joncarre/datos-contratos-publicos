"""Genera los *marts* Gold con DuckDB leyendo todo el Bronze.

Filosofía: el usuario NUNCA consulta los millones de filas en caliente. DuckDB ejecuta aquí los
GROUP BY pesados una sola vez y materializa marts diminutos (KB–pocos MB) en `web/public/data/`
como JSON, que el frontend lee directamente. También se deja una copia Parquet en `_gold/`.

Dos normalizaciones imprescindibles antes de agregar:
1. DEDUPLICACIÓN: los feeds republican el mismo expediente en cada cambio de estado
   (EV→PUB→ADJ→RES). Nos quedamos con el registro CANÓNICO (estado más avanzado/reciente) por
   `(source, órgano, expediente)`. Sin esto los importes se multiplican (perfil ~3,6x).
2. IMPORTE comparable: COALESCE(adjudicado, total c/IVA, summary, sin IVA); las anuladas no suman.
   La CCAA se deriva del código NUTS (`territorio_code`), más fiable que el nombre libre.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contratos_pipeline import config

# NUTS2 -> CCAA (NUTS-2021). ES7x = Canarias se trata aparte (a veces llega como NUTS1 'ES7').
_NUTS2_CCAA = {
    "ES11": "Galicia", "ES12": "Principado de Asturias", "ES13": "Cantabria",
    "ES21": "País Vasco", "ES22": "Comunidad Foral de Navarra", "ES23": "La Rioja",
    "ES24": "Aragón", "ES30": "Comunidad de Madrid", "ES41": "Castilla y León",
    "ES42": "Castilla-La Mancha", "ES43": "Extremadura", "ES51": "Cataluña",
    "ES52": "Comunitat Valenciana", "ES53": "Illes Balears", "ES61": "Andalucía",
    "ES62": "Región de Murcia", "ES63": "Ceuta", "ES64": "Melilla", "ES70": "Canarias",
}


def _ccaa_case() -> str:
    whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in _NUTS2_CCAA.items())
    return (
        "CASE substr(territorio_code, 1, 4) "
        f"{whens} "
        "ELSE CASE WHEN territorio_code LIKE 'ES7%' THEN 'Canarias' ELSE NULL END END"
    )


def _setup_views_sql() -> list[str]:
    bronze_glob = (config.bronze_root() / "*" / "*.parquet").as_posix()
    return [
        # Vista base con columnas derivadas.
        f"""
        CREATE OR REPLACE VIEW base AS
        SELECT
            *,
            COALESCE(organo_id, organo_nif, organo_dir3, organo_id_plataforma,
                     organo_id_oc_plat, organo_nombre) AS org_key,
            COALESCE(adjudicatario_id, adjudicatario_nif, adjudicatario_nombre) AS adj_key,
            {_ccaa_case()} AS ccaa,
            CASE upper(estado)
                WHEN 'RES' THEN 6 WHEN 'ADJ' THEN 5 WHEN 'PUB' THEN 4
                WHEN 'EV' THEN 3 WHEN 'PRE' THEN 2 WHEN 'ANUL' THEN 1 ELSE 0
            END AS status_rank,
            COALESCE(importe_adjudicado, importe_total_con_iva, sum_importe,
                     importe_sin_iva) AS importe,
            -- CLASIFICACIÓN para transparencia. NADA se excluye de los totales; solo se etiqueta,
            -- para que el usuario pueda interpretar/filtrar y para destacar lo llamativo.
            (lower(coalesce(objeto, '')) LIKE '%acuerdo marco%') AS es_acuerdo_marco,
            (upper(estado) = 'ANUL') AS es_anulada,
            -- Marca PROVISIONAL de revisión SOLO para imposibilidades físicas evidentes (un único
            -- contrato > ~10.000 M y no acuerdo marco; p. ej. el error de ~1/8 del PIB). NO define
            -- "lo normal": la detección real de anomalías (Fase 2) será data-driven y relativa a
            -- pares (CPV/tipo/territorio). Aquí solo se MARCA; jamás se borra ni se excluye.
            (COALESCE(importe_adjudicado, importe_total_con_iva, sum_importe, importe_sin_iva) > 1e10
             AND lower(coalesce(objeto, '')) NOT LIKE '%acuerdo marco%') AS revisar_importe
        FROM read_parquet('{bronze_glob}', union_by_name = true)
        """,
        # Registro canónico: 1 fila por (fuente, órgano, expediente), el estado más reciente.
        """
        CREATE OR REPLACE VIEW contratos AS
        SELECT * EXCLUDE (_rn) FROM (
            SELECT *, row_number() OVER (
                PARTITION BY source, org_key, id_origen
                ORDER BY updated DESC NULLS LAST, status_rank DESC
            ) AS _rn
            FROM base
        ) WHERE _rn = 1
        """,
    ]


def _write_json(rows: list[dict[str, Any]], name: str) -> Path:
    out = config.web_data_dir() / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return out


def _query(con, sql: str) -> list[dict[str, Any]]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# (nombre_mart, SQL sobre la vista `contratos` ya deduplicada). Marts pequeños, una pregunta cada uno.
# `importe` = importe COMPLETO (nada excluido). La composición (acuerdos marco / anuladas /
# a-verificar) se reporta en `resumen` para transparencia. Ver memoria objetividad-no-ocultar.
_MARTS: dict[str, str] = {
    "resumen": """
        SELECT source,
               count(*)                          AS contratos,
               count(DISTINCT adj_key)           AS adjudicatarios,
               count(DISTINCT org_key)           AS organos,
               round(sum(importe), 2)            AS importe,
               count(*) FILTER (WHERE status_rank >= 5)         AS adjudicados,
               count(*) FILTER (WHERE es_acuerdo_marco)         AS n_acuerdo_marco,
               round(sum(importe) FILTER (WHERE es_acuerdo_marco), 2) AS importe_acuerdo_marco,
               count(*) FILTER (WHERE es_anulada)               AS n_anuladas,
               count(*) FILTER (WHERE revisar_importe)          AS n_revisar,
               round(sum(importe) FILTER (WHERE revisar_importe), 2)  AS importe_revisar
        FROM contratos GROUP BY source ORDER BY importe DESC NULLS LAST
    """,
    "serie_anual": """
        SELECT year, source, count(*) AS contratos, round(sum(importe), 2) AS importe
        FROM contratos WHERE year BETWEEN 2012 AND 2026
        GROUP BY year, source ORDER BY year, source
    """,
    "territorio": """
        SELECT ccaa, year, source, count(*) AS contratos, round(sum(importe), 2) AS importe
        FROM contratos WHERE ccaa IS NOT NULL AND year BETWEEN 2012 AND 2026
        GROUP BY ccaa, year, source ORDER BY ccaa, year
    """,
    "top_adjudicatarios": """
        SELECT any_value(adjudicatario_nombre) AS nombre, adj_key AS id, source,
               count(*) AS contratos, round(sum(importe), 2) AS importe,
               count(*) FILTER (WHERE es_acuerdo_marco) AS n_acuerdo_marco
        FROM contratos WHERE adj_key IS NOT NULL AND status_rank >= 5
        GROUP BY adj_key, source ORDER BY importe DESC NULLS LAST LIMIT 200
    """,
    "top_organos": """
        SELECT any_value(organo_nombre) AS nombre, org_key AS id, source,
               count(*) AS contratos, round(sum(importe), 2) AS importe
        FROM contratos WHERE org_key IS NOT NULL
        GROUP BY org_key, source ORDER BY importe DESC NULLS LAST LIMIT 200
    """,
    # Vista de transparencia: los contratos individuales más grandes, con detalle y banderas.
    # Aquí aparecen los acuerdos marco enormes y el contrato "a verificar" — nada se oculta.
    "top_contratos": """
        SELECT id_origen, source, estado, year, ccaa,
               substr(objeto, 1, 140) AS objeto,
               organo_nombre, adjudicatario_nombre, round(importe, 2) AS importe,
               es_acuerdo_marco, revisar_importe, link_detalle
        FROM contratos WHERE importe IS NOT NULL
        ORDER BY importe DESC LIMIT 150
    """,
}


def build_marts() -> dict[str, int]:
    """Construye todos los marts. Devuelve {mart: n_filas}."""
    import duckdb

    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    for sql in _setup_views_sql():
        con.execute(sql)

    gold = config.gold_root()
    gold.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for name, sql in _MARTS.items():
        rows = _query(con, sql)
        _write_json(rows, name)
        parquet_path = (gold / f"{name}.parquet").as_posix()
        con.execute(f"COPY ({sql}) TO '{parquet_path}' (FORMAT PARQUET)")
        counts[name] = len(rows)
    return counts
