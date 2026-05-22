# Estructura futura: redes sociales y delivery

Esta etapa solo prepara columnas vacías. No implementa scraping ni búsquedas en Instagram, Facebook, TikTok, Uber Eats, PedidosYa o Rappi.

## Columnas nuevas de redes sociales

- `Instagram URL`
- `Instagram Usuario`
- `Facebook URL`
- `TikTok URL`
- `Tiene Redes`
- `Calidad Redes`

## Columnas nuevas de delivery

- `Está en Uber Eats`
- `URL Uber Eats`
- `Confianza Uber Eats`
- `Está en PedidosYa`
- `URL PedidosYa`
- `Confianza PedidosYa`
- `Está en Rappi`
- `URL Rappi`
- `Confianza Rappi`

## Criterios futuros sugeridos

`Tiene Redes`:

- `Sí`: se encontró al menos una red social oficial.
- `No`: se buscó y no se encontró.
- vacío: todavía no se ha buscado.

`Calidad Redes`:

- `Alta`: red oficial clara desde sitio web o perfil verificado/coincidente.
- `Media`: perfil probable, pero requiere revisión.
- `Baja`: coincidencia débil o dudosa.
- vacío: todavía no se ha evaluado.

`Confianza Uber Eats`, `Confianza PedidosYa`, `Confianza Rappi`:

- `Alta`: nombre, comuna/dirección y marca coinciden.
- `Media`: nombre coincide, pero falta confirmar dirección.
- `Baja`: coincidencia parcial o dudosa.
- vacío: todavía no se ha buscado.

## Regla importante

Estas columnas quedan vacías a propósito hasta implementar una etapa separada de búsqueda y validación.
