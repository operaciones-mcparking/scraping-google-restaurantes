# Actualización incremental paso a paso

Esta etapa convierte el proyecto en una aplicación simple para uso semanal.

## Archivo principal para el usuario

Abrir siempre:

```text
data/base_restaurantes_actualizada.xlsx
```

Este Excel es la base de trabajo para negocio. Incluye restaurantes antiguos y nuevos, sin duplicados según las reglas internas.

## Qué hace el sistema

Al ejecutar `actualizar_restaurantes.bat`, el sistema:

1. Lee la base actual.
2. Usa SQLite internamente para controlar duplicados.
3. Ejecuta scraping controlado según configuración, cuando `modoPrueba` está en `false`.
4. Compara resultados nuevos contra la base existente.
5. Inserta solo restaurantes nuevos.
6. Ignora duplicados.
7. Genera Excel y CSV actualizados.
8. Muestra un resumen final claro.

## Archivos creados

```text
data/restaurantes.db
data/base_restaurantes_actualizada.xlsx
data/base_restaurantes_actualizada.csv
data/logs/actualizacion_incremental.log
```

## Configuración

Editar solo si es necesario:

```text
configs/actualizacion_incremental.json
```

Campos importantes:

- `modoPrueba`: si está en `true`, no hace scraping real.
- `comunas`: comunas que se buscarán.
- `maxNuevosObjetivo`: límite objetivo de nuevos registros.
- `maxResultadosPorComuna`: máximo de resultados por comuna.
- `maxScrollsPorComuna`: scrolls máximos.
- `pausaMinMs` y `pausaMaxMs`: pausas entre acciones.
- `detenerSiCaptchaOBloqueo`: debe quedar en `true`.

## Modo prueba sin scraping

El proyecto queda inicialmente en modo prueba:

```json
"modoPrueba": true
```

Esto permite validar que:

- SQLite se crea;
- la base inicial se importa;
- el Excel actualizado se genera;
- el `.bat` funciona con doble clic;
- no se abre Google Maps.

## Cómo ejecutar

Haz doble clic en:

```text
actualizar_restaurantes.bat
```

Al terminar, abre:

```text
data/base_restaurantes_actualizada.xlsx
```

## Cómo activar actualización real

Cuando quieras correr scraping real:

1. Abre `configs/actualizacion_incremental.json`.
2. Cambia:

```json
"modoPrueba": false
```

3. Guarda.
4. Haz doble clic en `actualizar_restaurantes.bat`.

## Reglas de duplicados

El sistema usa estas llaves, en orden:

1. `Google Maps URL`
2. `Nombre normalizado + Dirección normalizada + Comuna`
3. `Nombre normalizado + Latitud + Longitud`

SQLite es interno. No necesitas abrirlo ni saber SQL.

## Resumen final

La ventana muestra:

- total base antes;
- resultados encontrados en la corrida;
- nuevos insertados;
- duplicados ignorados;
- errores;
- total base final;
- archivo Excel generado.

## Riesgos

- Si aparece captcha o bloqueo, no se debe evadir.
- No conviene subir mucho el volumen.
- El HTML de Google Maps puede cambiar.
- Siempre revisa el Excel final antes de usarlo comercialmente.
