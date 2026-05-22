# Riesgos y limitaciones del scraping de Google Maps

Este proyecto evita APIs pagadas, pero scraping de Google Maps tiene riesgos importantes.

## Riesgos legales y de términos

Google Maps no está diseñado para extracción masiva automatizada. Sus términos pueden restringir copiar, exportar, almacenar o usar contenido fuera de Google Maps.

Antes de usar los datos comercialmente, revisa:

- https://cloud.google.com/maps-platform/terms
- https://www.google.com/help/terms_maps/

## Riesgos técnicos

- Google puede cambiar el HTML de Maps y romper el scraper.
- Puede aparecer captcha o aviso de tráfico inusual.
- Algunos restaurantes no tienen teléfono o sitio web visible.
- La cantidad de reseñas puede aparecer con textos distintos según sesión, idioma o diseño de Google Maps.
- Los datos visibles pueden variar por sesión, idioma, ubicación o historial.
- El scroll puede no cargar todos los resultados.
- La categoría no siempre aparece en un selector estable.
- La latitud y longitud se infieren desde la URL cuando están disponibles.

## Reglas del piloto

- No hacer extracción masiva.
- No intentar evadir captchas.
- Usar pausas lentas entre acciones.
- Abrir fichas una por una.
- Guardar logs para entender errores.
- Dejar campos vacíos si Google no muestra el dato.
- Marcar calidad del dato y observaciones para revisión manual.

## Recomendación

Usa este scraper solo como piloto controlado y de bajo volumen. Para una base comercial estable, conviene complementar con fuentes propias, sitios oficiales de restaurantes o permisos explícitos.
