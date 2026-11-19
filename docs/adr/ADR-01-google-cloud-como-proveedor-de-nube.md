# ADR-01: Google Cloud como proveedor de nube

**Estado:** Aprobado

## Contexto
La propuesta inicial se planteó sobre Microsoft Azure. El curso se desarrolló en Google Cloud y el entregable exige implementar mínimo cinco servicios de nube y uno de IA generativa.

## Decisión
Implementar toda la solución en Google Cloud, región us-central1.

## Alternativas evaluadas
Microsoft Azure (propuesta original); AWS.

## Justificación técnica
Cloud Run despliega contenedores sin administrar servidores ni clústeres; Gemini está integrado en Vertex AI con la misma identidad (IAM) y facturación del proyecto; Power BI se conecta a BigQuery con conector nativo, así que la gerencia conserva su herramienta de reportes.

## Criterio FinOps
Cloud Run, Firestore, Pub/Sub, BigQuery, Cloud Storage y Cloud Scheduler tienen capa gratuita mensual que cubre el volumen del piloto; us-central1 está incluida en ella.

## Consecuencias
Se reescribe el ADR de proveedor de la propuesta. El Ingenio usa Microsoft 365: el inicio de sesión corporativo (Entra ID) queda como federación futura con Identity Platform (ADR-09).
