# ADR-11: Identificación por QR del carné + geolocalización (sin biometría)

**Estado:** Aprobado

## Contexto
La Ley 1581 de 2012 clasifica los datos biométricos como sensibles.

## Decisión
El supervisor lee el QR del carné existente; la posición GPS valida la geocerca del frente.

## Alternativas evaluadas
Huella o reconocimiento facial; planilla con firma.

## Justificación técnica
Usa los carnés actuales y evita tratar datos sensibles; la geocerca reduce marcaciones remotas.

## Criterio FinOps
No requiere hardware dedicado.

## Consecuencias
No impide que un supervisor marque por otro trabajador; la trazabilidad (quién registró) y la auditoría lo hacen detectable.
