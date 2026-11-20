"""Definición de los diagramas de arquitectura de Turnos Cosecha.

Genera HTML (editable) y PNG en dos temas:
    python docs/diagramas/fuente/diagramas.py
Requiere: playwright con Chromium (solo para exportar a PNG).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from motor import LEYENDA_BASE, Diagrama, Flecha, Limite, Nodo, render_html  # noqa: E402

PLATAFORMA = (
    "<b>Plataforma:</b> IAM (5 cuentas de servicio, mínimo privilegio) · Secret Manager (tokens por rol) · "
    "Artifact Registry · Cloud Build · Cloud Logging + Monitoring · presupuesto con alertas"
)


def arquitectura() -> Diagrama:
    d = Diagrama("Turnos Cosecha · Arquitectura en Google Cloud", 1840, 1010, leyenda=LEYENDA_BASE)
    d.limites += [
        Limite(290, 40, 1500, 740, "Google Cloud · us-central1 · proyecto cosecha-turnos-uao"),
        Limite(700, 84, 300, 590, "Cloud Run · escala 0 → N", tono="nucleo"),
    ]
    d.nodos += [
        Nodo("usr", 40, 110, "Usuarios", "supervisor · PWA offline<br>jefe de frente · analista", "USR", "externo", w=220),
        Nodo("asi", 720, 110, "ms-asistencia", "API + PWA · público<br>token por rol", "RUN", "nucleo"),
        Nodo("fs", 1100, 110, "Firestore", "turnos · marcaciones<br>jornadas · auditoría", "DB", "datos"),
        Nodo("ps", 340, 330, "Pub/Sub", "marcaciones · orden por<br>trabajador · DLQ · alertas", "MSG"),
        Nodo("val", 720, 330, "ms-validacion", "10 reglas + Isolation Forest<br>privado · OIDC", "RUN", "nucleo"),
        Nodo("gem", 1100, 330, "Vertex AI · Gemini", "gemini-3.8-flash · explica<br>resume · asistente", "IA", "nucleo"),
        Nodo("bq", 1480, 330, "BigQuery", "jornadas_validadas<br>decisiones · cierres", "BQ", "datos"),
        Nodo("sch", 340, 550, "Cloud Scheduler", "cierre-diario<br>05:30 America/Bogota", "CRON"),
        Nodo("rep", 720, 550, "ms-reportes", "cierre diario · privado<br>lee Firestore", "RUN", "nucleo"),
        Nodo("gcs", 1100, 550, "Cloud Storage", "nómina CSV · resúmenes<br>modelo .joblib", "GCS", "datos"),
        Nodo("nom", 1100, 820, "ERP / Nómina", "horas válidas o aprobadas", "EXT", "externo"),
        Nodo("pbi", 1480, 820, "Power BI · Looker Studio", "vista v_horas_por_frente", "EXT", "externo"),
    ]
    d.flechas += [
        Flecha([(260, 158), (720, 158)], "HTTPS · token por rol", "externa"),
        Flecha([(980, 158), (1100, 158)], "idempotente", "interna"),
        Flecha([(800, 206), (800, 268), (470, 268), (470, 330)], "publica evento", "principal", pos=(635, 268)),
        Flecha([(600, 378), (720, 378)], "push OIDC", "asincrona"),
        Flecha([(980, 378), (1100, 378)], "explica", "principal"),
        Flecha([(950, 330), (950, 250), (1180, 250), (1180, 206)], "jornadas", "interna", pos=(1065, 250)),
        Flecha([(980, 350), (1040, 350), (1040, 300), (1610, 300), (1610, 330)], "histórico", "interna", pos=(1340, 300)),
        Flecha([(930, 550), (930, 480), (1200, 480), (1200, 426)], "resumen diario", "principal", pos=(1065, 480)),
        Flecha([(600, 598), (720, 598)], "OIDC · 05:30", "asincrona"),
        Flecha([(980, 598), (1100, 598)], "CSV nómina", "interna"),
        Flecha([(1230, 646), (1230, 820)], "archivo diario", "asincrona", pos=(1230, 740)),
        Flecha([(1610, 426), (1610, 820)], "vistas SQL", "asincrona", pos=(1610, 740)),
    ]
    d.notas.append((340, 712, 760, PLATAFORMA))
    return d


def flujo() -> Diagrama:
    d = Diagrama("Turnos Cosecha · Flujo de una marcación", 1860, 900, leyenda=LEYENDA_BASE)
    d.limites += [Limite(290, 30, 1530, 700, "Google Cloud · us-central1")]
    d.nodos += [
        Nodo("pwa", 40, 240, "Supervisor · PWA", "QR + GPS · UUID<br>cola en IndexedDB", "USR", "externo", w=200),
        Nodo("jefe", 40, 600, "Jefe de frente", "aprueba o rechaza<br>observadas", "USR", "externo", w=200),
        Nodo("asi", 360, 240, "ms-asistencia", "valida el payload<br>responde 202", "RUN", "nucleo", w=240),
        Nodo("dlq", 740, 70, "Pub/Sub · DLQ", "marcaciones-dlq<br>reintentos agotados", "MSG", w=240),
        Nodo("ps", 740, 240, "Pub/Sub", "marcaciones · orden<br>por trabajador", "MSG", w=240),
        Nodo("val", 1120, 240, "ms-validacion", "5 · reglas R01–R10<br>+ Isolation Forest", "RUN", "nucleo", w=240),
        Nodo("gem", 1500, 240, "Vertex AI · Gemini", "explicación +<br>acción sugerida", "IA", "nucleo", w=280),
        Nodo("fs", 360, 440, "Firestore", "marcaciones (estado) · jornadas · alertas · auditoría de cada acción",
             "DB", "datos", w=1000, h=80),
        Nodo("bq", 1500, 600, "BigQuery", "jornadas_validadas<br>particionada por fecha", "BQ", "datos", w=280),
    ]
    d.flechas += [
        Flecha([(240, 288), (360, 288)], "1 · lote", "externa"),
        Flecha([(480, 336), (480, 440)], "2 · guarda (UUID)", "interna", pos=(480, 392)),
        Flecha([(600, 288), (740, 288)], "3 · publica", "principal"),
        Flecha([(980, 288), (1120, 288)], "4 · push OIDC", "asincrona"),
        Flecha([(1360, 288), (1500, 288)], "6 · explica", "principal"),
        Flecha([(1240, 336), (1240, 440)], "7 · jornada + alerta", "interna", pos=(1240, 392)),
        Flecha([(1360, 320), (1430, 320), (1430, 648), (1500, 648)], "8 · histórico", "interna", pos=(1430, 580)),
        Flecha([(860, 240), (860, 166)], "5 intentos fallidos", "asincrona", pos=(860, 203)),
        Flecha([(240, 648), (310, 648), (310, 310), (360, 310)], "9 · decide", "externa", pos=(310, 470)),
    ]
    d.notas += [
        (360, 560, 1000,
         "<b>Sin señal:</b> el paso 1 espera en el dispositivo y se envía al volver la conexión. "
         "El UUID generado en el celular hace que un reintento responda «duplicada» en vez de crear otra jornada."),
        (360, 635, 1000,
         "<b>Tolerancia a fallos:</b> si ms-validacion o Gemini fallan, Pub/Sub reintenta con espera creciente "
         "(10 s a 5 min); tras 5 intentos el mensaje pasa a la cola dead-letter. Si Gemini no responde, "
         "una plantilla redacta la explicación y el flujo sigue."),
    ]
    return d


def seguridad() -> Diagrama:
    d = Diagrama("Turnos Cosecha · Seguridad e identidades", 1840, 960, leyenda=LEYENDA_BASE)
    d.limites += [
        Limite(290, 40, 1500, 760, "Google Cloud · us-central1"),
        Limite(1075, 84, 465, 700, "IAM · cuentas de servicio (mínimo privilegio)", tono="nucleo"),
    ]
    roles_asi = "datastore.user · pubsub.publisher (marcaciones)<br>secretAccessor (api-tokens) · aiplatform.user<br>bigquery.dataEditor (dataset)"
    roles_val = "datastore.user · pubsub.publisher (alertas)<br>storage.objectViewer (modelo) · aiplatform.user<br>bigquery.dataEditor (dataset)"
    roles_rep = "datastore.user · storage.objectUser (bucket)<br>aiplatform.user · bigquery.dataEditor"
    roles_cb = "run.admin · artifactregistry.writer<br>iam.serviceAccountUser · logging.logWriter"
    d.nodos += [
        Nodo("usr", 40, 120, "Usuarios", "supervisor · jefe de frente<br>analista", "USR", "externo", w=220),
        Nodo("ps", 340, 300, "Pub/Sub", "suscripción push<br>firma con sa-invocador", "MSG"),
        Nodo("sch", 340, 480, "Cloud Scheduler", "cierre-diario<br>firma con sa-invocador", "CRON"),
        Nodo("asi", 720, 120, "ms-asistencia", "público · token Bearer<br>por rol (3 roles)", "RUN", "nucleo"),
        Nodo("val", 720, 300, "ms-validacion", "privado · run.invoker<br>solo sa-invocador", "RUN", "nucleo"),
        Nodo("rep", 720, 480, "ms-reportes", "privado · run.invoker<br>solo sa-invocador", "RUN", "nucleo"),
        Nodo("cbs", 720, 660, "Cloud Build", "construye y despliega", "BUILD"),
        Nodo("sa1", 1100, 114, "sa-asistencia", roles_asi, "IAM", "servicio", w=410, h=108),
        Nodo("sa2", 1100, 294, "sa-validacion", roles_val, "IAM", "servicio", w=410, h=108),
        Nodo("sa3", 1100, 474, "sa-reportes", roles_rep, "IAM", "servicio", w=410, h=108),
        Nodo("sa4", 1100, 654, "sa-cloudbuild", roles_cb, "IAM", "servicio", w=410, h=108),
        Nodo("sec", 1570, 120, "Secret Manager", "api-tokens<br>(JSON por rol)", "SEC", "datos", w=200, h=104),
    ]
    d.flechas += [
        Flecha([(260, 168), (720, 168)], "HTTPS · Bearer", "externa"),
        Flecha([(600, 348), (720, 348)], "OIDC", "asincrona"),
        Flecha([(600, 528), (720, 528)], "OIDC", "asincrona"),
        Flecha([(980, 168), (1100, 168)], "corre como", "asincrona", pos=(1024, 154)),
        Flecha([(980, 348), (1100, 348)], "corre como", "asincrona", pos=(1024, 334)),
        Flecha([(980, 528), (1100, 528)], "corre como", "asincrona", pos=(1024, 514)),
        Flecha([(980, 708), (1100, 708)], "corre como", "asincrona", pos=(1024, 694)),
        Flecha([(1570, 168), (1510, 168)], "", "interna"),
    ]
    d.notas += [
        (340, 668, 340,
         "<b>Ley 1581 de 2012:</b> datos sintéticos, sin biometría (QR + GPS), seudonimización antes de Gemini "
         "y auditoría de cada acción."),
        (1570, 260, 200,
         "<b>Sin llaves:</b> ningún servicio usa archivos de credenciales; el repositorio no contiene secretos."),
    ]
    return d


def cicd() -> Diagrama:
    d = Diagrama("Turnos Cosecha · CI/CD y despliegue", 1640, 900, leyenda=LEYENDA_BASE)
    d.limites += [
        Limite(380, 40, 1220, 740, "Google Cloud · us-central1 · cosecha-turnos-uao"),
        Limite(1160, 150, 320, 470, "Cloud Run", tono="nucleo"),
    ]
    d.nodos += [
        Nodo("dev", 40, 120, "Desarrollador", "VS Code · PowerShell<br>navegador", "USR", "externo", w=260),
        Nodo("gh", 40, 330, "GitHub", "jovidal243/<br>cosecha-turnos-gcp", "GIT", "externo", w=260),
        Nodo("gha", 40, 560, "GitHub Actions", "ruff · pytest (19)<br>docker build × 3", "CI", "externo", w=260),
        Nodo("csh", 440, 120, "Cloud Shell", "infra/01 → 04<br>scripts idempotentes", "CLI"),
        Nodo("cb", 800, 330, "Cloud Build", "pytest → 3 imágenes<br>→ push → deploy", "BUILD", "nucleo"),
        Nodo("ar", 800, 560, "Artifact Registry", "3 imágenes<br>etiqueta vAAAAMMDD-HHMM", "AR", "datos"),
        Nodo("r1", 1190, 190, "ms-asistencia", "público", "RUN", "nucleo"),
        Nodo("r2", 1190, 340, "ms-validacion", "privado", "RUN", "nucleo"),
        Nodo("r3", 1190, 490, "ms-reportes", "privado", "RUN", "nucleo"),
        Nodo("obs", 1190, 660, "Logging + Monitoring", "logs · métricas<br>presupuesto USD 20", "OBS"),
    ]
    d.flechas += [
        Flecha([(170, 216), (170, 330)], "git push", "externa", pos=(170, 273)),
        Flecha([(170, 426), (170, 560)], "CI en cada push", "asincrona", pos=(170, 493)),
        Flecha([(300, 168), (440, 168)], "ejecuta", "externa", pos=(340, 152)),
        Flecha([(700, 168), (930, 168), (930, 330)], "gcloud builds submit", "principal", pos=(815, 168)),
        Flecha([(300, 378), (800, 378)], "activador opcional", "asincrona", pos=(550, 378)),
        Flecha([(930, 426), (930, 560)], "push imágenes", "interna", pos=(930, 493)),
        Flecha([(1060, 608), (1120, 608), (1120, 238), (1190, 238)], "despliega", "principal", pos=(1120, 420)),
        Flecha([(1120, 388), (1190, 388)], "", "principal"),
        Flecha([(1120, 538), (1190, 538)], "", "principal"),
        Flecha([(1320, 586), (1320, 660)], "", "asincrona"),
    ]
    d.notas += [
        (440, 680, 640,
         "<b>Verificado el 18/11/2026:</b> STATUS SUCCESS en 3 min 19 s (primer despliegue) y 3 min 22 s (actualización). "
         "Cloud Build corre como sa-cloudbuild; la CI de GitHub repite pruebas e imágenes en cada push."),
    ]
    return d


TODOS = {
    "01_arquitectura": arquitectura,
    "02_flujo": flujo,
    "05_seguridad": seguridad,
    "06_cicd": cicd,
}


def exportar(salida_html: str, salida_png: str) -> None:
    from playwright.sync_api import sync_playwright

    os.makedirs(salida_html, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
        pagina = nav.new_page(device_scale_factor=2)
        for nombre, fabrica in TODOS.items():
            d = fabrica()
            for tema in ("color", "bn"):
                html = render_html(d, tema)
                sufijo = "" if tema == "color" else "_bn"
                ruta_html = os.path.join(salida_html, f"{nombre}{sufijo}.html")
                with open(ruta_html, "w", encoding="utf-8") as f:
                    f.write(html)
                pagina.set_viewport_size({"width": d.ancho, "height": d.alto})
                pagina.goto("file://" + os.path.abspath(ruta_html))
                pagina.locator(".lienzo").screenshot(path=os.path.join(salida_png, f"{nombre}{sufijo}.png"))
                print("ok", nombre, tema)
        nav.close()


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exportar(os.path.join(base, "html"), base)
