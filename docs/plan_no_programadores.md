# Plan paso a paso para no programadores

## Paso 1: Preparar Google

1. Crear una cuenta o proyecto en Google Cloud.
2. Activar facturación.
3. Habilitar `Places API (New)`.
4. Crear una API key.
5. Guardar esa API key en un lugar privado.

## Paso 2: Hacer una prueba pequeña

Ejecuta el script con el modo normal. Ese modo revisa pocas comunas y sirve para confirmar que todo funciona.

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY"
```

Al terminar, abre:

```text
data/restaurantes_rm_google_places.xlsx
```

## Paso 3: Revisar calidad

En Excel:

1. Ordena por comuna.
2. Revisa que haya nombres, direcciones y links de Google Maps.
3. Filtra teléfonos vacíos.
4. Filtra sitios web vacíos.
5. Abre algunos links al azar para validar.

## Paso 4: Ejecutar Región Metropolitana completa

Cuando el piloto se vea bien:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Modo Completo
```

Esto puede demorar y consumir más llamadas de Google Places.

## Paso 5: Guardar una versión

Cada vez que generes una base importante, copia el Excel con fecha en el nombre:

```text
restaurantes_rm_google_places_2026-05-21.xlsx
```

## Paso 6: Cruce con Rappi, Uber Eats y PedidosYa

Esta etapa debe hacerse después de tener una base limpia.

Método recomendado:

1. Buscar cada restaurante por nombre y comuna.
2. Guardar si aparece o no aparece.
3. Guardar el link de la plataforma si aparece.
4. Registrar fecha y método.

Columnas sugeridas:

- Presente en Rappi
- Link Rappi
- Presente en Uber Eats
- Link Uber Eats
- Presente en PedidosYa
- Link PedidosYa
- Fecha de verificación delivery
- Método de verificación

## Paso 7: Actualizar periódicamente

Frecuencia sugerida:

- Una actualización general al mes.
- Revisión manual de casos importantes.
- Cruce delivery mensual si la base se usa para ventas o prospección.
