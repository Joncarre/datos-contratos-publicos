"""Módulo político (sección J): ¿la alineación partidista CCAA↔gobierno central se asocia con
diferencias en la contratación ESTATAL territorializada por CCAA?

Honestidad metodológica (ver docs/metodologia.md):
- Solo `organo_nivel = 'estatal'` (Administración General del Estado): lo que decide el gobierno
  central. El gasto autonómico lo decide cada CCAA, no Moncloa.
- Comparar es delicado: las CCAA difieren en tamaño/PIB. Sin población aún, se usa **cuota del
  total estatal** (%), no importes absolutos, y un contraste **dentro de cada CCAA** alrededor del
  cambio de gobierno central de 2019 (PP→PSOE), donde la alineación se invierte.
- `alineado` = coincidencia EXACTA de partido. Se exponen los partidos en crudo (incl. PSC≠PSOE)
  para que el usuario interprete; no se presuponen "bloques". Correlación, no causalidad.
"""

from __future__ import annotations

import json
import unicodedata
from typing import Any

from contratos_pipeline import config


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().strip()


# Nombres CCAA que produce el pipeline desde NUTS (con acentos/grafía oficial).
_NUTS_NAMES = [
    "Galicia", "Principado de Asturias", "Cantabria", "País Vasco",
    "Comunidad Foral de Navarra", "La Rioja", "Aragón", "Comunidad de Madrid",
    "Castilla y León", "Castilla-La Mancha", "Extremadura", "Cataluña",
    "Comunitat Valenciana", "Illes Balears", "Andalucía", "Región de Murcia",
    "Ceuta", "Melilla", "Canarias",
]
_NORM_TO_NUTS = {_norm(n): n for n in _NUTS_NAMES}

# Los JSON usan alguna grafía distinta a la oficial NUTS.
_ALIAS = {
    "islas baleares": "Illes Balears",
    "comunidad valenciana": "Comunitat Valenciana",
    "asturias": "Principado de Asturias",
    "navarra": "Comunidad Foral de Navarra",
}


def _map_ccaa(json_name: str) -> str | None:
    n = _norm(json_name)
    return _ALIAS.get(n) or _NORM_TO_NUTS.get(n)


