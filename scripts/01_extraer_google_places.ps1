param(
    [string]$ApiKey = $env:GOOGLE_PLACES_API_KEY,
    [ValidateSet("Piloto", "Completo")]
    [string]$Modo = "Piloto",
    [string]$Comunas = "",
    [string]$Categorias = "",
    [int]$MaxPaginas = 1,
    [int]$MaxResultados = 10,
    [string]$OutputBaseName = "restaurantes_rm_google_places",
    [switch]$Sobrescribir
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$configDir = Join-Path $root "configs"
$dataDir = Join-Path $root "data"
$comunasPath = Join-Path $configDir "comunas_rm.csv"
$categoriasPath = Join-Path $configDir "categorias_restaurantes.csv"
$converterPath = Join-Path $root "scripts\convert_csv_to_xlsx.py"
$bundledPythonPath = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if ($OutputBaseName.EndsWith(".xlsx", [System.StringComparison]::OrdinalIgnoreCase) -or
    $OutputBaseName.EndsWith(".csv", [System.StringComparison]::OrdinalIgnoreCase) -or
    $OutputBaseName.EndsWith(".log", [System.StringComparison]::OrdinalIgnoreCase)) {
    $OutputBaseName = [System.IO.Path]::GetFileNameWithoutExtension($OutputBaseName)
}

$csvPath = Join-Path $dataDir "$OutputBaseName.csv"
$xlsxPath = Join-Path $dataDir "$OutputBaseName.xlsx"
$logPath = Join-Path $dataDir "$OutputBaseName.log"

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

if (-not $Sobrescribir -and ((Test-Path $csvPath) -or (Test-Path $xlsxPath) -or (Test-Path $logPath))) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputBaseName = "${OutputBaseName}_$timestamp"
    $csvPath = Join-Path $dataDir "$OutputBaseName.csv"
    $xlsxPath = Join-Path $dataDir "$OutputBaseName.xlsx"
    $logPath = Join-Path $dataDir "$OutputBaseName.log"
    Write-Host "Ya existía una salida con ese nombre. Se usará: $OutputBaseName"
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $ApiKey = Read-Host "Pega tu API key de Google Places"
}

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Write-Host $line
    Add-Content -Path $logPath -Value $line -Encoding UTF8
}

function Get-FirstValue {
    param(
        $Object,
        [string[]]$Names
    )
    foreach ($name in $Names) {
        if ($null -ne $Object.$name -and -not [string]::IsNullOrWhiteSpace([string]$Object.$name)) {
            return [string]$Object.$name
        }
    }
    return ""
}

function Convert-ToRow {
    param(
        $Place,
        [string]$Comuna,
        [string]$Region,
        [string]$Categoria
    )

    $name = ""
    if ($Place.displayName -and $Place.displayName.text) {
        $name = [string]$Place.displayName.text
    }

    $phone = Get-FirstValue -Object $Place -Names @("nationalPhoneNumber", "internationalPhoneNumber")
    $lat = ""
    $lng = ""
    if ($Place.location) {
        $lat = $Place.location.latitude
        $lng = $Place.location.longitude
    }

    [PSCustomObject]@{
        "Nombre del restaurante" = $name
        "Teléfono" = $phone
        "Dirección" = [string]$Place.formattedAddress
        "Comuna" = $Comuna
        "Región" = $Region
        "Sitio web" = [string]$Place.websiteUri
        "Rating" = $Place.rating
        "Cantidad de reseñas" = $Place.userRatingCount
        "Link de Google Maps" = [string]$Place.googleMapsUri
        "Latitud" = $lat
        "Longitud" = $lng
        "Categoría" = $Categoria
        "Fuente" = "Google Places API (New)"
        "Fecha de actualización" = (Get-Date -Format "yyyy-MM-dd")
        "Place ID" = [string]$Place.id
    }
}

function Search-GooglePlaces {
    param(
        [string]$TextQuery,
        [string]$ApiKey,
        [int]$MaxPaginas,
        [int]$MaxResultados
    )

    $url = "https://places.googleapis.com/v1/places:searchText"
    $headers = @{
        "Content-Type" = "application/json; charset=utf-8"
        "X-Goog-Api-Key" = $ApiKey
        "X-Goog-FieldMask" = "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.googleMapsUri,places.websiteUri,places.nationalPhoneNumber,places.internationalPhoneNumber,places.primaryType,places.types,nextPageToken"
    }

    $allPlaces = @()
    $pageToken = $null
    $page = 0
    $pageSize = [Math]::Min([Math]::Max($MaxResultados, 1), 20)

    do {
        $page++
        $body = @{
            textQuery = $TextQuery
            languageCode = "es"
            regionCode = "CL"
            includedType = "restaurant"
            pageSize = $pageSize
        }

        if ($pageToken) {
            $body.pageToken = $pageToken
            Start-Sleep -Seconds 2
        }

        $jsonBody = $body | ConvertTo-Json -Depth 6
        $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $jsonBody

        if ($response.places) {
            $allPlaces += $response.places
        }

        $pageToken = $response.nextPageToken
    } while ($pageToken -and $page -lt $MaxPaginas -and $allPlaces.Count -lt $MaxResultados)

    return $allPlaces | Select-Object -First $MaxResultados
}

