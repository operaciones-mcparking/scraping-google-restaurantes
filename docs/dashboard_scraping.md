# Dashboard local de scraping

El panel `app_scraping_status.py` funciona como centro de control operacional para el scraping local.

## Abrir panel

Ejecutar:

```bat
ver_estado_scraping.bat
```

El dashboard se autoactualiza cada 3 segundos. No deberia ser necesario apretar F5.

## Acciones principales

La parte superior concentra las acciones de uso diario:

- **Iniciar scraping**: ejecuta `actualizar_restaurantes.bat` en segundo plano con `subprocess.Popen`.
- **Detener scraping**: crea `data/stop_scraping.flag`; el scraper se detiene en el siguiente punto seguro.
- **Reintentar sync Supabase**: ejecuta la sincronizacion incremental sin volver a scrapear.

Para evitar dobles corridas, el dashboard guarda el PID en:

```text
data/scraping_process.json
```

Si el proceso sigue activo o `status = running`, el boton **Iniciar scraping** queda deshabilitado.

## Vista principal

Por defecto solo se muestra lo operacional:

- estado actual
- etapa del pipeline
- barra de progreso
- comuna actual
- avance de comunas
- ultimo restaurante procesado
- tiempo transcurrido y restante
- KPIs: revisados, nuevos, duplicados, subidos Supabase y errores
- resumen de la ultima ejecucion cuando aplica

## Informacion secundaria

El detalle tecnico queda colapsado en expanders:

- configuracion scraping
- comunas configuradas
- SQLite, Supabase y sincronizacion
- variables tecnicas
- logs completos

## Archivo de progreso

El estado se escribe en:

```text
data/scraping_progress.json
```

Campos principales:

- `status`
- `started_at`
- `updated_at`
- `finished_at`
- `porcentaje_estimado`
- `tiempo_transcurrido_segundos`
- `tiempo_estimado_restante_segundos`
- `mensaje_actual`
- `etapa_actual`
- `comuna_actual`
- `comuna_index`
- `total_comunas`
- `ultimo_restaurante`
- `restaurantes_revisados`
- `restaurantes_nuevos`
- `duplicados_ignorados`
- `subidos_supabase`
- `errores`
- `errores_supabase`

## Detencion segura

El boton **Detener scraping** crea:

```text
data/stop_scraping.flag
```

El orquestador y el scraper revisan ese archivo en puntos seguros:

- antes de cada comuna
- durante scrolls
- antes de procesar cada ficha
- antes de exportar o sincronizar Supabase

Si se solicita detener, se conserva el avance ya guardado y el estado queda como `stopped`.

## Reintentar sincronizacion Supabase

El boton **Reintentar sync Supabase** ejecuta:

```bat
python scripts/sincronizar_incremental_supabase.py --config configs/actualizacion_incremental_manual.json
```

No vuelve a scrapear. Solo compara SQLite local con Supabase y sube faltantes usando `SUPABASE_SERVICE_ROLE_KEY`.

## Seguridad

- No imprime secrets.
- No cambia `actualizar_restaurantes.bat`.
- No cambia el CRM Next.js.
- No cambia el modelo de datos.
- No fuerza el cierre del proceso; usa detencion cooperativa con flag.
