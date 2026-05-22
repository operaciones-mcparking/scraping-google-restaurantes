# Deploy en Streamlit Cloud

Esta guia prepara el CRM para correr online usando Supabase como backend y Supabase Auth para proteger el acceso.

## Secrets necesarios

En Streamlit Cloud, abrir la app y configurar los secrets con este formato:

```toml
SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_KEY = "tu-key-de-supabase"
```

No guardar estos valores dentro del codigo ni subir `.streamlit/secrets.toml` a GitHub.

## Login con Supabase Auth

El CRM usa usuarios reales creados en Supabase Auth:

- El login pide email y contrasena.
- Si Supabase valida el usuario, se abre el CRM.
- La sesion se guarda en `st.session_state`.
- Si el token expira, el CRM intenta renovarlo con `refresh_token`.
- Si las credenciales son incorrectas, muestra `Correo electronico o contrasena incorrectos`.
- El boton `Cerrar sesion` llama a `sign_out` y borra la sesion local.

Limitacion: los tokens no se guardan en archivos. La sesion se mantiene durante la sesion activa del navegador/Streamlit. Si Streamlit Cloud reinicia la sesion, el usuario podria tener que ingresar nuevamente.

Para crear usuarios:

1. Entrar a Supabase.
2. Ir a `Authentication`.
3. Crear un usuario con email y contrasena.
4. Usar ese email y contrasena para entrar al CRM.

## Modo de datos

El modo se controla en:

```text
configs/app_mode.json
```

Valores posibles:

- `local`: lee Excel local.
- `supabase`: lee Supabase.

Para la version online, usar normalmente:

```json
{
  "data_mode": "supabase"
}
```

## Checklist antes de publicar

1. Confirmar que `.streamlit/secrets.toml` esta en `.gitignore`.
2. Confirmar que `SUPABASE_URL` y `SUPABASE_KEY` estan configurados en Streamlit Cloud.
3. Confirmar que existe al menos un usuario en Supabase Auth.
4. Probar login con email y contrasena.
5. Probar cierre de sesion.
6. Probar carga del CRM.
7. Probar lectura y escritura en Supabase con un lead de prueba.

## Importante

Esta configuracion protege la URL con Supabase Auth. Mas adelante se pueden agregar roles, perfiles y permisos por usuario si el CRM lo necesita.
