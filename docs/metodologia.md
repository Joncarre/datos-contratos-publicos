# Metodología (presentación responsable)

Este proyecto presenta indicadores como **señales para investigar, no acusaciones**. Reglas de comunicación obligatorias.

## Principios

- **Lenguaje responsable.** Usar: "patrones llamativos", "concentración de adjudicaciones/proveedores", "anomalías estadísticas", "contratación sin concurrencia". **Evitar:** "fraude", "corrupción", "amaño".
- **Contexto siempre visible** en cada vista: *fuente · año/periodo · cobertura · nota de interpretación*.
- **Honestidad sobre la cobertura.** Mostrar explícitamente los huecos (encargos 2022+, agregaciones 2016+, menores 2018+).
- **Correlación ≠ causalidad.** Ningún indicador afirma intención.
- **Reproducibilidad.** Cada cifra se deriva de un pipeline auditable (hash de fichero, log de ingesta).

## Cobertura por fuente

| Fuente | Desde | Nota |
|---|---|---|
| Contratos menores | 2018 | Posible concentración / fraccionamiento |
| Perfil del contratante (PLACSP) | 2012 | Base de contratación formal |
| Agregaciones | 2016 | Cobertura de plataformas autonómicas |
| Encargos a medios propios | 2022 | Sin concurrencia; interpretar con cautela |

## Normalización de importes (crítico para la credibilidad) — **clasificar, nunca ocultar**

Los datos crudos **no** se suman tal cual, pero **nada se excluye del total**:

1. **Deduplicación a registro canónico** (corrige un artefacto técnico de la sindicación). Los feeds republican el mismo expediente en cada cambio de estado (EV→PUB→ADJ→RES); contar todas las filas multiplica el importe (perfil ×3,6). Nos quedamos con **una fila por `(fuente, órgano, expediente)`**, la del estado más reciente.
2. **Clasificación, NO exclusión.** El total incluye TODO. Cada contrato se **etiqueta** para interpretarlo y para **destacar lo llamativo**:
   - **Acuerdos marco** (`es_acuerdo_marco`): su importe es un **techo total** (no gasto ejecutado) y suele repartirse entre varios ganadores. Se marcan, **se cuentan en el total** y se desglosan aparte.
   - **A verificar** (`revisar_importe`): importe implausible para un único contrato (> €10.000 M y no acuerdo marco), p. ej. €200.000.200.000 a una persona física. **Posible error de grabación: se marca, NO se borra**, y se muestra con su detalle para investigarlo.

Los importes altos o atípicos son **señales, no ruido**: el mart `top_contratos` los destaca con objeto, órgano, adjudicatario y enlace a PLACSP. La presentación responsable es de **lenguaje** (no acusar), **nunca** de ocultar datos. **Objetividad ante todo, sean cuales sean las conclusiones.**

> Cautela: el "importe" mezcla importe adjudicado (cuando existe) y presupuesto de licitación (cuando aún no hay adjudicación). En Fase 2 se separarán "licitado" vs "adjudicado" y se resolverá la identidad de adjudicatarios (mismo NIF, distintas grafías: "FCC MEDIO AMBIENTE, S.A.U." vs "SAU").

## Indicadores (definición y cautelas)

### Anomalías de importe (data-driven, relativas a pares)
Para cada contrato se compara su importe con el de **contratos similares** (misma división CPV + tipo de contrato) mediante un **z robusto**: `score = (ln(importe) − mediana_pares) / (1,4826 · MAD_pares)`. El signo indica + (mucho más caro que sus pares) o − (mucho más barato). **No se presupone ningún umbral absoluto de "normal"**: es la propia distribución de cada grupo la que define qué es atípico. Requiere ≥ 30 pares para ser fiable. Es **descriptivo, no concluyente**: ordena por rareza e invita a investigar (con enlace a PLACSP), nunca afirma irregularidad. Así afloran tanto el error de Santiago como, p. ej., los €4.827 M en "caminos municipales", sin que nadie haya decidido a mano que son anómalos.

### Concentración de adjudicaciones (HHI)
Índice Herfindahl-Hirschman sobre el **número de adjudicaciones** por adjudicatario dentro de un órgano. (El HHI por importe se distorsiona con los importes-error como el de Santiago; el HHI por conteo es **robusto**.) HHI∈[0,1]: 1 = todas las adjudicaciones a un único proveedor. Mínimo 20 contratos por órgano para estabilidad. **Cautela:** mercados pequeños o regulados (p. ej. distribución eléctrica) concentran de forma legítima; es señal para mirar, no prueba.

### Proveedores recurrentes (dependencia / captura)
Vista proveedor-céntrica: por adjudicatario, importe total, nº de órganos distintos que le adjudican y **% de sus contratos que vienen de un único órgano** (`pct_top_organo`). Una dependencia muy alta de un solo comprador es una señal a mirar (captura/relación exclusiva), no una acusación. Mínimo 10 contratos.

### Fraccionamiento (importes pegados al umbral)
Para contratos menores, se cuentan los que tienen importe (sin IVA) en la banda **[90 %, 100 %) del umbral legal** —línea **objetiva**, no presupuesta por nosotros: 15.000 € servicios/suministros, 40.000 € obras—. Los pares (órgano, proveedor) con ≥5 contratos en esa banda señalan posible fraccionamiento. **Cautela:** muchos suministros recurrentes cuestan legítimamente cerca del umbral; es patrón a investigar, no acusación.

### Alineación política (exploratorio — con limitaciones graves, NO concluyente)
Compara la contratación **estatal** (`organo_nivel = 'estatal'`, Administración General del Estado) territorializada por CCAA según la **alineación** del partido del gobierno central con el de la presidencia autonómica.

**Hallazgo empírico (2026-06, datos 2012–2026) — por qué NO se puede concluir:**
- **Efecto sede (Madrid-HQ):** Madrid concentra el **75,4 %** de toda la contratación estatal con CCAA asignada, porque los organismos del Estado tienen su sede en Madrid y `RealizedLocation` recoge la sede, no dónde llega el beneficio. Madrid sale 71–98 % **todos los años**, gobierne quien gobierne.
- **Artefacto temporal:** la diferencia aparente "no alineadas 9,3 % vs alineadas 5,1 %" se debe a que Madrid está *no alineada* justo en 2019–2026, cuando existen casi todos los datos (2023: 28.610 contratos estatales con CCAA; 2017: 58). Mide *cuándo hay datos y dónde está la sede*, no política.
- **Ruido en CCAA pequeñas:** un único macrocontrato dispara su cuota (Canarias 68 %→4 %, Cataluña 50 %→2 %).

**Conclusión:** con estos datos **no se puede afirmar** que la alineación influya en la contratación estatal. Presentarlo como hallazgo sería falso. Para un análisis válido haría falta: (1) resolver el efecto sede (la contratación estatal es HQ-céntrica por diseño — posible limitación estructural insalvable con este dato); (2) normalizar per cápita/PIB (falta `dim_poblacion`); (3) medidas robustas a macrocontratos; (4) suficientes datos por CCAA y era. El módulo se conserva como **infraestructura exploratoria con estos avisos**, nunca como conclusión.

## Derecho de corrección
Se habilitará una vía de contacto para que cualquier entidad señale errores. Un dato erróneo defendido sin revisión destruye la credibilidad del proyecto.
