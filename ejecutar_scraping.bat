@echo off
chcp 65001 > nul
echo ==========================================
echo Iniciando scraping de restaurantes...
echo ==========================================
echo.
powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath 'C:\Users\gabyp\Documents\SCRAPING_GOOGLE'; Write-Host 'Ejecutando actualizar_restaurantes.bat' -ForegroundColor Cyan; .\actualizar_restaurantes.bat"
