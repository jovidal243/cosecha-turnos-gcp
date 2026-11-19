# ADR-08: Isolation Forest empaquetado dentro de ms-validacion

**Estado:** Aprobado

## Contexto
Las reglas no capturan patrones atípicos combinados (p. ej., una entrada a las 02:10 con duración normal).

## Decisión
Modelo Isolation Forest (scikit-learn) con 4 variables: horas trabajadas, desfase frente al inicio de turno, descanso previo y distancia al frente. Se entrena en la construcción de la imagen y puede reemplazarse con un modelo reentrenado en Cloud Storage (MODEL_URI).

## Alternativas evaluadas
Endpoint de predicción en Vertex AI; servicio de ML separado.

## Justificación técnica
La inferencia toma milisegundos y escala a cero con el servicio. Contaminación 1 %: tasa de falsos positivos de ~0,9 % sobre datos normales de prueba.

## Criterio FinOps
Un endpoint gestionado mantiene cómputo encendido 24/7; embebido no tiene costo adicional.

## Consecuencias
El reentrenamiento mensual con datos reales se ejecutaría como Cloud Run Job (trabajo futuro).
