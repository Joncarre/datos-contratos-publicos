# pipeline/ — Pipeline de datos (Python)

Convierte los ATOM/CODICE (137 GB) en Parquet columnar, una sola vez, por lotes.

```
ingest/   ATOM (streaming) -> Bronze (Parquet crudo fiel + payload_json + metadatos)
normalize/  Bronze -> Silver (modelo canónico, fechas/importes/códigos normalizados)  [Fase 1]
dedup/      marca registro canónico sin borrar originales                              [Fase 1]
aggregate/  Silver -> Gold (marts agregados para el frontend, vía DuckDB)              [Fase 1]
mappings/   mapeos versionados fuente x periodo -> modelo canónico
```

## Comandos

```bash
# desde la raíz del repo, con el venv activado/instalado:
python -m contratos_pipeline info
python -m contratos_pipeline parse-file "data/contratos_menores/<f>.atom" --limit 3
python -m contratos_pipeline ingest contratos_menores
```

## Diseño del parser (clave para 137 GB)

`ingest/atom_parser.py` usa `lxml.etree.iterparse` con `tag="{*}entry"`: lee **una entrada cada vez** y libera el nodo (`elem.clear()` + borrado de hermanos previos). Memoria constante aunque el fichero tenga 500k líneas.

La extracción de campos canónicos es **agnóstica a namespaces** (compara por *local-name*) y está dirigida por `FIELD_PATHS`, fácil de ajustar contra muestras reales sin tocar la lógica. Todo el contenido original se conserva en `payload_json`.
