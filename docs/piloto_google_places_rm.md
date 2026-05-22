# Piloto controlado Google Places - Región Metropolitana

Objetivo: probar Google Places con una extracción pequeña antes de escalar.

## Alcance del piloto

- Comuna: Santiago
- Categoría: Restaurante
- Páginas de Google Places: 1
- Máximo esperado: hasta 20 resultados
- Archivo de salida: `data/piloto_santiago_restaurante.xlsx`

## Por qué este piloto es seguro

El script no borra carpetas ni datos existentes.

Por defecto, si ya existe un archivo con el mismo nombre de salida, crea uno nuevo con fecha y hora al final del nombre. Solo sobrescribe si se usa explícitamente `-Sobrescribir`.

Archivos que puede crear:

- `data/piloto_santiago_restaurante.csv`
- `data/piloto_santiago_restaurante.xlsx`
- `data/piloto_santiago_restaurante.log`

## Cómo obtener y configurar la API key

1. Entra a Google Cloud Console.
2. Crea un proyecto o elige uno existente.
3. Activa la facturación del proyecto.
4. Habilita `Places API (New)`.
5. Entra a `APIs y servicios` > `Credenciales`.
6. Haz clic en `Crear credenciales` > `Clave de API`.
7. Copia la clave.
8. En la misma pantalla, restringe la clave:
   - Restricción de API: selecciona solo `Places API (New)`.
   - Restricción de aplicación: para esta prueba local puedes dejarla temporalmente sin restricción de aplicación o restringirla por IP si sabes tu IP pública.
9. Configura una alerta de presupuesto en Google Cloud antes de hacer pruebas grandes.

Fuentes oficiales:

- https://developers.google.com/maps/documentation/places/web-service/get-api-key?hl=es-419
- https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
- https://developers.google.com/maps/api-security-best-practices?hl=es-419

## Comando para ejecutar el piloto

Abre PowerShell en:

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"
```

Ejecuta:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Comunas "Santiago" -Categorias "Restaurante" -MaxPaginas 1 -OutputBaseName "piloto_santiago_restaurante"
```

## Qué validar en Excel

Abre:

```text
data/piloto_santiago_restaurante.xlsx
```

Revisa que aparezcan estas columnas:

- Nombre del restaurante
- Teléfono
- Dirección
- Comuna
- Región
- Sitio web
- Rating
- Cantidad de reseñas
- Link de Google Maps
- Latitud
- Longitud
- Categoría
- Fuente
- Fecha de actualización

## Señales de que el piloto funcionó

- Hay restaurantes reales de Santiago.
- Las direcciones están en Chile.
- Los links de Google Maps abren correctamente.
- Latitud y longitud tienen valores.
- Rating y cantidad de reseñas aparecen cuando Google los tiene disponibles.
- Algunos restaurantes pueden venir sin teléfono o sitio web; eso es normal.
