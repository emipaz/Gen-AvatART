@echo off
echo ========================================
echo    Gem-AvatART - Iniciando Aplicacion
echo ========================================
echo.

:: Verificar si existe el entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Entorno virtual no encontrado
    echo Ejecuta setup.bat primero para instalar la aplicacion
    pause
    exit /b 1
)

:: Activar entorno virtual
echo Activando entorno virtual...
call venv\Scripts\activate.bat

:: Verificar archivo .env
if not exist ".env" (
    echo ERROR: Archivo .env no encontrado
    echo Copia .env.example a .env y configura las variables
    pause
    exit /b 1
)

:: Iniciar aplicacion
echo.
echo Iniciando Gem-AvatART...
echo.
echo La aplicacion estara disponible en: http://localhost:5000
echo Presiona Ctrl+C para detener la aplicacion
echo.

python app.py