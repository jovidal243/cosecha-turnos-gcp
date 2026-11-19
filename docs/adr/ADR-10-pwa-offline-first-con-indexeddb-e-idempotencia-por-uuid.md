# ADR-10: PWA offline-first con IndexedDB e idempotencia por UUID

**Estado:** Aprobado

## Contexto
Los frentes tienen cobertura móvil intermitente.

## Decisión
App web progresiva: service worker para abrir sin señal, cola local en IndexedDB y sincronización en lote ordenada por hora. Cada marcación lleva un UUID generado en el dispositivo.

## Alternativas evaluadas
App nativa Android; web solo en línea.

## Justificación técnica
Un solo código para cualquier celular, sin publicar en tiendas. El UUID permite reintentar sin duplicar (el backend responde 'duplicada').

## Criterio FinOps
Se sirve desde el mismo ms-asistencia; no requiere hosting adicional.

## Consecuencias
La lectura de QR usa la API BarcodeDetector (Chrome Android); en otros navegadores se digita el código.
