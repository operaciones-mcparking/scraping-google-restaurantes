# Scraper local con sincronizacion Supabase

El scraper incremental sigue corriendo en el PC local. No se mueve a Streamlit Cloud.

## Flujo

1. `actualizar_restaurantes.bat` ejecuta el actualizador local.
2. El scraper abre Google Maps localmente.
3. Los resultados nuevos se guardan primero en SQLite y Excel:

```text
data/restaurantes.db
data/base_restaurantes_actualizada.xlsx
data/base_restaurantes_actualizada.csv
```

4. Despues de guardar localmente, el sistema intenta subir solo los nuevos a Supabase.
5. El CRM online lee esos datos desde Supabase.

## Tablas que actualiza

Cuando encuentra un restaurante nuevo, sube:

- `restaurantes`
- `crm_estado`
- `historial_contactos`

En `crm_estado` crea:

```text
Estado CRM = Nuevo
Estado WhatsApp = No contactado
```

En `historial_contactos` crea el evento inicial:

```text
Canal = Sistema
Accion = Restaurante agregado
Mensaje enviado = Lead ingresado a la base
```

## Duplicados

El sincronizador evita duplicados usando:

1. `crm_id`
2. `google_maps_url`

Si el restaurante ya existe en Supabase, no lo vuelve a insertar.

## Si Supabase falla

No se pierden datos.

El sistema mantiene actualizado el respaldo local en:

```text
data/restaurantes.db
data/base_restaurantes_actualizada.xlsx
```

El error queda registrado en el log configurado, por ejemplo:

```text
data/logs/actualizacion_incremental_manual.log
```

## Modo prueba

Si `modoPrueba` esta en `true`, el sistema no hace scraping real y la sincronizacion Supabase corre en modo dry-run.

## Configuracion

En:

```text
configs/actualizacion_incremental_manual.json
```

La subida a Supabase se controla con:

```json
"sincronizarSupabase": true
```

Para desactivar temporalmente la subida online:

```json
"sincronizarSupabase": false
```

## Prueba manual sin insertar

Puedes validar la sincronizacion sin subir datos:

```powershell
python scripts/sincronizar_incremental_supabase.py --config configs/actualizacion_incremental_manual.json --dry-run
```

## Prueba real

Ejecuta:

```text
actualizar_restaurantes.bat
```

Al final del resumen apareceran tambien:

- nuevos subidos a Supabase
- duplicados Supabase ignorados
- errores Supabase
