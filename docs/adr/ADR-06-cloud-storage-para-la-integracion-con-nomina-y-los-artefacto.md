# ADR-06: Cloud Storage para la integración con nómina y los artefactos del modelo

**Estado:** Aprobado

## Contexto
La liquidación de nómina está fuera del alcance; el sistema entrega horas validadas.

## Decisión
El cierre diario escribe gs://BUCKET/nomina/fecha=AAAA-MM-DD/horas_validadas.csv (solo jornadas válidas o aprobadas) y el resumen en Markdown. El modelo reentrenado se publica en gs://BUCKET/modelos/.

## Alternativas evaluadas
API directa al ERP; SFTP.

## Justificación técnica
Contrato simple y auditable con el ERP; el archivo por fecha es idempotente (se puede regenerar).

## Criterio FinOps
5 GB-mes gratis en us-central1; acceso público bloqueado.

## Consecuencias
El ERP debe leer el archivo (adaptador fuera del alcance del curso).
