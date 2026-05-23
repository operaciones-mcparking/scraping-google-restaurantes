# Resultado piloto Rappi

## Resumen ejecutivo

Se reviso manualmente el archivo:

`data/rappi_piloto_revision_manual_30.xlsx`

La muestra tiene 30 restaurantes. El objetivo fue validar si la busqueda asistida permite detectar presencia en Rappi con suficiente precision antes de automatizar.

Conclusion principal:

Conviene avanzar con una estrategia hibrida: automatizacion parcial para generar candidatos y evidencia, pero con revision manual antes de escribir resultados definitivos en Supabase o mostrarlos como certeza en el CRM.

No recomiendo automatizar como `Encontrado` o `No encontrado` de forma completa todavia, porque varios casos tienen URLs posibles de Rappi, pero requieren criterio humano para confirmar sucursal, comuna o coincidencia real.

## Conteo de estados

| Estado revision Rappi | Cantidad | Porcentaje |
|---|---:|---:|
| No encontrado | 17 | 56.7% |
| Dudoso | 10 | 33.3% |
| Encontrado | 3 | 10.0% |

## Encontrados confirmados

| Restaurante | Comuna | Tipo negocio | Nivel comercial |
|---|---|---|---|
| Bom Burger Chile | Curico | Fast Food | Medio potencial |
| Ay Mi Madre Restobar Nunoa | Nunoa | Bar/Pub | Alto potencial |
| La Cocina de Javier - Restaurant | Vitacura | Sin tipo en cruce local | Sin nivel en cruce local |

## Comunas con encontrados

| Comuna | Encontrados |
|---|---:|
| Curico | 1 |
| Nunoa | 1 |
| Vitacura | 1 |

## Tipos de negocio con encontrados

| Tipo negocio | Encontrados |
|---|---:|
| Fast Food | 1 |
| Bar/Pub | 1 |
| Sin tipo en cruce local | 1 |

## Lecturas por nivel comercial

| Nivel comercial | Dudoso | Encontrado | No encontrado |
|---|---:|---:|---:|
| Alto potencial | 6 | 1 | 8 |
| Medio potencial | 0 | 1 | 0 |
| Bajo potencial | 2 | 0 | 5 |
| Sin nivel en cruce local | 2 | 1 | 4 |

La presencia en Rappi no parece estar directamente relacionada con `Alto potencial`. Muchos restaurantes de alto potencial no fueron encontrados, lo que puede indicar que varios locales premium o independientes no trabajan delivery, o que aparecen con nombres/sucursales distintos.

## Patrones detectados

### Nombres que funcionan mejor

Funcionan mejor los nombres con marca distintiva y URL directa de Rappi:

- `Bom Burger Chile`
- `Ay Mi Madre`
- `La Cocina de Javier`

Estos casos tienen nombres relativamente unicos y una pagina publica clara.

### Casos dudosos con URL

Varios casos tienen URL de Rappi, pero no alcanzan para marcar automaticamente como `Encontrado`:

- `Kaitona Sushi la Florida`: aparece como `Kaitona Sushi`, pero la comuna no queda clara dentro de Rappi.
- `La Cabrera Al Paso Egana`: aparece en Google con Rappi, pero requiere confirmar sucursal.
- `Zia Bistro y Cafe`: URL compatible, pero requiere confirmar que corresponde al mismo local.
- `Vecchia Casa`: URL compatible, pero falta validar sucursal/comuna.
- `Beasty Butchers`: URL compatible, requiere validacion manual.
- `La Lena`: aparece como hamburgueseria y ahumados; puede ser el mismo negocio o una variante.
- `Aay Chabela Restaurant`: URL compatible, requiere confirmacion.
- `El Hoyo`: aparece como `El Hoyo 1912`, puede corresponder a marca/sucursal distinta.

Este grupo es el principal motivo para no automatizar todavia como encontrado.

### Busquedas que generan falsos positivos o dudas

Las busquedas tienden a generar dudas cuando:

