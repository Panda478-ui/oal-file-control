@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  OAL File Control - Tunel local
echo ============================================
echo.
echo 1) Arranca la app en http://127.0.0.1:5000
echo 2) Crea un tunel publico HTTPS
echo 3) Copia la URL *.trycloudflare.com
echo 4) Pegala en https://oal-file-control.onrender.com
echo.

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  start "OAL File Control" cmd /c "py -3 app.py"
) else (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    start "OAL File Control" cmd /c "python app.py"
  ) else (
    echo No se encontro Python.
    pause
    exit /b 1
  )
)

timeout /t 2 /nobreak >nul

where cloudflared >nul 2>&1
if %ERRORLEVEL%==0 (
  cloudflared tunnel --url http://127.0.0.1:5000
) else (
  echo cloudflared no esta instalado.
  echo Instala Cloudflare cloudflared o abre solo http://127.0.0.1:5000
  pause
)