def load_dim_alineacion() -> tuple[list[dict[str, Any]], set[str]]:
    """Filas (ccaa, year, partido_ccaa, partido_central, alineado) + nombres CCAA sin mapear."""
    pol = config.data_root() / "partidos_politicos"

    central: dict[int, str] = {}
    for line in (pol / "gobierno_central.csv").read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        year, partido = line.split(",")
        central[int(year)] = partido.strip()

    data = json.loads((pol / "partidos_ccaa.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    unmapped: set[str] = set()
    for com in data["comunidades"]:
        ccaa = _map_ccaa(com["nombre"])
        if ccaa is None:
            unmapped.add(com["nombre"])
            continue
        for year_str, partido in com["mandatos"].items():
            year = int(year_str)
            pc = central.get(year)
            rows.append({
                "ccaa": ccaa,
                "year": year,
                "partido_ccaa": partido,
                "partido_central": pc,
                "alineado": (partido == pc) if pc is not None else None,
            })
    return rows, unmapped


def load_poblacion() -> tuple[list[dict[str, Any]], set[str]]:
    """Filas (ccaa, year, poblacion) desde el JSON del INE. 2026 = 2025 (aún sin dato del año)."""
    path = config.data_root() / "poblacion_ccaa" / "poblacion_total.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    unmapped: set[str] = set()
    pob_2025: dict[str, int] = {}
    for d in data:
        ccaa = _map_ccaa(d["ccaa"])
        if ccaa is None:
            unmapped.add(d["ccaa"])
            continue
        year, pob = int(d["anio"]), int(d["poblacion"])
        rows.append({"ccaa": ccaa, "year": year, "poblacion": pob})
        if year == 2025:
            pob_2025[ccaa] = pob
    for ccaa, pob in pob_2025.items():
        rows.append({"ccaa": ccaa, "year": 2026, "poblacion": pob})
    return rows, unmapped


# Mart per (ccaa, year) de la contratación ESTATAL, con su cuota nacional y la alineación.
_POLITICA_SQL = """
    WITH est AS (
        SELECT ccaa, year,
               count(*) AS contratos,
               sum(CASE WHEN revisar_importe THEN 0 ELSE importe END) AS importe
        FROM contratos
        WHERE organo_nivel = 'estatal' AND ccaa IS NOT NULL AND year BETWEEN 2012 AND 2026
        GROUP BY ccaa, year
    ),
    tot AS (SELECT year, sum(importe) AS imp_nac, sum(contratos) AS con_nac FROM est GROUP BY year)
    SELECT e.ccaa, e.year,
           d.partido_ccaa, d.partido_central, d.alineado,
           e.contratos, round(e.importe, 2) AS importe,
           round(100.0 * e.importe / nullif(t.imp_nac, 0), 3) AS pct_importe_nac,
           round(100.0 * e.contratos / nullif(t.con_nac, 0), 3) AS pct_contratos_nac
    FROM est e
    JOIN tot t USING (year)
    LEFT JOIN dim_alineacion d ON d.ccaa = e.ccaa AND d.year = e.year
    ORDER BY e.ccaa, e.year
"""

# Contraste DENTRO de cada CCAA: cuota media de contratación estatal en la era PP (2012-18) vs
# PSOE (2019-26), junto a si en esa era estuvo alineada con el gobierno central.
_POLITICA_DID_SQL = """
    WITH base AS (
        SELECT ccaa, year,
               sum(CASE WHEN revisar_importe THEN 0 ELSE importe END) AS importe,
               count(*) AS contratos
        FROM contratos
        WHERE organo_nivel = 'estatal' AND ccaa IS NOT NULL AND year BETWEEN 2012 AND 2026
        GROUP BY ccaa, year
    ),
    tot AS (SELECT year, sum(importe) AS imp_nac FROM base GROUP BY year),
    shares AS (
        SELECT b.ccaa, b.year, 100.0 * b.importe / nullif(t.imp_nac, 0) AS pct,
               CASE WHEN b.year <= 2018 THEN 'PP_2012_2018' ELSE 'PSOE_2019_2026' END AS era
        FROM base b JOIN tot t USING (year)
    ),
    al AS (
        SELECT ccaa, CASE WHEN year <= 2018 THEN 'PP_2012_2018' ELSE 'PSOE_2019_2026' END AS era,
               max(CASE WHEN alineado THEN 1 ELSE 0 END) AS alguna_vez_alineada,
               round(avg(CASE WHEN alineado THEN 1.0 ELSE 0.0 END), 2) AS frac_anios_alineada
        FROM dim_alineacion WHERE year BETWEEN 2012 AND 2026 GROUP BY 1, 2
    )
    SELECT s.ccaa, s.era,
           round(avg(s.pct), 3) AS pct_importe_medio,
           al.frac_anios_alineada
    FROM shares s LEFT JOIN al ON al.ccaa = s.ccaa AND al.era = s.era
    GROUP BY s.ccaa, s.era, al.frac_anios_alineada
    ORDER BY s.ccaa, s.era
"""

# Per cápita por CCAA/año: gasto (sin los errores `revisar`) / población. Comparación JUSTA
# (Madrid maneja más que Murcia). Incluye acuerdos marco (objetividad); excluye solo errores.
_PERCAPITA_SQL = """
    WITH t AS (
        SELECT ccaa, year,
               sum(CASE WHEN revisar_importe THEN 0 ELSE importe END) AS importe,
               count(*) AS contratos
        FROM contratos
        WHERE ccaa IS NOT NULL AND year BETWEEN 2012 AND 2026
        GROUP BY ccaa, year
    )
    SELECT t.ccaa, t.year, round(t.importe, 2) AS importe, t.contratos,
           p.poblacion, round(t.importe / nullif(p.poblacion, 0), 2) AS per_capita
    FROM t LEFT JOIN dim_poblacion p ON p.ccaa = t.ccaa AND p.year = t.year
    ORDER BY t.ccaa, t.year
"""


def build_politica(con, write_json) -> dict[str, int]:
    """Registra las dims (alineación, población) y construye marts políticos y per cápita."""
    import pyarrow as pa

    rows, unmapped = load_dim_alineacion()
    if unmapped:
        print(f"[politica] CCAA del JSON sin mapear a NUTS: {sorted(unmapped)}")
    con.register("dim_alineacion", pa.Table.from_pylist(rows))

    pob, pob_unmapped = load_poblacion()
    if pob_unmapped:
        print(f"[poblacion] CCAA sin mapear a NUTS: {sorted(pob_unmapped)}")
    con.register("dim_poblacion", pa.Table.from_pylist(pob))

    gold = config.gold_root()
    counts: dict[str, int] = {}
    marts = (
        ("politica", _POLITICA_SQL),
        ("politica_did", _POLITICA_DID_SQL),
        ("territorio_percapita", _PERCAPITA_SQL),
    )
    for name, sql in marts:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in cur.fetchall()]
        write_json(data, name)
        con.execute(f"COPY ({sql}) TO '{(gold / f'{name}.parquet').as_posix()}' (FORMAT PARQUET)")
        counts[name] = len(data)
    return counts
