"""Fuente única de las decisiones de arquitectura (ADR).

Genera docs/adr/ADR-XX-*.md y la tabla resumen que se inserta en el documento del proyecto:
    python docs/adr/adrs.py
"""
from __future__ import annotations

import os
import re
import unicodedata

ADRS = [
    {
        "id": "ADR-01", "titulo": "Google Cloud como proveedor de nube", "estado": "Aprobado",
        "contexto": "La propuesta inicial se planteó sobre Microsoft Azure. El curso se desarrolló en Google Cloud y el "
                    "entregable exige implementar mínimo cinco servicios de nube y uno de IA generativa.",
        "decision": "Implementar toda la solución en Google Cloud, región us-central1.",
        "alternativas": "Microsoft Azure (propuesta original); AWS.",
        "tecnica": "Cloud Run despliega contenedores sin administrar servidores ni clústeres; Gemini está integrado "
                   "en Vertex AI con la misma identidad (IAM) y facturación del proyecto; Power BI se conecta a "
                   "BigQuery con conector nativo, así que la gerencia conserva su herramienta de reportes.",
        "finops": "Cloud Run, Firestore, Pub/Sub, BigQuery, Cloud Storage y Cloud Scheduler tienen capa gratuita "
                  "mensual que cubre el volumen del piloto; us-central1 está incluida en ella.",
        "consecuencias": "Se reescribe el ADR de proveedor de la propuesta. El Ingenio usa Microsoft 365: el inicio de "
                         "sesión corporativo (Entra ID) queda como federación futura con Identity Platform (ADR-09).",
    },
    {
        "id": "ADR-02", "titulo": "Tres microservicios en Cloud Run", "estado": "Aprobado",
        "contexto": "Captura, validación y reportes tienen cargas y ritmos distintos: la captura tiene picos en "
                    "cambio de turno, la validación depende de la cola y los reportes corren una vez al día.",
        "decision": "ms-asistencia (API + PWA, público), ms-validacion (privado, consumidor de eventos) y "
                    "ms-reportes (privado, tareas programadas), cada uno en su servicio de Cloud Run con su propia "
                    "cuenta de servicio.",
        "alternativas": "Monolito en App Engine; GKE Autopilot; Cloud Run functions.",
        "tecnica": "Cada servicio escala por separado (0 a N instancias) y se despliega de forma independiente. GKE "
                   "exige operar el clúster; functions dificulta compartir el dominio y probar localmente. Se "
                   "reducen los 4 servicios de la propuesta a 3: la integración con nómina pasa a ms-reportes.",
        "finops": "Escala a cero fuera de uso: sin tráfico no hay costo de cómputo. Límites de instancias máximas (3/3/1) "
                  "acotan el gasto ante errores o abuso.",
        "consecuencias": "Arranque en frío de 1 a 3 s en la primera petición tras inactividad; aceptable porque la "
                         "PWA encola localmente y la validación es asíncrona.",
    },
    {
        "id": "ADR-03", "titulo": "Comunicación asíncrona con Pub/Sub (push, orden, reintentos y dead-letter)",
        "estado": "Aprobado",
        "contexto": "La captura no debe depender de que la validación, Gemini o BigQuery estén disponibles.",
        "decision": "ms-asistencia publica AsistenciaRegistrada en el tópico marcaciones con ordering key = código "
                    "del trabajador. Una suscripción push autenticada con OIDC entrega a ms-validacion; tras 5 "
                    "intentos fallidos el mensaje pasa a marcaciones-dlq. ms-validacion publica AlertaGenerada.",
        "alternativas": "Llamada HTTP síncrona; Cloud Tasks; Eventarc.",
        "tecnica": "La ordering key garantiza que la entrada de un trabajador se procese antes que su salida. El "
                   "procesamiento es idempotente (solo procesa marcaciones en estado 'recibida'), por lo que la "
                   "entrega al menos una vez de Pub/Sub no duplica jornadas.",
        "finops": "10 GiB/mes gratis; cada marcación pesa menos de 1 KB.",
        "consecuencias": "Consistencia eventual: la jornada aparece validada pocos segundos después de la marcación.",
    },
    {
        "id": "ADR-04", "titulo": "Firestore para los datos operativos", "estado": "Aprobado",
        "contexto": "La propuesta planteaba PostgreSQL. Los accesos del sistema son por clave (UUID de marcación, "
                    "código de trabajador) y por igualdad (fecha, estado, frente).",
        "decision": "Firestore en modo nativo con colecciones frentes, trabajadores, turnos, marcaciones, jornadas, "
                    "alertas, resumenes y auditoria, detrás de un repositorio con la misma interfaz que la versión "
                    "en memoria.",
        "alternativas": "Cloud SQL para PostgreSQL; AlloyDB.",
        "tecnica": "Serverless, sin conexiones que administrar desde Cloud Run; create() atómico da la idempotencia "
                   "por UUID. Solo se usan filtros de igualdad, por lo que no se requieren índices compuestos.",
        "finops": "Capa gratuita diaria (lecturas, escrituras y 1 GiB). Cloud SQL cobra la instancia encendida 24/7 "
                  "aunque no haya tráfico.",
        "consecuencias": "La integridad referencial se valida en la aplicación (trabajador y turno se verifican en "
                         "ms-validacion). Los análisis complejos se hacen en BigQuery (ADR-05).",
    },
    {
        "id": "ADR-05", "titulo": "BigQuery como histórico analítico", "estado": "Aprobado",
        "contexto": "La gerencia analiza horas y horas extra en Power BI y el modelo necesita histórico para "
                    "reentrenarse.",
        "decision": "ms-validacion y ms-reportes insertan en las tablas jornadas_validadas, decisiones y "
                    "cierres_diarios, particionadas por fecha; la vista v_horas_por_frente alimenta los tableros.",
        "alternativas": "Consultar Firestore directamente; exportar CSV a Power BI.",
        "tecnica": "SQL estándar, conector nativo de Power BI y Looker Studio, y separación entre la carga "
                   "operativa y la analítica.",
        "finops": "10 GiB de almacenamiento y 1 TiB de consultas al mes gratis; el particionado por fecha limita lo "
                  "que se escanea.",
        "consecuencias": "Las inserciones son por streaming; para cargas masivas se usaría carga por lotes.",
    },
    {
        "id": "ADR-06", "titulo": "Cloud Storage para la integración con nómina y los artefactos del modelo",
        "estado": "Aprobado",
        "contexto": "La liquidación de nómina está fuera del alcance; el sistema entrega horas validadas.",
        "decision": "El cierre diario escribe gs://BUCKET/nomina/fecha=AAAA-MM-DD/horas_validadas.csv (solo "
                    "jornadas válidas o aprobadas) y el resumen en Markdown. El modelo reentrenado se publica en "
                    "gs://BUCKET/modelos/.",
        "alternativas": "API directa al ERP; SFTP.",
        "tecnica": "Contrato simple y auditable con el ERP; el archivo por fecha es idempotente (se puede regenerar).",
        "finops": "5 GB-mes gratis en us-central1; acceso público bloqueado.",
        "consecuencias": "El ERP debe leer el archivo (adaptador fuera del alcance del curso).",
    },
    {
        "id": "ADR-07", "titulo": "IA generativa con Gemini en Vertex AI", "estado": "Aprobado",
        "contexto": "El jefe de frente debe entender rápido por qué una jornada quedó observada y la gerencia "
                    "necesita un resumen diario sin armarlo a mano.",
        "decision": "Usar gemini-3.8-flash (configurable con GEMINI_MODEL) mediante el SDK google-genai para: "
                    "(1) explicar hallazgos y sugerir acción; (2) redactar el resumen del cierre diario; "
                    "(3) asistente que responde preguntas sobre los indicadores del día.",
        "alternativas": "API de un proveedor externo; modelo abierto autoalojado (Gemma en GPU); no usar IA generativa.",
        "tecnica": "Misma cuenta de servicio e IAM del proyecto, sin llaves externas. A Gemini solo se envían "
                   "códigos seudonimizados y cifras agregadas (nunca nombres ni ubicaciones). Temperatura 0,2 e "
                   "instrucciones que prohíben inventar datos. Si Gemini falla, una plantilla responde y el "
                   "flujo no se detiene (campo origen = plantilla).",
        "finops": "Pago por token; solo se invoca en jornadas observadas o rechazadas (~13 % en la simulación), "
                  "una vez al día para el resumen y bajo demanda en el asistente. Un modelo Flash es varias veces "
                  "más barato que uno Pro.",
        "consecuencias": "El asistente no consulta datos crudos: responde solo con los indicadores agregados que "
                         "recibe, lo que limita el alcance de las preguntas pero evita fugas de datos.",
    },
    {
        "id": "ADR-08", "titulo": "Isolation Forest empaquetado dentro de ms-validacion", "estado": "Aprobado",
        "contexto": "Las reglas no capturan patrones atípicos combinados (p. ej., una entrada a las 02:10 con "
                    "duración normal).",
        "decision": "Modelo Isolation Forest (scikit-learn) con 4 variables: horas trabajadas, desfase frente al "
                    "inicio de turno, descanso previo y distancia al frente. Se entrena en la construcción de la "
                    "imagen y puede reemplazarse con un modelo reentrenado en Cloud Storage (MODEL_URI).",
        "alternativas": "Endpoint de predicción en Vertex AI; servicio de ML separado.",
        "tecnica": "La inferencia toma milisegundos y escala a cero con el servicio. Contaminación 1 %: tasa de "
                   "falsos positivos de ~0,9 % sobre datos normales de prueba.",
        "finops": "Un endpoint gestionado mantiene cómputo encendido 24/7; embebido no tiene costo adicional.",
        "consecuencias": "El reentrenamiento mensual con datos reales se ejecutaría como Cloud Run Job (trabajo futuro).",
    },
    {
        "id": "ADR-09", "titulo": "Autenticación por rol y servicios internos privados", "estado": "Aprobado (piloto)",
        "contexto": "Hay tres roles (supervisor, jefe de frente, analista) y dos servicios que nunca deben ser "
                    "públicos.",
        "decision": "Tokens Bearer por rol guardados en Secret Manager e inyectados a ms-asistencia; ms-validacion "
                    "y ms-reportes sin acceso público, invocables solo por sa-invocador con token OIDC (Pub/Sub y "
                    "Cloud Scheduler). Cada servicio tiene su cuenta de servicio con permisos mínimos.",
        "alternativas": "Identity Platform o Firebase Authentication con usuarios; API Gateway.",
        "tecnica": "Suficiente para el piloto y sin dependencias adicionales; las comparaciones de token son en "
                   "tiempo constante.",
        "finops": "Secret Manager: 6 versiones activas gratis.",
        "consecuencias": "Propuesto para producción: Identity Platform federado con Entra ID del Ingenio, para "
                         "usuarios nominales y MFA.",
    },
    {
        "id": "ADR-10", "titulo": "PWA offline-first con IndexedDB e idempotencia por UUID", "estado": "Aprobado",
        "contexto": "Los frentes tienen cobertura móvil intermitente.",
        "decision": "App web progresiva: service worker para abrir sin señal, cola local en IndexedDB y "
                    "sincronización en lote ordenada por hora. Cada marcación lleva un UUID generado en el dispositivo.",
        "alternativas": "App nativa Android; web solo en línea.",
        "tecnica": "Un solo código para cualquier celular, sin publicar en tiendas. El UUID permite reintentar sin "
                   "duplicar (el backend responde 'duplicada').",
        "finops": "Se sirve desde el mismo ms-asistencia; no requiere hosting adicional.",
        "consecuencias": "La lectura de QR usa la API BarcodeDetector (Chrome Android); en otros navegadores se "
                         "digita el código.",
    },
    {
        "id": "ADR-11", "titulo": "Identificación por QR del carné + geolocalización (sin biometría)",
        "estado": "Aprobado",
        "contexto": "La Ley 1581 de 2012 clasifica los datos biométricos como sensibles.",
        "decision": "El supervisor lee el QR del carné existente; la posición GPS valida la geocerca del frente.",
        "alternativas": "Huella o reconocimiento facial; planilla con firma.",
        "tecnica": "Usa los carnés actuales y evita tratar datos sensibles; la geocerca reduce marcaciones remotas.",
        "finops": "No requiere hardware dedicado.",
        "consecuencias": "No impide que un supervisor marque por otro trabajador; la trazabilidad (quién registró) "
                         "y la auditoría lo hacen detectable.",
    },
    {
        "id": "ADR-12", "titulo": "Infraestructura con scripts gcloud idempotentes y CI/CD con Cloud Build y GitHub Actions",
        "estado": "Aprobado; Terraform propuesto",
        "contexto": "El ambiente debe poder recrearse y eliminarse fácilmente para la sustentación.",
        "decision": "Scripts infra/01..04 idempotentes (verifican antes de crear), cloudbuild.yaml para pruebas, "
                    "imágenes y despliegue, y GitHub Actions para lint, pruebas y construcción en cada push.",
        "alternativas": "Terraform; despliegue manual por consola.",
        "tecnica": "Los scripts son legibles y se ejecutan en Cloud Shell sin instalar nada. Terraform aporta "
                   "estado y detección de desvíos: queda como evolución.",
        "finops": "Cloud Build: minutos gratis diarios; infra/99_eliminar.sh borra todo tras la sustentación.",
        "consecuencias": "Sin archivo de estado, los cambios manuales en consola no se detectan automáticamente.",
    },
    {
        "id": "ADR-13", "titulo": "Escalado de ms-asistencia y observabilidad definidos con pruebas de carga",
        "estado": "Aprobado",
        "contexto": "El objetivo de registro es p95 < 300 ms en POST /api/marcaciones. La primera prueba de carga "
                    "(25 usuarios simultáneos) mostró colas de 5 a 30 s; había que separar la latencia del servicio "
                    "de la del cliente y de los arranques de instancias nuevas.",
        "decision": "ms-asistencia con 10 solicitudes simultáneas por instancia, entre 1 y 5 instancias, y "
                    "conexiones a Firestore y Pub/Sub abiertas al arrancar (antes de recibir tráfico). La latencia "
                    "oficial se mide en el servidor (registros de Cloud Run); el cliente la complementa. Cloud "
                    "Monitoring con verificación de /salud, 4 alertas por correo y un tablero de operación.",
        "alternativas": "Mantener 40 solicitudes por instancia y escala a cero; 3 instancias siempre encendidas; "
                        "más CPU por instancia.",
        "tecnica": "Con 40 solicitudes por instancia una sola CPU atendía toda la ráfaga. Con 3 instancias "
                   "encendidas la cola del cliente no desapareció, lo que demostró que venía de la red de Cloud Shell "
                   "y no del servicio. Medido en el servidor, el registro cumple: p95 de 209 a 246 ms.",
        "finops": "Una instancia mínima inactiva cuesta unos USD 8 al mes en us-central1; tres costarían el triple "
                  "sin mejorar la medida del servidor. Tras la sustentación, infra/99_eliminar.sh la elimina.",
        "consecuencias": "La primera marcación tras un periodo inactivo ya no paga el arranque en frío. Las ráfagas "
                         "que exigen instancias nuevas pueden demorar algunas solicitudes; la PWA offline-first "
                         "(ADR-10) las conserva en el celular y las reintenta, así que el supervisor no espera.",
    },
]


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60]


