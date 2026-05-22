# Qué archivo debo usar

## Excel principal

El archivo que debes abrir y usar para revisar la base es:

```text
data/base_restaurantes_actualizada.xlsx
```

Este es el Excel vivo del proyecto.

## Qué pasa cuando ejecuto actualizar_restaurantes.bat

Cuando haces doble clic en:

```text
actualizar_restaurantes.bat
```

el sistema:

1. Revisa la base interna.
2. Busca restaurantes según la configuración manual.
3. Compara contra los restaurantes existentes.
4. Inserta solo restaurantes nuevos.
5. Ignora duplicados.
6. Vuelve a generar:

```text
data/base_restaurantes_actualizada.xlsx
```

## Cuándo abrir el Excel principal

Abre el Excel principal después de que la ventana del `.bat` muestre el resumen final.

No lo abras mientras el actualizador está corriendo, porque Excel puede bloquear el archivo y evitar que se guarde correctamente.

## Dónde quedaron los Excel antiguos

Todos los Excel históricos, pilotos o intermedios fueron movidos a:

```text
data/archive_excels/
```

Ahí quedaron archivos de:

- pilotos iniciales;
- extracciones por comuna;
- consolidados antiguos;
- enriquecimientos anteriores;
- plantillas.

No se borró nada.

## Qué archivos no debo tocar

No edites ni borres manualmente:

```text
data/restaurantes.db
configs/
scripts/
data/logs/
node_modules/
```

Qué son:

- `data/restaurantes.db`: motor interno para evitar duplicados.
- `configs/`: configuraciones del sistema.
- `scripts/`: programas que hacen la actualización.
- `data/logs/`: historial de ejecuciones y errores.
- `node_modules/`: dependencia técnica para Playwright/Node.

## Qué sí puedes abrir

Puedes abrir:

```text
data/base_restaurantes_actualizada.xlsx
```

También puedes revisar los Excel antiguos dentro de:

```text
data/archive_excels/
```

pero esos son solo referencia histórica.

## Regla simple

Para trabajo diario:

```text
Abrir solo data/base_restaurantes_actualizada.xlsx
```

Para actualizar:

```text
Doble clic en actualizar_restaurantes.bat
```
