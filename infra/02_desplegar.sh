#!/usr/bin/env bash
# Paso 2: pruebas + construcción de imágenes + despliegue de los 3 servicios en Cloud Run (vía Cloud Build).
set -euo pipefail
cd "$(dirname "$0")/.."
source infra/variables.env
TAG="v$(date +%Y%m%d-%H%M)"

gcloud builds submit --config cloudbuild.yaml \
  --region="$REGION" \
  --service-account="projects/${PROJECT_ID}/serviceAccounts/sa-cloudbuild@${PROJECT_ID}.iam.gserviceaccount.com" \
  --substitutions="_REGION=${REGION},_AR_REPO=${AR_REPO},_BUCKET=${BUCKET},_BQ_DATASET=${BQ_DATASET},_GEMINI_MODEL=${GEMINI_MODEL},_GEMINI_LOCATION=${GEMINI_LOCATION},_TAG=${TAG}"

echo
gcloud run services list --region "$REGION" --format="table(metadata.name,status.url)"
echo "Siguiente paso (solo la primera vez): bash infra/03_conectar_eventos.sh"
