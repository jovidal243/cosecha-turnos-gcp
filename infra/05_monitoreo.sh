#!/usr/bin/env bash
# Paso 5 (operación): canal de correo, verificación de disponibilidad, 4 alertas y tablero en Cloud Monitoring.
# Es idempotente: si un recurso con el mismo nombre ya existe, no lo vuelve a crear.
set -euo pipefail
cd "$(dirname "$0")/.."
source infra/variables.env
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable monitoring.googleapis.com --quiet

if [[ -z "${ALERT_EMAIL:-}" ]]; then
  read -r -p "Correo que recibirá las alertas: " ALERT_EMAIL
fi

echo "1/4 Canal de notificación por correo (${ALERT_EMAIL})"
CANAL=$(gcloud beta monitoring channels list \
  --filter="type=\"email\" AND labels.email_address=\"${ALERT_EMAIL}\"" --format='value(name)' | head -1)
if [[ -z "$CANAL" ]]; then
  CANAL=$(gcloud beta monitoring channels create --type=email \
    --display-name="Turnos Cosecha · ${ALERT_EMAIL}" \
    --channel-labels="email_address=${ALERT_EMAIL}" --format='value(name)')
fi
echo "    $CANAL"

echo "2/4 Verificación de disponibilidad de /salud cada 5 minutos"
URL_ASI=$(gcloud run services describe ms-asistencia --region "$REGION" --format='value(status.url)')
HOST=${URL_ASI#https://}
NOMBRE_UPTIME="Turnos Cosecha · ms-asistencia /salud"
UPTIME=$(gcloud monitoring uptime list-configs \
  --filter="displayName=\"${NOMBRE_UPTIME}\"" --format='value(name)' | head -1)
if [[ -z "$UPTIME" ]]; then
  UPTIME=$(gcloud monitoring uptime create "$NOMBRE_UPTIME" \
    --resource-type=uptime-url --resource-labels="host=${HOST},project_id=${PROJECT_ID}" \
    --protocol=https --port=443 --path=/salud --period=5 --timeout=10 --format='value(name)')
fi
CHECK_ID=${UPTIME##*/}
echo "    $HOST/salud (id ${CHECK_ID})"

echo "3/4 Políticas de alerta"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
for f in infra/monitoreo/alerta_*.json; do
  sed -e "s#__CANAL__#${CANAL}#" -e "s#__CHECK_ID__#${CHECK_ID}#" "$f" > "$TMP/$(basename "$f")"
  NOMBRE=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['displayName'])" "$f")
  if [[ -n $(gcloud alpha monitoring policies list --filter="displayName=\"${NOMBRE}\"" --format='value(name)') ]]; then
    echo "    ya existe: $NOMBRE"
  else
    gcloud alpha monitoring policies create --policy-from-file="$TMP/$(basename "$f")" --quiet >/dev/null
    echo "    creada:    $NOMBRE"
  fi
done

echo "4/4 Tablero de operación"
NOMBRE_TABLERO=$(python3 -c "import json; print(json.load(open('infra/monitoreo/tablero.json'))['displayName'])")
if [[ -n $(gcloud monitoring dashboards list --filter="displayName=\"${NOMBRE_TABLERO}\"" --format='value(name)') ]]; then
  echo "    ya existe: $NOMBRE_TABLERO"
else
  gcloud monitoring dashboards create --config-from-file=infra/monitoreo/tablero.json --quiet >/dev/null
  echo "    creado:    $NOMBRE_TABLERO"
fi

echo
echo "Listo. Revise el correo ${ALERT_EMAIL}: Google no envía alertas hasta que el canal quede verificado (si llega un correo de verificación, ábralo)."
echo "Tablero: https://console.cloud.google.com/monitoring/dashboards?project=${PROJECT_ID}"
echo "Alertas: https://console.cloud.google.com/monitoring/alerting?project=${PROJECT_ID}"
