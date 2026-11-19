# ADR-05: BigQuery como histórico analítico

**Estado:** Aprobado

## Contexto
La gerencia analiza horas y horas extra en Power BI y el modelo necesita histórico para reentrenarse.

## Decisión
ms-validacion y ms-reportes insertan en las tablas jornadas_validadas, decisiones y cierres_diarios, particionadas por fecha; la vista v_horas_por_frente alimenta los tableros.

## Alternativas evaluadas
Consultar Firestore directamente; exportar CSV a Power BI.

## Justificación técnica
SQL estándar, conector nativo de Power BI y Looker Studio, y separación entre la carga operativa y la analítica.

## Criterio FinOps
10 GiB de almacenamiento y 1 TiB de consultas al mes gratis; el particionado por fecha limita lo que se escanea.

## Consecuencias
Las inserciones son por streaming; para cargas masivas se usaría carga por lotes.
