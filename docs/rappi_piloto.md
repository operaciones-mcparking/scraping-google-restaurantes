# Piloto Rappi Manual

## Objetivo

Validar manualmente si los restaurantes ya existen en Rappi antes de automatizar cualquier busqueda.

La busqueda automatica anterior no entrego evidencia auditable suficiente, por lo que esta etapa usa un flujo semi-manual asistido.

## Que genera el script

Archivo principal:

`data/rappi_piloto_revision_manual_30.xlsx`

Archivo adicional:

`data/rappi_piloto_revision_manual_30.csv`

La planilla contiene hasta 30 restaurantes seleccionados como muestra representativa. Sirve para calibrar si vale la pena automatizar la deteccion en Rappi y para ajustar criterios antes de escalar.

## Como se elige la muestra

El script no toma simplemente los primeros restaurantes. Selecciona una muestra mas util usando estos criterios:

- prioriza `Nivel comercial = Alto potencial`
- mezcla comunas
- incluye distintos tipos de negocio
- prefiere restaurantes con telefono o sitio web
- evita repetir cadenas o nombres muy similares cuando es posible

## Columnas del Excel

- `Restaurante`
- `Comuna`
- `Query Google sugerida`
- `URL busqueda Google`
- `Query Rappi sugerida`
- `Estado revision Rappi`
- `URL Rappi encontrada`
- `Observacion`
- `Revisado manualmente`

## Como ejecutar

Desde PowerShell, en la carpeta del proyecto:

```powershell
python scripts/enriquecer_rappi_piloto.py --limit 30
```

Este comando:

- lee restaurantes desde Supabase
- selecciona hasta 30 restaurantes representativos
- genera el Excel de revision manual
- genera un CSV de respaldo
- no escribe nada en Supabase
- no modifica el CRM
- no hace scraping automatico

## Como revisar manualmente

1. Abrir `data/rappi_piloto_revision_manual_30.xlsx`.
2. Abrir el link de `URL busqueda Google`.
3. Abrir el link de `Query Rappi sugerida`.
4. Revisar si aparece una pagina clara del restaurante en Rappi.
5. Si existe evidencia clara, completar:
   - `Estado revision Rappi` = `Encontrado`
   - `URL Rappi encontrada` = URL encontrada
   - `Revisado manualmente` = `Si`
6. Si no aparece evidencia clara, dejar:
   - `Estado revision Rappi` = `Dudoso`
   - agregar observacion

## Estados recomendados

- `Dudoso`: estado inicial. Usarlo si no hay evidencia suficiente.
- `Encontrado`: solo si la URL corresponde claramente al restaurante.
- `No encontrado`: solo despues de revisar manualmente y estar segura.
- `Error`: si hubo algun problema en la revision.

## Criterios para marcar Encontrado

Marcar `Encontrado` solo si:

- el nombre coincide claramente
- la comuna o zona es compatible cuando se pueda verificar
- la URL pertenece a Rappi
- no parece una sucursal distinta

## Como evitar falsos positivos

No marcar encontrado si:

- el nombre es parecido, pero no igual
- hay muchas sucursales y no queda claro cual es
- el resultado es una nota, anuncio o pagina generica
- no hay una URL especifica del restaurante

## Proximo paso

Despues de revisar manualmente el Excel, el CRM permite guardar la revision manual asistida por restaurante.

## Flujo nuevo dentro del CRM

En `CRM Comercial`, al seleccionar un restaurante aparece un bloque llamado `Rappi` dentro del panel `Lead seleccionado`.

Ese bloque permite:

- ver el estado actual de revision Rappi
- abrir una busqueda sugerida con nombre + comuna + Rappi
- pegar una URL de Rappi encontrada
- escribir una observacion
- guardar la revision manual

Estados disponibles:

- `No revisado`
- `Encontrado`
- `No encontrado`
- `Dudoso`

Regla de uso:

- usar `Encontrado` solo cuando la URL corresponda claramente al restaurante
- usar `Dudoso` cuando haya una URL posible, pero falte confirmar sucursal, comuna o coincidencia exacta
- usar `No encontrado` solo despues de revisar manualmente
- dejar `No revisado` si todavia no se reviso

El filtro superior `Rappi` permite ver restaurantes por estado de revision.

La lista de restaurantes muestra un indicador pequeno con el estado Rappi para acelerar la revision.

## Guardado

En modo Supabase, el CRM guarda en la tabla `restaurantes`:

- `estado_revision_rappi`
- `url_rappi`
- `fecha_revision_rappi`
- `observacion_revision_rappi`

En modo local, el CRM mantiene las mismas columnas en el Excel local.

## Que no hace este flujo

- no hace scraping automatico de Rappi
- no confirma coincidencias por si solo
- no toca Uber Eats
- no toca PedidosYa
- no marca restaurantes automaticamente como encontrados

## Siguiente etapa posible

Despues de acumular suficientes revisiones manuales, se puede crear una segunda etapa que:

1. lea el Excel revisado
2. actualice Supabase
3. mantenga evidencia por URL
4. muestre badges en el CRM

El objetivo es usar la revision manual como base para calibrar reglas mas seguras antes de automatizar.
