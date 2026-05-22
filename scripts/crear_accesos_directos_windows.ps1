$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\gabyp\Documents\SCRAPING_GOOGLE"
$Desktop = [Environment]::GetFolderPath("Desktop")

$Shortcuts = @(
    @{
        Name = "CRM Restaurantes"
        Target = Join-Path $ProjectRoot "abrir_crm_restaurantes.bat"
        Description = "Abrir CRM visual de restaurantes"
        Icon = Join-Path $ProjectRoot "assets\Rappi_logo.ico"
    },
    @{
        Name = "Actualizar Restaurantes"
        Target = Join-Path $ProjectRoot "actualizar_restaurantes.bat"
        Description = "Actualizar restaurantes localmente y sincronizar Supabase"
        Icon = Join-Path $ProjectRoot "assets\Rappi_logo.ico"
    }
)

$Shell = New-Object -ComObject WScript.Shell

foreach ($Item in $Shortcuts) {
    if (-not (Test-Path $Item.Target)) {
        throw "No existe el destino: $($Item.Target)"
    }

    $ShortcutPath = Join-Path $Desktop "$($Item.Name).lnk"
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $Item.Target
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.Description = $Item.Description

    if (Test-Path $Item.Icon) {
        $Shortcut.IconLocation = $Item.Icon
    } elseif ($Item.Name -eq "CRM Restaurantes") {
        $Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
    } else {
        $Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,238"
    }

    $Shortcut.Save()
    Write-Host "Acceso directo creado: $ShortcutPath"
}

Write-Host "Listo. Puedes usar los accesos directos desde el Escritorio."
