# Piloto pequeño: Las Condes / restaurante

Este piloto sirve para validar Google Places con muy pocos resultados antes de hacer una extracción mayor.

## Configuración

- Comuna: Las Condes
- Categoría: Restaurante
- Límite sugerido: 5 resultados
- Páginas: 1
- Archivo final: `data/piloto_las_condes_restaurantes.xlsx`

## Comando recomendado

Abre PowerShell en la carpeta del proyecto:

```powershell
cd "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"
```

Ejecuta:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Comunas "Las Condes" -Categorias "Restaurante" -MaxPaginas 1 -MaxResultados 5 -OutputBaseName "piloto_las_condes_restaurantes"
```

Si prefieres, también puedes escribir el nombre con `.xlsx`; el script lo entiende:

```powershell
.\scripts\01_extraer_google_places.ps1 -ApiKey "TU_API_KEY" -Comunas "Las Condes" -Categorias "Restaurante" -MaxPaginas 1 -MaxResultados 5 -OutputBaseName "piloto_las_condes_restaurantes.xlsx"
```

## Qué archivos se crearán

- `data/piloto_las_condes_restaurantes.csv`
- `data/piloto_las_condes_restaurantes.xlsx`
- `data/piloto_las_condes_restaurantes.log`

Si ya existen, el script no los pisa por defecto: crea otro nombre con fecha y hora.

## Qué revisar en el Excel

- Nombre del restaurante
- Teléfono
- Dirección
- Comuna
- Región
- Sitio web
- Rating
- Cantidad de reseñas
- Link de Google Maps
- Latitud
- Longitud
- Categoría
- Fuente
- Fecha de actualización
