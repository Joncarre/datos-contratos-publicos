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
