# Base de restaurantes de Chile

Proyecto paso a paso para construir una base actualizada de restaurantes de Chile, comenzando por la Región Metropolitana.

## Estrategia actual: piloto con Google Maps web

Como no se usará Google Places API por ahora, el piloto actual usa Playwright para abrir Google Maps web lentamente, buscar pocos resultados y exportarlos a Excel.

Piloto configurado:

- Comuna: Las Condes
- Región: Metropolitana
- País: Chile
- Búsqueda: restaurantes
- Máximo resultados: 10
- Scrolls máximos: 3
- Salida CSV: `data/piloto_las_condes_restaurantes.csv`
- Salida Excel: `data/piloto_las_condes_restaurantes.xlsx`
- Salida raw: `data/piloto_las_condes_restaurantes_raw.json`
- Columnas de control: `Calidad dato`, `Es restaurante válido`, `Observaciones`
- Columnas futuras vacías: redes sociales y plataformas delivery

Prueba técnica sin scraping:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\02_scraper_google_maps_playwright.js" --config ".\configs\scraper_google_maps.json" --check
```

Ejecutar piloto:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\02_scraper_google_maps_playwright.js" --config ".\configs\scraper_google_maps.json"
```

Ejecutar piloto ampliado Las Condes 50:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\02_scraper_google_maps_playwright.js" --config ".\configs\scraper_google_maps_las_condes_50.json"
```

Lee antes:

- `docs/scraping_google_maps_paso_a_paso.md`
- `docs/riesgos_scraping_google_maps.md`
- `docs/estructura_futura_redes_delivery.md`
- `docs/estrategia_multi_comuna_priorizada.md`

Preparar configs multi-comuna sin scraping:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\04_correr_multi_comuna.js" --config ".\configs\scraper_google_maps_multi_comuna.json" --check
```

Ejecutar extracción multi-comuna priorizada:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\04_correr_multi_comuna.js" --config ".\configs\scraper_google_maps_multi_comuna.json"
```

Normalizar calidad comercial del consolidado:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\06_normalizar_calidad_comercial.py"
```

Preparar piloto de enriquecimiento de redes sociales:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\07_preparar_enriquecimiento_redes.py"
```

Ejecutar piloto real de enriquecimiento social de 10 restaurantes:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\08_enriquecer_redes_piloto.py"
```

Ejecutar enriquecimiento social de los 99 alto potencial:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\08_enriquecer_redes_piloto.py" ".\configs\enriquecimiento_redes_sociales_alto_potencial.json"
```

Aplicación incremental semanal:

```text
actualizar_restaurantes.bat
```

El archivo visible para negocio es:

```text
data/base_restaurantes_actualizada.xlsx
```

Modo manual recomendado:

- Botón: `actualizar_restaurantes.bat`
- Configuración: `configs/actualizacion_incremental_manual.json`
- Guía: `docs/uso_manual_actualizador.md`

CRM visual local:

```text
abrir_crm_restaurantes.bat
```

Guía:

```text
docs/crm_restaurantes_paso_a_paso.md
```

## Estrategia anterior: Google Places API

## Qué genera

El archivo final queda en `data/restaurantes_rm_google_places.xlsx` y contiene estas columnas:

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
- Place ID

`Place ID` se agrega como columna técnica para deduplicar y actualizar registros con más seguridad.

## Antes de empezar

Necesitas una API key de Google Cloud con Places API (New) habilitada.

Pasos simples:

1. Entra a Google Cloud Console.
2. Crea o elige un proyecto.
3. Activa la facturación.
4. Habilita `Places API (New)`.
5. Crea una API key.
6. Idealmente restringe la API key para usar solo Places API.

Importante: Google Maps Platform tiene reglas de uso, atribución y almacenamiento. Este proyecto guarda la fecha de actualización y la fuente para facilitar auditoría, pero debes revisar las políticas oficiales antes de usar la base comercialmente. Ver `docs/notas_legales_google_places.md`.

## Uso recomendado

Abre PowerShell dentro de esta carpeta:

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"
```

Ejecuta un piloto con pocas comunas:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY"
```

Para una prueba todavía más chica, usa 1 comuna y 1 categoría:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Comunas "Santiago" -Categorias "Restaurante" -MaxPaginas 1 -OutputBaseName "piloto_santiago_restaurante"
```

Ver también `docs/piloto_google_places_rm.md`.

Para el piloto pequeño de Las Condes:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Comunas "Las Condes" -Categorias "Restaurante" -MaxPaginas 1 -MaxResultados 5 -OutputBaseName "piloto_las_condes_restaurantes"
```

Ver también `docs/piloto_las_condes_restaurantes.md`.

Si el piloto funciona, ejecuta toda la Región Metropolitana:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Modo Completo
```

También puedes elegir comunas específicas:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Comunas "Santiago,Providencia,Las Condes"
```

## Cómo evitar gastos innecesarios

- Primero usa el piloto.
- Revisa el archivo generado.
- Luego agrega más comunas o activa `-Modo Completo`.
- En Google Cloud configura alertas de presupuesto.

## Etapas del proyecto

### Etapa 1: Base principal con Google Places

Objetivo: crear una base limpia, deduplicada y actualizada de restaurantes.

Se busca por comuna y categoría, por ejemplo `restaurante en Providencia, Región Metropolitana, Chile`, `sushi en Santiago`, `pizza en Ñuñoa`.

### Etapa 2: Validación manual rápida

Objetivo: revisar duplicados raros, cadenas, locales cerrados o negocios que Google clasifique mal.

Acciones:

- Filtrar por comuna.
- Revisar restaurantes sin teléfono o sin sitio web.
- Ordenar por cantidad de reseñas.
- Abrir algunos links de Google Maps para validar.

### Etapa 3: Cruce con delivery apps

Objetivo: saber si cada restaurante está en Rappi, Uber Eats y PedidosYa.

En esta etapa conviene crear columnas nuevas:

- Presente en Rappi
- Link Rappi
- Presente en Uber Eats
- Link Uber Eats
- Presente en PedidosYa
- Link PedidosYa
- Fecha de verificación delivery
- Método de verificación

No se usará `leads-rappi` como fuente principal. Como máximo puede servir para orientación secundaria o comparación.

### Etapa 4: Mantención

Objetivo: actualizar la base periódicamente.

Recomendación:

- Restaurantes nuevos: mensual.
- Rating y reseñas: mensual o trimestral.
- Teléfono, sitio web y dirección: trimestral.
- Cruce delivery: mensual si se usará para ventas.

## Archivos del proyecto

- `scripts/01_extraer_google_places.ps1`: extrae restaurantes desde Google Places API.
- `configs/comunas_rm.csv`: comunas de la Región Metropolitana.
- `configs/categorias_restaurantes.csv`: categorías de búsqueda.
- `data/`: carpeta de salida.
- `docs/plan_no_programadores.md`: guía paso a paso sin jerga técnica.

## Fuentes oficiales revisadas

- [Places API overview](https://developers.google.com/maps/documentation/places/web-service/overview)
- [Text Search (New)](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [Place data fields](https://developers.google.com/maps/documentation/places/web-service/data-fields)
- [Policies and attributions for Places API](https://developers.google.com/maps/documentation/places/web-service/policies)
