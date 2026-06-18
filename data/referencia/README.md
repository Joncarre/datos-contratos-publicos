# Datos de referencia (dimensiones)

Pequeños, versionables y revisables. **Verifica siempre estos datos contra una fuente autorizada** antes de publicar conclusiones.

## Datos políticos → `data/partidos_politicos/`
La fuente **canónica** de datos políticos vive en `data/partidos_politicos/` (también versionada):
- `gobierno_central.csv` — `year, partido_gobierno_central` (PP 2012–18 · PSOE 2019–26).
- `partidos_ccaa.json` — partido en la presidencia de cada CCAA/ciudad autónoma, año a año 2012–2026, con matices reales (PSC, CC, ERC, PRC, PNV, art. 155, coaliciones).

El pipeline derivará de ahí `alineacion` (misma fuerza que el gobierno central / distinta) para el módulo político (Fase 2), presentado **siempre normalizado** (per cápita y % del total) y como **correlación, no causalidad**.

> `partidos_ccaa_2012_2026.json` en esta carpeta es una versión anterior, superada por `partidos_politicos/partidos_ccaa.json`. Puede eliminarse.

## Dimensiones pendientes de añadir
- `dim_poblacion.csv` — `ccaa_id, year, poblacion` (INE) para normalizar per cápita.
- `dim_nuts_ccaa.csv` — NUTS (`territorio_code`, p. ej. ES300, ES7) → `ccaa_id`/`ccaa`. El campo NUTS de origen es más fiable que el nombre libre `CountrySubentity`.
- `dim_territorio` / geometría (TopoJSON de CCAA) para el mapa coroplético.
- `dim_cpv.csv` — categorías de objeto de contrato.

## Códigos INE de CCAA
01 Andalucía · 02 Aragón · 03 Asturias · 04 Baleares · 05 Canarias · 06 Cantabria · 07 Castilla y León · 08 Castilla-La Mancha · 09 Cataluña · 10 C. Valenciana · 11 Extremadura · 12 Galicia · 13 Madrid · 14 Murcia · 15 Navarra · 16 País Vasco · 17 La Rioja · 18 Ceuta · 19 Melilla
