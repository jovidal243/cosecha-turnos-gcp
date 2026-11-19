# ADR-02: Tres microservicios en Cloud Run

**Estado:** Aprobado

## Contexto
Captura, validación y reportes tienen cargas y ritmos distintos: la captura tiene picos en cambio de turno, la validación depende de la cola y los reportes corren una vez al día.

## Decisión
ms-asistencia (API + PWA, público), ms-validacion (privado, consumidor de eventos) y ms-reportes (privado, tareas programadas), cada uno en su servicio de Cloud Run con su propia cuenta de servicio.

## Alternativas evaluadas
Monolito en App Engine; GKE Autopilot; Cloud Run functions.

## Justificación técnica
Cada servicio escala por separado (0 a N instancias) y se despliega de forma independiente. GKE exige operar el clúster; functions dificulta compartir el dominio y probar localmente. Se reducen los 4 servicios de la propuesta a 3: la integración con nómina pasa a ms-reportes.

## Criterio FinOps
Escala a cero fuera de uso: sin tráfico no hay costo de cómputo. Límites de instancias máximas (3/3/1) acotan el gasto ante errores o abuso.

## Consecuencias
Arranque en frío de 1 a 3 s en la primera petición tras inactividad; aceptable porque la PWA encola localmente y la validación es asíncrona.
