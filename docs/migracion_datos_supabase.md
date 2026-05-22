# Migracion de datos a Supabase

## Objetivo

Preparar la migracion de los datos locales actuales a Supabase sin romper el modo local.

Esta etapa no modifica:

- `app_crm_restaurantes.py`
- scraper local
- SQLite local
- Excel principal

## Archivos creados

```text
supabase/schema.sql
scripts/migrar_datos_a_supabase.py
docs/migracion_datos_supabase.md
```

## Tablas incluidas

El archivo `supabase/schema.sql` crea:

- `restaurantes`
- `crm_estado`
- `historial_contactos`
- `mensajes_whatsapp`
- `logs_actualizaciones`

Tambien crea indices y llaves unicas para evitar duplicados.

## Paso 1: crear tablas en Supabase

1. Entrar al proyecto Supabase.
2. Abrir SQL Editor.
3. Copiar el contenido de:

```text
supabase/schema.sql
```

4. Ejecutarlo.

Esto crea las tablas, pero no carga datos.

## Paso 2: probar migracion en dry-run

Desde PowerShell:

```powershell
cd C:\Users\gabyp\Documents\SCRAPING_GOOGLE
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\scripts\migrar_datos_a_supabase.py
```

Resultado esperado:

```text
Migracion Supabase
Modo: DRY-RUN
restaurantes: XXX registros preparados
crm_estado: XXX registros preparados
historial_contactos: XXX registros preparados
mensajes_whatsapp: XXX registros preparados
Dry-run completado. No se inserto nada.
```

En dry-run no se escribe nada en Supabase.

## Paso 3: ejecutar migracion real

Solo despues de revisar el dry-run:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\scripts\migrar_datos_a_supabase.py --execute
```

Con `--execute`, el script hace upsert en Supabase.

## Fuentes locales usadas

El script lee:

```text
data/base_restaurantes_actualizada.xlsx
data/crm_restaurantes_estado.xlsx
data/historial_contactos.xlsx
configs/mensajes_whatsapp.json
```

Si `data/historial_contactos.xlsx` o `configs/mensajes_whatsapp.json` no existen, simplemente migra 0 registros para esa tabla.

## Como evita duplicados

### restaurantes

Usa `crm_id` como llave principal de upsert.

El `crm_id` se calcula con prioridad:

1. `Google Maps URL`
2. `Nombre restaurante + Direccion + Comuna`

Tambien prepara llaves internas:

- `unique_key`
- `key_google_maps_url`
- `key_nombre_direccion_comuna`
- `key_nombre_lat_lng`

### crm_estado

Usa `crm_id`.

Cada lead mantiene un solo estado actual.

### historial_contactos

Usa `event_key`, generado desde:

```text
crm_id + fecha_hora + canal + accion + mensaje
```

Esto permite mantener muchos eventos por restaurante sin duplicar el mismo evento exacto.

### mensajes_whatsapp

Usa `codigo`.

Ejemplo:

- `1`
- `2`
- `3`

## Que no hace todavia

Este script no:

- cambia el CRM a modo Supabase
- cambia el scraper
- crea tablas automaticamente desde Python
- borra datos locales
- borra datos en Supabase
- migra logs locales todavia

La tabla `logs_actualizaciones` queda preparada para una etapa posterior.

## Requisitos

Debe existir:

```text
.streamlit/secrets.toml
```

Con:

```toml
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "TU-KEY"
```

En Windows, si el archivo quedo como `.streamlit/secrets.toml.txt`, el helper actual tambien puede leerlo, aunque el nombre recomendado es `secrets.toml`.

## Validacion recomendada despues de --execute

En Supabase, revisar conteos:

```sql
select count(*) from restaurantes;
select count(*) from crm_estado;
select count(*) from historial_contactos;
select count(*) from mensajes_whatsapp;
```

Comparar con el dry-run.

## Respaldo

Aunque se migren datos a Supabase, el modo local sigue intacto:

- Excel local sigue existiendo.
- SQLite local sigue existiendo.
- CRM local sigue leyendo archivos locales.
- Scraper local sigue funcionando igual.

Supabase queda preparado como copia online, no como reemplazo obligatorio todavia.
