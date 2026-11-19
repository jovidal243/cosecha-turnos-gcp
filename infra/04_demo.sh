#!/usr/bin/env bash
# Paso 4 (demo): simula dos días de marcaciones con casos atípicos y ejecuta el cierre diario.
set -euo pipefail
cd "$(dirname "$0")/.."
source infra/variables.env
URL_ASI=$(gcloud run services describe ms-asistencia --region "$REGION" --format='value(status.url)')
URL_REP=$(gcloud run services describe ms-reportes --region "$REGION" --format='value(status.url)')
TOKEN_SUP=$(grep '^supervisor=' infra/tokens.local.txt | cut -d= -f2)
D1=$(TZ=America/Bogota date -d '2 days ago' +%F); D2=$(TZ=America/Bogota date -d 'yesterday' +%F)

pip install -q --user httpx >/dev/null 2>&1 || true
python3 -m scripts.simular_dia --url "$URL_ASI" --token "$TOKEN_SUP" --fechas "$D1" "$D2"

echo "Esperando a que Pub/Sub entregue y ms-validacion procese..."
sleep 30
for F in "$D1" "$D2"; do
  curl -s -X POST "${URL_REP}/tareas/cierre-diario" \
    -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
    -H "Content-Type: application/json" -d "{\"fecha\":\"$F\"}" | python3 -m json.tool | head -20
done
echo
echo "Revise: ${URL_ASI}/app/ (fecha $D2) · BigQuery: ${BQ_DATASET}.jornadas_validadas · gs://${BUCKET}/nomina/"
