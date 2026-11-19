# ADR-07: IA generativa con Gemini en Vertex AI

**Estado:** Aprobado

## Contexto
El jefe de frente debe entender rápido por qué una jornada quedó observada y la gerencia necesita un resumen diario sin armarlo a mano.

## Decisión
Usar gemini-3.8-flash (configurable con GEMINI_MODEL) mediante el SDK google-genai para: (1) explicar hallazgos y sugerir acción; (2) redactar el resumen del cierre diario; (3) asistente que responde preguntas sobre los indicadores del día.

## Alternativas evaluadas
API de un proveedor externo; modelo abierto autoalojado (Gemma en GPU); no usar IA generativa.

## Justificación técnica
Misma cuenta de servicio e IAM del proyecto, sin llaves externas. A Gemini solo se envían códigos seudonimizados y cifras agregadas (nunca nombres ni ubicaciones). Temperatura 0,2 e instrucciones que prohíben inventar datos. Si Gemini falla, una plantilla responde y el flujo no se detiene (campo origen = plantilla).

## Criterio FinOps
Pago por token; solo se invoca en jornadas observadas o rechazadas (~13 % en la simulación), una vez al día para el resumen y bajo demanda en el asistente. Un modelo Flash es varias veces más barato que uno Pro.

## Consecuencias
El asistente no consulta datos crudos: responde solo con los indicadores agregados que recibe, lo que limita el alcance de las preguntas pero evita fugas de datos.
