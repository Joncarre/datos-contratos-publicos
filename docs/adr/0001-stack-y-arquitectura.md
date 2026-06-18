# ADR-0001 — Stack y arquitectura

- **Estado:** aceptado · 2026-06-18
- **Contexto:** plataforma de visualización/análisis de contratación pública (España, 2012+). Fuentes en **ATOM/XML (CODICE/UBL)**, ~**137 GB**, miles de ficheros de 50k+ líneas.

## Decisiones

1. **Local-first; publicación pública en Fase 4.** El procesamiento pesado ocurre en local, por lotes; la web se publica después como sitio estático.
2. **Profundidad: agregados precalculados.** La web no consulta a nivel de contrato en caliente. Esto permite una arquitectura **estática** (sin servidor de base de datos).
3. **Arquitectura medallion:** `ATOM → Bronze → Silver → Gold (marts) → web/public/data`. Una transformación cara una vez; muchas lecturas baratas.
4. **Formato:** **Parquet** columnar (zstd), particionado por `source`/`year`. No se consulta el XML en caliente jamás.
5. **Motor analítico:** **DuckDB** sobre Parquet (out-of-core, predicate pushdown). Sin servidor.
6. **Pipeline:** **Python 3.11+** con `lxml.iterparse` (streaming, memoria constante).
7. **Frontend:** **React + TypeScript + Vite** (SPA estática). Tipografía 100% monoespaciada, tema claro premium.
8. **Tolerancia a esquemas:** modelo canónico con núcleo estable + columna `payload_json` (fidelidad total) + **mapeos versionados** por fuente×periodo.
9. **Deduplicación:** se conserva el registro original; se marca el canónico (`is_canonical`, `dup_group_id`).

## Alternativas descartadas

- **Postgres/Elasticsearch:** innecesario sin consulta libre a nivel de contrato; añade servidor y operación.
- **Streamlit/Dash:** no alcanzan el *look & feel* premium con tipografía mono requerido.
- **Spark:** sobredimensionado; DuckDB resuelve 137 GB en una sola máquina.
- **pnpm:** bloqueado por permisos de `corepack` en `C:\Program Files`. Se usa **npm workspaces**.

## Consecuencias

- Los 137 GB **nunca** se suben al repo (`.gitignore`). Solo `data/referencia/` se versiona.
- La actualización es **manual e incremental** (idempotencia por hash de fichero).
- El frontend solo depende de *marts* pequeños (KB–pocos MB): navegación instantánea, hosting casi gratis.
