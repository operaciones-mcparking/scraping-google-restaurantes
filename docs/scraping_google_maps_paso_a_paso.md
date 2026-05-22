# Scraping Google Maps paso a paso

Este piloto usa Playwright para abrir Google Maps en Chrome, buscar restaurantes en Las Condes y guardar pocos resultados en CSV, Excel y JSON.

## Qué hace

1. Abre Google Maps web.
2. Busca `restaurantes en Las Condes, Región Metropolitana, Chile`.
3. Espera entre 2 y 5 segundos entre acciones.
4. Hace hasta 3 scrolls lentos en el panel de resultados.
5. Junta hasta 10 fichas visibles.
6. Abre cada ficha una por una.
7. Extrae datos disponibles.
8. Evita duplicados por URL de ficha o por nombre + dirección.
9. Agrega columnas de calidad:
   - `Calidad dato`
   - `Es restaurante válido`
   - `Observaciones`
10. Agrega columnas vacías para futuras etapas de redes sociales y delivery.
11. Guarda:
   - `data/piloto_las_condes_restaurantes.csv`
   - `data/piloto_las_condes_restaurantes.xlsx`
   - `data/piloto_las_condes_restaurantes_raw.json`
   - `data/logs/piloto_las_condes_restaurantes.log`

## Antes de correr

Confirma que existe Chrome en:

```text
C:\Program Files\Google\Chrome\Application\chrome.exe
```

La configuración está en:

```text
configs/scraper_google_maps.json
```

## Comando para correr desde Windows PowerShell

Abre PowerShell y entra a la carpeta:

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"
```

Ejecuta el piloto:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\02_scraper_google_maps_playwright.js" --config ".\configs\scraper_google_maps.json"
```

## Piloto ampliado Las Condes 50

Este piloto mantiene una sola comuna y una sola búsqueda, pero sube el máximo a 50 resultados y 8 scrolls.

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\02_scraper_google_maps_playwright.js" --config ".\configs\scraper_google_maps_las_condes_50.json"
```

Salidas:

- `data/las_condes_restaurantes_50.csv`
- `data/las_condes_restaurantes_50.xlsx`
- `data/las_condes_restaurantes_50_raw.json`
- `data/logs/las_condes_restaurantes_50.log`

Al terminar, PowerShell muestra:

- total filas extraídas
- total restaurantes válidos
- total no válidos
- teléfonos vacíos
- direcciones vacías
- sitios web vacíos
- duplicados eliminados

## Prueba técnica sin scraping

Este comando solo valida que Playwright cargue:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\02_scraper_google_maps_playwright.js" --config ".\configs\scraper_google_maps.json" --check
```

## Qué revisar después

Abre:

```text
data/piloto_las_condes_restaurantes.xlsx
```

Revisa:

- Que haya máximo 10 filas.
- Que los nombres sean restaurantes reales.
- Que las direcciones correspondan a Las Condes o cercanías.
- Que Google Maps URL abra la ficha correcta.
- Que latitud y longitud tengan valores cuando Google los entregue en la URL.
- Que campos no disponibles estén vacíos.
- Que `Calidad dato` ayude a priorizar revisión manual.
- Que `Es restaurante válido` marque `No` cuando el resultado parezca cafetería, comida rápida, dark kitchen o local dudoso.
- Que las columnas de redes sociales y delivery existan, aunque queden vacías.

## Cómo interpretar calidad

- `Completo`: tiene nombre, rating, reviews, dirección, teléfono y sitio web.
- `Parcial`: falta algún dato no crítico.
- `Sin teléfono`: tiene dirección, pero no se encontró teléfono visible.
- `Sin dirección`: no se encontró dirección visible.

## Cómo interpretar restaurante válido

`Sí` significa que el nombre/categoría parece restaurante. `No` significa que conviene revisar manualmente porque falta nombre o parece un local no claramente restaurante.

## Si aparece captcha o bloqueo

El scraper debe detenerse. No intentes evadir captcha ni repetir muchas veces. Espera y prueba otro día con menos resultados.
