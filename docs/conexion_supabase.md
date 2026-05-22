# Conexion Supabase

## Objetivo

Probar que el proyecto puede conectarse a Supabase sin migrar datos todavia y sin romper el modo local.

Esta etapa no crea tablas, no modifica el CRM y no cambia el scraper.

## Archivo de secrets

El proyecto usa:

```text
.streamlit/secrets.toml
```

Nota Windows: si el archivo aparece como `.streamlit/secrets.toml.txt`, la prueba tambien puede leerlo, pero el nombre recomendado para Streamlit es `secrets.toml`.

Debe contener:

```toml
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "TU-KEY"
```

Ese archivo no debe subirse a GitHub. Ya esta protegido por `.gitignore`.

`SUPABASE_URL` debe ser la URL base del proyecto, por ejemplo:

```text
https://TU-PROYECTO.supabase.co
```

Si por error incluye `/rest/v1`, el helper lo normaliza para la prueba.

## Archivos creados

```text
supabase_client.py
scripts/test_supabase_connection.py
```

`supabase_client.py`:

- lee `.streamlit/secrets.toml`
- valida que existan `SUPABASE_URL` y `SUPABASE_KEY`
- crea el cliente Supabase
- prueba una llamada simple a Supabase Auth, sin necesitar tablas

`scripts/test_supabase_connection.py`:

- ejecuta la prueba de conexion
- imprime `Conexión Supabase OK` si Supabase responde correctamente
- muestra error claro si falta URL, falta KEY o falla la conexion

## Como probar la conexion

Desde PowerShell, dentro del proyecto:

```powershell
cd C:\Users\gabyp\Documents\SCRAPING_GOOGLE
& "C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\scripts\test_supabase_connection.py
```

Resultado esperado:

```text
Conexión Supabase OK
Status HTTP: 200
```

## Como verificar que Supabase responde

Si el script imprime `Conexión Supabase OK`, significa que:

- el archivo `.streamlit/secrets.toml` fue encontrado
- `SUPABASE_URL` existe
- `SUPABASE_KEY` existe
- Supabase respondio a una consulta HTTP autenticada
- no fue necesario crear tablas para esta prueba

## Errores comunes

### Falta `SUPABASE_URL`

Mensaje esperado:

```text
Error de configuración: Falta SUPABASE_URL en .streamlit/secrets.toml
```

Solucion:

- abrir `.streamlit/secrets.toml`
- agregar `SUPABASE_URL`

### Falta `SUPABASE_KEY`

Mensaje esperado:

```text
Error de configuración: Falta SUPABASE_KEY en .streamlit/secrets.toml
```

Solucion:

- abrir `.streamlit/secrets.toml`
- agregar `SUPABASE_KEY`

### Error HTTP o conexion

Puede pasar si:

- la URL no corresponde al proyecto
- la key no es valida
- no hay internet
- Supabase esta temporalmente caido

En ese caso revisar:

- Supabase Project URL
- API Key
- conexion a internet

## Importante

Esta prueba no migra datos.

El CRM sigue funcionando en modo local con:

- `data/base_restaurantes_actualizada.xlsx`
- `data/crm_restaurantes_estado.xlsx`
- `data/historial_contactos.xlsx`

El scraper incremental sigue funcionando localmente igual que antes.
