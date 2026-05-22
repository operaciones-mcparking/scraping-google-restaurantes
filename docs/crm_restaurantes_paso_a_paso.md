# CRM Restaurantes paso a paso

Este CRM es una aplicacion visual local para trabajar restaurantes como leads comerciales.

## Como abrir el CRM

Haz doble clic en:

```text
abrir_crm_restaurantes.bat
```

Se abrira una ventana negra y luego el navegador con la aplicacion.

No cierres la ventana negra mientras estes usando el CRM.

## Logo

La app puede mostrar un logo en el encabezado.

Si quieres usarlo, guarda la imagen aqui:

```text
assets/rappi_logo.png
```

Si ese archivo no existe, la app mostrara el nombre:

```text
Rappi Leads CRM
```

## Excel principal

El CRM lee la base principal:

```text
data/base_restaurantes_actualizada.xlsx
```

Ese archivo es la base viva de restaurantes.

## Donde se guarda el seguimiento comercial

Los cambios de ventas se guardan aparte en:

```text
data/crm_restaurantes_estado.xlsx
```

Esto protege la base principal. Puedes cambiar estados, responsables y notas sin romper el Excel de restaurantes.

## Navegacion principal

El CRM tiene solo dos pestanas:

- `CRM Comercial`: vista principal para trabajar leads.
- `Actualizar base`: vista para buscar restaurantes nuevos y actualizar el Excel principal.

## CRM Comercial

Esta es la vista principal.

Arriba muestra KPIs:

- Total restaurantes.
- Alto potencial.
- Pendientes contacto.
- Contactados.
- Interesados.

Despues puedes filtrar por:

- Comuna.
- Nivel comercial.
- Tipo negocio.
- Estado CRM.
- Tiene telefono.
- WhatsApp.
- Fecha de carga.

La tabla principal muestra:

- Nombre.
- Comuna.
- Tipo negocio.
- Nivel comercial.
- Score comercial.
- Telefono.
- Instagram.
- Estado CRM.
- Proxima accion.

Tambien veras seguimiento de WhatsApp y resultados de mensajes para medir respuestas e interesados sin mezclar esas metricas con el `Estado CRM`.

## Editar un lead

En `CRM Comercial`, baja hasta `Editar lead`.

Puedes editar:

- Estado CRM.
- Estado WhatsApp.
- Fecha ultimo WhatsApp.
- Variante mensaje.
- Mensaje enviado.
- Respondio.
- Interesado.
- Notas comerciales.
- Resultado comercial.

Presiona:

```text
Guardar cambios
```

Los cambios quedan guardados en:

```text
data/crm_restaurantes_estado.xlsx
```

## Estados CRM

Valores disponibles:

- Nuevo.
- Pendiente contacto.
- Contactado.

Para los indicadores:

- `Pendientes contacto` cuenta solo leads en `Pendiente contacto`.
- `Contactados` cuenta solo leads en `Contactado`.
- `Interesados` se mide aparte desde el campo WhatsApp/comercial `Interesado`.

Si el archivo tenia estados antiguos como `Respondio`, `Interesado`, `No interesado` o `Cliente potencial`, el CRM los convierte automaticamente a `Contactado`. Las columnas de analitica WhatsApp se mantienen separadas.

## Reglas CRM

Automatizaciones:

- Despues de 24 horas: `Nuevo` pasa a `Pendiente contacto` si no hubo contacto ni cambios manuales.
- Al abrir WhatsApp: `Estado CRM` pasa a `Contactado`.
- Al abrir WhatsApp: `Estado WhatsApp` pasa a `Contactado manualmente`.
- Las variantes A/B/C se asignan automaticamente por bloques de 20 contactos.

Acciones manuales:

- Marcar `Respondio`.
- Marcar `Interesado`.
- Escribir notas comerciales.
- Editar mensajes WhatsApp A/B/C.
- Cambiar `Estado CRM` manualmente solo entre `Nuevo`, `Pendiente contacto` y `Contactado`.

## Links rapidos

Cuando hay datos disponibles, la ficha del lead muestra links para:

- WhatsApp.
- Instagram.
- Facebook.
- Google Maps.
- Sitio web.

El link de WhatsApp solo abre la conversacion. No envia mensajes automaticamente.

## Fecha de carga

El CRM usa una fecha interna para saber cuando se cargo cada restaurante.

La toma en este orden:

1. `Fecha carga`, si existe.
2. `Fecha extraccion`, si existe.
3. `Fecha actualizacion`, si existe.
4. Fecha del archivo Excel, si no hay ninguna columna de fecha.

La app no agrega esa columna al Excel principal. Solo la usa para filtrar y calcular indicadores.

## Actualizar base

Entra a:

```text
Actualizar base
```

Esta vista permite buscar restaurantes nuevos en las comunas seleccionadas.

Controles:

- `Objetivo nuevos`: maximo de restaurantes nuevos que intentaremos agregar. Parte en 10 y no permite mas de 50 desde la app.
- `Maximo resultados por comuna`: restaurantes que se revisaran por cada comuna.
- `Scrolls maximos`: veces que bajara en la lista para encontrar mas locales.
- `Comunas a actualizar`: comunas donde se buscaran restaurantes nuevos.

Boton principal:

```text
Buscar nuevos restaurantes
```

Ese boton revisa Google Maps, agrega nuevos restaurantes y evita duplicados.

Boton secundario:

```text
Actualizar datos en pantalla
```

Usalo despues de buscar nuevos restaurantes para que el CRM vuelva a leer el Excel actualizado.

## Resumen de actualizacion

Al terminar veras:

- `Base antes`: cantidad de restaurantes antes de empezar.
- `Encontrados`: resultados encontrados durante la busqueda.
- `Nuevos agregados`: restaurantes agregados porque no estaban duplicados.
- `Duplicados ignorados`: resultados que ya existian y no se agregaron.
- `Errores`: problemas encontrados durante la busqueda.
- `Base final`: cantidad total de restaurantes al terminar.

## Seguridad

La app mantiene reglas conservadoras:

- No permite ejecutar dos busquedas al mismo tiempo.
- No permite mas de 50 nuevos como objetivo desde la pantalla.
- Usa pausas lentas.
- No evade captchas.
- Si aparece captcha o bloqueo, espera antes de intentar nuevamente.

Tambien puedes seguir usando el boton clasico de Windows:

```text
actualizar_restaurantes.bat
```

## Que archivos no tocar

No edites manualmente:

```text
data/restaurantes.db
scripts/
configs/
node_modules/
```

Para trabajar normalmente usa:

```text
abrir_crm_restaurantes.bat
actualizar_restaurantes.bat
data/base_restaurantes_actualizada.xlsx
data/crm_restaurantes_estado.xlsx
```

## Contacto por WhatsApp

En la ficha del lead seleccionado puedes usar:

```text
💬 Abrir WhatsApp
```

La app solo abre WhatsApp Web o Desktop con un mensaje sugerido. No envia mensajes automaticamente. Revisa el texto y presiona enviar manualmente solo si corresponde.

La app usa la columna `Teléfono` de la base principal. Para mostrar el boton, el numero debe parecer celular chileno valido en formato `569XXXXXXXX`. Si no es valido, veras el aviso:

```text
No hay teléfono válido para WhatsApp
```

El seguimiento de WhatsApp se guarda en:

```text
data/crm_restaurantes_estado.xlsx
```

Campos nuevos:

- `Fecha último WhatsApp`
- `Mensaje WhatsApp sugerido`
- `Estado WhatsApp`

Estados disponibles:

- `No contactado`
- `Link abierto`
- `Contactado manualmente`
- `Respondio`
- `No respondio`