- el nombre en Google Maps incluye comuna o sucursal, pero Rappi muestra solo la marca
- hay tildes, ene, apostrofes o variantes de escritura
- el resultado corresponde a una marca, pero no necesariamente a la misma sucursal
- el lugar de Google Maps es un centro gastronomico, boulevard o zona con varios locales
- el nombre es generico o existe en mas de una ciudad

### Cadenas, franquicias y sucursales

Los casos con sucursal requieren una regla especial. Una coincidencia por nombre no basta si el restaurante tiene varias ubicaciones.

Ejemplos:

- `La Cabrera Al Paso Egana`
- `Kaitona Sushi la Florida`
- `El Hoyo`
- `La Lena`

Para estos casos se deberia exigir evidencia adicional: comuna, direccion, zona de cobertura o nombre de sucursal.

### Restaurantes premium

Muchos restaurantes premium o de mayor ticket aparecen como `No encontrado` o `Dudoso`.

Ejemplos no encontrados:

- `Cassis Mall Arauco Chillan`
- `Margó Isidora Goyenechea`
- `Nolita Isidora Goyenechea`
- `Ostras Chiloe - Los Trapenses`
- `Vita Wines House, Casa de vinos`

Esto sugiere que el segmento premium no necesariamente usa Rappi o puede usar otro canal de venta.

### Fast food y comida rapida

Fast food muestra mejor probabilidad de presencia, pero no es garantia.

- `Bom Burger Chile`: encontrado.
- `Kaitona Sushi la Florida`: dudoso con URL.
- `La Lena`: dudoso con URL.
- `Sabrosura`: no encontrado.

La regla deberia favorecer estos candidatos, pero sin marcarlos automaticamente.

## Precision estimada

Con los estados actuales:

- Confirmados como encontrados: 3 de 30, equivalente a 10.0%.
- Casos dudosos: 10 de 30, equivalente a 33.3%.
- Casos no encontrados: 17 de 30, equivalente a 56.7%.

Si una automatizacion marcara como `Encontrado` cualquier resultado con URL de Rappi, seria riesgosa. Hay 8 casos dudosos con URL, por lo que la precision confirmada de esa regla seria baja sin revision manual.

Estimacion practica:

- Automatizacion para generar candidatos: viable.
- Automatizacion para marcar `Encontrado` sin humano: todavia no recomendable.
- Automatizacion para marcar `No encontrado`: no recomendable con la evidencia actual.

## Riesgos

- Falsos positivos por sucursales parecidas.
- Falsos positivos por marcas con varias comunas.
- Falsos negativos si Rappi no indexa bien en Google.
- Diferencias de escritura entre Google Maps y Rappi.
- Paginas publicas de Rappi que cambian o no aparecen siempre.
- Restaurantes premium que pueden estar ausentes de Rappi, pero presentes en otros canales.

## Estrategia recomendada

Recomiendo avanzar con una mezcla hibrida:

1. El sistema genera candidatos automaticamente.
2. El sistema guarda evidencia:
   - query usada
   - URL encontrada
   - nombre detectado en Rappi
   - score de similitud
   - razon de la clasificacion
3. Solo marcar automaticamente como `Encontrado` cuando la coincidencia sea muy fuerte:
   - nombre normalizado muy similar
   - URL de dominio Rappi valida
   - comuna, sucursal o direccion compatible
4. Si hay URL, pero falta comuna/sucursal clara:
   - estado = `Dudoso`
   - requiere revision manual
5. No marcar automaticamente `No encontrado` salvo que exista una busqueda auditable y repetible.

## Proximo paso recomendado

Crear una segunda version del piloto con automatizacion parcial:

- tomar 30 a 50 restaurantes
- buscar candidatos publicos de Rappi
- calcular similitud de nombre
- guardar evidencia y score
- generar Excel de revision
- no escribir Supabase todavia

Despues de revisar esa segunda muestra, se puede definir una regla mas segura para actualizar Supabase y mostrar badges en el CRM.

## Decision sugerida

Seguir con revision manual asistida por ahora, evolucionando hacia automatizacion parcial.

No recomiendo pasar aun a automatizacion completa.
