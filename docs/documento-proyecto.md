---
title: "Arquitectura cloud para la gestión y validación inteligente de turnos y asistencia en la Gerencia de Cosecha del Ingenio del Cauca S.A.S."
subtitle: "Computación en la Nube · Proyecto final · Documento de arquitectura"
author: "José Omar Vidal Mera · Docente: Ing. Juan Guillermo Gómez Torres"
date: "Universidad Autónoma de Occidente · Maestría en Inteligencia Artificial y Ciencia de Datos · Cali, noviembre de 2026"
lang: es
---

# 1. Identificación del proyecto

| Campo | Detalle |
|---|---|
| Título | Arquitectura cloud para la gestión y validación inteligente de turnos y asistencia en la Gerencia de Cosecha del Ingenio del Cauca S.A.S. |
| Estudiante | José Omar Vidal Mera · jose_oma.vidal@uao.edu.co |
| Docente | Ing. Juan Guillermo Gómez Torres |
| Proveedor cloud | Google Cloud (región us-central1) |
| Servicios de nube implementados | Cloud Run, Pub/Sub, Firestore, BigQuery, Cloud Storage, Vertex AI (Gemini), Secret Manager, Cloud Scheduler, Artifact Registry, Cloud Build, Cloud Logging y Monitoring |
| IA generativa | Gemini 3.8 Flash en Vertex AI (SDK google-genai) |
| Repositorio | [github.com/jovidal243/cosecha-turnos-gcp](https://github.com/jovidal243/cosecha-turnos-gcp) (código, infraestructura, pruebas y esta documentación) |
| Despliegue | Proyecto `cosecha-turnos-uao` en Google Cloud, desplegado el 18 de noviembre de 2026 · aplicación: [ms-asistencia-s65h3bbweq-uc.a.run.app/app/](https://ms-asistencia-s65h3bbweq-uc.a.run.app/app/) |
| Datos | 100 % sintéticos: no se usa información real de trabajadores (Ley 1581 de 2012) |

# 2. Definición y descripción del proyecto

## 2.1 Contexto

El Ingenio del Cauca S.A.S. es una agroindustria azucarera del Valle del Cauca. La Gerencia de Cosecha coordina frentes de corte manual y mecanizado, operadores de cosechadoras, tractoristas y conductores, en frentes alejados entre sí y con turnos que cambian según la programación de cosecha. El costo de la mano de obra y de las horas extra es uno de los rubros que la gerencia revisa con más frecuencia.

## 2.2 Problema

En el proceso actual se identifican dos cuellos de botella:

1. **Captura manual y tardía.** Las novedades de turno y asistencia se consolidan después de la jornada, a partir de planillas o archivos, lo que retrasa la información y abre espacio a errores de digitación.
2. **Falta de trazabilidad.** No hay un registro único de quién registró, modificó o aprobó cada marcación, lo que dificulta las auditorías y la atención de reclamos.

Como consecuencia, inconsistencias como jornadas que exceden el máximo, turnos continuos o horas extra sin autorización se descubren cuando ya se liquidaron.

## 2.3 Solución propuesta

Una plataforma de microservicios serverless en Google Cloud que:

- **Digitaliza la captura en campo** con una aplicación web progresiva (PWA) que funciona sin señal: el supervisor lee el QR del carné, la app toma hora y ubicación y guarda la marcación en el dispositivo hasta sincronizarla.
- **Valida automáticamente cada marcación** de forma asíncrona (Pub/Sub) con un motor de 10 reglas de negocio y un modelo de detección de anomalías (Isolation Forest).
- **Usa IA generativa (Gemini)** para explicar en lenguaje natural por qué una jornada quedó observada, redactar el resumen del cierre diario y responder preguntas sobre los indicadores del día.
- **Deja trazabilidad completa** (auditoría de cada acción con actor y hora) y **entrega a nómina solo horas válidas o aprobadas** por el jefe de frente, en un archivo diario en Cloud Storage.
- **Alimenta la analítica** en BigQuery, que se conecta a Power BI o Looker Studio.

## 2.4 Alcance

| Incluye | No incluye |
|---|---|
| Captura offline, validación por reglas y modelo, aprobación del jefe de frente, alertas, cierre diario, archivo para nómina, histórico analítico, IA generativa | Liquidación de nómina, integración directa con SAP, usuarios nominales con Entra ID, datos reales de trabajadores |

# 3. Objetivos

## 3.1 Objetivo general

Diseñar e implementar en Google Cloud una arquitectura de microservicios serverless, orientada a eventos y con IA generativa, que digitalice el registro de turnos y asistencia de la Gerencia de Cosecha del Ingenio del Cauca y lo valide automáticamente, para entregar a nómina horas trazables y confiables y detectar el mismo día las jornadas irregulares y las horas extra no autorizadas.

## 3.2 Objetivos específicos

| Capa | Objetivo | Indicador y resultado |
|---|---|---|
| Presentación | Desarrollar una PWA offline-first que registre una marcación en menos de 10 s y la sincronice sin duplicados. | Cola en IndexedDB + UUID por marcación. Prueba automática de idempotencia: el reenvío responde "duplicada" y no crea una segunda jornada. |
| Servicios | Implementar 3 microservicios desacoplados que escalen de 0 a N instancias y validen cada marcación en menos de 60 s tras sincronizarla. | 3 servicios en Cloud Run (máx. 3/3/1 instancias). Validación asíncrona por Pub/Sub con orden por trabajador, reintentos y dead-letter. |
| Datos | Registrar en auditoría el 100 % de las acciones y conservar el histórico analítico. | Colección `auditoria` en cada registro, validación, decisión y cierre; tablas de BigQuery particionadas por fecha. |
| IA | Aplicar las reglas al 100 % de las marcaciones; detector de anomalías con falsos positivos ≤ 2 %; explicación generada para el 100 % de las jornadas observadas o rechazadas. | Falsos positivos medidos: 0,9 % sobre 3.000 jornadas normales. En la simulación se detectaron los 7 casos inyectados (sección 9). |
| Gobernanza | Costo mensual del piloto por debajo de USD 20 con presupuesto y alertas; cumplimiento de la Ley 1581. | Estimación ≈ USD 4 a 8 al mes (sección 8). Datos sintéticos, seudonimización ante Gemini, cuentas de servicio con mínimo privilegio. |

# 4. Arquitectura

## 4.1 Vista general

![Arquitectura de la solución en Google Cloud: servicios, flujos y límites](diagramas/01_arquitectura.png)

## 4.2 Servicios de Google Cloud utilizados

El profesor exige mínimo cinco servicios de nube más uno de IA generativa. La solución usa seis servicios centrales, uno de IA generativa y cinco de apoyo:

| # | Servicio | Tipo | Uso en el proyecto |
|---|---|---|---|
| 1 | **Cloud Run** | Cómputo serverless (contenedores) | Ejecuta ms-asistencia, ms-validacion y ms-reportes |
| 2 | **Pub/Sub** | Mensajería | Tópicos `marcaciones` (con orden y dead-letter) y `alertas` |
| 3 | **Firestore** | Base de datos NoSQL | Datos operativos y auditoría |
| 4 | **BigQuery** | Data warehouse | Histórico de jornadas, decisiones y cierres; vista para Power BI |
| 5 | **Cloud Storage** | Almacenamiento de objetos | Archivo diario para nómina, resúmenes y modelo entrenado |
| 6 | **Cloud Scheduler** | Programación | Dispara el cierre diario a las 05:30 (hora Colombia) |
| 7 | **Vertex AI – Gemini** | **IA generativa** | Explicaciones, resumen diario y asistente de preguntas |
| 8 | Secret Manager | Seguridad | Tokens de acceso por rol |
| 9 | Artifact Registry | DevOps | Imágenes Docker de los servicios |
| 10 | Cloud Build | CI/CD | Pruebas, construcción y despliegue |
| 11 | IAM (cuentas de servicio) | Seguridad | Una identidad por servicio con mínimo privilegio |
| 12 | Cloud Logging y Monitoring | Observabilidad | Registros, métricas y presupuesto con alertas |

## 4.3 Microservicios y API

| Servicio | Acceso | Endpoints principales | Responsabilidad |
|---|---|---|---|
| ms-asistencia | Público (token por rol) | `POST /api/marcaciones`, `POST /api/marcaciones/lote`, `GET /api/jornadas`, `POST /api/jornadas/{id}/decision`, `GET /api/alertas`, `GET /api/kpis`, `POST /api/asistente`, `GET /api/turnos`, `/app/` (PWA), `/docs` (OpenAPI) | Captura idempotente, consultas, decisiones del jefe de frente, asistente IA |
| ms-validacion | Privado (OIDC de Pub/Sub) | `POST /pubsub/push` | Reglas, Isolation Forest, explicación con Gemini, alertas, escritura en BigQuery |
| ms-reportes | Privado (OIDC de Cloud Scheduler) | `POST /tareas/cierre-diario` | Archivo para nómina, resumen con Gemini, indicadores del cierre |

## 4.4 Flujo de una marcación

![Flujo de una marcación en 9 pasos: captura, validación asíncrona, IA y decisión](diagramas/02_flujo.png)

## 4.5 Ciclo de vida de una jornada

![Estados de marcaciones y jornadas](diagramas/03_estados.png)

## 4.6 Modelo de datos (Firestore)

![Colecciones de Firestore](diagramas/04_datos.png)

## 4.7 Reglas de validación

| Código | Regla | Severidad |
|---|---|---|
| R01 | Jornada mayor a 10 h (8 ordinarias + 2 extra) | Observación |
| R02 | Descanso menor a 8 h desde la jornada anterior (turno continuo) | Observación |
| R03 | Entrada con una jornada abierta (traslape) | Rechazo |
| R04 | Horas extra por encima de las autorizadas en el turno (tolerancia 15 min) | Observación |
| R05 | Marcación fuera de la geocerca del frente | Observación |
| R06 | Salida sin entrada | Rechazo |
| R07 | Duración inválida (≤ 0 o > 24 h) | Rechazo |
| R08 | Patrón atípico según Isolation Forest | Observación |
| R09 | Trabajador sin turno programado | Observación |
| R10 | Código de trabajador no registrado | Rechazo |

Los parámetros (jornada máxima, descanso mínimo, tolerancia) están centralizados en `services/ms_validacion/reglas.py`.

## 4.8 Inteligencia artificial

**Detección de anomalías.** Isolation Forest (scikit-learn, 300 árboles, contaminación 1 %) entrenado con 4.000 jornadas sintéticas normales. Variables: horas trabajadas, desfase entre la entrada y el inicio de turno más cercano, horas de descanso previo y distancia al frente. Score menor que 0 equivale a anomalía. El modelo se empaqueta en la imagen y puede reemplazarse por uno reentrenado en Cloud Storage sin redesplegar código.

**IA generativa (Gemini 3.8 Flash en Vertex AI).**

| Uso | Entrada | Salida |
|---|---|---|
| Explicar una jornada observada o rechazada | Código seudonimizado, cargo, horas, turno, hallazgos y score | 2 a 3 frases con la causa y una acción sugerida al jefe de frente |
| Resumen del cierre diario | Indicadores agregados y alertas abiertas | Viñetas ejecutivas para la gerencia |
| Asistente "pregúntale a los datos" | Pregunta del usuario + indicadores del día | Respuesta basada solo en esos datos |

Controles: temperatura 0,2; instrucción de sistema que prohíbe inventar datos e ignorar instrucciones incrustadas en la pregunta; nunca se envían nombres ni coordenadas; si Gemini no responde, una plantilla genera el texto y el campo `origen` lo indica.

## 4.9 Despliegue y CI/CD

![CI/CD: de GitHub y Cloud Shell a Cloud Run con Cloud Build y Artifact Registry](diagramas/06_cicd.png)

# 5. Registro de decisiones de arquitectura (ADR)

Se documentan 12 decisiones. Cada una registra contexto, alternativas, justificación técnica y criterio FinOps. También están como archivos individuales en `docs/adr/`.

| ID | Decisión | Alternativas evaluadas | Estado |
|---|---|---|---|
| ADR-01 | Google Cloud como proveedor de nube | Microsoft Azure (propuesta original); AWS. | Aprobado |
| ADR-02 | Tres microservicios en Cloud Run | Monolito en App Engine; GKE Autopilot; Cloud Run functions. | Aprobado |
| ADR-03 | Comunicación asíncrona con Pub/Sub (push, orden, reintentos y dead-letter) | Llamada HTTP síncrona; Cloud Tasks; Eventarc. | Aprobado |
| ADR-04 | Firestore para los datos operativos | Cloud SQL para PostgreSQL; AlloyDB. | Aprobado |
| ADR-05 | BigQuery como histórico analítico | Consultar Firestore directamente; exportar CSV a Power BI. | Aprobado |
| ADR-06 | Cloud Storage para la integración con nómina y los artefactos del modelo | API directa al ERP; SFTP. | Aprobado |
| ADR-07 | IA generativa con Gemini en Vertex AI | API de un proveedor externo; modelo abierto autoalojado (Gemma en GPU); no usar IA generativa. | Aprobado |
| ADR-08 | Isolation Forest empaquetado dentro de ms-validacion | Endpoint de predicción en Vertex AI; servicio de ML separado. | Aprobado |
| ADR-09 | Autenticación por rol y servicios internos privados | Identity Platform o Firebase Authentication con usuarios; API Gateway. | Aprobado (piloto) |
| ADR-10 | PWA offline-first con IndexedDB e idempotencia por UUID | App nativa Android; web solo en línea. | Aprobado |
| ADR-11 | Identificación por QR del carné + geolocalización (sin biometría) | Huella o reconocimiento facial; planilla con firma. | Aprobado |
| ADR-12 | Infraestructura con scripts gcloud idempotentes y CI/CD con Cloud Build y GitHub Actions | Terraform; despliegue manual por consola. | Aprobado; Terraform propuesto |

### ADR-01. Google Cloud como proveedor de nube

**Estado:** Aprobado

- **Contexto:** La propuesta inicial se planteó sobre Microsoft Azure. El curso se desarrolló en Google Cloud y el entregable exige implementar mínimo cinco servicios de nube y uno de IA generativa.
- **Decisión:** Implementar toda la solución en Google Cloud, región us-central1.
- **Alternativas:** Microsoft Azure (propuesta original); AWS.
- **Justificación técnica:** Cloud Run despliega contenedores sin administrar servidores ni clústeres; Gemini está integrado en Vertex AI con la misma identidad (IAM) y facturación del proyecto; Power BI se conecta a BigQuery con conector nativo, así que la gerencia conserva su herramienta de reportes.
- **Criterio FinOps:** Cloud Run, Firestore, Pub/Sub, BigQuery, Cloud Storage y Cloud Scheduler tienen capa gratuita mensual que cubre el volumen del piloto; us-central1 está incluida en ella.
- **Consecuencias:** Se reescribe el ADR de proveedor de la propuesta. El Ingenio usa Microsoft 365: el inicio de sesión corporativo (Entra ID) queda como federación futura con Identity Platform (ADR-09).

### ADR-02. Tres microservicios en Cloud Run

**Estado:** Aprobado

- **Contexto:** Captura, validación y reportes tienen cargas y ritmos distintos: la captura tiene picos en cambio de turno, la validación depende de la cola y los reportes corren una vez al día.
- **Decisión:** ms-asistencia (API + PWA, público), ms-validacion (privado, consumidor de eventos) y ms-reportes (privado, tareas programadas), cada uno en su servicio de Cloud Run con su propia cuenta de servicio.
- **Alternativas:** Monolito en App Engine; GKE Autopilot; Cloud Run functions.
- **Justificación técnica:** Cada servicio escala por separado (0 a N instancias) y se despliega de forma independiente. GKE exige operar el clúster; functions dificulta compartir el dominio y probar localmente. Se reducen los 4 servicios de la propuesta a 3: la integración con nómina pasa a ms-reportes.
- **Criterio FinOps:** Escala a cero fuera de uso: sin tráfico no hay costo de cómputo. Límites de instancias máximas (3/3/1) acotan el gasto ante errores o abuso.
- **Consecuencias:** Arranque en frío de 1 a 3 s en la primera petición tras inactividad; aceptable porque la PWA encola localmente y la validación es asíncrona.

### ADR-03. Comunicación asíncrona con Pub/Sub (push, orden, reintentos y dead-letter)

**Estado:** Aprobado

- **Contexto:** La captura no debe depender de que la validación, Gemini o BigQuery estén disponibles.
- **Decisión:** ms-asistencia publica AsistenciaRegistrada en el tópico marcaciones con ordering key = código del trabajador. Una suscripción push autenticada con OIDC entrega a ms-validacion; tras 5 intentos fallidos el mensaje pasa a marcaciones-dlq. ms-validacion publica AlertaGenerada.
- **Alternativas:** Llamada HTTP síncrona; Cloud Tasks; Eventarc.
- **Justificación técnica:** La ordering key garantiza que la entrada de un trabajador se procese antes que su salida. El procesamiento es idempotente (solo procesa marcaciones en estado 'recibida'), por lo que la entrega al menos una vez de Pub/Sub no duplica jornadas.
- **Criterio FinOps:** 10 GiB/mes gratis; cada marcación pesa menos de 1 KB.
- **Consecuencias:** Consistencia eventual: la jornada aparece validada pocos segundos después de la marcación.

### ADR-04. Firestore para los datos operativos

**Estado:** Aprobado

- **Contexto:** La propuesta planteaba PostgreSQL. Los accesos del sistema son por clave (UUID de marcación, código de trabajador) y por igualdad (fecha, estado, frente).
- **Decisión:** Firestore en modo nativo con colecciones frentes, trabajadores, turnos, marcaciones, jornadas, alertas, resumenes y auditoria, detrás de un repositorio con la misma interfaz que la versión en memoria.
- **Alternativas:** Cloud SQL para PostgreSQL; AlloyDB.
- **Justificación técnica:** Serverless, sin conexiones que administrar desde Cloud Run; create() atómico da la idempotencia por UUID. Solo se usan filtros de igualdad, por lo que no se requieren índices compuestos.
- **Criterio FinOps:** Capa gratuita diaria (lecturas, escrituras y 1 GiB). Cloud SQL cobra la instancia encendida 24/7 aunque no haya tráfico.
- **Consecuencias:** La integridad referencial se valida en la aplicación (trabajador y turno se verifican en ms-validacion). Los análisis complejos se hacen en BigQuery (ADR-05).

### ADR-05. BigQuery como histórico analítico

**Estado:** Aprobado

- **Contexto:** La gerencia analiza horas y horas extra en Power BI y el modelo necesita histórico para reentrenarse.
- **Decisión:** ms-validacion y ms-reportes insertan en las tablas jornadas_validadas, decisiones y cierres_diarios, particionadas por fecha; la vista v_horas_por_frente alimenta los tableros.
- **Alternativas:** Consultar Firestore directamente; exportar CSV a Power BI.
- **Justificación técnica:** SQL estándar, conector nativo de Power BI y Looker Studio, y separación entre la carga operativa y la analítica.
- **Criterio FinOps:** 10 GiB de almacenamiento y 1 TiB de consultas al mes gratis; el particionado por fecha limita lo que se escanea.
- **Consecuencias:** Las inserciones son por streaming; para cargas masivas se usaría carga por lotes.

### ADR-06. Cloud Storage para la integración con nómina y los artefactos del modelo

**Estado:** Aprobado

- **Contexto:** La liquidación de nómina está fuera del alcance; el sistema entrega horas validadas.
- **Decisión:** El cierre diario escribe gs://BUCKET/nomina/fecha=AAAA-MM-DD/horas_validadas.csv (solo jornadas válidas o aprobadas) y el resumen en Markdown. El modelo reentrenado se publica en gs://BUCKET/modelos/.
- **Alternativas:** API directa al ERP; SFTP.
- **Justificación técnica:** Contrato simple y auditable con el ERP; el archivo por fecha es idempotente (se puede regenerar).
- **Criterio FinOps:** 5 GB-mes gratis en us-central1; acceso público bloqueado.
- **Consecuencias:** El ERP debe leer el archivo (adaptador fuera del alcance del curso).

### ADR-07. IA generativa con Gemini en Vertex AI

**Estado:** Aprobado

- **Contexto:** El jefe de frente debe entender rápido por qué una jornada quedó observada y la gerencia necesita un resumen diario sin armarlo a mano.
- **Decisión:** Usar gemini-3.8-flash (configurable con GEMINI_MODEL) mediante el SDK google-genai para: (1) explicar hallazgos y sugerir acción; (2) redactar el resumen del cierre diario; (3) asistente que responde preguntas sobre los indicadores del día.
- **Alternativas:** API de un proveedor externo; modelo abierto autoalojado (Gemma en GPU); no usar IA generativa.
- **Justificación técnica:** Misma cuenta de servicio e IAM del proyecto, sin llaves externas. A Gemini solo se envían códigos seudonimizados y cifras agregadas (nunca nombres ni ubicaciones). Temperatura 0,2 e instrucciones que prohíben inventar datos. Si Gemini falla, una plantilla responde y el flujo no se detiene (campo origen = plantilla).
- **Criterio FinOps:** Pago por token; solo se invoca en jornadas observadas o rechazadas (~13 % en la simulación), una vez al día para el resumen y bajo demanda en el asistente. Un modelo Flash es varias veces más barato que uno Pro.
- **Consecuencias:** El asistente no consulta datos crudos: responde solo con los indicadores agregados que recibe, lo que limita el alcance de las preguntas pero evita fugas de datos.

### ADR-08. Isolation Forest empaquetado dentro de ms-validacion

**Estado:** Aprobado

- **Contexto:** Las reglas no capturan patrones atípicos combinados (p. ej., una entrada a las 02:10 con duración normal).
- **Decisión:** Modelo Isolation Forest (scikit-learn) con 4 variables: horas trabajadas, desfase frente al inicio de turno, descanso previo y distancia al frente. Se entrena en la construcción de la imagen y puede reemplazarse con un modelo reentrenado en Cloud Storage (MODEL_URI).
- **Alternativas:** Endpoint de predicción en Vertex AI; servicio de ML separado.
- **Justificación técnica:** La inferencia toma milisegundos y escala a cero con el servicio. Contaminación 1 %: tasa de falsos positivos de ~0,9 % sobre datos normales de prueba.
- **Criterio FinOps:** Un endpoint gestionado mantiene cómputo encendido 24/7; embebido no tiene costo adicional.
- **Consecuencias:** El reentrenamiento mensual con datos reales se ejecutaría como Cloud Run Job (trabajo futuro).

### ADR-09. Autenticación por rol y servicios internos privados

**Estado:** Aprobado (piloto)

- **Contexto:** Hay tres roles (supervisor, jefe de frente, analista) y dos servicios que nunca deben ser públicos.
- **Decisión:** Tokens Bearer por rol guardados en Secret Manager e inyectados a ms-asistencia; ms-validacion y ms-reportes sin acceso público, invocables solo por sa-invocador con token OIDC (Pub/Sub y Cloud Scheduler). Cada servicio tiene su cuenta de servicio con permisos mínimos.
- **Alternativas:** Identity Platform o Firebase Authentication con usuarios; API Gateway.
- **Justificación técnica:** Suficiente para el piloto y sin dependencias adicionales; las comparaciones de token son en tiempo constante.
- **Criterio FinOps:** Secret Manager: 6 versiones activas gratis.
- **Consecuencias:** Propuesto para producción: Identity Platform federado con Entra ID del Ingenio, para usuarios nominales y MFA.

### ADR-10. PWA offline-first con IndexedDB e idempotencia por UUID

**Estado:** Aprobado

- **Contexto:** Los frentes tienen cobertura móvil intermitente.
- **Decisión:** App web progresiva: service worker para abrir sin señal, cola local en IndexedDB y sincronización en lote ordenada por hora. Cada marcación lleva un UUID generado en el dispositivo.
- **Alternativas:** App nativa Android; web solo en línea.
- **Justificación técnica:** Un solo código para cualquier celular, sin publicar en tiendas. El UUID permite reintentar sin duplicar (el backend responde 'duplicada').
- **Criterio FinOps:** Se sirve desde el mismo ms-asistencia; no requiere hosting adicional.
- **Consecuencias:** La lectura de QR usa la API BarcodeDetector (Chrome Android); en otros navegadores se digita el código.

### ADR-11. Identificación por QR del carné + geolocalización (sin biometría)

**Estado:** Aprobado

- **Contexto:** La Ley 1581 de 2012 clasifica los datos biométricos como sensibles.
- **Decisión:** El supervisor lee el QR del carné existente; la posición GPS valida la geocerca del frente.
- **Alternativas:** Huella o reconocimiento facial; planilla con firma.
- **Justificación técnica:** Usa los carnés actuales y evita tratar datos sensibles; la geocerca reduce marcaciones remotas.
- **Criterio FinOps:** No requiere hardware dedicado.
- **Consecuencias:** No impide que un supervisor marque por otro trabajador; la trazabilidad (quién registró) y la auditoría lo hacen detectable.

### ADR-12. Infraestructura con scripts gcloud idempotentes y CI/CD con Cloud Build y GitHub Actions

**Estado:** Aprobado; Terraform propuesto

- **Contexto:** El ambiente debe poder recrearse y eliminarse fácilmente para la sustentación.
- **Decisión:** Scripts infra/01..04 idempotentes (verifican antes de crear), cloudbuild.yaml para pruebas, imágenes y despliegue, y GitHub Actions para lint, pruebas y construcción en cada push.
- **Alternativas:** Terraform; despliegue manual por consola.
- **Justificación técnica:** Los scripts son legibles y se ejecutan en Cloud Shell sin instalar nada. Terraform aporta estado y detección de desvíos: queda como evolución.
- **Criterio FinOps:** Cloud Build: minutos gratis diarios; infra/99_eliminar.sh borra todo tras la sustentación.
- **Consecuencias:** Sin archivo de estado, los cambios manuales en consola no se detectan automáticamente.


# 6. Stack tecnológico

| Capa | Tecnología | Función |
|---|---|---|
| Frontend | HTML, CSS y JavaScript sin frameworks; service worker; IndexedDB; BarcodeDetector | PWA del supervisor y consola del jefe de frente |
| Backend | Python 3.12, FastAPI, Pydantic, Uvicorn | API REST con contrato OpenAPI |
| Datos | Firestore, BigQuery, Cloud Storage | Operativo, analítico y objetos |
| Mensajería | Pub/Sub | Eventos AsistenciaRegistrada y AlertaGenerada |
| IA | scikit-learn (Isolation Forest), google-genai (Gemini) | Anomalías e IA generativa |
| DevOps | Docker, Artifact Registry, Cloud Build, GitHub Actions, gcloud | CI/CD e infraestructura reproducible |
| Seguridad | IAM, Secret Manager, OIDC | Identidad, secretos y acceso entre servicios |
| Calidad | pytest (19 pruebas), ruff | Pruebas unitarias y de punta a punta |

# 7. Seguridad y protección de datos

![Seguridad e identidades: acceso público con token, servicios privados con OIDC y una cuenta de servicio por microservicio](diagramas/05_seguridad.png)

- **Mínimo privilegio:** cada microservicio usa su propia cuenta de servicio con solo los roles que necesita (p. ej., solo ms-asistencia publica en `marcaciones` y solo ms-validacion lee el modelo).
- **Servicios internos privados:** ms-validacion y ms-reportes no aceptan tráfico anónimo; solo `sa-invocador` con token OIDC.
- **Secretos fuera del código:** los tokens están en Secret Manager; el repositorio no contiene credenciales.
- **Ley 1581 de 2012:** datos sintéticos, sin biometría, seudonimización ante Gemini y auditoría de cada acción.
- **Cifrado:** Google Cloud cifra en reposo por defecto y todo el tráfico va por HTTPS.
- **Robustez:** validación de entradas con Pydantic, rechazo de marcaciones con hora futura, límites de tamaño de lote y de pregunta.

# 8. Estimación de costos (FinOps)

Supuestos del piloto: 1 a 5 frentes, 40 trabajadores, ~80 marcaciones al día, ~20 llamadas diarias a Gemini.

| Servicio | Consumo estimado al mes | Costo estimado |
|---|---|---|
| Cloud Run (3 servicios, escala a cero) | < 50.000 solicitudes | USD 0 (capa gratuita) |
| Firestore | ~3.000 escrituras y ~20.000 lecturas al día | USD 0 (capa gratuita) |
| Pub/Sub | < 10 MB | USD 0 |
| BigQuery | < 100 MB almacenados, consultas particionadas | USD 0 |
| Cloud Storage | < 50 MB | USD 0 |
| Cloud Scheduler, Secret Manager | 1 tarea, 1 secreto | USD 0 |
| Artifact Registry | ~1,5 GB de imágenes | ≈ USD 0,10 |
| Vertex AI – Gemini 3.8 Flash | ~0,9 M tokens de entrada y ~0,7 M de salida | ≈ USD 3,4 (tarifa introductoria hasta el 31/12/2026); ≈ USD 6,8 desde 2027 |
| **Total** | | **≈ USD 4 a 8 al mes** |

Controles FinOps: escala a cero, instancias máximas por servicio, Gemini solo en jornadas no válidas, presupuesto de USD 20 con alertas al 50 %, 90 % y 100 %, y script `infra/99_eliminar.sh` para borrar los recursos al terminar. Las tarifas deben confirmarse en la calculadora de precios de Google Cloud antes de pasar a producción.

# 9. Pruebas y resultados

**Pruebas automáticas (19, todas aprobadas):** reglas de negocio (8), modelo de anomalías (3) y flujo de punta a punta (8): autenticación y roles, jornada válida, idempotencia, jornada larga observada con explicación y alerta, traslape y salida sin entrada rechazados, marcación con hora futura, decisión del jefe de frente con cierre y archivo de nómina, y simulación completa.

**Simulación de dos días** (40 trabajadores, 5 frentes, 160 marcaciones) con siete casos atípicos inyectados el segundo día:

| Caso inyectado | Resultado del sistema |
|---|---|
| T001: jornada de 11,6 h con 2 h extra autorizadas | Observada: R01 + R04 |
| T010: 9,8 h sin horas extra autorizadas | Observada: R04 |
| T015: entrada a ~2,9 km del frente | Observada: R05 + R08 (modelo) |
| T021: doble entrada | Segunda marcación rechazada: R03 |
| T027: salida sin entrada | Marcación rechazada: R06 |
| T031: sale a las 23:40 y entra a las 05:50 | Observada: R02 (6,2 h de descanso) |
| T034: entrada a las 02:10 con duración normal | Observada solo por el modelo: R08 |

| Indicador | Día 1 | Día 2 |
|---|---|---|
| Jornadas | 40 | 39 |
| Válidas / observadas | 40 / 0 | 34 / 5 |
| Marcaciones rechazadas | 0 | 2 |
| Horas trabajadas / horas extra | 330,3 / 10,5 | 326,7 / 15,0 |
| Jornadas en el archivo de nómina | 40 | 34 (las 5 observadas quedan pendientes de decisión) |

El caso T034 muestra el valor del modelo: ninguna regla lo detecta, pero el Isolation Forest lo marca como atípico.

## 9.1 Evidencia del despliegue en Google Cloud

La solución se desplegó el 18 de noviembre de 2026 en el proyecto `cosecha-turnos-uao` (región us-central1) con los scripts del repositorio, y la misma simulación produjo en la nube los mismos resultados que en local.

| Evidencia | Resultado |
|---|---|
| Cloud Build (`infra/02_desplegar.sh`) | Pruebas, 3 imágenes y 3 despliegues: `STATUS: SUCCESS` en 3 min 19 s |
| Cloud Run | ms-asistencia (público, `https://ms-asistencia-s65h3bbweq-uc.a.run.app`); ms-validacion y ms-reportes (privados, solo OIDC) |
| Salud del servicio | `/salud` responde `{"estado":"ok","modo":"gcp"}` |
| Pub/Sub y validación | 160 marcaciones procesadas; el 17/11/2026: 39 jornadas, 34 válidas, 5 observadas y 2 marcaciones rechazadas |
| Cierre diario y nómina | 34 jornadas en `gs://cosecha-turnos-uao-cosecha-turnos/nomina/fecha=2026-11-17/horas_validadas.csv`; 5 pendientes de decisión |
| Cloud Scheduler | Tarea `cierre-diario` a las 05:30, zona America/Bogota, con token OIDC |
| Gemini en Vertex AI | Explicaciones y resumen diario con origen `gemini:gemini-3.8-flash` |

Explicación generada por Gemini para la jornada observada de T031, tal como la ve el jefe de frente:

> La jornada del tractorista T031 en el frente F01 quedó en estado 'observado' por el incumplimiento de la regla R02_DESCANSO_MINIMO, al registrarse únicamente 6.16 horas de descanso previo frente al mínimo establecido de 8 horas. Como acción concreta, se sugiere al jefe de frente revisar y ajustar la programación de turnos del trabajador para garantizar que se cumpla con el tiempo mínimo de descanso requerido antes de iniciar su labor.

![Aplicación en Cloud Run: jornada observada con la explicación escrita por Gemini](capturas/nube_jornadas.png)

![Aplicación en Cloud Run: indicadores del día y resumen del cierre redactado por Gemini](capturas/nube_indicadores.png)

## 9.2 Lecciones del despliegue

| Situación encontrada | Causa | Ajuste aplicado |
|---|---|---|
| Error 429 al crear cuentas de servicio | Límite de cuentas creadas por minuto en un proyecto nuevo | `01_aprovisionar.sh` crea una a la vez y reintenta tras 65 s |
| 2 jornadas abiertas en el primer cierre | Arranque en frío de Cloud Run; Pub/Sub aún entregaba salidas | `04_demo.sh` espera hasta que no queden jornadas abiertas |
| Pruebas fallidas en Windows | Windows no trae la base de zonas horarias y cambia los saltos de línea del CSV | Dependencia `tzdata` y escritura del CSV sin conversión de saltos de línea |
| Asteriscos sueltos en el resumen | Gemini respondía con formato Markdown | Instrucción de texto plano y presentación de negritas en la app |

# 10. Despliegue

Todo se ejecuta desde Cloud Shell, en la raíz del repositorio:

1. `cp infra/variables.env.example infra/variables.env` y ajustar el ID del proyecto.
2. `bash infra/01_aprovisionar.sh`: APIs, Artifact Registry, Firestore, bucket, tópicos, BigQuery, cuentas de servicio, secreto y presupuesto.
3. `bash infra/02_desplegar.sh`: Cloud Build ejecuta las pruebas, construye las 3 imágenes y despliega en Cloud Run.
4. `bash infra/03_conectar_eventos.sh`: suscripción push con OIDC, tarea de Cloud Scheduler y carga de datos sintéticos.
5. `bash infra/04_demo.sh`: simula dos días y ejecuta el cierre.
6. Tras la sustentación: `bash infra/99_eliminar.sh`.

Sin Google Cloud, el sistema completo corre en un solo proceso con `python -m scripts.run_local --simular`.

# 11. Cambios frente a la propuesta

| Propuesta (Azure) | Implementación (Google Cloud) | Motivo |
|---|---|---|
| Azure Container Apps, 4 microservicios | Cloud Run, 3 microservicios | Proveedor visto en clase; integración con nómina dentro de ms-reportes |
| API Management | Token por rol en ms-asistencia + servicios internos privados con OIDC | Menos componentes para el piloto (ADR-09) |
| Service Bus | Pub/Sub con orden, reintentos y dead-letter | Equivalente gestionado en GCP |
| PostgreSQL Flexible Server + Redis | Firestore | Sin costo fijo y sin conexiones que administrar (ADR-04) |
| Blob Storage + Parquet | Cloud Storage + BigQuery | Analítica con SQL y conector nativo a Power BI |
| Azure ML | Isolation Forest embebido | Sin endpoint encendido 24/7 (ADR-08) |
| Sin IA generativa | Gemini en Vertex AI | Requisito del entregable (ADR-07) |
| Terraform + GitHub Actions | Scripts gcloud + Cloud Build + GitHub Actions | Ejecución directa en Cloud Shell (ADR-12) |

# 12. Limitaciones y trabajo futuro

- Usuarios nominales con Identity Platform federado con Entra ID del Ingenio y MFA.
- Reentrenamiento mensual del modelo como Cloud Run Job con el histórico real de BigQuery.
- Notificaciones de alertas por correo o Google Chat suscritas al tópico `alertas`.
- Adaptador hacia SAP para cargar el archivo de horas validadas.
- Pruebas de carga en GCP para medir la latencia p95 del registro y Terraform para gestionar el estado de la infraestructura.
- Conectar el modelo de predicción de horas extra del trabajo de grado al histórico de BigQuery.
