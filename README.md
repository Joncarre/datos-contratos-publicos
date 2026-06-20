# Datos de Contratación Pública (España, 2012+)

Plataforma de **visualización y análisis de contratación pública en España**, orientada a público general, periodistas y analistas. Enfoque en gasto por territorio, proveedores recurrentes, contratos menores, encargos a medios propios y patrones llamativos, presentados con **lenguaje responsable y no difamatorio**.

> **Filosofía de la arquitectura:** procesar una vez (pesado, local, por lotes) → publicar muchas veces (ligero, agregados pequeños, instantáneo). Los 137 GB de ATOM/XML **nunca** se consultan en caliente.

## Arquitectura (medallion)

```
ATOM/XML (137 GB)  ──►  BRONZE (Parquet)  ──►  GOLD (marts)        ──►  web/public/data
   data/*               ~38 cols tipadas       dedup canónico +         JSON (KB)
                        + compactación         análisis (DuckDB)        React + TS
[Python + lxml streaming]   [idempotente/hash]   [SQL sobre 9,25M filas]
```

Flujo: `ingest` (ATOM → Bronze por fichero) → `compact` (miles de Parquet → 1 por fuente) → `marts` (dedup + análisis → JSON). La capa "Silver" (normalización/dedup) vive integrada en el paso `marts` (DuckDB), no como materialización aparte.

- **Ingestión / procesamiento (`pipeline/`)** — Python 3.11+, `lxml` (streaming), DuckDB, Parquet.
- **Presentación (`web/`)** — React + TypeScript + Vite. Solo lee los *marts* agregados.
- **Datos (`data/`)** — local, **fuera del repo** (ver `.gitignore`). Solo `data/referencia/` se versiona.

## Estructura

```
pipeline/   Pipeline de datos en Python (ingest → normalize → dedup → aggregate)
web/        Frontend React + TS (Vite SPA)
data/       Datos locales (gitignored salvo data/referencia/)
docs/       Metodología, diccionario de datos y decisiones de arquitectura (ADR)
```

## Puesta en marcha

### 1. Pipeline (Python)

```bash
py -m venv .venv
.venv/Scripts/python -m pip install -e "./pipeline[dev]"
.venv/Scripts/python -m pytest pipeline -q          # tests del parser

# Flujo completo de datos (idempotente: reprocesa solo lo nuevo)
.venv/Scripts/python -m contratos_pipeline ingest contratos_menores   # idem: perfil_contratante, agregaciones, encargos
.venv/Scripts/python -m contratos_pipeline compact                    # consolida miles de Parquet -> 1 por fuente (rebuild rápido)
.venv/Scripts/python -m contratos_pipeline silver                     # capa canónica CONSULTABLE (5,08M expedientes)
.venv/Scripts/python -m contratos_pipeline index-files                # índice de ficheros .atom (carpeta/año -> ruta)
.venv/Scripts/python -m contratos_pipeline web-index                  # índice del navegador (DuckDB-WASM) -> web/public/data/contratos.parquet
.venv/Scripts/python -m contratos_pipeline marts                      # análisis -> web/public/data/*.json

# Utilidades
.venv/Scripts/python -m contratos_pipeline info                       # rutas y fuentes
.venv/Scripts/python -m contratos_pipeline parse-file "ruta.atom" --limit 3
```

### 2. Web (React)

```bash
npm install
npm run dev
```

## Estado

**Fase 2 — análisis avanzado.** Histórico completo 2012–2026 ingerido: **≈9,25 M filas crudas → 1,95 M expedientes canónicos** (dedup por `(fuente, órgano, expediente)`, estado más reciente), **0 errores**. Bronze compactado → rebuild de marts en ~72 s. Web con datos reales.

## Análisis disponibles (marts Gold → `web/public/data/`)

- **`resumen`, `serie_anual`, `territorio`** (CCAA vía NUTS) — totales y evolución, con **composición transparente** (acuerdos marco / a verificar; nada se excluye del total).
- **`territorio_percapita`** — gasto €/persona por CCAA/año (población INE), para comparar de forma **justa** (Madrid vs Murcia).
- **`top_contratos`, `top_adjudicatarios`, `top_organos`** — los más grandes, con banderas y enlace a PLACSP.
- **`anomalias`** — sobrecoste relativo a contratos similares (z robusto por CPV+tipo; **sin umbrales presupuestos**).
- **`concentracion`** — HHI de adjudicaciones por órgano (sobre nº de contratos, robusto a importes-error).
- **`proveedores`** — vista proveedor-céntrica: importe, nº de órganos y **dependencia** de un único órgano (posible captura).
- **`fraccionamiento`** — contratos menores pegados al **umbral legal** (15k/40k €), por órgano-proveedor.
- **`politica`, `politica_did`** — alineación CCAA↔gobierno central. **Exploratorio, NO concluyente** (efecto sede de Madrid; ver metodología).

## Datos: ¿dónde van?

Los 137 GB **no se suben nunca**. Colócalos localmente así (ver `data/README.md`):

```
data/contratos_menores/            (2018+)
data/placsp/perfil_contratante/    (2012+, licitaciones directas, sin menores)
data/placsp/agregaciones/          (2016+, licitaciones agregadas)
data/placsp/encargos/              (2022+, encargos a medios propios)
data/referencia/                   (dimensiones pequeñas y versionables)
```

## Investigación a nivel de contrato (CLI)

Sobre la capa **Silver** (5,08 M expedientes canónicos), con **trazabilidad al fichero ATOM de origen** para verificar cualquier dato en disco:

```bash
# Buscar por filtros (combínalos): adjudicatario, órgano, NIF, objeto, CPV, CCAA, año, fuente, importe…
python -m contratos_pipeline find --adjudicatario "SANTIAGO PUENTE"
python -m contratos_pipeline find --min-importe 1000000000 --ccaa Madrid --year 2023
python -m contratos_pipeline find --revisar           # solo los marcados "a verificar"

# Ficha completa de un expediente + su FICHERO y CARPETA de origen
python -m contratos_pipeline inspect "1802/2024" --source perfil_contratante

# Conclusiones AGREGADAS sobre cualquier filtro (total, top adjudicatarios, por año)
python -m contratos_pipeline stats --adjudicatario "DRAGADOS"
python -m contratos_pipeline stats --ccaa Madrid --year 2023
```

`find`/`inspect` muestran el `id_origen`, el adjudicatario/órgano, el importe, las banderas y la **ruta exacta** del `.atom` (p. ej. `placsp/perfil_contratante/2026/licitaciones…_9.atom`), para abrirlo y comprobar el dato. Nota: un mismo `id_origen` puede repetirse entre órganos distintos; ambos se muestran.

**En la web** (folio **Investigar**) lo mismo, pero **en el navegador** con **DuckDB-WASM** sobre `contratos.parquet` (~300 MB, leído por *range requests*, sin backend): filtras los 5,08 M, ves la ficha de cada contrato con su **fichero de origen** y un resumen agregado. Requiere haber ejecutado `web-index` antes de `npm run dev`.

## Aviso

Indicadores como "concentración de adjudicaciones" o "anomalías estadísticas" son **señales para investigar, no acusaciones**. Cada visualización muestra fuente, año, cobertura y nota de interpretación. Ver `docs/metodologia.md`.
