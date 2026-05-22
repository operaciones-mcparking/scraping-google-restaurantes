# Plan de migracion a Supabase

## Objetivo

Preparar el proyecto para una version online sin mover todavia el scraping a la nube.

Arquitectura objetivo:

- Supabase sera la base de datos online.
- Streamlit sera el CRM online.
- El scraper incremental seguira corriendo localmente en el PC.
- Cuando el scraper local encuentre restaurantes nuevos, los subira a Supabase.
- El CRM online leera Supabase.
- La version local con Excel/SQLite se mantiene como respaldo.

## Estructura actual del proyecto

Archivos principales actuales:

- `app_crm_restaurantes.py`: CRM visual Streamlit local.
- `actualizar_restaurantes.bat`: boton local para actualizar restaurantes.
- `abrir_crm_restaurantes.bat`: boton local para abrir el CRM.
- `scripts/10_actualizar_incremental.js`: actualizacion incremental con Playwright.
- `scripts/09_importar_base_a_sqlite.py`: importacion/deduplicacion interna en SQLite.
- `data/base_restaurantes_actualizada.xlsx`: Excel vivo de restaurantes.
- `data/crm_restaurantes_estado.xlsx`: estado comercial actual de cada lead.
- `data/historial_contactos.xlsx`: historial de eventos/contactos.
- `data/restaurantes.db`: motor SQLite local para deduplicacion.
- `configs/mensajes_whatsapp.json`: mensajes WhatsApp editables.
- `configs/actualizacion_incremental_manual.json`: configuracion segura del scraper local.

## Tablas Supabase propuestas

### 1. `restaurantes`

Tabla principal. Equivale a `data/base_restaurantes_actualizada.xlsx` y al contenido principal de SQLite.

Columnas sugeridas:

| Columna | Tipo sugerido | Origen actual |
|---|---:|---|
| `id` | uuid primary key | generado en Supabase |
| `crm_id` | text unique | llave actual derivada del restaurante |
| `unique_key` | text unique | SQLite `unique_key` |
| `key_google_maps_url` | text | SQLite |
| `key_nombre_direccion_comuna` | text | SQLite |
| `key_nombre_lat_lng` | text | SQLite |
| `nombre_restaurante` | text | Excel |
| `nombre_normalizado` | text | Excel |
| `rating` | numeric | Excel |
| `cantidad_reviews` | integer | Excel |
| `direccion` | text | Excel |
| `telefono` | text | Excel |
| `telefono_normalizado` | text | derivado por CRM |
| `telefono_tipo` | text | Celular/Fijo/Sin telefono |
| `whatsapp_disponible` | boolean | derivado por CRM |
| `sitio_web` | text | Excel |
| `categoria` | text | Excel |
| `google_maps_url` | text | Excel |
| `latitud` | numeric | Excel |
| `longitud` | numeric | Excel |
| `comuna` | text | Excel |
| `region` | text | Excel |
| `pais` | text | Excel |
| `fuente` | text | Excel |
| `fecha_extraccion` | timestamptz | Excel |
| `fecha_carga` | timestamptz | derivada |
| `calidad_dato` | text | Excel |
| `es_restaurante_valido` | boolean/text | Excel actual usa Si/No |
| `instagram_url` | text | Excel |
| `instagram_usuario` | text | Excel |
| `facebook_url` | text | Excel |
| `tiktok_url` | text | Excel |
| `tiene_redes` | text/boolean | Excel |
| `calidad_redes` | text | Excel |
| `esta_en_uber_eats` | text/boolean | Excel |
| `url_uber_eats` | text | Excel |
| `confianza_uber_eats` | text | Excel |
| `esta_en_pedidosya` | text/boolean | Excel |
| `url_pedidosya` | text | Excel |
| `confianza_pedidosya` | text | Excel |
| `esta_en_rappi` | text/boolean | Excel |
| `url_rappi` | text | Excel |
| `confianza_rappi` | text | Excel |
| `observaciones` | text | Excel |
| `posible_cadena_franquicia` | text/boolean | Excel |
| `grupo_cadena_franquicia` | text | Excel |
| `posible_duplicado_entre_comunas` | text/boolean | Excel |
| `grupo_duplicado` | text | Excel |
| `tipo_negocio` | text | Excel |
| `score_comercial` | numeric | Excel |
| `nivel_comercial` | text | Excel |
| `data_json` | jsonb | respaldo flexible |
| `created_at` | timestamptz | Supabase |
| `updated_at` | timestamptz | Supabase |

