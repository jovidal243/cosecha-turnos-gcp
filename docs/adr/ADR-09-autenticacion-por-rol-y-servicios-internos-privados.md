# ADR-09: Autenticación por rol y servicios internos privados

**Estado:** Aprobado (piloto)

## Contexto
Hay tres roles (supervisor, jefe de frente, analista) y dos servicios que nunca deben ser públicos.

## Decisión
Tokens Bearer por rol guardados en Secret Manager e inyectados a ms-asistencia; ms-validacion y ms-reportes sin acceso público, invocables solo por sa-invocador con token OIDC (Pub/Sub y Cloud Scheduler). Cada servicio tiene su cuenta de servicio con permisos mínimos.

## Alternativas evaluadas
Identity Platform o Firebase Authentication con usuarios; API Gateway.

## Justificación técnica
Suficiente para el piloto y sin dependencias adicionales; las comparaciones de token son en tiempo constante.

## Criterio FinOps
Secret Manager: 6 versiones activas gratis.

## Consecuencias
Propuesto para producción: Identity Platform federado con Entra ID del Ingenio, para usuarios nominales y MFA.
