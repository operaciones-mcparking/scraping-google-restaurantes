# Piloto real de enriquecimiento social

Este piloto procesa solo los 10 restaurantes del archivo piloto de alto potencial.

## Entrada

El script busca primero:

```text
data/piloto_alto_potencial_redes.xlsx
```

Si no existe, usa:

```text
data/social/piloto_alto_potencial_redes.xlsx
```

## Salidas

```text
data/piloto_alto_potencial_redes_enriquecido.xlsx
data/piloto_alto_potencial_redes_enriquecido.csv
data/piloto_alto_potencial_redes_enriquecido.json
data/logs/piloto_alto_potencial_redes_enriquecido.log
```

## Qué hace

1. Lee solo 10 restaurantes.
2. Revisa el sitio web oficial si existe.
3. Extrae enlaces directos a Instagram/Facebook desde ese sitio.
4. Marca esos enlaces como confianza `Alta`.
5. Si no encuentra redes, deja búsqueda sugerida en observaciones.
6. No ejecuta búsquedas masivas en Google.
7. No modifica el consolidado original.

## Campos agregados

- `Fuente Redes`
- `Observaciones Redes`

También completa cuando corresponde:

- `Instagram URL`
- `Instagram Usuario`
- `Tiene Instagram`
- `Calidad Instagram`
- `Facebook URL`
- `Tiene Facebook`
- `Calidad Facebook`

## Comando exacto

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"

& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\08_enriquecer_redes_piloto.py"
```

## Escalar a 99 restaurantes de alto potencial

Este modo usa el mismo criterio conservador:

- Solo revisa sitio web oficial.
- Usa links directos desde sitio web como confianza `Alta`.
- No hace búsquedas agresivas en Google.
- Continúa con el siguiente si un sitio falla.
- No modifica el consolidado original.

Comando:

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"

& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\08_enriquecer_redes_piloto.py" ".\configs\enriquecimiento_redes_sociales_alto_potencial.json"
```

Salida:

```text
data/alto_potencial_redes_enriquecido.xlsx
data/alto_potencial_redes_enriquecido.csv
data/alto_potencial_redes_enriquecido.json
data/logs/alto_potencial_redes_enriquecido.log
```

## Limitaciones

- Si el restaurante no enlaza sus redes desde el sitio oficial, no se asume coincidencia.
- Si el sitio bloquea, falla o carga redes por JavaScript no visible en HTML inicial, quedará observación.
- No se evaden captchas ni bloqueos.
