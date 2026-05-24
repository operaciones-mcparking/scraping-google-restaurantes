# Optimizacion de rendimiento del CRM

## Objetivo

Hacer que las acciones de contacto, especialmente WhatsApp, se sientan mas rapidas y evitar recargas pesadas del CRM.

## Cambios aplicados

- El boton WhatsApp deja preparada la apertura del link `wa.me` antes de guardar el contacto.
- El guardado del contacto se procesa como una accion pendiente y no fuerza un `rerun` manual adicional.
- En modo Supabase, el CRM actualiza solo el registro del lead afectado en `crm_estado`, en vez de volver a subir toda la tabla de estados.
- Se redujo el uso de limpieza global de cache en acciones de contacto.
- Se agregaron caches con TTL para:
  - restaurantes
  - estado CRM
  - historial de contactos
  - merge restaurantes + CRM
- Se agregaron logs de tiempo en:
  - carga de restaurantes
  - carga de estado CRM
  - transicion automatica
  - merge de datos
  - generacion de eventos iniciales
  - alertas sin respuesta
  - render principal del CRM
  - guardado de WhatsApp/Llamada

## Archivo de logs

Los tiempos quedan en:

`data/logs/crm_performance.log`

Cada linea es JSON, por ejemplo:

```json
{"fecha":"2026-05-23 12:00:00","evento":"carga_restaurantes","segundos":0.42}
```

## Comportamiento esperado

Al apretar WhatsApp:

- Se abre WhatsApp con el mensaje sugerido.
- Se guarda el lead como `Contactado`.
- Se guarda `Estado WhatsApp = Contactado manualmente`.
- Se registra el evento `WhatsApp abierto`.
- Si el lead no estaba contactado, se registra `Estado CRM cambiado`.
- El selector de Estado CRM debe reflejar `Contactado` despues de actualizar la vista.

Al apretar Llamar:

- Se abre `tel:`.
- Se guarda el lead como `Contactado`.
- Se guarda `Canal ultimo contacto = Llamada`.
- Se registra `Llamada iniciada`.
- No se cambia el Estado WhatsApp.

## Limitacion de Streamlit

Streamlit vuelve a ejecutar el script cuando se presiona un boton. Por eso no se puede lograr una experiencia identica a una app SPA pura, pero el cambio reduce el trabajo hecho antes de abrir WhatsApp y evita recargas innecesarias.
