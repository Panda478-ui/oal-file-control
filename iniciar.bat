@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 app.py
  goto :eof
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python app.py
  goto :eof
)

echo No se encontro Python instalado.
echo Instala Python 3 desde https://www.python.org/downloads/
echo Marca la opcion "Add python.exe to PATH" durante la instalacion.
pause