Indices recomendados:

- unique `crm_id`
- unique `unique_key`
- index `google_maps_url`
- index `comuna`
- index `nivel_comercial`
- index `telefono`
- index `fecha_carga`

### 2. `crm_estado`

Tabla de estado actual del lead. Equivale a `data/crm_restaurantes_estado.xlsx`.

Columnas sugeridas:

| Columna | Tipo sugerido | Origen actual |
|---|---:|---|
| `id` | uuid primary key | generado |
| `crm_id` | text unique | Excel CRM |
| `restaurante_id` | uuid nullable | relacion futura con `restaurantes.id` |
| `estado_crm` | text | Nuevo/Pendiente contacto/Contactado |
| `fecha_ultimo_contacto` | timestamptz | Excel CRM |
| `canal_ultimo_contacto` | text | WhatsApp/Llamada/Manual |
| `observacion_crm` | text | Excel CRM |
| `fecha_ultimo_whatsapp` | timestamptz | Excel CRM |
| `mensaje_whatsapp_sugerido` | text | Excel CRM |
| `estado_whatsapp` | text | Excel CRM |
| `variante_mensaje` | text | Excel CRM |
| `mensaje_enviado` | text | Excel CRM |
| `fecha_envio_whatsapp` | timestamptz | Excel CRM |
| `resultado_seguimiento` | text | Sin respuesta/No interesado/Negociando/etc. |
| `created_at` | timestamptz | Supabase |
| `updated_at` | timestamptz | Supabase |

Columnas historicas que hoy existen pero se pueden dejar como legado:

- `responsable`
- `proxima_accion`
- `fecha_proxima_accion`
- `respondio`
- `interesado`
- `reunion_agendada`
- `resultado_comercial`

Recomendacion: no eliminarlas inmediatamente del Excel, pero no hacerlas protagonistas en la version online.

### 3. `historial_contactos`

Tabla append-only. Equivale a `data/historial_contactos.xlsx`.

Cada accion crea una fila nueva.

Columnas sugeridas:

| Columna | Tipo sugerido | Origen actual |
|---|---:|---|
| `id` | uuid primary key | generado |
| `crm_id` | text | Excel historial |
| `restaurante_id` | uuid nullable | relacion futura |
| `fecha_hora` | timestamptz | Excel historial |
| `restaurante` | text | Excel historial |
| `comuna` | text | Excel historial |
| `canal` | text | WhatsApp/Llamada/Manual/Sistema |
| `accion` | text | WhatsApp abierto/Llamada iniciada/etc. |
| `estado_crm_actual` | text | Excel historial |
| `resultado_seguimiento_actual` | text | Excel historial |
| `mensaje_enviado` | text | Excel historial |
| `created_at` | timestamptz | Supabase |

Eventos actuales o esperados:

- Restaurante agregado
- WhatsApp abierto
- Llamada iniciada
- Estado CRM cambiado
- Estado CRM cambiado automaticamente
- Resultado cambiado
- Nota comercial agregada
- Alerta sin respuesta

### 4. `mensajes_whatsapp`

Tabla de mensajes editables. Equivale a `configs/mensajes_whatsapp.json`.

Columnas sugeridas:

| Columna | Tipo sugerido | Origen actual |
|---|---:|---|
| `id` | uuid primary key | generado |
| `codigo` | text unique | 1, 2, 3... |
| `texto` | text | JSON |
| `activo` | boolean | JSON |
| `orden` | integer | JSON |
| `created_at` | timestamptz | Supabase |
| `updated_at` | timestamptz | Supabase |

Variables permitidas en el texto:

- `{nombre}`
- `{comuna}`

