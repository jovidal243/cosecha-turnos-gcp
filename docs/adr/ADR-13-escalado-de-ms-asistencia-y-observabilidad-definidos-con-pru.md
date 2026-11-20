# ADR-13: Escalado de ms-asistencia y observabilidad definidos con pruebas de carga

**Estado:** Aprobado

## Contexto
El objetivo de registro es p95 < 300 ms en POST /api/marcaciones. La primera prueba de carga (25 usuarios simultáneos) mostró colas de 5 a 30 s; había que separar la latencia del servicio de la del cliente y de los arranques de instancias nuevas.

## Decisión
ms-asistencia con 10 solicitudes simultáneas por instancia, entre 1 y 5 instancias, y conexiones a Firestore y Pub/Sub abiertas al arrancar (antes de recibir tráfico). La latencia oficial se mide en el servidor (registros de Cloud Run); el cliente la complementa. Cloud Monitoring con verificación de /salud, 4 alertas por correo y un tablero de operación.

## Alternativas evaluadas
Mantener 40 solicitudes por instancia y escala a cero; 3 instancias siempre encendidas; más CPU por instancia.

## Justificación técnica
Con 40 solicitudes por instancia una sola CPU atendía toda la ráfaga. Con 3 instancias encendidas la cola del cliente no desapareció, lo que demostró que venía de la red de Cloud Shell y no del servicio. Medido en el servidor, el registro cumple: p95 de 209 a 246 ms.

## Criterio FinOps
Una instancia mínima inactiva cuesta unos USD 8 al mes en us-central1; tres costarían el triple sin mejorar la medida del servidor. Tras la sustentación, infra/99_eliminar.sh la elimina.

## Consecuencias
La primera marcación tras un periodo inactivo ya no paga el arranque en frío. Las ráfagas que exigen instancias nuevas pueden demorar algunas solicitudes; la PWA offline-first (ADR-10) las conserva en el celular y las reintenta, así que el supervisor no espera.
