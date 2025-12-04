"""
Módulo de configuración para la aplicación Gen-AvatART.

Este módulo define todas las configuraciones necesarias para el funcionamiento
de la aplicación, incluyendo configuraciones para diferentes entornos 
(desarrollo, producción, testing) y la integración con servicios externos.

El módulo incluye:
    - Clase Config      : Configuración base con parámetros comunes
    - DevelopmentConfig : Configuración específica para desarrollo
    - ProductionConfig  : Configuración optimizada para producción  
    - TestingConfig     : Configuración para pruebas unitarias
    - config_dict       : Diccionario de configuraciones disponibles

Funcionalidades principales:
    - Gestión de variables de entorno con valores por defecto
    - Configuración de base de datos SQLAlchemy
    - Integración con HeyGen API
    - Configuración de correo electrónico
    - Configuración JWT para autenticación
    - Límites de archivos y paginación
    - Sistema de comisiones para productores/subproductores/afiliados
"""

import os
from decouple import config

class Config:
    """
    Clase de configuración base para la aplicación Gen-AvatART.
    
    Esta clase contiene todas las configuraciones comunes que son
    compartidas entre diferentes entornos (desarrollo, producción, testing).
    Utiliza python-decouple para cargar variables de entorno con valores
    por defecto seguros.
    
    Attributes:
        SECRET_KEY (str)                   : Clave secreta para sesiones Flask
        SQLALCHEMY_DATABASE_URI (str)      : URI de conexión a la base de datos
        SQLALCHEMY_TRACK_MODIFICATIONS     : Deshabilita seguimiento de cambios (optimización)
        HEYGEN_BASE_URL (str)              : URL base para la API de HeyGen
        MAIL_SERVER (str)                  : Servidor SMTP para envío de emails
        MAIL_PORT (int)                    : Puerto del servidor SMTP
        MAIL_USE_TLS (bool)                : Habilita TLS para conexiones seguras
        MAIL_USERNAME (str)                : Usuario para autenticación SMTP
        MAIL_PASSWORD (str)                : Contraseña para autenticación SMTP
        JWT_SECRET_KEY (str)               : Clave secreta para tokens JWT
        JWT_ACCESS_TOKEN_EXPIRES (int)     : Tiempo de expiración de tokens (segundos)
        UPLOAD_FOLDER (str)                : Directorio para archivos subidos
        MAX_CONTENT_LENGTH (int)           : Tamaño máximo de archivo (16MB)
        ITEMS_PER_PAGE (int)               : Elementos por página en paginación
        PRODUCER_COMMISSION_RATE (float)   : Tasa de comisión para productores (15%)
        SUBPRODUCER_COMMISSION_RATE (float): Tasa de comisión para subproductores (10%)
    """

    # Configuración de seguridad Flask
    SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-change-in-production')
    
    # Configuración de base de datos SQLAlchemy
    SQLALCHEMY_DATABASE_URI = config(
        'DATABASE_URL', 
        default='sqlite:///gem_avatart.db' # SQLite por defecto para desarrollo
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Optimización: deshabilita seguimiento automático
    
    # HeyGen API Configuration
    HEYGEN_BASE_URL = config('HEYGEN_BASE_URL', default='https://api.heygen.com')
    HEYGEN_OWNER_API_KEY = config('HEYGEN_API_KEY_OWNER', default=None)
    
    # Frontend URL Configuration
    FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5000')
    
    # Mail Configuration
    MAIL_SERVER   = config('MAIL_SERVER', default='smtp.gmail.com')
    MAIL_PORT     = int(config('MAIL_PORT', default=587))
    MAIL_USE_TLS  = config('MAIL_USE_TLS', default=True, cast=bool)
    MAIL_USERNAME = config('MAIL_USERNAME', default='')
    MAIL_PASSWORD = config('MAIL_PASSWORD', default='')
    MAIL_DEFAULT_SENDER = config('MAIL_DEFAULT_SENDER', default='noreply@gem-avatart.com')
    
    # JWT Configuration
    JWT_SECRET_KEY           = config('JWT_SECRET_KEY', default='jwt-secret-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = int(config('JWT_ACCESS_TOKEN_EXPIRES', default=3600))  # 1 hora
    
    # Upload Configuration
    UPLOAD_FOLDER      = config('UPLOAD_FOLDER', default='app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Pagination
    ITEMS_PER_PAGE = int(config('ITEMS_PER_PAGE', default=10))
    
    # Commission rates
    PRODUCER_COMMISSION_RATE    = float(config('PRODUCER_COMMISSION_RATE', default=0.15))  # 15%
    SUBPRODUCER_COMMISSION_RATE = float(config('SUBPRODUCER_COMMISSION_RATE', default=0.10))  # 10%
    # AFFILIATE_COMMISSION_RATE = float(config('AFFILIATE_COMMISSION_RATE', default=0.05))  # 5%

    ENCRYPTION_KEY = config('ENCRYPTION_KEY')

class DevelopmentConfig(Config):
    """
    Configuración específica para el entorno de desarrollo.
    
    Esta clase hereda de Config y añade configuraciones optimizadas
    para el desarrollo local, incluyendo debug habilitado y logging
    de consultas SQL para facilitar el desarrollo.
    
    Attributes:
        DEBUG (bool)           : Habilita modo debug de Flask
        SQLALCHEMY_ECHO (bool) : Habilita logging de consultas SQL
    
    Note:
        - El modo debug permite recarga automática y mejor manejo de errores
        - SQLALCHEMY_ECHO muestra todas las consultas SQL en consola
        - Ideal para desarrollo local y depuración
    """
    DEBUG           = True
    SQLALCHEMY_ECHO = False

class ProductionConfig(Config):
    """
    Configuración específica para pruebas unitarias y testing.
    
    Esta clase hereda de Config y establece un entorno aislado
    para la ejecución de tests, utilizando base de datos en memoria
    y deshabilitando protecciones CSRF que pueden interferir con tests.
    
    Attributes:
        TESTING (bool)                 : Habilita modo testing de Flask
        SQLALCHEMY_DATABASE_URI (str)  : Base de datos SQLite en memoria
        WTF_CSRF_ENABLED (bool)        : Deshabilita protección CSRF para tests
    
    Note:
        - Base de datos en memoria para tests rápidos y aislados
        - CSRF deshabilitado para facilitar tests automatizados
        - Configuración temporal que se resetea en cada test
    """
    DEBUG           = False
    SQLALCHEMY_ECHO = False

class TestingConfig(Config):
    """
    Configuración específica para pruebas unitarias y testing.
    
    Esta clase hereda de Config y establece un entorno aislado
    para la ejecución de tests, utilizando base de datos en memoria
    y deshabilitando protecciones CSRF que pueden interferir con tests.
    
    Attributes:
        TESTING (bool)                 : Habilita modo testing de Flask
        SQLALCHEMY_DATABASE_URI (str)  : Base de datos SQLite en memoria
        WTF_CSRF_ENABLED (bool)        : Deshabilita protección CSRF para tests
    
    Note:
        - Base de datos en memoria para tests rápidos y aislados
        - CSRF deshabilitado para facilitar tests automatizados
        - Configuración temporal que se resetea en cada test
    """
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuraciones disponibles
config_dict = {
    'development' : DevelopmentConfig,
    'production'  : ProductionConfig,
    'testing'     : TestingConfig,
    'default'     : DevelopmentConfig
}

"""
Diccionario que mapea nombres de entorno a sus clases de configuración correspondientes.

Este diccionario permite seleccionar dinámicamente la configuración apropiada
basándose en variables de entorno o parámetros de inicialización.

Keys:
    development (DevelopmentConfig): Para desarrollo local con debug
    production (ProductionConfig)  : Para servidores de producción
    testing (TestingConfig)        : Para ejecución de tests
    default (DevelopmentConfig)    : Configuración por defecto

Usage:
    config_name = os.environ.get('FLASK_ENV', 'default')
    app.config.from_object(config_dict[config_name])
"""