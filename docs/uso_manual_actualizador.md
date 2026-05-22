# Uso manual del actualizador

Este proyecto queda en modo manual. No se configuró Task Scheduler ni ninguna actualización automática.

## Qué archivo debes abrir con doble clic

Haz doble clic en:

```text
actualizar_restaurantes.bat
```

Ese archivo es el botón principal del sistema.

## Qué archivo Excel abrir después

Cuando termine el proceso, abre:

```text
data/base_restaurantes_actualizada.xlsx
```

Ese es el Excel principal para revisar la base actualizada.

## Qué configuración usa

El botón usa:

```text
configs/actualizacion_incremental_manual.json
```

Configuración actual:

- `modoPrueba`: `false`
- objetivo de nuevos restaurantes: `30`
- máximo resultados por comuna: `15`
- scrolls máximos por comuna: `4`
- pausas: entre 2 y 5 segundos
- detener si aparece captcha o bloqueo: `true`

## Qué significa el resumen final

Al terminar, la ventana muestra:

- `total base antes`: cuántos restaurantes había antes de iniciar.
- `resultados encontrados en la corrida`: cuántos resultados leyó Google Maps en esta ejecución.
- `nuevos insertados`: cuántos restaurantes nuevos se agregaron a la base.
- `duplicados ignorados`: cuántos ya existían y no se agregaron de nuevo.
- `errores`: problemas al procesar resultados o archivos.
- `total base final`: total de restaurantes después de actualizar.
- `archivo Excel generado`: ruta del Excel actualizado.

## Qué hacer si aparece captcha o bloqueo

No intentes evadirlo.

Recomendación:

1. Cierra la ventana.
2. Espera varias horas o hasta el día siguiente.
3. Baja el volumen en `configs/actualizacion_incremental_manual.json`.
4. Prueba con una sola comuna.

Campos para bajar volumen:

```json
"maxNuevosObjetivo": 10,
"maxResultadosPorComuna": 10,
"maxScrollsPorComuna": 3
```

## Cómo cambiar comunas

Abre:

```text
configs/actualizacion_incremental_manual.json
```

Busca la sección:

```json
"comunas": [
  {
    "comuna": "La Florida",
    "region": "Metropolitana",
    "pais": "Chile",
    "busqueda": "restaurantes",
    "slug": "la_florida_manual"
  }
]
```

Para agregar otra comuna, copia el bloque y cambia:

- `comuna`
- `region`
- `slug`

Ejemplo:

```json
{
  "comuna": "Providencia",
  "region": "Metropolitana",
  "pais": "Chile",
  "busqueda": "restaurantes",
  "slug": "providencia_manual"
}
```

Importante: si agregas varias comunas, el proceso tardará más y aumenta el riesgo de bloqueo.

## Recomendación de uso

Ejecuta manualmente una vez por semana o cuando realmente necesites actualizar. Mantén volúmenes bajos para cuidar la estabilidad.
