# Enriquecimiento de Delivery Apps

## Objetivo

Detectar de forma controlada si cada restaurante ya está presente en:

- Rappi
- Uber Eats
- PedidosYa

Esta etapa no modifica el CRM visual todavía. Primero se prepara la estructura técnica para hacer pruebas pequeñas, guardar evidencia y evitar falsos positivos.

## Principios

- El proceso corre localmente en el PC, no en Streamlit Cloud.
- El CRM online sigue leyendo Supabase.
- No se hace scraping agresivo.
- Primero se prueba con 5 restaurantes.
- Se prioriza precisión sobre volumen.
- Si un resultado es dudoso, se marca como `Dudoso`, no como encontrado.
- Siempre se guarda la URL/evidencia cuando exista.

## Columnas propuestas en Supabase

Tabla: `restaurantes`

Columnas nuevas sugeridas:

| Columna | Tipo sugerido | Descripción |
| --- | --- | --- |
| `en_rappi` | boolean | Indica si el restaurante fue encontrado en Rappi. |
| `en_uber_eats` | boolean | Indica si el restaurante fue encontrado en Uber Eats. |
| `en_pedidosya` | boolean | Indica si el restaurante fue encontrado en PedidosYa. |
| `url_rappi` | text | URL encontrada del restaurante en Rappi. |
| `url_uber_eats` | text | URL encontrada del restaurante en Uber Eats. |
| `url_pedidosya` | text | URL encontrada del restaurante en PedidosYa. |
| `fecha_revision_delivery` | timestamptz | Fecha/hora de la última revisión. |
| `estado_revision_delivery` | text | Estado general de la revisión. |
| `observacion_revision_delivery` | text | Observaciones, errores o dudas. |

Estados posibles para `estado_revision_delivery`:

- `No revisado`
- `Encontrado`
- `No encontrado`
- `Dudoso`
- `Error`

## Nota sobre columnas existentes

El esquema actual ya contiene columnas históricas:

- `esta_en_uber_eats`
- `url_uber_eats`
- `confianza_uber_eats`
- `esta_en_pedidosya`
- `url_pedidosya`
- `confianza_pedidosya`
- `esta_en_rappi`
- `url_rappi`
- `confianza_rappi`

Para la nueva etapa conviene migrar gradualmente hacia nombres más simples:

- `en_rappi`
- `en_uber_eats`
- `en_pedidosya`

Mientras no se migre, el script puede escribir en las columnas nuevas y, si se decide, mantener compatibilidad con las antiguas.

## SQL sugerido

No ejecutar todavía sin revisar.

```sql
alter table public.restaurantes
add column if not exists en_rappi boolean,
add column if not exists en_uber_eats boolean,
add column if not exists en_pedidosya boolean,
add column if not exists fecha_revision_delivery timestamptz,
add column if not exists estado_revision_delivery text default 'No revisado',
add column if not exists observacion_revision_delivery text;

alter table public.restaurantes
add column if not exists url_rappi text,
add column if not exists url_uber_eats text,
add column if not exists url_pedidosya text;
```

## Script local futuro

Archivo preparado:

`scripts/enriquecer_delivery_apps.py`

El script debe:

1. Leer restaurantes desde Supabase.
2. Filtrar restaurantes pendientes de revisión.
3. Buscar por `nombre_restaurante + comuna`.
4. Revisar Rappi, Uber Eats y PedidosYa.
5. Guardar:
   - presencia por plataforma
   - URL encontrada
   - fecha de revisión
   - estado
   - observación
6. Evitar duplicados usando `crm_id`.
7. Manejar errores por restaurante y continuar.
8. Correr en `dry-run` por defecto.
9. Escribir en Supabase solo si se usa `--execute`.

## Estrategia segura de búsqueda

Primera prueba:

- Máximo 5 restaurantes.
- Solo restaurantes con buen nombre y comuna.
- Registrar resultados en modo `dry-run`.
- Revisar manualmente si las URLs encontradas son correctas.

Luego:

- Lotes de 20 a 50 restaurantes.
- Pausas entre búsquedas.
- No insistir si aparece bloqueo, captcha o acceso restringido.
- Marcar como `Dudoso` si el nombre coincide parcialmente pero no hay suficiente evidencia.

## Criterios para marcar encontrado

Marcar como encontrado solo si:

- El nombre coincide claramente.
- La comuna, dirección o zona coincide cuando esté disponible.
- La página pertenece a la plataforma correcta.
- Existe una URL específica del restaurante.

Marcar como `Dudoso` si:

- El nombre se parece, pero la comuna no está clara.
- Hay varias sucursales y no se puede confirmar cuál corresponde.
- El resultado parece marca parecida, pero no igual.

Marcar como `No encontrado` si:

- No aparece resultado confiable.
- Solo aparecen resultados genéricos o terceros no verificables.

## Flujo futuro en CRM

Más adelante, el CRM puede mostrar badges:

- Rappi
- Uber Eats
- PedidosYa

Ejemplo visual:

- `Rappi: Encontrado`
- `Uber Eats: No encontrado`
- `PedidosYa: Dudoso`

También se puede agregar filtro:

- `En Rappi`
- `En Uber Eats`
- `En PedidosYa`
- `Estado revisión delivery`

## Riesgos y limitaciones

- Las plataformas pueden bloquear automatizaciones.
- Algunas URLs cambian por ciudad o zona.
- Una cadena puede aparecer con varias sucursales.
- Puede haber restaurantes con nombres muy parecidos.
- No se debe asumir presencia solo por similitud de nombre.

## Recomendación

Avanzar en este orden:

1. Crear columnas en Supabase.
2. Ejecutar `dry-run` con 5 restaurantes.
3. Revisar manualmente resultados.
4. Ajustar criterios de coincidencia.
5. Ejecutar lote pequeño con `--execute`.
6. Recién después mostrar badges en el CRM.
