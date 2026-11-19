# ADR-03: Comunicación asíncrona con Pub/Sub (push, orden, reintentos y dead-letter)

**Estado:** Aprobado

## Contexto
La captura no debe depender de que la validación, Gemini o BigQuery estén disponibles.

## Decisión
ms-asistencia publica AsistenciaRegistrada en el tópico marcaciones con ordering key = código del trabajador. Una suscripción push autenticada con OIDC entrega a ms-validacion; tras 5 intentos fallidos el mensaje pasa a marcaciones-dlq. ms-validacion publica AlertaGenerada.

## Alternativas evaluadas
Llamada HTTP síncrona; Cloud Tasks; Eventarc.

## Justificación técnica
La ordering key garantiza que la entrada de un trabajador se procese antes que su salida. El procesamiento es idempotente (solo procesa marcaciones en estado 'recibida'), por lo que la entrega al menos una vez de Pub/Sub no duplica jornadas.

## Criterio FinOps
10 GiB/mes gratis; cada marcación pesa menos de 1 KB.

## Consecuencias
Consistencia eventual: la jornada aparece validada pocos segundos después de la marcación.
