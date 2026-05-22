# Modo Supabase del CRM

## Objetivo

Permitir que el CRM lea datos desde Supabase sin eliminar el modo local.

El proyecto queda con dos modos:

- `local`: usa Excel/JSON locales como hasta ahora.
- `supabase`: lee desde las tablas Supabase ya migradas.

El scraper local y SQLite no cambian en esta etapa.

## Configuracion

El modo se controla en:

```text
configs/app_mode.json
```

Contenido por defecto:

```json
{
  "data_mode": "local"
}
```

Valores posibles:

```json
{
  "data_mode": "local"
}
```

o:

```json
{
  "data_mode": "supabase"
}
```

## Como cambiar a Supabase

1. Abrir `configs/app_mode.json`.
2. Cambiar:

```json
"data_mode": "local"
```

por:

```json
"data_mode": "supabase"
```

3. Guardar el archivo.
4. Cerrar y volver a abrir el CRM.

El header mostrara:

```text
Modo datos: Supabase
```

## Como volver a modo local

1. Abrir `configs/app_mode.json`.
2. Cambiar:

```json
"data_mode": "supabase"
```

por:

```json
"data_mode": "local"
```

3. Guardar.
4. Cerrar y volver a abrir el CRM.

El header mostrara:

```text
Modo datos: Local
```

## Tablas que lee en modo Supabase

El helper `data_source.py` lee:

- `restaurantes`
- `crm_estado`
- `historial_contactos`
- `mensajes_whatsapp`

Y entrega al CRM estructuras compatibles con las que ya usaba localmente.

## Archivos locales que se mantienen

Aunque uses Supabase, estos archivos no se eliminan:

- `data/base_restaurantes_actualizada.xlsx`
- `data/crm_restaurantes_estado.xlsx`
- `data/historial_contactos.xlsx`
- `data/restaurantes.db`
- `configs/mensajes_whatsapp.json`

Siguen siendo respaldo local.

## Importante sobre escritura

Esta etapa es solo lectura desde Supabase.

No se modifico todavia:

- guardado CRM hacia Supabase
- scraper incremental
- sincronizacion automatica local -> Supabase
- actualizacion incremental en nube

Eso significa:

- En modo local, el CRM sigue guardando como antes.
- En modo Supabase, esta etapa sirve para validar lectura online.
- La escritura online se debe implementar en una etapa posterior.

## Riesgos

### Datos desactualizados

Si el scraper local agrega restaurantes nuevos pero no se sincroniza Supabase, el CRM en modo Supabase no los vera.

Mitigacion:

- mantener modo local como respaldo
- usar el script de migracion/sincronizacion cuando corresponda

### Cambios de CRM no persistidos online

Como esta etapa es solo lectura Supabase, los cambios comerciales online todavia no deben considerarse definitivos.

Mitigacion:

- usar modo Supabase primero para validar visualizacion
- implementar escritura Supabase en una etapa posterior

### Falla de internet o Supabase

Si Supabase no responde, cambiar `configs/app_mode.json` a:

```json
{
  "data_mode": "local"
}
```

y volver a abrir el CRM.

## Fallback recomendado

Mantener `local` como modo principal hasta validar:

1. que Supabase muestra todos los restaurantes
2. que CRM estado coincide
3. que historial aparece correctamente
4. que mensajes WhatsApp se leen bien

Despues de eso se puede avanzar a escritura Supabase.