Nota: antes de migrar conviene corregir el encoding del JSON actual, porque algunos textos aparecen con caracteres corruptos.

### 5. `logs_actualizaciones`

Tabla de resumen de corridas del scraper local. Equivale a logs locales y tabla SQLite `actualizaciones`.

Columnas sugeridas:

| Columna | Tipo sugerido | Origen actual |
|---|---:|---|
| `id` | uuid primary key | generado |
| `fecha` | timestamptz | SQLite/log |
| `modo` | text | manual/piloto/ui |
| `config_usada` | jsonb | config incremental |
| `comunas` | jsonb | comunas procesadas |
| `encontrados` | integer | resumen scraper |
| `insertados` | integer | resumen scraper |
| `duplicados` | integer | resumen scraper |
| `errores` | integer | resumen scraper |
| `detenido_por_bloqueo` | boolean | scraper |
| `notas` | text | logs |
| `created_at` | timestamptz | Supabase |

## Que datos vienen desde Excel/SQLite actual

Desde `data/base_restaurantes_actualizada.xlsx`:

- Datos publicos del restaurante.
- Redes sociales.
- Delivery.
- Normalizacion comercial.
- Score comercial.
- Nivel comercial.
- Tipo negocio.

Desde `data/crm_restaurantes_estado.xlsx`:

- Estado CRM actual.
- Resultado seguimiento.
- Ultimo contacto.
- Estado WhatsApp.
- Mensaje enviado.
- Notas comerciales.

Desde `data/historial_contactos.xlsx`:

- Eventos/contactos historicos.
- Linea de tiempo del lead.
- Alertas de sistema.

Desde `data/restaurantes.db`:

- Deduplicacion local.
- Llaves internas:
  - Google Maps URL
  - nombre + direccion + comuna
  - nombre + latitud + longitud
- Logs de actualizaciones locales.

Desde `configs/mensajes_whatsapp.json`:

- Mensajes WhatsApp activos/inactivos.
- Textos editables.

## Migracion inicial a Supabase

Pasos recomendados:

1. Crear proyecto Supabase.
2. Crear tablas:
   - `restaurantes`
   - `crm_estado`
   - `historial_contactos`
   - `mensajes_whatsapp`
   - `logs_actualizaciones`
3. Crear indices y restricciones unicas.
4. Crear un script de migracion local, por ejemplo:
   - `scripts/11_migrar_a_supabase.py`
5. El script debe leer:
   - `data/base_restaurantes_actualizada.xlsx`
   - `data/crm_restaurantes_estado.xlsx`
   - `data/historial_contactos.xlsx`
   - `configs/mensajes_whatsapp.json`
   - opcionalmente `data/restaurantes.db`
6. Subir primero `restaurantes`.
7. Subir despues `crm_estado`.
8. Subir despues `historial_contactos`.
9. Subir despues `mensajes_whatsapp`.
10. Validar conteos:
   - restaurantes locales vs Supabase
   - estados CRM locales vs Supabase
   - historial local vs Supabase
11. Mantener los Excel como respaldo.

## Como cambiaria el CRM Streamlit

Hoy el CRM lee principalmente:

- `data/base_restaurantes_actualizada.xlsx`
- `data/crm_restaurantes_estado.xlsx`
- `data/historial_contactos.xlsx`
- `configs/mensajes_whatsapp.json`

En version online deberia tener dos modos:

### Modo local

Usa archivos locales como ahora.

Variables sugeridas:

- `DATA_MODE=local`

### Modo Supabase

Usa Supabase como fuente principal.

Variables sugeridas:

- `DATA_MODE=supabase`
- `SUPABASE_URL`
- `SUPABASE_KEY`

Cambios internos:

- Crear una capa de acceso a datos, por ejemplo `data_sources/`.
- Funciones actuales como `load_base()`, `load_crm_state()`, `load_contact_history()` y `load_message_config()` deberian delegar en:
  - lector local si `DATA_MODE=local`
  - lector Supabase si `DATA_MODE=supabase`
