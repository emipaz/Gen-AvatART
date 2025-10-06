@echo off
echo ========================================
echo    Gem-AvatART - Setup Automatico
echo ========================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH
    echo Por favor instala Python 3.8+ desde https://python.org
    pause
    exit /b 1
)

echo Python detectado correctamente
echo.

:: Crear entorno virtual
echo Creando entorno virtual...
python -m venv venv
if errorlevel 1 (
    echo ERROR: No se pudo crear el entorno virtual
    pause
    exit /b 1
)

echo Activando entorno virtual...
call venv\Scripts\activate.bat

:: Actualizar pip
echo Actualizando pip...
python -m pip install --upgrade pip

:: Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)

:: Crear archivo .env si no existe
if not exist ".env" (
    echo Creando archivo de configuracion .env...
    copy .env.example .env
    echo.
    echo IMPORTANTE: Edita el archivo .env con tus configuraciones
    echo Especialmente la SECRET_KEY y configuracion de base de datos
    echo.
)

:: Inicializar base de datos
echo Inicializando base de datos...
python init_db.py

echo.
echo ========================================
echo    Instalacion Completada!
echo ========================================
echo.
echo Para iniciar la aplicacion:
echo   1. Activa el entorno virtual: venv\Scripts\activate
echo   2. Ejecuta la aplicacion: python app.py
echo.
echo La aplicacion estara disponible en: http://localhost:5000
echo.
pause