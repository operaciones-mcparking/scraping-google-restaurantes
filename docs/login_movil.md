# Login movil en iPhone

## Por que Safari puede pedir login nuevamente

El CRM corre sobre Streamlit y usa Supabase Auth. Streamlit mantiene el estado de la app en `st.session_state`, pero ese estado depende de la sesion del navegador y del proceso de Streamlit.

En iPhone/Safari puede perderse antes de lo esperado por varias razones:

- iOS puede cerrar o suspender pestanas en segundo plano para ahorrar memoria.
- Safari puede limpiar estado temporal si la pestana queda mucho tiempo sin uso.
- Streamlit Cloud puede reiniciar el proceso de la app.
- Si se limpian cookies o datos del sitio, se pierde la sesion guardada.
- Si Supabase invalida el `refresh_token`, la app debe pedir login otra vez.

## Que hace ahora el CRM

Al iniciar sesion, el CRM guarda en `st.session_state` los datos de Supabase Auth:

- `access_token`
- `refresh_token`
- `expires_at`

En cada carga valida la sesion antes de mostrar el login. Si el `access_token` vencio, intenta renovar la sesion con `refresh_session` usando el `refresh_token`. Si la renovacion funciona, el usuario entra sin volver a escribir la clave.

## Mantener sesion iniciada

En la pantalla de login existe la opcion **Mantener sesion iniciada**.

Si esta activa, el CRM tambien guarda los tokens de sesion de Supabase en una cookie del navegador mediante `extra-streamlit-components`. Esto ayuda a recuperar la sesion cuando Safari recarga la pagina o Streamlit pierde el `session_state`.

Si esta desactivada, la sesion se conserva solo mientras Streamlit mantenga vivo el estado de la pestana. Al cerrar sesion, el CRM llama a Supabase `sign_out`, limpia `st.session_state` y borra la cookie.

Limitacion importante: desde Streamlit no se puede crear una cookie `HttpOnly` real controlada por el servidor. Por eso esta cookie debe usarse solo sobre HTTPS, como en Streamlit Cloud, y solo contiene los tokens necesarios para restaurar la sesion de Supabase.

## Mejor experiencia de login en iPhone

El formulario de login ajusta los campos para Safari/iOS:

- correo con `autocomplete="email"`
- clave con `autocomplete="current-password"`
- autocapitalizacion y autocorreccion desactivadas
- textos orientados a iniciar sesion, no a crear una cuenta nueva

Esto reduce las sugerencias de "crear/generar contrasena segura" y favorece el autocompletado de una clave existente.

## Recomendacion para uso diario

Para que el CRM sea mas comodo en iPhone:

1. Abrir el CRM en Safari.
2. Tocar el boton de compartir.
3. Elegir **Agregar a pantalla de inicio**.
4. Entrar desde ese icono y marcar **Mantener sesion iniciada**.

Usarlo como app desde la pantalla de inicio suele reducir cierres accidentales de pestanas y mejora la sensacion de uso diario. Aun asi, iOS puede cerrar la sesion si elimina datos del sitio, si el usuario cierra sesion manualmente o si Supabase invalida el refresh token.

## Alternativa evaluada

El proyecto usa `extra-streamlit-components` para manejar cookies, que cumple una funcion equivalente a `streamlit-cookies-controller` y ya esta declarado en `requirements.txt`.

Si mas adelante se quiere cambiar de componente, `streamlit-cookies-controller` es una alternativa valida. La logica esperada seria la misma:

- guardar solo tokens de sesion de Supabase necesarios para restaurar login;
- no guardar contrasenas;
- borrar la cookie al cerrar sesion;
- mantener el despliegue bajo HTTPS.
