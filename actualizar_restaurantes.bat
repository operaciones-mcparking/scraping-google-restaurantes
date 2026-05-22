@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ==========================================
echo Actualizacion incremental de restaurantes
echo ==========================================
echo.
echo Esta ventana puede tardar varios minutos.
echo Modo manual: se ejecuta solo cuando haces doble clic.
echo Configuracion: configs\actualizacion_incremental_manual.json
echo.
"C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" ".\scripts\10_actualizar_incremental.js" --config ".\configs\actualizacion_incremental_manual.json"
echo.
echo Proceso terminado. Revisa el resumen anterior.
echo Archivo principal:
echo data\base_restaurantes_actualizada.xlsx
echo.
pause
