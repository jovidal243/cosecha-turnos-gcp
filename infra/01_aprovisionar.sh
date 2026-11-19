#!/usr/bin/env bash
# Paso 1: crea la infraestructura base en Google Cloud (idempotente: se puede repetir).
# Ejecutar desde Cloud Shell, en la raíz del repositorio:  bash infra/01_aprovisionar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source infra/variables.env

gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
PUBSUB_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
sa() { echo "$1@${PROJECT_ID}.iam.gserviceaccount.com"; }

echo "==> 1/9 Habilitando APIs"
gcloud services enable \
  run.googleapis.com pubsub.googleapis.com firestore.googleapis.com bigquery.googleapis.com \
  storage.googleapis.com aiplatform.googleapis.com secretmanager.googleapis.com \
  cloudscheduler.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  logging.googleapis.com monitoring.googleapis.com iam.googleapis.com billingbudgets.googleapis.com

echo "==> 2/9 Artifact Registry"
gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location="$REGION" \
       --description="Imágenes de los microservicios de turnos de Cosecha"

echo "==> 3/9 Firestore (modo nativo)"
gcloud firestore databases describe --database='(default)' >/dev/null 2>&1 \
  || gcloud firestore databases create --location="$REGION" --type=firestore-native

echo "==> 4/9 Cloud Storage"
gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 \
  || gcloud storage buckets create "gs://$BUCKET" --location="$REGION" \
       --uniform-bucket-level-access --public-access-prevention

echo "==> 5/9 Pub/Sub"
for t in marcaciones marcaciones-dlq alertas; do
  gcloud pubsub topics describe "$t" >/dev/null 2>&1 || gcloud pubsub topics create "$t"
done
gcloud pubsub subscriptions describe marcaciones-dlq-sub >/dev/null 2>&1 \
  || gcloud pubsub subscriptions create marcaciones-dlq-sub --topic=marcaciones-dlq --message-retention-duration=7d
gcloud pubsub subscriptions describe alertas-auditoria >/dev/null 2>&1 \
  || gcloud pubsub subscriptions create alertas-auditoria --topic=alertas --message-retention-duration=7d

echo "==> 6/9 BigQuery"
bq show "${PROJECT_ID}:${BQ_DATASET}" >/dev/null 2>&1 \
  || bq --location="$REGION" mk --dataset --description "Histórico de turnos y asistencia (sintético)" "${PROJECT_ID}:${BQ_DATASET}"
for tabla in jornadas_validadas decisiones cierres_diarios; do
  bq show "${PROJECT_ID}:${BQ_DATASET}.${tabla}" >/dev/null 2>&1 \
    || bq mk --table --time_partitioning_field fecha --time_partitioning_type DAY \
         "${PROJECT_ID}:${BQ_DATASET}.${tabla}" "infra/bigquery/${tabla}.json"
done
PROJECT_ID=$PROJECT_ID BQ_DATASET=$BQ_DATASET envsubst < infra/bigquery/vista_horas_por_frente.sql \
  | bq query --use_legacy_sql=false --location="$REGION" >/dev/null

echo "==> 7/9 Cuentas de servicio (mínimo privilegio)"
# Google limita cuántas cuentas de servicio se crean por minuto en un proyecto nuevo (error 429):
# se crea una a la vez y, si se alcanza el límite, se espera y se reintenta.
crear_sa() {
  gcloud iam service-accounts describe "$(sa "$1")" >/dev/null 2>&1 && return 0
  for intento in 1 2 3 4; do
    gcloud iam service-accounts create "$1" --display-name="$1 (turnos cosecha)" && { sleep 5; return 0; }
    echo "    Límite de creación de cuentas alcanzado; reintento ${intento}/4 en 65 s..."
    sleep 65
  done
  return 1
}
for c in sa-asistencia sa-validacion sa-reportes sa-invocador sa-cloudbuild; do
  crear_sa "$c"
done
proyecto() { gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$(sa "$1")" --role="$2" --condition=None >/dev/null; }
for c in sa-asistencia sa-validacion sa-reportes; do
  proyecto "$c" roles/datastore.user
  proyecto "$c" roles/aiplatform.user
  proyecto "$c" roles/logging.logWriter
done
for c in sa-asistencia sa-validacion sa-reportes; do
  bq add-iam-policy-binding --member="serviceAccount:$(sa $c)" --role=roles/bigquery.dataEditor \
    "${PROJECT_ID}:${BQ_DATASET}" >/dev/null 2>&1 || proyecto "$c" roles/bigquery.dataEditor
done
gcloud pubsub topics add-iam-policy-binding marcaciones --member="serviceAccount:$(sa sa-asistencia)" --role=roles/pubsub.publisher >/dev/null
gcloud pubsub topics add-iam-policy-binding alertas --member="serviceAccount:$(sa sa-validacion)" --role=roles/pubsub.publisher >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$(sa sa-validacion)" --role=roles/storage.objectViewer >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$(sa sa-reportes)" --role=roles/storage.objectUser >/dev/null
# Cloud Build: construir, publicar imágenes y desplegar en Cloud Run
for r in roles/run.admin roles/iam.serviceAccountUser roles/artifactregistry.writer roles/logging.logWriter roles/storage.objectViewer; do
  proyecto sa-cloudbuild "$r"
done
# Agente de Pub/Sub: firmar tokens OIDC del push y manejar la cola dead-letter
gcloud iam service-accounts add-iam-policy-binding "$(sa sa-invocador)" \
  --member="serviceAccount:${PUBSUB_AGENT}" --role=roles/iam.serviceAccountTokenCreator >/dev/null
gcloud pubsub topics add-iam-policy-binding marcaciones-dlq --member="serviceAccount:${PUBSUB_AGENT}" --role=roles/pubsub.publisher >/dev/null

echo "==> 8/9 Secret Manager (tokens por rol)"
if ! gcloud secrets describe api-tokens >/dev/null 2>&1; then
  T_SUP=$(openssl rand -hex 20); T_JEFE=$(openssl rand -hex 20); T_ANA=$(openssl rand -hex 20)
  printf '{"%s":"supervisor","%s":"jefe_frente","%s":"analista"}' "$T_SUP" "$T_JEFE" "$T_ANA" \
    | gcloud secrets create api-tokens --replication-policy=automatic --data-file=-
  printf 'supervisor=%s\njefe_frente=%s\nanalista=%s\n' "$T_SUP" "$T_JEFE" "$T_ANA" > infra/tokens.local.txt
  chmod 600 infra/tokens.local.txt
  echo "    Tokens guardados en infra/tokens.local.txt (NO subir a GitHub)"
fi
gcloud secrets add-iam-policy-binding api-tokens --member="serviceAccount:$(sa sa-asistencia)" \
  --role=roles/secretmanager.secretAccessor >/dev/null

echo "==> 9/9 Presupuesto (FinOps)"
if [[ -n "${BILLING_ACCOUNT:-}" ]]; then
  gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" --format='value(displayName)' | grep -qx "turnos-cosecha" \
    || gcloud billing budgets create --billing-account="$BILLING_ACCOUNT" --display-name="turnos-cosecha" \
         --budget-amount="${PRESUPUESTO_USD}USD" --filter-projects="projects/${PROJECT_ID}" \
         --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
else
  echo "    BILLING_ACCOUNT vacío: cree el presupuesto desde Facturación > Presupuestos y alertas"
fi

echo "Listo. Siguiente paso: bash infra/02_desplegar.sh"
