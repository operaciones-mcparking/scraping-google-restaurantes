# Estructura final del proyecto SCRAPING_GOOGLE

Fecha de ordenamiento: 2026-05-22

## Archivo principal para negocio

Usar este archivo para análisis comercial, priorización y lectura ejecutiva:

```text
data/consolidado_restaurantes_priorizados_normalizado.xlsx
```

Contiene:

- Base consolidada de restaurantes.
- 33 columnas originales.
- Normalización comercial.
- Tipo de negocio.
- Score comercial.
- Nivel comercial.
- Posibles cadenas/franquicias.
- Posibles duplicados entre comunas.
- Hojas de resumen, rankings y conteos.

## Archivo recomendado para CRM

Usar este archivo para prospección y carga inicial de contactos de alto potencial:

```text
data/alto_potencial_redes_enriquecido.xlsx
```

Contiene:

- Solo restaurantes de `Alto potencial`.
- Links de Instagram/Facebook encontrados desde sitio oficial o red declarada como sitio web.
- Calidad de Instagram/Facebook.
- Fuente Redes.
- Observaciones Redes.

Este es el mejor archivo para equipos comerciales porque ya reduce ruido y prioriza contactos.

## Archivos principales actuales

```text
data/consolidado_restaurantes_priorizados.xlsx
data/consolidado_restaurantes_priorizados.csv
data/resumen_restaurantes_priorizados.csv
data/consolidado_restaurantes_priorizados_normalizado.xlsx
data/consolidado_restaurantes_priorizados_normalizado.csv
data/alto_potencial_redes_enriquecido.xlsx
data/alto_potencial_redes_enriquecido.csv
data/alto_potencial_redes_enriquecido.json
```

## Archivos por comuna

Se mantienen como respaldo técnico y trazabilidad de origen:

```text
data/comunas/
```

Cada comuna tiene:

- `.xlsx`: archivo legible en Excel.
- `.csv`: base tabular.
- `_raw.json`: respaldo técnico de extracción.

## Logs

Se mantienen todos los logs:

```text
data/logs/
```

Sirven para auditar:

- cuándo se ejecutó cada etapa;
- cuántas filas salieron;
- errores de sitio web;
- bloqueos o fallos;
- resumen de extracción.

## Configuraciones

Se mantienen:

```text
configs/
configs/runs/
```

Son archivos técnicos que permiten repetir:

- scraping Google Maps;
- extracción multi-comuna;
- consolidación;
- enriquecimiento de redes.

## Scripts

Se mantienen:

```text
scripts/
```

Uso recomendado:

- `02_scraper_google_maps_playwright.js`: scraping controlado de Google Maps.
- `04_correr_multi_comuna.js`: ejecución multi-comuna.
- `05_consolidar_resultados.py`: consolidación.
- `06_normalizar_calidad_comercial.py`: normalización comercial.
- `07_preparar_enriquecimiento_redes.py`: preparación de candidatos de redes.
- `08_enriquecer_redes_piloto.py`: enriquecimiento conservador desde sitios oficiales.

Scripts históricos o auxiliares:

- `01_extraer_google_places.ps1`: alternativa antigua con Google Places API.
- `00_crear_plantilla_excel.mjs`: generador de plantilla inicial.
- `03_actualizar_columnas_futuras.py`: migración de columnas futuras.
- `convert_csv_to_xlsx.py`: utilidad técnica.

## Documentación

Se mantiene:

```text
docs/
```

Los documentos más importantes ahora son:

- `estructura_proyecto_final.md`
- `normalizacion_calidad_comercial.md`
- `enriquecimiento_redes_sociales.md`
- `piloto_enriquecimiento_redes_real.md`
- `estrategia_multi_comuna_priorizada.md`
- `riesgos_scraping_google_maps.md`

## Archivos históricos movidos a archive

Se creó:

```text
data/archive/
```

Se movieron archivos piloto y temporales:

```text
data/archive/piloto_las_condes_restaurantes.*
data/archive/las_condes_restaurantes_50.*
data/archive/piloto_alto_potencial_redes_enriquecido.*
data/archive/social/piloto_alto_potencial_redes.*
```

Estos archivos no se borraron. Quedan disponibles para auditoría y comparación.

## Archivos técnicos o intermedios

Pueden mantenerse mientras el proyecto siga activo:

```text
data/social/alto_potencial_redes_candidatos.xlsx
data/social/alto_potencial_redes_candidatos.csv
data/plantilla_restaurantes_chile.xlsx
package.json
package-lock.json
node_modules/
```

Notas:

- `data/social/alto_potencial_redes_candidatos.*` sirve como base previa al enriquecimiento social.
- `data/plantilla_restaurantes_chile.xlsx` es una plantilla histórica.
- `package.json`, `package-lock.json` y `node_modules/` son soporte técnico de Node/Playwright.

## Qué dejar en la raíz

Recomendado:

```text
README.md
configs/
data/
docs/
scripts/
package.json
package-lock.json
node_modules/
```

La raíz ya está razonablemente limpia. No conviene mover `scripts`, `configs`, `docs` ni `data`.

## Qué dejar visible en data

Recomendado:

```text
data/consolidado_restaurantes_priorizados_normalizado.xlsx
data/alto_potencial_redes_enriquecido.xlsx
data/consolidado_restaurantes_priorizados.xlsx
data/comunas/
data/logs/
data/social/
data/archive/
```

## Qué mover a archive si se quiere limpiar más

Opcional, no hecho automáticamente:

```text
data/consolidado_restaurantes_priorizados.csv
data/consolidado_restaurantes_priorizados_normalizado.csv
data/alto_potencial_redes_enriquecido.csv
data/alto_potencial_redes_enriquecido.json
data/resumen_restaurantes_priorizados.csv
data/plantilla_restaurantes_chile.xlsx
data/social/alto_potencial_redes_candidatos.*
```

Estos no son basura, pero son secundarios si se trabaja solo con Excel.

## Qué eliminar eventualmente

Solo después de confirmar respaldos:

- Pilotos dentro de `data/archive/`.
- CSV intermedios si el Excel es suficiente.
- JSON raw antiguos si no se necesita auditoría técnica.
- `data/plantilla_restaurantes_chile.xlsx` si ya no se usa.

No recomiendo eliminar:

- Excel final normalizado.
- Excel de alto potencial enriquecido.
- Scripts.
- Configs.
- Logs recientes.
- Documentación.