function Export-XlsxWithExcel {
    param(
        [string]$CsvPath,
        [string]$XlsxPath
    )

    try {
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $false
        $excel.DisplayAlerts = $false
        $workbook = $excel.Workbooks.Open($CsvPath)
        $worksheet = $workbook.Worksheets.Item(1)
        $worksheet.Name = "Restaurantes"
        $usedRange = $worksheet.UsedRange
        $usedRange.EntireColumn.AutoFit() | Out-Null
        $workbook.SaveAs($XlsxPath, 51)
        $workbook.Close($true)
        $excel.Quit()
        return $true
    }
    catch {
        Write-Log "No se pudo crear XLSX con Excel instalado. Se mantiene CSV. Detalle: $($_.Exception.Message)"
        try {
            if ($workbook) { $workbook.Close($false) }
            if ($excel) { $excel.Quit() }
        }
        catch {}
        return $false
    }
}

function Export-XlsxWithPython {
    param(
        [string]$CsvPath,
        [string]$XlsxPath
    )

    if (-not (Test-Path $bundledPythonPath)) {
        Write-Log "No se encontró Python incluido en Codex para convertir a XLSX. Se mantiene CSV."
        return $false
    }

    if (-not (Test-Path $converterPath)) {
        Write-Log "No se encontró el conversor scripts\convert_csv_to_xlsx.py. Se mantiene CSV."
        return $false
    }

    try {
        & $bundledPythonPath $converterPath $CsvPath $XlsxPath
        if ($LASTEXITCODE -eq 0 -and (Test-Path $XlsxPath)) {
            return $true
        }
        Write-Log "Python no pudo crear el XLSX. Se mantiene CSV."
        return $false
    }
    catch {
        Write-Log "Error creando XLSX con Python. Se mantiene CSV. Detalle: $($_.Exception.Message)"
        return $false
    }
}

Write-Log "Inicio de extracción. Modo: $Modo. MaxPaginas: $MaxPaginas. MaxResultados: $MaxResultados"

$comunasConfig = Import-Csv -Path $comunasPath
$categoriasConfig = Import-Csv -Path $categoriasPath

if (-not [string]::IsNullOrWhiteSpace($Comunas)) {
    $selectedNames = $Comunas.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $comunasConfig = $comunasConfig | Where-Object { $selectedNames -contains $_.Comuna }
}
elseif ($Modo -eq "Piloto") {
    $comunasConfig = $comunasConfig | Where-Object { $_.Piloto -eq "SI" }
    $categoriasConfig = $categoriasConfig | Where-Object { $_.Piloto -eq "SI" }
}

if (-not [string]::IsNullOrWhiteSpace($Categorias)) {
    $selectedCategories = $Categorias.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $categoriasConfig = $categoriasConfig | Where-Object {
        ($selectedCategories -contains $_.Categoria) -or ($selectedCategories -contains $_.Consulta)
    }
}

if (-not $comunasConfig) {
    throw "No hay comunas seleccionadas. Revisa el parámetro -Comunas o el archivo configs/comunas_rm.csv."
}

if (-not $categoriasConfig) {
    throw "No hay categorías seleccionadas. Revisa configs/categorias_restaurantes.csv."
}

$rowsByPlaceId = @{}
$queryCount = 0

foreach ($comuna in $comunasConfig) {
    foreach ($categoria in $categoriasConfig) {
        $queryCount++
        $textQuery = "$($categoria.Consulta) en $($comuna.Comuna), $($comuna.Region), Chile"
        Write-Log "Consulta ${queryCount}: $textQuery"

        try {
            $places = Search-GooglePlaces -TextQuery $textQuery -ApiKey $ApiKey -MaxPaginas $MaxPaginas -MaxResultados $MaxResultados
            foreach ($place in $places) {
                if ([string]::IsNullOrWhiteSpace([string]$place.id)) {
                    continue
                }

                if (-not $rowsByPlaceId.ContainsKey($place.id)) {
                    $rowsByPlaceId[$place.id] = Convert-ToRow -Place $place -Comuna $comuna.Comuna -Region $comuna.Region -Categoria $categoria.Categoria
                }
            }
            Write-Log "Resultados acumulados únicos: $($rowsByPlaceId.Count)"
            Start-Sleep -Milliseconds 250
        }
        catch {
            Write-Log "Error en consulta '$textQuery': $($_.Exception.Message)"
        }
    }
}

$rows = $rowsByPlaceId.Values | Sort-Object "Comuna", "Nombre del restaurante"
$rows = $rows | Select-Object -First $MaxResultados

if ($rows.Count -eq 0) {
    throw "No se encontraron resultados. Revisa la API key, permisos de Places API (New), facturación y logs."
}

$rows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
Write-Log "CSV creado: $csvPath"

$xlsxCreated = Export-XlsxWithExcel -CsvPath $csvPath -XlsxPath $xlsxPath
if (-not $xlsxCreated) {
    $xlsxCreated = Export-XlsxWithPython -CsvPath $csvPath -XlsxPath $xlsxPath
}

if ($xlsxCreated) {
    Write-Log "Excel creado: $xlsxPath"
}

Write-Log "Fin. Restaurantes únicos exportados: $($rows.Count)"
