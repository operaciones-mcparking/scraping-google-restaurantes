# Estrategia multi-comuna priorizada

Esta etapa reemplaza la idea de recorrer todas las comunas de la Región Metropolitana. El foco queda en:

- Santiago Oriente
- La Florida
- Curicó
- Chillán

## Interpretación de Santiago Oriente

Santiago Oriente se ejecutará como estas comunas individuales:

- Las Condes
- Vitacura
- Lo Barnechea
- Providencia
- La Reina
- Ñuñoa

Además se ejecutarán:

- La Florida
- Curicó
- Chillán

Total: 9 comunas.

## Configuración por comuna

- Búsqueda: `restaurantes`
- Máximo resultados por comuna: 30
- Scrolls máximos por comuna: 6
- Pausas: 2 a 5 segundos entre acciones
- Captcha/bloqueo: detener y no evadir

## Estructura de salida esperada

Un Excel por comuna:

```text
data/comunas/las_condes_restaurantes_30.xlsx
data/comunas/vitacura_restaurantes_30.xlsx
data/comunas/lo_barnechea_restaurantes_30.xlsx
data/comunas/providencia_restaurantes_30.xlsx
data/comunas/la_reina_restaurantes_30.xlsx
data/comunas/nunoa_restaurantes_30.xlsx
data/comunas/la_florida_restaurantes_30.xlsx
data/comunas/curico_restaurantes_30.xlsx
data/comunas/chillan_restaurantes_30.xlsx
```

También se generarán CSV y RAW JSON por comuna con el mismo nombre base.

Base consolidada:

```text
data/consolidado_restaurantes_priorizados.xlsx
data/consolidado_restaurantes_priorizados.csv
data/resumen_restaurantes_priorizados.csv
```

El Excel consolidado tendrá dos hojas:

- `Base consolidada`
- `Resumen`

## Columnas mantenidas

Se mantienen las 33 columnas actuales, incluyendo redes sociales y delivery vacíos:

- datos Google Maps
- `Calidad dato`
- `Es restaurante válido`
- `Observaciones`
- columnas de redes sociales
- columnas de Uber Eats, PedidosYa y Rappi

## Comando para preparar configs sin scraping

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"

& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\04_correr_multi_comuna.js" --config ".\configs\scraper_google_maps_multi_comuna.json" --check
```

## Comando para correr extracción multi-comuna

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"

& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\04_correr_multi_comuna.js" --config ".\configs\scraper_google_maps_multi_comuna.json"
```

## Comando para consolidar solamente

Úsalo si ya existen los CSV por comuna y solo quieres reconstruir la base consolidada:

```powershell
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\04_correr_multi_comuna.js" --config ".\configs\scraper_google_maps_multi_comuna.json" --solo-consolidar
```

## Estimación de volumen

Máximo teórico:

```text
9 comunas x 30 resultados = 270 restaurantes
```

Estimación realista:

```text
180 a 270 filas antes de revisión manual
```

Google Maps puede entregar menos resultados visibles por comuna aunque el máximo sea 30.

## Estimación de duración

Cada comuna puede tardar aproximadamente 4 a 8 minutos, dependiendo de cuántas fichas se logren abrir y de las pausas aleatorias.

Estimación total:

```text
36 a 72 minutos
```

Si aparece captcha o bloqueo, el proceso se detendrá antes de terminar todas las comunas.
