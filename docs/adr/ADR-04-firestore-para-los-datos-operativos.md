# ADR-04: Firestore para los datos operativos

**Estado:** Aprobado

## Contexto
La propuesta planteaba PostgreSQL. Los accesos del sistema son por clave (UUID de marcación, código de trabajador) y por igualdad (fecha, estado, frente).

## Decisión
Firestore en modo nativo con colecciones frentes, trabajadores, turnos, marcaciones, jornadas, alertas, resumenes y auditoria, detrás de un repositorio con la misma interfaz que la versión en memoria.

## Alternativas evaluadas
Cloud SQL para PostgreSQL; AlloyDB.

## Justificación técnica
Serverless, sin conexiones que administrar desde Cloud Run; create() atómico da la idempotencia por UUID. Solo se usan filtros de igualdad, por lo que no se requieren índices compuestos.

## Criterio FinOps
Capa gratuita diaria (lecturas, escrituras y 1 GiB). Cloud SQL cobra la instancia encendida 24/7 aunque no haya tráfico.

## Consecuencias
La integridad referencial se valida en la aplicación (trabajador y turno se verifican en ms-validacion). Los análisis complejos se hacen en BigQuery (ADR-05).
