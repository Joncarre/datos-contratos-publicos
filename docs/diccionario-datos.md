# Diccionario de datos (modelo canónico)

Fuente única de verdad del esquema. El frontend y el pipeline deben mantenerse alineados con esto.

## Tabla `contrato`

Un registro = un contrato/lote/procedimiento normalizado. **Todos los campos del núcleo son opcionales (nullable)** para tolerar esquemas variables entre fuentes y periodos.

### Claves y trazabilidad
| Campo | Tipo | Descripción |
|---|---|---|
| `id_canonico` | str | Hash determinista; apunta al registro canónico |
| `id_origen` | str | ID de expediente/procedimiento en la fuente |
| `source` | enum | `contratos_menores` \| `perfil_contratante` \| `agregaciones` \| `encargos` |
| `source_file` | str | Fichero ATOM de origen |
| `source_file_hash` | str | SHA-256 del fichero (idempotencia/auditoría) |
| `ingested_at` | datetime | Marca de ingesta |
| `year` | int | Año derivado (adjudicación o `updated`) |
| `is_canonical` | bool | Registro canónico tras deduplicar |
| `dup_group_id` | str | Grupo de duplicados |

### Núcleo normalizado (Silver)
| Campo | Tipo | Notas |
|---|---|---|
| `objeto` | str | Objeto del contrato |
| `organo_nombre` / `organo_id` | str | Órgano de contratación |
| `organo_nivel` | enum | `estatal` \| `autonomico` \| `local` \| `otro` |
| `ccaa_id` / `provincia_id` / `municipio_id` | str | Códigos INE |
| `adjudicatario_nombre` / `adjudicatario_id` | str | NIF normalizado y **seudonimizado** si es persona física (GDPR) |
| `importe_adjudicacion` / `importe_licitacion` | float | EUR |
| `con_iva` | bool | |
| `fecha_adjudicacion` / `fecha_publicacion` / `fecha_formalizacion` | date | ISO 8601 |
| `cpv` | str | Código CPV |
| `tipo_contrato` / `procedimiento` | str | |
| `es_contrato_menor` / `es_encargo_medio_propio` | bool | |

### Flexible y cobertura
| Campo | Tipo | Notas |
|---|---|---|
| `payload_json` | str (JSON) | **Bronze:** copia fiel de todo el original (nada se pierde) |
| `attributes` | JSON | **Silver:** campos no mapeados de esa fuente×periodo |
| `coverage_flags` | JSON | Qué campos venían vacíos en origen |
| `schema_version` | str | Versión del mapeo aplicado |

## Estado actual: Bronze real (Fase 1, validado contra datos reales)

El parser emite **~35 columnas tipadas** (sin `payload_json`: los `.atom` en disco son la capa cruda inmutable, así que el Parquet es pequeño y eficiente). Esquema en `atom_parser.py:FIELD_TYPES`:

| Grupo | Columnas |
|---|---|
| entry | `entry_id, link_detalle, title, updated, summary` |
| digest `<summary>` | `sum_id, sum_organo, sum_importe, sum_estado` (cruce robusto) |
| folder | `id_origen, estado` |
| órgano | `organo_nombre, organo_nif, organo_dir3, organo_id_plataforma, organo_ciudad, organo_cp, poder_tipo, actividad, admin_hierarchy` |
| objeto | `objeto, tipo_contrato, subtipo_contrato, importe_estimado, importe_sin_iva, importe_total_con_iva, cpv, territorio_nombre, territorio_code` |
| adjudicación | `n_resultados, result_code, fecha_adjudicacion, adjudicatario_nombre, adjudicatario_nif, importe_adjudicado, importe_adjudicado_sin_iva` |
| metadatos | `source, source_file, source_file_hash, ingested_at, year` |

Notas de extracción aprendidas del esquema CODICE real:
- **`PartyIdentification` repetido por `schemeName`** (DIR3/NIF/ID_PLATAFORMA): se elige el **NIF** para órgano y adjudicatario.
- **`year`** se deriva de `updated` (timestamp de sindicación, fiable), no de `AwardDate` (puede venir malformado).
- **`admin_hierarchy`** = cadena `ParentLocatedParty` (municipio › provincia › CCAA › nivel › Sector Público).
- Puede haber **varios `TenderResult`** (uno por lote): se toma el primer adjudicatario y se **suma** el importe adjudicado.

## Capa Gold (marts, `aggregate/marts.py`)
`importe` = `COALESCE(importe_adjudicado, importe_total_con_iva, sum_importe, importe_sin_iva)`. `ccaa` se deriva del **NUTS** (`territorio_code`, ej. ES242→Aragón, ES300→Madrid, ES7→Canarias). Marts: `resumen, serie_anual, territorio, top_adjudicatarios, top_organos` → `web/public/data/*.json`.

## Deduplicación
- **Exacta:** `(id_origen, organo_id)` o `(cpv, organo_id, adjudicatario_id, fecha, importe)`.
- **Difusa:** *blocking* por `(ccaa, año, tramo_importe)` + similitud de `objeto`.
- Prioridad de fuente en el solape: `perfil_contratante` > `agregaciones`.

## Dimensiones (`data/referencia/`)
`dim_gobierno_central`, `dim_partido_ccaa`, `dim_poblacion`, `dim_territorio` (geometría), `dim_cpv`, `dim_umbral`.
