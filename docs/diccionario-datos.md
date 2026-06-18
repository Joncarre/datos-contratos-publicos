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

## Estado actual (Bronze, Fase 0)
El parser ya emite los campos `entry_id, title, updated, id_origen, estado, organo_nombre, organo_id, objeto, tipo_contrato, cpv, territorio_code, importe_licitacion, fecha_adjudicacion, adjudicatario_nombre, adjudicatario_id, importe_adjudicacion, payload_json` + metadatos. Las rutas de extracción (`FIELD_PATHS` en `atom_parser.py`) se **afinan contra muestras reales**.

## Deduplicación
- **Exacta:** `(id_origen, organo_id)` o `(cpv, organo_id, adjudicatario_id, fecha, importe)`.
- **Difusa:** *blocking* por `(ccaa, año, tramo_importe)` + similitud de `objeto`.
- Prioridad de fuente en el solape: `perfil_contratante` > `agregaciones`.

## Dimensiones (`data/referencia/`)
`dim_gobierno_central`, `dim_partido_ccaa`, `dim_poblacion`, `dim_territorio` (geometría), `dim_cpv`, `dim_umbral`.
