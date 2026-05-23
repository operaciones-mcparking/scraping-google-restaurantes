# Deploy en Streamlit Community Cloud

Esta guia deja el CRM online usando GitHub, Streamlit Community Cloud y Supabase.

## 1. Antes de subir a GitHub

Confirmar que existe `requirements.txt` con las dependencias del CRM:

```text
streamlit
pandas
openpyxl
supabase
requests
```

Confirmar que `.gitignore` incluye:

```text
.streamlit/secrets.toml
```

Ese archivo contiene claves privadas y no debe subirse a GitHub.

## 2. Modo Supabase

Para la version online, confirmar que `configs/app_mode.json` tenga:

```json
{
  "data_mode": "supabase"
}
```

Con este modo, el CRM lee y escribe en Supabase. El Excel local queda como respaldo, pero no es la fuente principal online.

## 3. Subir el proyecto a GitHub

Desde la carpeta del proyecto:

```powershell
git status
git add .
git commit -m "Preparar CRM para Streamlit Cloud"
git push
```

Si el repositorio aun no existe, crear uno en GitHub y seguir las instrucciones de GitHub para conectar el remoto.

## 4. Crear la app en Streamlit Community Cloud

1. Entrar a `https://share.streamlit.io`.
2. Iniciar sesion con GitHub.
3. Presionar `New app`.
4. Elegir el repositorio del proyecto.
5. Elegir la rama que se va a desplegar, normalmente `main`.
6. En `Main file path`, escribir:

```text
app_crm_restaurantes.py
```

7. Presionar `Deploy`.

## 5. Configurar secrets en Streamlit Cloud

En la app de Streamlit Cloud:

1. Abrir `Settings`.
2. Entrar a `Secrets`.
3. Agregar:

```toml
SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_KEY = "tu-key-de-supabase"

```

Por ahora el CRM no usa login interno de Streamlit. El control de acceso debe ser externo/manual:

- no compartir la URL publicamente;
- usar una URL privada solo con personas internas;
- si se necesita seguridad formal mas adelante, agregar autenticacion externa estable antes de compartir masivamente.

## 6. Acceso al CRM

Para dar acceso en esta etapa:

1. Compartir la URL de Streamlit Cloud solo con usuarios internos.
2. No publicar la URL en sitios abiertos.
3. Mantener las credenciales de Supabase solo en `Secrets`.

## 7. Redeploy

Cada vez que subas cambios a GitHub:

```powershell
git add .
git commit -m "Actualizar CRM"
git push
```

Streamlit Cloud normalmente hace redeploy automatico.

Si no ocurre:

1. Entrar a la app en Streamlit Cloud.
2. Abrir el menu de la app.
3. Presionar `Reboot` o `Deploy latest commit`.

## 8. Revisar logs

Si la app no carga:

1. Entrar a Streamlit Cloud.
2. Abrir la app.
3. Ir a `Manage app`.
4. Revisar `Logs`.

Errores comunes:

- Falta `SUPABASE_URL`.
- Falta `SUPABASE_KEY`.
- `requirements.txt` no incluye alguna libreria.
- `configs/app_mode.json` no esta en modo `supabase`.

## 9. Limitacion importante

El scraping incremental sigue siendo local. La version online del CRM debe usarse para gestionar leads, revisar historial y trabajar contactos.

No ejecutar busquedas masivas desde Streamlit Cloud. La actualizacion con Google Maps debe seguir corriendo desde el PC local y luego subir datos a Supabase.
