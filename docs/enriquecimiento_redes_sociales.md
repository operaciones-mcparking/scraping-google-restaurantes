# Enriquecimiento de redes sociales

Esta etapa prepara el trabajo para Instagram y Facebook, pero no ejecuta búsquedas masivas.

## Alcance inicial

Solo restaurantes con:

```text
Nivel comercial = Alto potencial
```

Modo piloto:

```text
Máximo 10 restaurantes
```

## Archivos

Configuración:

```text
configs/enriquecimiento_redes_sociales.json
```

Script de preparación:

```text
scripts/07_preparar_enriquecimiento_redes.py
```

Salidas piloto:

```text
data/social/piloto_alto_potencial_redes.xlsx
data/social/piloto_alto_potencial_redes.csv
data/social/piloto_alto_potencial_redes.json
```

Salidas de candidatos completos:

```text
data/social/alto_potencial_redes_candidatos.xlsx
data/social/alto_potencial_redes_candidatos.csv
```

## Campos sociales

- `Instagram URL`
- `Instagram Usuario`
- `Tiene Instagram`
- `Calidad Instagram`
- `Facebook URL`
- `Tiene Facebook`
- `Calidad Facebook`

Además, el archivo de trabajo agrega:

- `Búsqueda Instagram sugerida`
- `Búsqueda Facebook sugerida`
- `Estado enriquecimiento redes`
- `Observación redes`

## Estrategia segura y mantenible

1. Trabajar primero con 10 restaurantes de alto potencial.
2. Priorizar precisión sobre volumen.
3. Usar búsquedas sugeridas como apoyo, no como verdad automática.
4. Confirmar coincidencia por nombre, comuna, dirección o sitio web.
5. Registrar `Calidad Instagram` y `Calidad Facebook`.
6. No llenar URL si hay duda razonable.

## Criterios de calidad

`Calidad Instagram` y `Calidad Facebook`:

- `Alta`: perfil claramente oficial, coincide nombre/marca y existe señal desde sitio web o datos del perfil.
- `Media`: coincide nombre y comuna, pero falta confirmación fuerte.
- `Baja`: coincidencia débil; no usar para venta sin revisión.
- vacío: no revisado todavía.

`Tiene Instagram` y `Tiene Facebook`:

- `Sí`: existe perfil confirmado.
- `No`: se revisó y no se encontró.
- vacío: pendiente.

## Riesgos y limitaciones

- Instagram y Facebook cambian interfaces con frecuencia.
- Muchos restaurantes usan nombres distintos en redes.
- Existen cuentas de fans, sucursales antiguas o perfiles no oficiales.
- Los buscadores pueden mostrar falsos positivos.
- Automatizar consultas masivas puede gatillar bloqueos o captchas.
- No conviene evadir captchas ni simular comportamiento agresivo.

## Comando de preparación

Este comando no busca en redes. Solo crea archivos de trabajo.

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"

& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ".\scripts\07_preparar_enriquecimiento_redes.py"
```

## Próxima etapa sugerida

Hacer revisión manual asistida de 10 restaurantes:

1. Abrir la búsqueda sugerida.
2. Confirmar si el perfil es oficial.
3. Completar Instagram/Facebook.
4. Marcar calidad.
5. Recién después automatizar parcialmente con límites bajos.
