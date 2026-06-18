# Datos de Contratación Pública (España, 2012+)

Plataforma de **visualización y análisis de contratación pública en España**, orientada a público general, periodistas y analistas. Enfoque en gasto por territorio, proveedores recurrentes, contratos menores, encargos a medios propios y patrones llamativos, presentados con **lenguaje responsable y no difamatorio**.

> **Filosofía de la arquitectura:** procesar una vez (pesado, local, por lotes) → publicar muchas veces (ligero, agregados pequeños, instantáneo). Los 137 GB de ATOM/XML **nunca** se consultan en caliente.

## Arquitectura (medallion)

```
ATOM/XML (137 GB)  ──►  BRONZE  ──►  SILVER  ──►  GOLD (marts)  ──►  web/public/data
   data/*               crudo fiel    canónico +    agregados        Parquet/JSON
                        + hash/log    dedup         precalculados    (pocos MB)
[Python + lxml streaming]      [mapeos versionados]   [DuckDB SQL]    [React + TS]
```

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

# Verificar el parser con el fixture sintético
.venv/Scripts/python -m pytest pipeline -q

# Inspeccionar un fichero ATOM real (cuando tengas muestras)
.venv/Scripts/python -m contratos_pipeline parse-file "data/contratos_menores/<fichero>.atom" --limit 3

# Ingestar una fuente completa a Bronze (Parquet)
.venv/Scripts/python -m contratos_pipeline ingest contratos_menores
```

### 2. Web (React)

```bash
npm install
npm run dev
```

## Estado

**Fase 0 — Validación del concepto.** Esqueleto del monorepo, parser ATOM por streaming verificado, shell de UI premium. Pendiente: ejecutar el parser contra **muestras reales** para fijar el mapeo canónico (ver `docs/diccionario-datos.md`).

## Datos: ¿dónde van?

Los 137 GB **no se suben nunca**. Colócalos localmente así (ver `data/README.md`):

```
data/contratos_menores/            (2018+)
data/placsp/perfil_contratante/    (2012+, licitaciones directas, sin menores)
data/placsp/agregaciones/          (2016+, licitaciones agregadas)
data/placsp/encargos/              (2022+, encargos a medios propios)
data/referencia/                   (dimensiones pequeñas y versionables)
```

## Aviso

Indicadores como "concentración de adjudicaciones" o "anomalías estadísticas" son **señales para investigar, no acusaciones**. Cada visualización muestra fuente, año, cobertura y nota de interpretación. Ver `docs/metodologia.md`.
