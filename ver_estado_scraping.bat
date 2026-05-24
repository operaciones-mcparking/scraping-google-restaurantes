@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ==========================================
echo Estado scraping restaurantes
echo ==========================================
echo.
echo Se abrira el dashboard local en el navegador.
echo No cierres esta ventana mientras uses el panel.
echo.
"C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m streamlit run ".\app_scraping_status.py" --server.headless=false
echo.
echo Dashboard cerrado.
pause
