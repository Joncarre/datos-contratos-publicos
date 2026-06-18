# Datos de referencia (dimensiones)

Pequeños, versionables y revisables. **Verifica siempre estos datos contra una fuente autorizada** antes de publicar conclusiones: un error aquí contamina todo el análisis político.

## `dim_gobierno_central.csv`
`year, partido_gobierno_central` — partido en La Moncloa por año (2012–2026). Confirmado: **PP 2012–2018**, **PSOE 2019–2026**.

## `dim_partido_ccaa.csv` (PLANTILLA — completar)
`ccaa_id, ccaa, year, partido_presidencia` — partido en la **presidencia autonómica** por CCAA y año.

Ahora mismo solo contiene el ejemplo de **Madrid (PP, 2019–2026)**. **Debes completar las 17 CCAA × años (2012–2026)** desde una fuente verificable (resultados electorales / investiduras autonómicas).

Códigos INE de CCAA:

| id | CCAA | id | CCAA |
|----|------|----|------|
| 01 | Andalucía | 11 | Extremadura |
| 02 | Aragón | 12 | Galicia |
| 03 | Asturias | 13 | Comunidad de Madrid |
| 04 | Illes Balears | 14 | Región de Murcia |
| 05 | Canarias | 15 | C. Foral de Navarra |
| 06 | Cantabria | 16 | País Vasco |
| 07 | Castilla y León | 17 | La Rioja |
| 08 | Castilla-La Mancha | 18 | Ceuta |
| 09 | Cataluña | 19 | Melilla |
| 10 | Comunitat Valenciana | | |

A partir de estos dos ficheros, el pipeline deriva `alineacion` (misma fuerza que el gobierno central / distinta) para el módulo de análisis político. Ese análisis se presenta **siempre normalizado** (per cápita y % del total nacional) y como **correlación, no causalidad**.

## Pendientes de añadir
- `dim_poblacion.csv` — `ccaa_id, year, poblacion` (INE) para normalizar per cápita.
- `dim_territorio` / geometría (TopoJSON de CCAA) para el mapa coroplético.
- `dim_cpv.csv` — categorías de objeto de contrato.
