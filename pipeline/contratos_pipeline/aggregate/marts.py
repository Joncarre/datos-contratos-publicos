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
    bronze_glob = config.bronze_glob()  # usa el compactado si existe (lectura rápida)
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
            -- Marca de revisión SOLO para magnitudes FÍSICAMENTE IMPOSIBLES en un único contrato
            -- (> 100.000 M ≈ >6% del PIB), incluidos acuerdos marco: p. ej. Santiago (200.000 M) y
            -- el techo de 1.307.568 M de GMV. NO define "lo normal" (de eso se ocupa el score de
            -- anomalías, data-driven). Solo se MARCA; jamás se borra ni se excluye.
            (COALESCE(importe_adjudicado, importe_total_con_iva, sum_importe, importe_sin_iva)
                 > 1e11) AS revisar_importe,
            -- Nivel del órgano, derivado de la jerarquía administrativa REAL (sin presuponer
            -- textos; categorías observadas en los datos). ESTATAL = lo que decide el gobierno
            -- central, clave para el módulo político.
            CASE
                WHEN strip_accents(upper(coalesce(admin_hierarchy, '')))
                     LIKE '%ADMINISTRACION GENERAL DEL ESTADO%' THEN 'estatal'
                WHEN strip_accents(upper(coalesce(admin_hierarchy, '')))
                     LIKE '%COMUNIDADES%AUTONOMAS%' THEN 'autonomico'
                WHEN strip_accents(upper(coalesce(admin_hierarchy, '')))
                     LIKE '%ENTIDADES LOCALES%' THEN 'local'
                ELSE 'otro'
            END AS organo_nivel
        FROM read_parquet('{bronze_glob}', union_by_name = true)
        """,
        # Registro canónico: 1 fila por (fuente, órgano, expediente), el estado más reciente.
        # TEMP TABLE (no VIEW): materializa el dedup UNA vez; si fuera vista se recalcularía en
        # cada mart y en cada paso de la query de anomalías (deduplicar 9M filas decenas de veces).
        """
        CREATE OR REPLACE TEMP TABLE contratos AS
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
    # Anomalías de importe DATA-DRIVEN: no se presupone qué es "normal". Para cada contrato se
    # compara su log-importe con el de sus PARES (división CPV + tipo) mediante un z robusto (MAD).
    # `score` = nº de desviaciones robustas respecto a la mediana de pares (signo: + caro / - barato).
    # Solo descriptivo: se ordena por rareza y se MUESTRA; no hay umbral absoluto ni se descarta nada.
    "anomalias": """
        WITH c AS (
            SELECT id_origen, source, year, ccaa, objeto, organo_nombre, adjudicatario_nombre,
                   importe, cpv, tipo_contrato, es_acuerdo_marco, link_detalle,
                   coalesce(substr(cpv, 1, 2), 'NA') || '|' || coalesce(tipo_contrato, 'NA') AS peer,
                   ln(importe) AS limp
            FROM contratos WHERE importe > 0
        ),
        -- median() + mad() en UNA pasada (mad = mediana de |x - mediana|); robusto a outliers.
        stats AS (SELECT peer, median(limp) AS med, mad(limp) AS madv, count(*) AS n
                  FROM c GROUP BY peer)
        SELECT c.id_origen, c.source, c.year, c.ccaa, substr(c.objeto, 1, 120) AS objeto,
               c.organo_nombre, c.adjudicatario_nombre, round(c.importe, 2) AS importe,
               c.cpv, c.peer, s.n AS peers, c.es_acuerdo_marco,
               round(exp(s.med), 2) AS importe_mediano_peer,
               round((c.limp - s.med) / (1.4826 * s.madv), 2) AS score,
               c.link_detalle
        FROM c JOIN stats s USING (peer)
        WHERE s.n >= 30 AND s.madv > 0
        -- Orden por sobrecoste relativo (score DESC): primero lo MUCHO más caro que sus similares,
        -- que es la señal investigativa. Los de signo negativo (anormalmente baratos) también
        -- existen en los datos; se podrán explorar en una vista simétrica. Nada se descarta.
        ORDER BY (c.limp - s.med) / (1.4826 * s.madv) DESC NULLS LAST
        LIMIT 200
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

    # Módulo político (usa la TEMP TABLE `contratos`, que ya incluye organo_nivel).
    from contratos_pipeline.aggregate import politica

    counts.update(politica.build_politica(con, _write_json))
    return counts
