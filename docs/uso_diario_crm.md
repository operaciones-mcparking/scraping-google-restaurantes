# Uso diario del CRM

Para trabajar mas facil, el proyecto tiene dos accesos directos en el Escritorio.

## CRM Restaurantes

Abre el CRM visual.

Usalo para:

- ver restaurantes
- filtrar leads
- abrir WhatsApp
- registrar llamadas
- revisar historial de contactos
- editar notas comerciales

Destino del acceso directo:

```text
C:\Users\gabyp\Documents\SCRAPING_GOOGLE\abrir_crm_restaurantes.bat
```

## Actualizar Restaurantes

Ejecuta la actualizacion local.

Este acceso directo:

- abre el scraper local
- busca restaurantes nuevos segun la configuracion
- guarda respaldo local en SQLite/Excel
- intenta sincronizar los nuevos restaurantes con Supabase
- deja logs de la ejecucion

Destino del acceso directo:

```text
C:\Users\gabyp\Documents\SCRAPING_GOOGLE\actualizar_restaurantes.bat
```

## Importante

El scraping sigue corriendo en tu PC. No corre en Streamlit Cloud.

Si Supabase falla durante una actualizacion, los datos locales no se pierden. El Excel y SQLite local quedan como respaldo.

## Crear nuevamente los accesos directos

Si algun acceso directo se borra, puedes volver a crearlos ejecutando:

```powershell
.\scripts\crear_accesos_directos_windows.ps1
```

desde la carpeta:

```text
C:\Users\gabyp\Documents\SCRAPING_GOOGLE
```