- Las acciones de guardado deben cambiar:
  - guardar estado CRM en `crm_estado`
  - agregar eventos en `historial_contactos`
  - editar mensajes en `mensajes_whatsapp`

Importante: no conviene mezclar consultas Supabase directamente en toda la app. Es mejor crear una capa intermedia para no romper la version local.

## Como el scraper local actualizaria Supabase

El scraper local seguiria corriendo con:

- `actualizar_restaurantes.bat`
- `scripts/10_actualizar_incremental.js`
- Playwright local
- SQLite local como respaldo de deduplicacion

Nuevo flujo sugerido:

1. El usuario ejecuta el `.bat` local.
2. El scraper busca restaurantes en Google Maps.
3. Deduplica localmente con SQLite.
4. Inserta nuevos restaurantes en Excel/SQLite local.
5. Si `SUPABASE_SYNC=true`, tambien hace upsert en Supabase:
   - tabla `restaurantes`
   - tabla `logs_actualizaciones`
   - evento `Restaurante agregado` en `historial_contactos`
6. Si Supabase falla:
   - no se pierde la actualizacion local
   - se guarda error en log local
   - se puede reintentar sincronizacion despues

Recomendacion: implementar primero una sincronizacion manual:

- `scripts/12_sincronizar_local_a_supabase.py`

Luego, cuando este validado, conectarla al incremental.

## Variables secretas necesarias

Para local:

```powershell
setx SUPABASE_URL "https://TU-PROYECTO.supabase.co"
setx SUPABASE_KEY "TU-KEY"
```

Para Streamlit Cloud:

Usar `.streamlit/secrets.toml` o el panel de secrets de Streamlit:

```toml
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "TU-KEY"
DATA_MODE = "supabase"
```

Importante:

- No subir `.streamlit/secrets.toml` a GitHub.
- El `.gitignore` ya ignora `.streamlit/secrets.toml`.
- Para el CRM online conviene usar una key con permisos controlados.

## Seguridad y permisos

Para partir simple:

- Mantener Supabase privado.
- Usar service role key solo en entorno seguro del servidor, no expuesta en navegador.
- En Streamlit Cloud, guardar secrets en el panel de secrets.

Luego se puede mejorar con:

- Row Level Security.
- Usuario admin unico.
- Politicas por tabla.

## Estrategia por etapas

### Etapa 1: Solo documentacion y diseno

Estado actual. No cambia el codigo.

### Etapa 2: Crear Supabase y tablas

Crear proyecto, tablas, indices y secrets.

### Etapa 3: Migracion inicial

Crear script para subir Excel/JSON actuales a Supabase.

### Etapa 4: CRM con doble modo

Modificar Streamlit para soportar:

- local
- supabase

Sin eliminar modo local.

### Etapa 5: Sincronizador local

Crear script local que suba cambios nuevos a Supabase.

### Etapa 6: Integrar scraper local + Supabase

Al terminar scraping incremental:

- actualizar Excel/SQLite local
- subir nuevos a Supabase
- registrar log online

### Etapa 7: Deploy del CRM online

Subir a GitHub y desplegar en Streamlit Cloud.

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Duplicados entre local y Supabase | usar `crm_id`, `unique_key` y Google Maps URL como llaves |
| Supabase no disponible | mantener Excel/SQLite local como respaldo |
| Secretos expuestos en GitHub | usar `.streamlit/secrets.toml` ignorado y secrets del hosting |
| Encoding de mensajes WhatsApp | corregir JSON antes de migrar |
| Cambios simultaneos local/online | definir Supabase como fuente de verdad para CRM una vez migrado |
| Scraping bloqueado | mantener regla actual: no evadir captchas y detener si hay bloqueo |

## Recomendacion final

No mover el scraping a la nube todavia.

La mejor arquitectura inicial es:

1. Scraper local sigue igual.
2. Excel/SQLite local siguen como respaldo.
3. Supabase recibe una copia sincronizada.
4. CRM online lee Supabase.
5. CRM local sigue disponible por si falla internet o Supabase.

Esto reduce riesgo y permite migrar paso a paso.
