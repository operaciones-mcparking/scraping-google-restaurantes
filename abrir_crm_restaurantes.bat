@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ==========================================
echo CRM Restaurantes
echo ==========================================
echo.
echo Se abrira la aplicacion visual en el navegador.
echo No cierres esta ventana mientras uses el CRM.
echo.
"C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m streamlit run ".\app_crm_restaurantes.py" --server.headless=false
echo.
echo CRM cerrado.
pause
