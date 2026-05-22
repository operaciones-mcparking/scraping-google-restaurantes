# Normalización y calidad comercial

Esta etapa trabaja solo sobre:

```text
data/consolidado_restaurantes_priorizados.xlsx
```

No hace scraping nuevo.

## Salidas

```text
data/consolidado_restaurantes_priorizados_normalizado.xlsx
data/consolidado_restaurantes_priorizados_normalizado.csv
```

## Columnas nuevas

- `Nombre normalizado`
- `Posible cadena/franquicia`
- `Grupo cadena/franquicia`
- `Posible duplicado entre comunas`
- `Grupo duplicado`
- `Tipo negocio`
- `Score comercial`
- `Nivel comercial`

## Tipo negocio

Valores posibles:

- Restaurante
- Cafetería
- Fast Food
- Bar/Pub
- Bakery/Pastelería
- Dark Kitchen
- Otro

## Nivel comercial

Valores posibles:

- Alto potencial
- Medio potencial
- Bajo potencial

## Score comercial

El score va de 0 a 100 y considera:

- Rating
- Cantidad de reviews
- Sitio web
- Teléfono
- Calidad dato
- Penalización si `Es restaurante válido` es `No`

## Hojas del Excel

- `Base normalizada`
- `Resumen comercial`
- `Top reviews`
- `Top rating`
- `Comunas`
- `Categorías`
- `Tipos negocio`
- `Niveles comerciales`

## Comando

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"

& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\06_normalizar_calidad_comercial.py"
```
