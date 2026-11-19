# ADR-12: Infraestructura con scripts gcloud idempotentes y CI/CD con Cloud Build y GitHub Actions

**Estado:** Aprobado; Terraform propuesto

## Contexto
El ambiente debe poder recrearse y eliminarse fácilmente para la sustentación.

## Decisión
Scripts infra/01..04 idempotentes (verifican antes de crear), cloudbuild.yaml para pruebas, imágenes y despliegue, y GitHub Actions para lint, pruebas y construcción en cada push.

## Alternativas evaluadas
Terraform; despliegue manual por consola.

## Justificación técnica
Los scripts son legibles y se ejecutan en Cloud Shell sin instalar nada. Terraform aporta estado y detección de desvíos: queda como evolución.

## Criterio FinOps
Cloud Build: minutos gratis diarios; infra/99_eliminar.sh borra todo tras la sustentación.

## Consecuencias
Sin archivo de estado, los cambios manuales en consola no se detectan automáticamente.
