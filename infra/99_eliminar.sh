#!/usr/bin/env bash
# Elimina los recursos del proyecto para no generar costos después de la sustentación.
# Alternativa más simple: gcloud projects delete "$PROJECT_ID"
set -uo pipefail
cd "$(dirname "$0")/.."
source infra/variables.env
read -r -p "Se eliminarán los recursos de ${PROJECT_ID}. Escriba ELIMINAR para continuar: " ok
[[ "$ok" == "ELIMINAR" ]] || exit 1
# Monitoreo (paso 05): alertas, verificación de disponibilidad y tablero
for p in $(gcloud alpha monitoring policies list --filter='displayName:"Turnos Cosecha"' --format='value(name)'); do gcloud alpha monitoring policies delete "$p" --quiet; done
for u in $(gcloud monitoring uptime list-configs --filter='displayName:"Turnos Cosecha"' --format='value(name)'); do gcloud monitoring uptime delete "$u" --quiet; done
for d in $(gcloud monitoring dashboards list --filter='displayName:"Turnos Cosecha"' --format='value(name)'); do gcloud monitoring dashboards delete "$d" --quiet; done
gcloud scheduler jobs delete cierre-diario --location "$REGION" --quiet
for s in ms-asistencia ms-validacion ms-reportes; do gcloud run services delete "$s" --region "$REGION" --quiet; done
for s in validacion-push marcaciones-dlq-sub alertas-auditoria; do gcloud pubsub subscriptions delete "$s" --quiet; done
for t in marcaciones marcaciones-dlq alertas; do gcloud pubsub topics delete "$t" --quiet; done
bq rm -r -f "${PROJECT_ID}:${BQ_DATASET}"
gcloud storage rm -r "gs://${BUCKET}"
gcloud artifacts repositories delete "$AR_REPO" --location "$REGION" --quiet
gcloud secrets delete api-tokens --quiet
gcloud firestore databases delete --database='(default)' --quiet
echo "Recursos eliminados."
