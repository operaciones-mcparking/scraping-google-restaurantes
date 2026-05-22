# Autenticacion con Supabase Auth

El CRM usa Supabase Auth para permitir acceso solo a usuarios creados en Supabase.

## Como funciona

1. La pantalla de entrada pide email y contrasena.
2. `auth.py` envia esas credenciales a Supabase Auth.
3. Si Supabase responde correctamente, el CRM guarda la sesion en `st.session_state`.
4. Mientras el token siga valido, el usuario puede usar el CRM sin volver a entrar.
5. Si el token expira, el CRM intenta renovar la sesion usando `refresh_token`.
6. Para mantener el login entre recargas, el CRM guarda la sesion en una cookie del navegador.
7. Al presionar `Cerrar sesion`, se llama a `sign_out` y se borra la sesion local y la cookie.

## Persistencia de sesion

La sesion se mantiene en una cookie del navegador por hasta 30 dias o hasta que Supabase invalide el token.

Por seguridad, los tokens no se guardan en archivos locales ni en Git.

Limitaciones:

- Si el usuario presiona `Cerrar sesion`, debe ingresar nuevamente.
- Si se limpian cookies del navegador, debe ingresar nuevamente.
- Si Supabase invalida el refresh token, debe ingresar nuevamente.
- Si se cambia de navegador o dispositivo, debe ingresar nuevamente.

## Secrets requeridos

Configurar en `.streamlit/secrets.toml` local o en Streamlit Cloud:

```toml
SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_KEY = "tu-key-de-supabase"
```

Ya no se usa:

```toml
[auth]
username = "..."
password = "..."
```

## Crear usuarios

En Supabase:

1. Abrir el proyecto.
2. Ir a `Authentication`.
3. Crear un usuario con email y contrasena.
4. Usar esas credenciales en el CRM.

## Que no cambia

- La lectura de restaurantes desde Supabase.
- La escritura de estados CRM.
- El historial de contactos.
- El modo local como respaldo.
- El flujo de WhatsApp y llamadas.

## Errores comunes

Si aparece `Falta configurar SUPABASE_URL y SUPABASE_KEY`, revisar los secrets.

Si aparece `Correo electronico o contrasena incorrectos`, revisar que el usuario exista en Supabase Auth y que la contrasena sea correcta.
