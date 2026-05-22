# Reporte revision CRM

Fecha: 22/05/2026

## Problemas encontrados

- Habia textos corruptos por encoding en `app_crm_restaurantes.py`, especialmente en la pestaña Actualizar base y en algunos botones.
- Ejemplos corregidos: textos de configuracion de busqueda, ultima actualizacion, botones de busqueda, ultimo log y etiquetas de estado.
- Habia textos corruptos en funciones antiguas o de compatibilidad que podian aparecer si se renderizaban vistas legacy.
- El navegador integrado no permitio abrir `localhost`/`127.0.0.1` por bloqueo del cliente, pero el servidor Streamlit respondio correctamente por HTTP.

## Problemas corregidos

- Se dejo `app_crm_restaurantes.py` legible en UTF-8.
- Se eliminaron marcadores de mojibake del archivo principal.
- Se reemplazaron emojis corruptos por texto simple en botones visibles.
- Se corrigieron textos de la pestaña Actualizar base:
  - Configuracion de busqueda
  - Ultima actualizacion
  - Ultimos nuevos agregados
  - Buscar nuevos restaurantes
  - Ver ultimo log
  - Abrir Excel actualizado
  - Cancelar busqueda
- Se mantuvo la logica de WhatsApp, llamada, filtros, guardado CRM y actualizacion manual.

## Pruebas realizadas

- Compilacion:
  - `python -m py_compile app_crm_restaurantes.py`
- Revision de encoding:
  - Busqueda de marcadores de mojibake sin resultados.
- Carga de datos:
  - `data/base_restaurantes_actualizada.xlsx`: 227 restaurantes cargados.
  - `data/crm_restaurantes_estado.xlsx`: 12 registros CRM cargados.
  - Merge base + CRM: 227 filas.
- Telefonos:
  - Restaurantes con WhatsApp valido: 133.
  - Restaurantes con telefono para llamada, pero no WhatsApp: 75.
  - Restaurantes sin telefono: 19.
- WhatsApp en modo prueba sin escribir al Excel real:
  - Celular valido genera link WhatsApp.
  - Telefono fijo no genera WhatsApp, pero permite llamada.
  - Sin telefono no genera WhatsApp ni llamada.
  - Al abrir WhatsApp se prepara:
    - Estado CRM = Contactado.
    - Estado WhatsApp = Contactado manualmente.
    - Resultado seguimiento = Sin respuesta.
    - Fecha/hora WhatsApp.
    - Mensaje enviado.
- Actualizar base:
  - Configuracion manual cargada correctamente.
  - No habia actualizacion en curso.
  - No se ejecuto scraping real.
- Arranque Streamlit:
  - La app levanto en modo local.
  - HTTP respondio `200` en puerto de prueba.

## Pendiente

- Validacion visual completa en navegador real del usuario, porque el navegador integrado bloqueo `localhost`.
- Revisar visualmente la app con doble clic en `abrir_crm_restaurantes.bat`.
- Si se necesita, hacer una pasada final de microcopy para dejar algunos textos sin tildes o con tildes de forma uniforme.

## Estado final

El CRM compila, carga la base, carga el estado CRM, conserva la logica de WhatsApp y no ejecuta scraping real durante la revision.
