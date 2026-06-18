# Carpeta de datos (local)

**Nada de esta carpeta se sube al repositorio**, salvo `referencia/` (dimensiones pequeñas y versionables). Lo impone `.gitignore`.

## Dónde colocar cada fuente

| Carpeta | Fuente | Cobertura | Prioridad analítica |
|---|---|---|---|
| `contratos_menores/` | Contratos menores | 2018+ | 1 — concentración y posible fraccionamiento |
| `placsp/perfil_contratante/` | Licitaciones directas en PLACSP (sin menores) | 2012+ | 2 — base de contratación formal |
| `placsp/agregaciones/` | Licitaciones agregadas desde otras plataformas | 2016+ | 3 — cobertura nacional |
| `placsp/encargos/` | Encargos a medios propios | 2022+ | 4 — opacidad / sin concurrencia |
| `referencia/` | Dimensiones (territorio, partidos, población, CPV) | — | versionado |
| `_processed/` | Salida del pipeline (bronze/silver/gold) | generado | gitignored |

Los ficheros de fuente son **ATOM** (XML con esquema CODICE/UBL). Pueden venir comprimidos (`.zip`); el pipeline también acepta `.atom` sueltos.

## Cómo se procesan

No se consultan en caliente. El pipeline (`pipeline/`) los convierte una sola vez a Parquet:

```
ATOM/XML  →  _processed/_bronze/  →  _processed/_silver/  →  _processed/_gold/  →  web/public/data/
```