def archivo(a: dict) -> str:
    return (
        f"# {a['id']}: {a['titulo']}\n\n**Estado:** {a['estado']}\n\n"
        f"## Contexto\n{a['contexto']}\n\n## Decisión\n{a['decision']}\n\n"
        f"## Alternativas evaluadas\n{a['alternativas']}\n\n## Justificación técnica\n{a['tecnica']}\n\n"
        f"## Criterio FinOps\n{a['finops']}\n\n## Consecuencias\n{a['consecuencias']}\n"
    )


def detalle() -> str:
    partes = []
    for a in ADRS:
        partes.append(
            f"### {a['id']}. {a['titulo']}\n\n**Estado:** {a['estado']}\n\n"
            f"- **Contexto:** {a['contexto']}\n- **Decisión:** {a['decision']}\n"
            f"- **Alternativas:** {a['alternativas']}\n- **Justificación técnica:** {a['tecnica']}\n"
            f"- **Criterio FinOps:** {a['finops']}\n- **Consecuencias:** {a['consecuencias']}\n"
        )
    return "\n".join(partes)


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    indice = ["# Registro de decisiones de arquitectura (ADR)\n", "| ID | Decisión | Estado |", "|---|---|---|"]
    for a in ADRS:
        nombre = f"{a['id']}-{slug(a['titulo'])}.md"
        with open(os.path.join(base, nombre), "w", encoding="utf-8") as f:
            f.write(archivo(a))
        indice.append(f"| [{a['id']}]({nombre}) | {a['titulo']} | {a['estado']} |")
    with open(os.path.join(base, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(indice) + "\n")
    print(f"{len(ADRS)} ADR generados")
