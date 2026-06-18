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

### Concentración de proveedores (HHI)
Índice Herfindahl-Hirschman sobre la cuota de importe por adjudicatario dentro de un órgano/territorio. Alto = pocos proveedores acaparan. **Cautela:** mercados pequeños o especializados concentran de forma legítima.

### Importes bajo umbral
Distribución de importes de contratos menores respecto a los **umbrales legales** (`dim_umbral`). Una acumulación justo por debajo del umbral es un patrón llamativo. **Cautela:** muchos servicios cuestan legítimamente cerca del umbral; es señal, no prueba.

### Alineación política (exploratorio)
Compara la contratación **estatal** territorializada por CCAA según la **alineación** entre el partido del gobierno central y el de la presidencia autonómica, usando el cambio de gobierno de 2019 como corte (diferencia-en-diferencias).

**Cautelas críticas:**
- Normalizar **siempre** (per cápita y % del total nacional); nunca importes absolutos.
- Separar nivel `estatal` vs `autonomico`: el gasto autonómico lo decide cada CCAA, no el central.
- Declarar confusores: población, PIB, competencias transferidas, inversión heredada.
- Presentar como **pregunta abierta**, no como conclusión.

## Derecho de corrección
Se habilitará una vía de contacto para que cualquier entidad señale errores. Un dato erróneo defendido sin revisión destruye la credibilidad del proyecto.
