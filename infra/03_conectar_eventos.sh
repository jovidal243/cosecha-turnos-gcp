#!/usr/bin/env bash
# Paso 3: conecta Pub/Sub -> ms-validacion (push OIDC) y Cloud Scheduler -> ms-reportes, y carga los datos sintéticos.
set -euo pipefail
cd "$(dirname "$0")/.."
source infra/variables.env
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
PUBSUB_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
INVOCADOR="sa-invocador@${PROJECT_ID}.iam.gserviceaccount.com"
url() { gcloud run services describe "$1" --region "$REGION" --format='value(status.url)'; }
URL_VAL=$(url ms-validacion); URL_REP=$(url ms-reportes); URL_ASI=$(url ms-asistencia)

echo "==> Permiso de invocación (solo sa-invocador puede llamar a los servicios privados)"
for s in ms-validacion ms-reportes; do
  gcloud run services add-iam-policy-binding "$s" --region "$REGION" \
    --member="serviceAccount:${INVOCADOR}" --role=roles/run.invoker >/dev/null
done

echo "==> Suscripción push con orden por trabajador, reintentos y dead-letter"
if ! gcloud pubsub subscriptions describe validacion-push >/dev/null 2>&1; then
  gcloud pubsub subscriptions create validacion-push --topic=marcaciones \
    --push-endpoint="${URL_VAL}/pubsub/push" \
    --push-auth-service-account="$INVOCADOR" --push-auth-token-audience="$URL_VAL" \
    --ack-deadline=60 --enable-message-ordering \
    --dead-letter-topic=marcaciones-dlq --max-delivery-attempts=5 \
    --min-retry-delay=10s --max-retry-delay=300s
fi
gcloud pubsub subscriptions add-iam-policy-binding validacion-push \
  --member="serviceAccount:${PUBSUB_AGENT}" --role=roles/pubsub.subscriber >/dev/null

echo "==> Cloud Scheduler: cierre diario a las 05:30 (hora Colombia)"
if ! gcloud scheduler jobs describe cierre-diario --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs create http cierre-diario --location "$REGION" \
    --schedule="30 5 * * *" --time-zone="America/Bogota" \
    --uri="${URL_REP}/tareas/cierre-diario" --http-method=POST \
    --headers="Content-Type=application/json" --message-body='{}' \
    --oidc-service-account-email="$INVOCADOR" --oidc-token-audience="$URL_REP" \
    --attempt-deadline=300s
fi

echo "==> Datos sintéticos (frentes, trabajadores y turnos de los últimos 3 días y hoy)"
pip install -q --user google-cloud-firestore >/dev/null 2>&1 || true
MODO=gcp GOOGLE_CLOUD_PROJECT="$PROJECT_ID" python3 -m scripts.cargar_semilla --dias 4

echo
echo "App del supervisor: ${URL_ASI}/app/"
echo "Documentación API: ${URL_ASI}/docs"
echo "Tokens: infra/tokens.local.txt"
